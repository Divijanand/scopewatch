"""VOD timing and the Operator-gamble metrics on hand-built data."""
import duckdb
import pandas as pd
import pytest

from engine import vod
from engine.metrics import REGISTRY, Filters

# ------------------------------------------------------------------ VOD timing
BUY_END = {1: 1_000_000, 2: 1_120_000, 3: 1_250_000, 4: 1_400_000}   # ms, wall clock


def test_one_sync_places_every_round():
    t = vod.round_times(BUY_END, [(2, 600.0)])
    assert t[2]["buy_end_s"] == 600.0
    assert t[3]["buy_end_s"] == 730.0          # 130 s later on the wall clock
    assert t[1]["buy_end_s"] == 480.0          # before the sync: uses the first sync after it
    assert t[1]["synced_at_round"] == 2


def test_nearest_earlier_sync_wins_for_edited_vods():
    # an edited VOD cut 60 s between rounds 2 and 3; a second sync at round 3 corrects later rounds only
    t = vod.round_times(BUY_END, [(2, 600.0), (3, 670.0)])
    assert t[2]["buy_end_s"] == 600.0 and t[3]["buy_end_s"] == 670.0 and t[4]["buy_end_s"] == 820.0


def test_no_sync_no_times():
    assert vod.round_times(BUY_END, []) == {}


def test_save_get_clear(tmp_path):
    db = tmp_path / "user.sqlite"
    vod.save("G1", url="https://www.youtube.com/watch?v=abc", round_no=2, vod_s=600, path=db)
    vod.save("G1", round_no=2, vod_s=605, path=db)                  # re-time replaces
    assert vod.get("G1", path=db) == ("https://www.youtube.com/watch?v=abc", [(2, 605.0)])
    with pytest.raises(ValueError):
        vod.save("G1", url="javascript:alert(1)", path=db)
    with pytest.raises(ValueError):
        vod.save("G1", round_no=1, vod_s=-5, path=db)
    vod.clear("G1", path=db)
    assert vod.get("G1", path=db) == (None, [])


# ------------------------------------------------------------------ gamble metrics
TS = pd.Timestamp("2030-01-01")


def e(rk, eid, kind, ts, att, att_team, vic, vic_team, weapon="vandal", x=0.0, y=0.0, vx=0.0, vy=0.0,
      phase="pre_plant", agent="jett"):
    side = {"T1": "defender", "T2": "attacker"}
    return dict(round_key=rk, event_id=eid, kind=kind, ts_ms=ts, seq=ts, weapon=weapon, t_round=ts / 1000,
                phase=phase, att_id=att, att_name=att.upper(), att_team=att_team, att_side=side[att_team],
                att_agent=agent, att_x=x, att_y=y, vic_id=vic, vic_name=vic.upper(), vic_team=vic_team,
                vic_side=side[vic_team], vic_x=vx, vic_y=vy, map="testmap", started_at=TS)


@pytest.fixture
def con():
    c = duckdb.connect()
    eng = pd.DataFrame([
        # R1: p1 gets an Op kill at 10 s, dashes, survives -> kept, not punished, moved
        e("G:1", "1", "kill", 10_000, "p1", "T1", "x1", "T2", weapon="operator"),
        # R2: p1 Op kill at 10 s, no movement, dies at 12 s to x2 after a nearby flash and two shooters -> traded,
        #     punished, blinded and swarmed
        e("G:2", "2", "kill", 10_000, "p1", "T1", "x1", "T2", weapon="operator"),
        e("G:2", "3", "damage", 11_000, "x3", "T2", "p1", "T1", vx=100.0, vy=0.0),
        e("G:2", "4", "kill", 12_000, "x2", "T2", "p1", "T1", vx=100.0, vy=0.0),
        # R3: p1 dies at 5 s without an Op kill; enemy x2 (no Op at buy end) fires the Op at 20 s -> lost + stolen,
        #     a straight duel
        e("G:3", "5", "kill", 5_000, "x2", "T2", "p1", "T1", vx=0.0, vy=0.0),
        e("G:3", "6", "kill", 20_000, "x2", "T2", "p9", "T1", weapon="operator"),
    ])
    c.execute("CREATE TABLE engagements AS SELECT * FROM eng")
    pr = pd.DataFrame([dict(round_key=f"G:{i}", game_id="G", map="testmap", team_id="T1", side="defender",
                            player_id="p1", player_name="P1", agent="jett", has_op=True, started_at=TS)
                       for i in (1, 2, 3)]
                      + [dict(round_key="G:3", game_id="G", map="testmap", team_id="T2", side="attacker",
                              player_id="x2", player_name="X2", agent="sova", has_op=False, started_at=TS)])
    c.execute("CREATE TABLE player_rounds AS SELECT * FROM pr")
    tr = pd.DataFrame([dict(round_key=f"G:{i}", team_id="T1", won=w) for i, w in ((1, True), (2, False), (3, False))])
    c.execute("CREATE TABLE team_rounds AS SELECT * FROM tr")
    casts = pd.DataFrame([
        dict(round_key="G:1", player_id="p1", team_id="T1", ability="tailwind", ts_ms=10_500, spatial_ok=True,
             x=0.0, y=0.0),
        dict(round_key="G:2", player_id="x2", team_id="T2", ability="flashpoint", ts_ms=10_500, spatial_ok=True,
             x=1000.0, y=0.0),                        # 9 m from where p1 dies
        dict(round_key="G:3", player_id="x2", team_id="T2", ability="flashpoint", ts_ms=4_000, spatial_ok=True,
             x=9000.0, y=0.0),                        # 90 m away: not counted
    ])
    c.execute("CREATE TABLE casts AS SELECT * FROM casts")
    return c


F = Filters(team_id="T1", map="testmap", side="defender")


def test_gamble_outcomes(con):
    d, fn = REGISTRY["op.gamble"]
    r = fn(con, F)
    by = {b["bucket"]: b for b in r.breakdown}
    assert (r.rate.k, r.rate.n) == (1, 3)                       # R3: died without an Op kill
    assert by["kept"]["round_keys"] == ["G:1"] and by["traded"]["round_keys"] == ["G:2"]
    assert by["stolen"]["round_keys"] == ["G:3"]
    assert by["kept"]["won"].k == 1 and by["lost"]["won"].k == 0
    assert r.value["league_lost"].n == 3


def test_escapes(con):
    d, fn = REGISTRY["op.escapes"]
    r = fn(con, F)
    by = {b["bucket"]: b for b in r.breakdown}
    assert (r.rate.k, r.rate.n) == (1, 2)                       # R2 kill punished within 5 s
    assert by["moved"]["round_keys"] == ["G:1"] and by["moved"]["punished"].k == 0
    assert by["stayed"]["punished"].k == 1
    assert by["moved"]["abilities"][0]["ability"] == "tailwind"


def test_how_it_dies(con):
    d, fn = REGISTRY["op.how_it_dies"]
    r = fn(con, F)
    by = {b["bucket"]: b for b in r.breakdown}
    assert (r.rate.k, r.rate.n) == (1, 2)
    assert by["blinded"]["round_keys"] == ["G:2"] and by["swarmed"]["round_keys"] == ["G:2"]
    assert by["duel"]["round_keys"] == ["G:3"]                  # the far flash doesn't count


def test_an_enemy_tour_de_force_is_not_a_stolen_operator(con):
    con.execute("UPDATE engagements SET weapon = 'tour-de-force' WHERE event_id = '6'")
    d, fn = REGISTRY["op.gamble"]
    by = {b["bucket"]: b for b in fn(con, F).breakdown}
    assert by["stolen"]["round_keys"] == []
