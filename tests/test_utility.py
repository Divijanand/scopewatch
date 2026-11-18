"""Utility setups on hand-built casts."""
import duckdb
import pandas as pd
import pytest

from engine.callouts import Labeller
from engine.metrics import REGISTRY, Filters
from engine.metrics import utility as ut

TS = pd.Timestamp("2030-01-01")
ANCHORS = [dict(name="B Site", x=0.0, y=0.0), dict(name="B Main", x=3000.0, y=0.0)]


@pytest.fixture(autouse=True)
def anchors(monkeypatch):
    ut.labeller.cache_clear()
    monkeypatch.setattr(ut, "labeller", lambda m: Labeller(m, ANCHORS))


def cast(rk, ability, x, phase="buy", t=-10.0, ok=True, player="p1", team="T1", side="defender"):
    return dict(round_key=rk, ability=ability, agent="cypher", player_id=player, team_id=team, side=side,
                map="testmap", t_round=t, phase=phase, ts_ms=1, x=x if ok else None, y=0.0, vx=1.0, vy=0.0,
                spatial_ok=ok, low_rate=False, started_at=TS)


@pytest.fixture
def con():
    c = duckdb.connect()
    tr = pd.DataFrame([dict(round_key=f"G:{i}", team_id="T1", map="testmap", side="defender", started_at=TS)
                       for i in range(1, 5)])
    c.execute("CREATE TABLE team_rounds AS SELECT * FROM tr")
    casts = pd.DataFrame([
        cast("G:1", "trapwire", 100.0), cast("G:1", "trapwire", 200.0),    # two traps, one round
        cast("G:2", "trapwire", 50.0),
        cast("G:3", "trapwire", 2900.0),                                   # B Main
        cast("G:3", "trapwire", 0.0, ok=False),                            # no reliable position: unknown
        cast("G:4", "trapwire", 0.0, phase="post_round", t=95.0),          # after the round: ignored
        cast("G:4", "dark-cover", 0.0),                                    # a smoke: not a setup
        cast("G:2", "trapwire", 0.0, team="T2", side="attacker"),          # other team
    ])
    c.execute("CREATE TABLE casts AS SELECT * FROM casts")
    pr = pd.DataFrame([dict(round_key=f"G:{i}", player_id="p1", player_name="P1", team_id="T1", map="testmap",
                            side="defender", agent="cypher" if i < 4 else "omen", started_at=TS) for i in range(1, 5)])
    c.execute("CREATE TABLE player_rounds AS SELECT * FROM pr")
    c.execute("""CREATE TABLE engagements (round_key VARCHAR, ts_ms BIGINT, t_round DOUBLE, att_id VARCHAR,
                 att_name VARCHAR, att_agent VARCHAR, att_team VARCHAR, att_side VARCHAR, weapon VARCHAR,
                 vic_team VARCHAR, vic_x DOUBLE, vic_y DOUBLE, vic_callout VARCHAR, phase VARCHAR, map VARCHAR,
                 started_at TIMESTAMP)""")
    return c


F = Filters(team_id="T1", map="testmap", side="defender")


def test_setups_count_rounds_per_callout(con):
    d, fn = REGISTRY["util.placements"]
    r = fn(con, F, group="setup")
    top = r.breakdown[0]
    assert (top["ability"], top["callout"]) == ("trapwire", "B Site")
    assert (top["rate"].k, top["rate"].n) == (2, 4)        # rounds, not casts: G:1 had two traps
    assert top["casts"] == 3 and top["buy_phase"] == 3
    assert r.breakdown[1]["callout"] == "B Main"
    assert r.unknown[0].count == 1                         # unplaced cast reported, not drawn
    assert [a["ability"] for a in r.value["abilities"]] == ["trapwire"]
    assert r.supporting == ["G:1", "G:2"] and r.contrary == ["G:3", "G:4"]


