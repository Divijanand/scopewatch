import duckdb
import pandas as pd
from pathlib import Path

from engine.metrics import Filters, REGISTRY
from engine.metrics import fundamentals


def _db():
    con = duckdb.connect()
    con.execute("""
        CREATE TABLE team_rounds (
            round_key VARCHAR, series_id VARCHAR, map VARCHAR, round_no INTEGER,
            side VARCHAR, won BOOLEAN, team_id VARCHAR, economy VARCHAR, started_at TIMESTAMP
        )
    """)
    con.execute("""
        CREATE TABLE objectives (
            round_key VARCHAR, team_id VARCHAR, kind VARCHAR, t_round DOUBLE, ts_ms BIGINT
        )
    """)
    con.execute("""
        CREATE TABLE engagements (
            round_key VARCHAR, kind VARCHAR, phase VARCHAR, t_round DOUBLE, ts_ms BIGINT, seq INTEGER,
            vic_side VARCHAR, vic_id VARCHAR, att_team VARCHAR, vic_team VARCHAR,
            att_id VARCHAR, att_name VARCHAR, vic_name VARCHAR
        )
    """)
    con.execute("""
        CREATE TABLE casts (
            round_key VARCHAR, ability VARCHAR, phase VARCHAR, side VARCHAR, t_round DOUBLE, ts_ms BIGINT
        )
    """)
    return con


def _add_round(con, rk, series, rn, team, side, won, econ="full", opp="T2", opp_side="defender", opp_won=False, opp_econ="full"):
    con.execute(
        "INSERT INTO team_rounds VALUES (?, ?, 'm', ?, ?, ?, ?, ?, '2030-01-01')",
        [rk, series, rn, side, won, team, econ],
    )
    con.execute(
        "INSERT INTO team_rounds VALUES (?, ?, 'm', ?, ?, ?, ?, ?, '2030-01-01')",
        [rk, series, rn, opp_side, opp_won, opp, opp_econ],
    )


def _run(mid, con, side=None):
    _, fn = REGISTRY[mid]
    return fn(con, Filters(team_id="T1", map="m", side=side))


def test_numbers_at_plant_counts_kill_at_time_revive_before_and_not_after():
    con = _db()
    _add_round(con, "S1:1", "S1", 1, "T1", "defender", True)
    con.execute("INSERT INTO objectives VALUES ('S1:1', 'T2', 'plant', 40.0, 40000)")
    con.execute("INSERT INTO engagements VALUES ('S1:1','kill','pre_plant',40.0,40000,1,'attacker','A1','T1','T2','D1','d','a')")
    con.execute("INSERT INTO engagements VALUES ('S1:1','kill','post_plant',41.0,41000,2,'defender','D2','T2','T1','A2','a','d')")
    con.execute("INSERT INTO casts VALUES ('S1:1','resurrection','pre_plant','attacker',39.9,39900)")
    r = _run("team.retakes", con, side="defender")
    b = {x["bucket"]: x["rate"] for x in r.breakdown}
    assert sum(v.n for v in b.values()) == 1


def test_pistol_and_bonus_rules_only_rounds_1_13_and_after_pistol_win():
    con = _db()
    _add_round(con, "S1:1", "S1", 1, "T1", "attacker", True, "full", opp_econ="full")
    _add_round(con, "S1:2", "S1", 2, "T1", "attacker", False, "half", opp_econ="full")
    _add_round(con, "S1:13", "S1", 13, "T1", "defender", False, "full", opp_side="attacker", opp_econ="full")
    _add_round(con, "S1:14", "S1", 14, "T1", "defender", True, "half", opp_side="attacker", opp_econ="full")
    _add_round(con, "S1:25", "S1", 25, "T1", "attacker", True, "full", opp_econ="full")
    r = _run("team.economy", con)
    assert r.value["pistol"].n == 2
    assert r.value["bonus"].n == 1


def test_first_blood_orders_by_seq_when_same_timestamp():
    con = _db()
    _add_round(con, "S1:3", "S1", 3, "T1", "attacker", True)
    con.execute("INSERT INTO engagements VALUES ('S1:3','kill','pre_plant',10.0,10000,2,'defender','D2','T1','T2','A2','a2','d2')")
    con.execute("INSERT INTO engagements VALUES ('S1:3','kill','pre_plant',10.0,10000,1,'attacker','A1','T2','T1','D1','d1','a1')")
    r = _run("team.openings", con)
    assert r.value["first_blood"].k == 0


def test_retake_defuse_counts_but_detonation_or_defender_elim_do_not():
    con = _db()
    _add_round(con, "S1:4", "S1", 4, "T1", "defender", True)
    _add_round(con, "S1:5", "S1", 5, "T1", "defender", False)
    con.execute("INSERT INTO objectives VALUES ('S1:4','T2','plant',30.0,30000)")
    con.execute("INSERT INTO objectives VALUES ('S1:4','T1','defuse',50.0,50000)")
    con.execute("INSERT INTO objectives VALUES ('S1:5','T2','plant',30.0,30000)")
    con.execute("INSERT INTO objectives VALUES ('S1:5','T2','detonation',70.0,70000)")
    r = _run("team.retakes", con, side="defender")
    assert r.value["retake"].k == 1 and r.value["retake"].n == 2


def test_closing_flips_defender_view_and_threshold_denominators():
    con = _db()
    _add_round(con, "S1:6", "S1", 6, "T1", "defender", True)
    _add_round(con, "S1:7", "S1", 7, "T1", "defender", False)
    df = pd.DataFrame([
        {"round_key": "S1:6", "wp_before": 0.85, "wp_after": 0.82},
        {"round_key": "S1:6", "wp_before": 0.30, "wp_after": 0.10},
        {"round_key": "S1:7", "wp_before": 0.10, "wp_after": 0.15},
    ])
    path = con.execute("SELECT 'event_wp.parquet'").fetchone()[0]
    df.to_parquet(path, index=False)
    fundamentals.EVENT_WP_PARQUET = Path(path)
    r = _run("team.closing", con, side="defender")
    assert r.value["comebacks"].n == 1


def test_missing_event_wp_warns_not_raises(tmp_path, monkeypatch):
    con = _db()
    _add_round(con, "S1:8", "S1", 8, "T1", "attacker", True)
    monkeypatch.setattr(fundamentals, "EVENT_WP_PARQUET", tmp_path / "missing.parquet")
    r = _run("team.closing", con)
    assert r.warnings and "engine.model.wpa" in r.warnings[0]
