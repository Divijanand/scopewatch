from __future__ import annotations

import duckdb
import pandas as pd

from engine.model.charges import estimate_charges, merge_cast_uses
from engine.model.features import build_states


def _mkdb(path):
    con = duckdb.connect(str(path))
    con.execute("CREATE TABLE games (series_id TEXT, game_id TEXT, game_number INTEGER, map TEXT, patch TEXT, started_at TIMESTAMP, winner_team_id TEXT, team1_id TEXT, team1_name TEXT, team2_id TEXT, team2_name TEXT, event TEXT, stage TEXT, game_changers BOOLEAN)")
    con.execute("CREATE TABLE rounds (round_key TEXT, series_id TEXT, game_id TEXT, round_no INTEGER, map TEXT, patch TEXT, winner_side TEXT, winner_team_id TEXT)")
    con.execute("CREATE TABLE team_rounds (round_key TEXT, side TEXT, team_id TEXT, team_loadout INTEGER)")
    con.execute("CREATE TABLE player_rounds (round_key TEXT, player_id TEXT, side TEXT, team_id TEXT, agent TEXT, loadout_value INTEGER, has_op BOOLEAN)")
    con.execute("CREATE TABLE engagements (round_key TEXT, t_round DOUBLE, vic_id TEXT, vic_side TEXT, kind TEXT, phase TEXT)")
    con.execute("CREATE TABLE objectives (round_key TEXT, t_round DOUBLE, kind TEXT)")
    con.execute("CREATE TABLE casts (round_key TEXT, t_round DOUBLE, side TEXT, player_id TEXT, agent TEXT, ability TEXT, phase TEXT, ts_ms BIGINT)")
    return con


def _seed(con):
    con.execute("INSERT INTO games VALUES ('S1','G1',1,'ascent','p1', TIMESTAMP '2030-01-01 00:00:00',NULL,'TA','A','TD','D','evt','stg',false)")
    con.execute("INSERT INTO rounds VALUES ('G1:1','S1','G1',1,'ascent','p1','attacker','TA')")
    con.execute("INSERT INTO team_rounds VALUES ('G1:1', 'attacker', 'TA', 20000), ('G1:1', 'defender', 'TD', 20000)")
    con.execute("INSERT INTO player_rounds VALUES ('G1:1','a_sova','attacker','TA','sova',4000,false)")
    con.execute("INSERT INTO player_rounds VALUES ('G1:1','a_jett','attacker','TA','jett',4000,false)")
    con.execute("INSERT INTO player_rounds VALUES ('G1:1','a_sage','attacker','TA','sage',4000,false)")
    con.execute("INSERT INTO player_rounds VALUES ('G1:1','d_kj','defender','TD','killjoy',4000,false)")
    con.execute("INSERT INTO player_rounds VALUES ('G1:1','d_omen','defender','TD','omen',4000,false)")
    con.execute("INSERT INTO engagements VALUES ('G1:1', 12, 'a_sage', 'attacker', 'kill', 'pre_plant')")
    con.execute("INSERT INTO casts VALUES ('G1:1', 10, 'attacker', 'a_sova', 'sova', 'recon-bolt', 'pre_plant', 10000)")
    con.execute("INSERT INTO casts VALUES ('G1:1', 10.4, 'attacker', 'a_sova', 'sova', 'recon-bolt', 'pre_plant', 10400)")
    con.execute("INSERT INTO casts VALUES ('G1:1', 11.5, 'attacker', 'a_sova', 'sova', 'recon-bolt', 'pre_plant', 11500)")
    con.execute("INSERT INTO casts VALUES ('G1:1', 13, 'attacker', 'a_sage', 'sage', 'resurrection', 'pre_plant', 13000)")
    con.execute("INSERT INTO objectives VALUES ('G1:1', 14, 'plant')")


def test_merge_cast_uses_1s_rule():
    df = pd.DataFrame([
        {"round_key": "R1", "player_id": "P1", "ability": "A1", "t_round": 10.0},
        {"round_key": "R1", "player_id": "P1", "ability": "A1", "t_round": 10.4},
        {"round_key": "R1", "player_id": "P1", "ability": "A1", "t_round": 11.5},
    ])
    out = merge_cast_uses(df)
    assert len(out) == 2
    assert list(out["t_round"]) == [10.0, 11.5]


