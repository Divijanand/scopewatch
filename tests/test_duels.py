import duckdb
import pandas as pd
import pytest

from engine.metrics import REGISTRY, Filters
from engine.metrics import duels

DRY = {c: 0 for c in duels.DRY_COLS}


def fight(rk, opener_team, other_team, label, opener_side="attacker", series="S1", **kw):
    row = dict(round_key=rk, series_id=series, map="m", opener_team=opener_team, other_team=other_team,
               opener_side=opener_side, other_side="defender" if opener_side == "attacker" else "attacker",
               opener_side_alive=5, other_side_alive=5, planted=False, label=label,
               opener_agent="jett", other_agent="cypher", **DRY)
    row.update(kw)
    return row


@pytest.fixture
def fights_file(tmp_path, monkeypatch):
    path = tmp_path / "fights.parquet"
    monkeypatch.setattr(duels, "FIGHTS_PARQUET", path)
    duels._load.cache_clear()

    def write(rows):
        pd.DataFrame(rows).to_parquet(path, index=False)
    return write


def run(**f):
    _, fn = REGISTRY["fights.dry_duels"]
    return fn(duckdb.connect(), Filters(team_id="T1", map="m", **f))


def test_missing_fights_file_warns(tmp_path, monkeypatch):
    monkeypatch.setattr(duels, "FIGHTS_PARQUET", tmp_path / "missing.parquet")
    r = run(side="attacker")
    assert r.warnings and "engine.model.fights" in r.warnings[0]


def test_any_utility_makes_a_fight_not_dry(fights_file):
    fights_file([fight("S1:1", "T1", "T2", 1), fight("S1:2", "T1", "T2", 1, util_other_smoke=1),
                 fight("S1:3", "T1", "T2", 1, dmg_util_opener=12.0)])
    assert run().value["total"] == 1


def test_expected_flips_when_the_enemy_opened(fights_file):
    # league cell (attacker opener, 5v5, no plant): openers win 3 of 4 -> 0.75
    fights_file([fight("S1:1", "T1", "T2", 1), fight("S1:2", "T2", "T1", 1),
                 fight("S2:1", "T3", "T4", 1, series="S2"), fight("S2:2", "T3", "T4", 0, series="S2")])
    r = run()
    opened, enemy = r.breakdown[0], r.breakdown[1]
    assert opened["expected"] == pytest.approx(0.75) and opened["actual"] == 1
    assert enemy["expected"] == pytest.approx(0.25) and enemy["actual"] == 0


def test_zero_difference_at_league_rates(fights_file):
    # the team is the whole league: actual - expected averages to 0
    fights_file([fight("S1:1", "T1", "T2", 1), fight("S1:2", "T1", "T2", 0),
                 fight("S2:1", "T1", "T2", 1, series="S2"), fight("S2:2", "T1", "T2", 0, series="S2")])
    assert run().value["diff"] == pytest.approx(0.0)


def test_side_filter_and_agent_use_the_teams_own_player(fights_file):
    # T1 defends in a fight T2 opened from attack: T1's side is defender, its agent is the other player's
    fights_file([fight("S1:1", "T2", "T1", 0)] * 60)
    assert run(side="attacker").value == {}
    r = run(side="defender")
    assert r.value["total"] == 60
    agents = [b for b in r.breakdown if b["bucket"] == "agent"]
    assert [a["agent"] for a in agents] == ["cypher"]


def test_agent_pair_table_counts_each_pair_from_one_view():
    from scripts.agent_duels import pair_rows, table
    rows = [fight(f"S{i % 5}:{i}", "T1", "T2", 1, series=f"S{i % 5}", opener_agent="jett", other_agent="cypher")
            for i in range(20)]
    rows += [fight(f"S{i % 5}:x{i}", "T2", "T1", 1, series=f"S{i % 5}", opener_agent="cypher", other_agent="jett")
             for i in range(20)]
    pr = pair_rows(pd.DataFrame(rows))
    assert set(pr["agent_a"]) == {"cypher"} and set(pr["agent_b"]) == {"jett"}   # one view per pair
    t = table(pr, min_pair=10)
    assert len(t) == 1 and t.loc[0, "diff"] == pytest.approx(0.0)              # openers always win: no gap
