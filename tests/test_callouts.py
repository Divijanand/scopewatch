"""Callout naming and the callout metrics (setups, deaths) on hand-built data."""
import duckdb
import numpy as np
import pandas as pd
import pytest

from engine.callouts import Labeller, name_of
from engine.metrics import REGISTRY, Filters

ANCHORS = [dict(name="A Site", x=0.0, y=0.0), dict(name="A Main", x=1000.0, y=0.0),
           dict(name="B Site", x=0.0, y=1000.0)]
IDENTITY = dict(a=0.01, b=0.0, c=50.0, d=0.0, e=0.01, f=50.0)   # 1 px per metre, origin at (50, 50)


def floor_with_wall():
    """100x100 px floor with a wall along px x = 55..56, between A Site and A Main."""
    f = np.ones((100, 100), bool)
    f[:, 55:57] = False
    return f


def test_callout_names_read_like_comms():
    assert name_of(dict(superRegionName="A", regionName="Drop")) == "A Drop"
    assert name_of(dict(superRegionName="Mid", regionName="Market")) == "Mid Market"
    assert name_of(dict(superRegionName="Attacker Side", regionName="Spawn")) == "Attacker Spawn"


def test_nearest_anchor_without_a_floor():
    lab = Labeller("t", ANCHORS)
    names, d = lab.label([100.0, 900.0, 0.0], [0.0, 0.0, 900.0])
    assert list(names) == ["A Site", "A Main", "B Site"]
    assert d[0] == pytest.approx(1.0)


def test_wall_sends_the_name_to_the_reachable_anchor():
    pts_x = [700.0]   # px 57, just right of the wall: A Main is nearest and reachable
    lab = Labeller("t", ANCHORS, floor_with_wall(), IDENTITY)
    assert list(lab.label(pts_x, [0.0])[0]) == ["A Main"]
    lab2 = Labeller("t", [ANCHORS[0], dict(name="A Main", x=900.0, y=0.0)], floor_with_wall(), IDENTITY)
    # x=450 (px 54.5, left of the wall): A Main at 450 away is behind the wall, A Site at 450 is reachable
    names, _ = lab2.label([460.0], [0.0])
    assert list(names) == ["A Site"]


def test_far_and_missing_positions_stay_unnamed():
    lab = Labeller("t", ANCHORS)
    names, d = lab.label([10_000.0, np.nan], [10_000.0, np.nan])
    assert list(names) == [None, None]
    assert np.isnan(d).all()


TS = pd.Timestamp("2030-01-01")


def eng(rk, eid, kind, ts, att, team, side, att_c, vic_c, weapon="operator", t=10.0, vic="x", vic_team="T2",
        opening=False):
    return dict(round_key=rk, event_id=eid, kind=kind, ts_ms=ts, seq=ts, weapon=weapon, t_round=t,
                phase="pre_plant", opening_kill=opening, att_id=att, att_name=att.upper(), att_team=team,
                att_side=side, att_callout=att_c, vic_id=vic, vic_name=vic.upper(), vic_team=vic_team,
                vic_side="attacker" if side == "defender" else "defender", vic_callout=vic_c, map="testmap",
                started_at=TS)


@pytest.fixture
def con():
    c = duckdb.connect()
    e = pd.DataFrame([
        # round 1: first Op shot from A Site (hit, then the kill 300 ms later) -> counts as a kill
        eng("G:1", "1", "damage", 1000, "p1", "T1", "defender", "A Site", "A Main"),
        eng("G:1", "2", "kill", 1300, "p1", "T1", "defender", "A Site", "A Main"),
        eng("G:1", "3", "kill", 9000, "p1", "T1", "defender", "B Site", "B Main"),     # later shot: ignored
        # round 2: first Op shot from A Site, hit only
        eng("G:2", "4", "damage", 1000, "p1", "T1", "defender", "A Site", "A Main"),
        # round 3: from B Site
        eng("G:3", "5", "kill", 1000, "p2", "T1", "defender", "B Site", "B Main"),
        # round 3: a vandal kill doesn't count
        eng("G:3", "6", "kill", 500, "p2", "T1", "defender", "Mid", "Mid", weapon="vandal"),
        # round 4: shooter too far from any callout -> unknown
        eng("G:4", "7", "kill", 1000, "p1", "T1", "defender", None, "A Main"),
        # other team on the same map and side (league only)
        eng("H:1", "8", "kill", 1000, "q1", "T3", "defender", "B Site", "B Main"),
        # T1's holder p1 dies at A Site to a T2 player at A Main (round 2), first death
        eng("G:2", "9", "kill", 2000, "e1", "T2", "attacker", "A Main", "A Site", weapon="vandal", vic="p1",
            vic_team="T1", opening=True),
    ])
    c.execute("CREATE TABLE engagements AS SELECT * FROM e")
    pr = pd.DataFrame([dict(round_key="G:2", player_id="p1", has_op=True)])
    c.execute("CREATE TABLE player_rounds AS SELECT * FROM pr")
    return c


def test_setups_first_shot_per_round(con):
    d, fn = REGISTRY["op.setups"]
    r = fn(con, Filters(team_id="T1", map="testmap", side="defender"))
    top = r.breakdown[0]
    assert top["callout"] == "A Site" and (top["rate"].k, top["rate"].n) == (2, 3)
    assert top["kills"] == 1                         # round 1 kill within 1 s; round 2 was a hit
    assert top["targets"][0]["callout"] == "A Main"
    assert r.supporting == ["G:1", "G:2"] and r.contrary == ["G:3"]
    assert r.unknown[0].count == 1                   # round 4: no callout, reported not dropped silently
    assert r.value["league_rounds"] == 4             # T1's 3 named rounds + T3's 1


def test_setups_needs_map_and_side(con):
    d, fn = REGISTRY["op.setups"]
    r = fn(con, Filters(team_id="T1"))
    assert r.breakdown == [] and r.warnings


def test_deaths_of_the_holder(con):
    d, fn = REGISTRY["op.deaths"]
    r = fn(con, Filters(team_id="T1", map="testmap", side="defender"))
    assert [(b["callout"], b["rate"].k, b["rate"].n) for b in r.breakdown] == [("A Site", 1, 1)]
    assert r.breakdown[0]["from_"][0]["callout"] == "A Main"
    assert r.value["first_death"].k == 1
