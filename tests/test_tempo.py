import duckdb
import pandas as pd
import pytest

from engine.abilities import INFO
from engine.metrics import REGISTRY, Filters
from engine.metrics import tempo


def _tr(rk, won, team="T1", side="attacker"):
    return dict(round_key=rk, series_id=rk.split(":")[0], team_id=team, map="m", side=side, won=won,
                started_at=pd.Timestamp("2030-01-01"))


def _cast(rk, t, ability, agent, team="T1", side="attacker", phase="pre_plant"):
    return dict(round_key=rk, team_id=team, side=side, t_round=t, phase=phase, ability=ability, agent=agent)


@pytest.fixture
def con():
    tempo._LEAGUE_CACHE.clear()
    c = duckdb.connect()
    team_rounds = pd.DataFrame([
        _tr("S1:1", True), _tr("S1:2", False), _tr("S1:3", False),
        _tr("S1:1", False, team="T9", side="defender"),
        _tr("S2:1", True, team="T2"),
    ])
    casts = pd.DataFrame([
        _cast("S1:1", 20.0, "recon-bolt", "sova"),
        _cast("S1:1", 9.0, "trailblazer", "skye"),
        _cast("S1:1", 5.0, "dark-cover", "omen"),                           # a smoke, not recon
        _cast("S1:1", 2.0, "haunt", "fade", team="T9", side="defender"),     # the enemy's recon, not T1's
        _cast("S1:2", 30.0, "recon-bolt", "sova"),
        _cast("S2:1", 50.0, "recon-bolt", "sova", team="T2"),
    ])
    objectives = pd.DataFrame([dict(round_key="S1:1", kind="plant", t_round=30.0),
                               dict(round_key="S1:2", kind="plant", t_round=25.0)])   # S1:2 recon after the plant
    engagements = pd.DataFrame([
        dict(round_key="S1:1", kind="damage", phase="pre_plant", t_round=14.0, weapon="vandal", att_team="T1", vic_team="T9"),
        dict(round_key="S1:2", kind="damage", phase="pre_plant", t_round=31.0, weapon="Vandal", att_team="T9", vic_team="T1"),
    ])
    for name, df in dict(team_rounds=team_rounds, casts=casts, objectives=objectives, engagements=engagements).items():
        c.register(f"_{name}", df)
        c.execute(f"CREATE TABLE {name} AS SELECT * FROM _{name}")
    return c


def run(con):
    _, fn = REGISTRY["util.recon_timing"]
    return fn(con, Filters(team_id="T1", map="m", side="attacker"))


def test_trailblazer_is_recon():
    assert "trailblazer" in INFO


def test_first_recon_is_the_teams_earliest_recon(con):
    v = run(con).value
    assert v["n"] == 3
    assert v["first_recon"]["median"] == 19.5        # S1:1 trailblazer at 9 s (not the smoke, not T9's haunt); S1:2 at 30 s
    assert v["first_recon_agent"] == [dict(agent="skye", n=1), dict(agent="sova", n=1)]


def test_round_without_recon_counts_as_no_recon(con):
    assert run(con).value["no_recon"].k == 1          # S1:3


def test_commit_only_when_recon_came_first(con):
    v = run(con).value
    assert v["recon_to_plant"]["median"] == 21.0      # S1:1 only: 30 - 9; S1:2's recon came after its plant
    assert v["recon_to_contact"]["median"] == 3.0     # S1:1: 14 - 9 = 5; S1:2: 31 - 30 = 1 (Vandal, any case)


def test_late_split_at_league_75th_percentile(con):
    v = run(con).value
    # league attacker first recons on map m: 9 (S1:1), 30 (S1:2), 50 (S2:1) -> p75 = 40
    assert v["split_at"] == 40.0
    assert v["on_time"].n == 2 and v["late"].n == 1  # S1:3 has no recon -> late
    assert v["before_league_median"].k == 1 and v["before_league_median"].n == 2