def test_map_placed_smokes_get_timing_not_positions(con):
    d, fn = REGISTRY["util.placements"]
    r = fn(con, F, group="smoke")
    assert r.breakdown == []                                   # an Omen smoke is never drawn at Omen's feet
    [s] = r.value["timing"]
    assert s["ability"] == "dark-cover" and (s["rate"].k, s["rate"].n) == (1, 4)


def test_walls_run_along_the_aim(con):
    con.execute("INSERT INTO casts SELECT * FROM (SELECT 'G:2' round_key, 'toxic-screen' ability, 'viper' agent, "
                "'p1' player_id, 'T1' team_id, 'defender' side, 'testmap' map, -15.0 t_round, 'buy' phase, 1 ts_ms, "
                "0.0 x, 0.0 y, 1.0 vx, 0.0 vy, TRUE spatial_ok, FALSE low_rate, TIMESTAMP '2030-01-01' started_at)")
    d, fn = REGISTRY["util.placements"]
    r = fn(con, F, group="smoke")
    [w] = r.breakdown
    assert (w["ability"], w["callout"]) == ("toxic-screen", "B Site")
    assert w["toward"][0]["callout"] == "B Main"               # 20 m along +x from B Site is nearest B Main


def test_damage_lands_where_it_hurt_enemies(con):
    def hit(ts, att_team="T1", vic_team="T2", x=2900.0):
        return dict(round_key="G:1", ts_ms=ts, t_round=ts / 1000, att_id="p1", att_name="P1", att_agent="killjoy",
                    att_team=att_team, att_side="defender", weapon="nanoswarm", vic_team=vic_team, vic_x=x, vic_y=0.0,
                    vic_callout="B Main", phase="pre_plant", map="testmap", started_at=TS)
    eng = pd.DataFrame([hit(30_000), hit(30_500), hit(31_000, vic_team="T1")])   # last one: friendly fire, ignored
    con.execute("INSERT INTO engagements BY NAME SELECT * FROM eng")
    con.execute("INSERT INTO casts SELECT * FROM (SELECT 'G:1' round_key, 'nanoswarm' ability, 'killjoy' agent, "
                "'p1' player_id, 'T1' team_id, 'defender' side, 'testmap' map, -10.0 t_round, 'buy' phase, "
                "20000 ts_ms, 0.0 x, 0.0 y, 1.0 vx, 0.0 vy, TRUE spatial_ok, FALSE low_rate, TIMESTAMP '2030-01-01' started_at)")
    d, fn = REGISTRY["util.placements"]
    r = fn(con, F, group="damage")
    [b] = r.breakdown
    assert (b["ability"], b["callout"]) == ("nanoswarm", "B Main")   # where it hurt, not where KJ stood
    assert b["from_callouts"][0]["callout"] == "B Site"              # linked back to the throw
    assert b["hits"] == 2 and (b["rate"].k, b["rate"].n) == (1, 4)
    assert b["median_t"] == -10.0                                    # timed by the throw


def test_needs_map_and_side(con):
    d, fn = REGISTRY["util.placements"]
    r = fn(con, Filters(team_id="T1"), group="setup")
    assert r.breakdown == [] and r.warnings


def test_one_agent_shows_its_whole_kit_by_mode(con):
    d, fn = REGISTRY["util.placements"]
    r = fn(con, F, group=None, agent="cypher")
    assert r.value["rounds"] == 3                                # rounds where they fielded Cypher, not all rounds
    assert {k["ability"]: k["mode"] for k in r.value["kit"]} == {"trapwire": "placed", "dark-cover": "unplaced"}
    assert {b["ability"] for b in r.breakdown} == {"trapwire"}   # the unplaced ability is never drawn
    assert [t["ability"] for t in r.value["timing"]] == ["dark-cover"]
    assert {a["agent"]: a["rounds"] for a in r.value["agents"]} == {"cypher": 3, "omen": 1}
