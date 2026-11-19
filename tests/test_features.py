from __future__ import annotations

import duckdb

from engine.model.features import build_states
from engine.model import winprob


def _mkdb(path):
    con = duckdb.connect(str(path))
    con.execute("CREATE TABLE games (series_id TEXT, game_id TEXT, game_number INTEGER, map TEXT, patch TEXT, started_at TIMESTAMP, winner_team_id TEXT, team1_id TEXT, team1_name TEXT, team2_id TEXT, team2_name TEXT, event TEXT, stage TEXT, game_changers BOOLEAN)")
    con.execute("CREATE TABLE rounds (round_key TEXT, series_id TEXT, game_id TEXT, round_no INTEGER, map TEXT, patch TEXT, winner_side TEXT, winner_team_id TEXT)")
    con.execute("CREATE TABLE team_rounds (round_key TEXT, side TEXT, team_id TEXT, team_loadout INTEGER)")
    con.execute("CREATE TABLE player_rounds (round_key TEXT, player_id TEXT, side TEXT, team_id TEXT, agent TEXT, loadout_value INTEGER, has_op BOOLEAN)")
    con.execute("CREATE TABLE engagements (round_key TEXT, t_round DOUBLE, vic_id TEXT, vic_side TEXT, kind TEXT, phase TEXT)")
    con.execute("CREATE TABLE objectives (round_key TEXT, t_round DOUBLE, kind TEXT)")
    con.execute("CREATE TABLE casts (round_key TEXT, t_round DOUBLE, side TEXT, ability TEXT, phase TEXT, ts_ms BIGINT)")
    return con


def _seed_round(con, round_key="G1:1", round_no=1, winner_side="attacker", winner_team_id="TA", map_name="ascent", patch="p1"):
    con.execute("INSERT INTO games VALUES ('S1','G1',1,?,?, TIMESTAMP '2030-01-01 00:00:00',NULL,'TA','A','TD','D','evt','stg',false)", [map_name, patch])
    con.execute("INSERT INTO rounds VALUES (?,?,?,?,?,?,?,?)", [round_key, "S1", "G1", round_no, map_name, patch, winner_side, winner_team_id])
    con.execute("INSERT INTO team_rounds VALUES (?, 'attacker', 'TA', 20000), (?, 'defender', 'TD', 18000)", [round_key, round_key])
    players = [
        ("a_duel", "attacker", "TA", "jett", 5000, True),
        ("a_init", "attacker", "TA", "sova", 4000, False),
        ("a_ctrl", "attacker", "TA", "omen", 4000, False),
        ("a_sent", "attacker", "TA", "sage", 3000, False),
        ("a_x", "attacker", "TA", "reyna", 4000, False),
        ("d_duel", "defender", "TD", "raze", 4000, False),
        ("d_init", "defender", "TD", "breach", 3000, False),
        ("d_ctrl", "defender", "TD", "viper", 4000, False),
        ("d_sent", "defender", "TD", "killjoy", 3000, False),
        ("d_x", "defender", "TD", "sage", 4000, False),
    ]
    con.executemany("INSERT INTO player_rounds VALUES (?,?,?,?,?,?,?)", [(round_key, *p) for p in players])


