"""Site executes on hand-built rounds."""
import duckdb
import pandas as pd
import pytest

from engine.callouts import Labeller
from engine.metrics import REGISTRY, Filters
from engine.metrics import executes as ex

TS = pd.Timestamp("2030-01-01")
SITES = [dict(name="A Site", x=0.0, y=0.0), dict(name="B Site", x=10_000.0, y=0.0)]


@pytest.fixture(autouse=True)
def site_anchors(monkeypatch):
    ex._site_labeller.cache_clear()
    monkeypatch.setattr(ex, "_site_labeller", lambda m: Labeller(m, SITES))


def tr(rk, won, team="T1", side="attacker"):
    return dict(round_key=rk, team_id=team, map="testmap", side=side, won=won, started_at=TS)


def fight(rk, ts, att, att_team, att_c, vic, vic_team, vic_c, kind="kill", weapon="vandal", phase="pre_plant"):
    return dict(round_key=rk, ts_ms=ts, t_round=ts / 1000, kind=kind, weapon=weapon, phase=phase,
                att_id=att, att_team=att_team, att_callout=att_c, vic_id=vic, vic_team=vic_team, vic_callout=vic_c)


@pytest.fixture
def con():
    c = duckdb.connect()
    team_rounds = pd.DataFrame([tr("G:1", True), tr("G:2", False), tr("G:3", False),
                                tr("H:1", True, team="T3")])   # another team: league only
    c.execute("CREATE TABLE team_rounds AS SELECT * FROM team_rounds")
    objectives = pd.DataFrame([
        dict(round_key="G:1", kind="plant", ts_ms=50_000, t_round=50.0, x=100.0, y=0.0, team_id="T1"),
        dict(round_key="G:2", kind="plant", ts_ms=40_000, t_round=40.0, x=50.0, y=0.0, team_id="T1"),
        dict(round_key="H:1", kind="plant", ts_ms=40_000, t_round=40.0, x=9_900.0, y=0.0, team_id="T3"),
    ])
    c.execute("CREATE TABLE objectives AS SELECT * FROM objectives")
    eng = pd.DataFrame([
        # G:1 early pick in mid (not the site), then the first fight in A's area at 30 s
        fight("G:1", 10_000, "a1", "T1", "Mid Top", "d1", "T2", "Mid Bottom"),
        fight("G:1", 30_000, "d2", "T2", "A Site", "a2", "T1", "A Main"),
        # G:2 defenders' Operator (d9) dies without an Operator kill
        fight("G:2", 20_000, "a1", "T1", "A Main", "d9", "T2", "A Site"),
    ])
    c.execute("CREATE TABLE engagements AS SELECT * FROM eng")
    casts = pd.DataFrame([
        dict(round_key="G:1", team_id="T1", ability="dark-cover", ts_ms=40_000),   # 10 s before plant: counts
        dict(round_key="G:1", team_id="T1", ability="flashpoint", ts_ms=45_000),   # counts
        dict(round_key="G:1", team_id="T1", ability="dark-cover", ts_ms=5_000),    # 45 s before plant: no
        dict(round_key="G:2", team_id="T1", ability="dark-cover", ts_ms=30_000),   # counts
        dict(round_key="G:2", team_id="T2", ability="flashpoint", ts_ms=39_000),   # defenders' utility: no
    ])
    c.execute("CREATE TABLE casts AS SELECT * FROM casts")
    pr = pd.DataFrame([dict(round_key="G:2", team_id="T2", player_id="d9", has_op=True)])
    c.execute("CREATE TABLE player_rounds AS SELECT * FROM pr")
    return c


def test_sites_entry_and_utility(con):
    d, fn = REGISTRY["att.executes"]
    r = fn(con, Filters(team_id="T1", map="testmap", side="attacker"))
    [a] = r.breakdown
    assert a["site"] == "A" and (a["rate"].k, a["rate"].n) == (2, 3)
    assert a["won"].k == 1
    assert a["entry"].k == 2                                  # both rounds had a fight in A's area
    assert a["entry_callouts"][0]["callout"] == "A Main"      # the attacker's own position, not mid
    assert a["utility_per_round"]["smoke"] == 1.0 and a["utility_per_round"]["flash"] == 0.5
    assert a["abilities"][0] == dict(ability="dark-cover", rounds=2)
    assert a["vs_op"]["rounds"] == 1 and a["vs_op"]["lost_no_kill"].k == 1
    assert (r.value["no_plant"].k, r.value["no_plant"].n) == (1, 3)
    assert a["league"] is None                                # fewer than 20 league rounds


def test_defense_view_is_empty_and_quiet(con):
    d, fn = REGISTRY["att.executes"]
    r = fn(con, Filters(team_id="T1", map="testmap", side="defender"))
    assert r.breakdown == [] and r.warnings == []
