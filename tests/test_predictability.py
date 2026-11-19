"""Predictability on hand-built rounds: best-guess share, comparison with other teams, small samples."""
import duckdb
import pandas as pd
import pytest

from engine.metrics import REGISTRY, Filters
from engine.metrics import predictability as pr

TS = pd.Timestamp("2030-01-01")


def fight(rk, team, callout, t=10.0):
    return dict(round_key=rk, ts_ms=int(t * 1000), seq=1, t_round=t, kind="kill", phase="pre_plant",
                att_side="defender", vic_side="attacker", att_team=team, vic_team="ENEMY",
                att_callout=callout, vic_callout="Mid", weapon="vandal", map="testmap", started_at=TS)


@pytest.fixture
def con():
    pr._CACHE.clear()
    rows = []
    # T1: first contact at B Site in 12 of 12 rounds (very predictable)
    rows += [fight(f"A:{i}", "T1", "B Site") for i in range(12)]
    # T2 and T3: spread over three spots and three time windows
    for team in ("T2", "T3"):
        rows += [fight(f"{team}:{i}", team, ["A Main", "B Main", "Mid"][i % 3], t=[5.0, 20.0, 35.0][i % 3])
                 for i in range(12)]
    # T4: only 5 rounds, too few to compare
    rows += [fight(f"D:{i}", "T4", "A Main") for i in range(5)]
    c = duckdb.connect()
    eng = pd.DataFrame(rows)
    c.execute("CREATE TABLE engagements AS SELECT * FROM eng")
    tr = pd.DataFrame([dict(round_key=r["round_key"], team_id=r["att_team"], map="testmap", side="defender",
                            started_at=TS) for r in rows])
    c.execute("CREATE TABLE team_rounds AS SELECT * FROM tr")
    return c


def test_one_spot_every_round_is_more_predictable_than_everyone(con):
    d, fn = REGISTRY["team.predictability"]
    r = fn(con, Filters(team_id="T1", map="testmap", side="defender"))
    where = {b["habit"]: b for b in r.breakdown}["contact_where"]
    assert where["choice"] == "B Site" and (where["rate"].k, where["rate"].n) == (12, 12)
    assert where["league_teams"] == 2                       # T4 has too few rounds to be compared
    assert where["percentile"] == 100 and where["league_median"] == pytest.approx(4 / 12, abs=1e-3)
    assert r.value["score"] == 100


def test_a_spread_team_is_less_predictable(con):
    d, fn = REGISTRY["team.predictability"]
    r = fn(con, Filters(team_id="T2", map="testmap", side="defender"))
    where = {b["habit"]: b for b in r.breakdown}["contact_where"]
    assert (where["rate"].k, where["rate"].n) == (4, 12)
    assert where["percentile"] == 0                         # T1 is more predictable, T3 ties (ties don't count)


def test_small_samples_are_flagged_and_not_scored(con):
    d, fn = REGISTRY["team.predictability"]
    r = fn(con, Filters(team_id="T4", map="testmap", side="defender"))
    where = {b["habit"]: b for b in r.breakdown}["contact_where"]
    assert where["small_sample"] and where["percentile"] is None
    assert r.value["score"] is None