def test_build_states_keeps_kill_plant_rows_and_labels_series(tmp_path):
    db = tmp_path / "f.duckdb"
    con = _mkdb(db)
    _seed_round(con)
    con.execute("INSERT INTO engagements VALUES ('G1:1', 10, 'd_duel', 'defender', 'kill', 'pre_plant')")
    con.execute("INSERT INTO objectives VALUES ('G1:1', 25, 'plant')")
    con.close()

    got = build_states(db)

    original = duckdb.connect(":memory:")
    original.execute("CREATE TABLE rounds (round_key TEXT, series_id TEXT, winner_side TEXT)")
    original.execute("CREATE TABLE team_rounds (round_key TEXT, side TEXT, team_loadout INTEGER)")
    original.execute("CREATE TABLE engagements (round_key TEXT, t_round DOUBLE, vic_side TEXT, vic_id TEXT, kind TEXT, phase TEXT)")
    original.execute("CREATE TABLE objectives (round_key TEXT, t_round DOUBLE, kind TEXT)")
    original.execute("CREATE TABLE player_rounds (round_key TEXT, player_id TEXT, team_id TEXT, side TEXT, has_op BOOLEAN)")
    original.execute("CREATE TABLE casts (round_key TEXT, t_round DOUBLE, side TEXT, ability TEXT, phase TEXT, ts_ms BIGINT)")
    original.execute("INSERT INTO rounds VALUES ('G1:1','S1','attacker')")
    original.execute("INSERT INTO team_rounds VALUES ('G1:1','attacker',20000),('G1:1','defender',18000)")
    original.execute("INSERT INTO engagements VALUES ('G1:1',10,'defender','d_duel','kill','pre_plant')")
    original.execute("INSERT INTO objectives VALUES ('G1:1',25,'plant')")
    original.execute("INSERT INTO player_rounds VALUES ('G1:1','a_duel','TA','attacker',true)")

    orig_connect = duckdb.connect
    duckdb.connect = lambda *args, **kwargs: original
    try:
        expected = winprob.get_training_data()
    finally:
        duckdb.connect = orig_connect
        original.close()

    assert len(got) == len(expected) == 2
    assert got[["series_id", "round_key", "label"]].equals(expected[["series_id", "round_key", "label"]])


def test_no_future_leak_for_util_and_ult_and_role_and_aliveload(tmp_path):
    db = tmp_path / "f.duckdb"
    con = _mkdb(db)
    _seed_round(con)
    con.execute("INSERT INTO engagements VALUES ('G1:1', 10, 'a_sent', 'attacker', 'kill', 'pre_plant')")
    con.execute("INSERT INTO casts VALUES ('G1:1', 20, 'attacker', 'cloudburst', 'pre_plant', 20000)")
    con.execute("INSERT INTO casts VALUES ('G1:1', 22, 'attacker', 'resurrection', 'pre_plant', 22000)")
    con.execute("INSERT INTO casts VALUES ('G1:1', 24, 'attacker', 'lockdown', 'pre_plant', 24000)")
    con.execute("INSERT INTO objectives VALUES ('G1:1', 30, 'plant')")
    con.close()

    df = build_states(db).sort_values("seconds_since_buy_phase_end").reset_index(drop=True)
    first = df.iloc[0]
    assert first["seconds_since_buy_phase_end"] == 10
    assert first["util_att_smoke"] == 0
    assert first["ult_att_used"] == 0
    assert first["role_att_sentinel"] == 0
    assert first["aliveload_att"] == 17000


def test_alive_role_and_revive_behavior(tmp_path):
    db = tmp_path / "f.duckdb"
    con = _mkdb(db)
    _seed_round(con)
    con.execute("INSERT INTO engagements VALUES ('G1:1', 10, 'a_sent', 'attacker', 'kill', 'pre_plant')")
    con.execute("INSERT INTO casts VALUES ('G1:1', 11, 'attacker', 'resurrection', 'pre_plant', 11000)")
    con.execute("INSERT INTO objectives VALUES ('G1:1', 12, 'plant')")
    con.close()

    df = build_states(db).sort_values("seconds_since_buy_phase_end").reset_index(drop=True)
    assert df.iloc[0]["role_att_sentinel"] == 0
    assert df.iloc[1]["role_att_sentinel"] == 1


def test_alive_loadout_drops_exactly_on_death(tmp_path):
    db = tmp_path / "f.duckdb"
    con = _mkdb(db)
    _seed_round(con)
    con.execute("INSERT INTO engagements VALUES ('G1:1', 10, 'a_sent', 'attacker', 'kill', 'pre_plant')")
    con.execute("INSERT INTO objectives VALUES ('G1:1', 20, 'plant')")
    con.close()

    df = build_states(db).sort_values("seconds_since_buy_phase_end").reset_index(drop=True)
    assert df.iloc[0]["aliveload_att"] == 17000


