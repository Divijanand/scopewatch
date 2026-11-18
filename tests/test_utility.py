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
    pr = pd.DataFrame([dict(round_key=f"G:{i}", player_id="p1", player_name="P1") for i in range(1, 5)])
    c.execute("CREATE TABLE player_rounds AS SELECT * FROM pr")
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


def test_groups_separate_smokes(con):
    d, fn = REGISTRY["util.placements"]
    r = fn(con, F, group="smoke")
    assert [(b["ability"], b["rate"].k) for b in r.breakdown] == [("dark-cover", 1)]


def test_needs_map_and_side(con):
    d, fn = REGISTRY["util.placements"]
    r = fn(con, Filters(team_id="T1"), group="setup")
    assert r.breakdown == [] and r.warnings