def test_estimate_charges_reusable_by_p99_gt_p95_and_not_for_fixed(tmp_path):
    db = tmp_path / "charges.duckdb"
    con = _mkdb(db)
    _seed(con)
    for idx in range(2, 122):
        rk = f"G1:{idx}"
        con.execute("INSERT INTO rounds VALUES (?,?, 'G1', ?, 'ascent', 'p1', 'attacker', 'TA')", [rk, "S1", idx])
        con.execute("INSERT INTO team_rounds VALUES (?, 'attacker', 'TA', 20000), (?, 'defender', 'TD', 20000)", [rk, rk])
        con.execute("INSERT INTO player_rounds VALUES (?, 'a_sova', 'attacker', 'TA', 'sova', 4000, false)", [rk])
        con.execute("INSERT INTO player_rounds VALUES (?, 'd_omen', 'defender', 'TD', 'omen', 4000, false)", [rk])
        con.execute("INSERT INTO casts VALUES (?, 10.0, 'attacker', 'a_sova', 'sova', 'recon-bolt', 'pre_plant', 10000)", [rk])
        if idx >= 120:
            con.execute("INSERT INTO casts VALUES (?, 11.5, 'attacker', 'a_sova', 'sova', 'recon-bolt', 'pre_plant', 11500)", [rk])
            con.execute("INSERT INTO casts VALUES (?, 13.0, 'attacker', 'a_sova', 'sova', 'recon-bolt', 'pre_plant', 13000)", [rk])
            con.execute("INSERT INTO casts VALUES (?, 14.5, 'attacker', 'a_sova', 'sova', 'recon-bolt', 'pre_plant', 14500)", [rk])
            con.execute("INSERT INTO casts VALUES (?, 15.9, 'attacker', 'a_sova', 'sova', 'recon-bolt', 'pre_plant', 15900)", [rk])
        con.execute("INSERT INTO casts VALUES (?, 12.0, 'defender', 'd_omen', 'omen', 'dark-cover', 'pre_plant', 12000)", [rk])
    got = estimate_charges(con)
    con.close()

    rb = got[got["ability"] == "recon-bolt"].iloc[0]
    assert rb["p99"] > rb["p95"]
    assert bool(rb["reusable"])
    dc = got[got["ability"] == "dark-cover"].iloc[0]
    assert dc["p99"] == dc["p95"]
    assert not bool(dc["reusable"])


def test_remain_features_no_leak_and_revive_and_strict_vs_all(tmp_path):
    db = tmp_path / "remain.duckdb"
    con = _mkdb(db)
    _seed(con)
    con.close()
    df = build_states(db).sort_values("seconds_since_buy_phase_end").reset_index(drop=True)

    first = df.iloc[0]
    assert first["seconds_since_buy_phase_end"] == 12
    assert first["remain_all_att_recon"] >= first["remain_strict_att_recon"]
    assert first["remain_all_att_ult"] == 0
    assert first["remain_all_att_recon"] >= 0


# Reviewer tests: the remaining-utility rules from the brief, on the pure helper.
from engine.model.features import PlayerState, _remaining_features  # noqa: E402

CHARGES = {
    "recon-bolt": {"typical_charges": 2, "reusable": True},     # recon, reusable
    "flashpoint": {"typical_charges": 2, "reusable": False},    # flash, fixed
    "toxic-screen": {"typical_charges": 1, "reusable": False},  # smoke, fixed
}
KITS = {"a1": ("flashpoint", "rolling-thunder"), "a2": ("recon-bolt", "hunter's-fury"), "d1": ("toxic-screen", "viper's-pit")}


def _roster(alive=("a1", "a2", "d1")):
    sides = {"a1": "attacker", "a2": "attacker", "d1": "defender"}
    return {pid: PlayerState(side=s, role="initiator", loadout=0, alive=pid in alive) for pid, s in sides.items()}


def _feat(casts=None, alive=("a1", "a2", "d1"), ult_used=None):
    from collections import defaultdict
    so_far = defaultdict(dict)
    for pid, ab, n in (casts or []):
        so_far[pid][ab] = n
    return _remaining_features(_roster(alive), so_far, CHARGES, KITS, ult_used or {})


def test_remaining_drops_by_one_per_cast_and_never_below_zero():
    assert _feat()["remain_strict_att_flash"] == 2
    assert _feat([("a1", "flashpoint", 1)])["remain_strict_att_flash"] == 1
    assert _feat([("a1", "flashpoint", 5)])["remain_strict_att_flash"] == 0


def test_dead_player_contributes_nothing_and_revived_counts_again():
    assert _feat(alive=("a2", "d1"))["remain_strict_att_flash"] == 0
    assert _feat(alive=("a1", "a2", "d1"))["remain_strict_att_flash"] == 2


def test_ult_remains_until_cast():
    ults = [u for u in ("rolling-thunder", "hunter's-fury", "viper's-pit")]
    from engine.model.features import ULT_SET
    if not all(u in ULT_SET for u in ults):
        import pytest
        pytest.skip("ult names differ in engine.abilities")
    assert _feat()["remain_all_att_ult"] == 2
    assert _feat(ult_used={"a1": True})["remain_all_att_ult"] == 1
    assert _feat()["remain_all_def_ult"] == 1


def test_strict_excludes_reusable_all_includes_capped():
    f = _feat()
    assert f["remain_strict_att_recon"] == 0
    assert f["remain_all_att_recon"] == 2
    assert _feat([("a2", "recon-bolt", 4)])["remain_all_att_recon"] == 0
    assert f["remain_strict_def_smoke"] == 1