def test_score_before_round_side_swap_mapping(tmp_path):
    db = tmp_path / "f.duckdb"
    con = _mkdb(db)
    con.execute("INSERT INTO games VALUES ('S1','G1',1,'ascent','p1', TIMESTAMP '2030-01-01 00:00:00',NULL,'TA','A','TD','D','evt','stg',false)")
    for rno in range(1, 15):
        att, deff = ("TA", "TD") if rno <= 12 else ("TD", "TA")
        winner = "TA" if rno <= 12 else "TD"
        winner_side = "attacker" if winner == att else "defender"
        rk = f"G1:{rno}"
        con.execute("INSERT INTO rounds VALUES (?,?,?,?,?,?,?,?)", [rk, "S1", "G1", rno, "ascent", "p1", winner_side, winner])
        con.execute("INSERT INTO team_rounds VALUES (?, 'attacker', ?, 20000), (?, 'defender', ?, 20000)", [rk, att, rk, deff])
        con.execute("INSERT INTO engagements VALUES (?, 10, 'd', 'defender', 'kill', 'pre_plant')", [rk])
        con.execute("INSERT INTO player_rounds VALUES (?, 'a1', 'attacker', ?, 'jett', 5000, false)", [rk, att])
        con.execute("INSERT INTO player_rounds VALUES (?, 'd1', 'defender', ?, 'sage', 5000, false)", [rk, deff])
    con.close()

    df = build_states(db)
    r1 = df[df["round_key"] == "G1:1"].iloc[0]
    r13 = df[df["round_key"] == "G1:13"].iloc[0]
    assert r1["score_att_before"] == 0 and r1["score_def_before"] == 0
    assert r13["score_att_before"] == 0 and r13["score_def_before"] == 12


def test_build_states_matches_winprob_shared_columns_with_revive_and_repeat_death(tmp_path):
    db = tmp_path / "f.duckdb"
    con = _mkdb(db)
    _seed_round(con)
    con.execute("INSERT INTO engagements VALUES ('G1:1', 10, 'a_sent', 'attacker', 'kill', 'pre_plant')")
    con.execute("INSERT INTO engagements VALUES ('G1:1', 20, 'a_sent', 'attacker', 'kill', 'post_plant')")
    con.execute("INSERT INTO objectives VALUES ('G1:1', 15, 'plant')")
    con.execute("INSERT INTO casts VALUES ('G1:1', 12, 'attacker', 'resurrection', 'pre_plant', 12000)")
    con.close()

    got = build_states(db).sort_values(["round_key", "seconds_since_buy_phase_end"]).reset_index(drop=True)
    expected = winprob.get_training_data(db).sort_values(["round_key", "seconds_since_buy_phase_end"]).reset_index(drop=True)

    shared = [
        "series_id",
        "round_key",
        "seconds_since_buy_phase_end",
        "planted",
        "seconds_since_plant",
        "attackers_alive",
        "defenders_alive",
        "att_loadout_value",
        "def_loadout_value",
        "att_has_op",
        "def_has_op",
        "label",
    ]
    assert len(got) == len(expected) == 3
    assert got[shared].equals(expected[shared])


def test_six_player_roster_with_phantom_does_not_change_attackers_alive(tmp_path):
    db = tmp_path / "f.duckdb"
    con = _mkdb(db)
    _seed_round(con)
    con.execute("INSERT INTO player_rounds VALUES ('G1:1', 'a_phantom', 'attacker', 'TA', NULL, 0, false)")
    con.execute("INSERT INTO engagements VALUES ('G1:1', 10, 'd_duel', 'defender', 'kill', 'pre_plant')")
    con.execute("INSERT INTO objectives VALUES ('G1:1', 20, 'plant')")
    con.close()

    got = build_states(db).sort_values("seconds_since_buy_phase_end").reset_index(drop=True)
    expected = winprob.get_training_data(db).sort_values("seconds_since_buy_phase_end").reset_index(drop=True)
    assert got.loc[0, "attackers_alive"] == expected.loc[0, "attackers_alive"] == 5
