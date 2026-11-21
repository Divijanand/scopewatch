from __future__ import annotations

import duckdb

from engine.model.fights import build_fights


def _seed_base(con):
    con.execute("CREATE TABLE rounds(round_key VARCHAR, series_id VARCHAR, map VARCHAR)")
    con.execute("CREATE TABLE team_rounds(round_key VARCHAR, side VARCHAR, team_loadout BIGINT)")
    con.execute("CREATE TABLE player_rounds(round_key VARCHAR, player_id VARCHAR, has_op BOOLEAN)")
    con.execute("CREATE TABLE objectives(round_key VARCHAR, kind VARCHAR, t_round DOUBLE)")
    con.execute("""
        CREATE TABLE casts(
            round_key VARCHAR, t_round DOUBLE, ts_ms BIGINT, phase VARCHAR, side VARCHAR,
            ability VARCHAR, x DOUBLE, y DOUBLE, spatial_ok BOOLEAN
        )
    """)
    con.execute("""
        CREATE TABLE engagements(
            round_key VARCHAR, t_round DOUBLE, ts_ms BIGINT, kind VARCHAR, phase VARCHAR, weapon VARCHAR,
            att_id VARCHAR, att_side VARCHAR, vic_id VARCHAR, vic_side VARCHAR, damage DOUBLE,
            att_x DOUBLE, att_y DOUBLE, vic_x DOUBLE, vic_y DOUBLE, att_callout VARCHAR
        )
    """)

    con.execute("INSERT INTO rounds VALUES ('r1', 's1', 'ascent')")
    con.execute("INSERT INTO team_rounds VALUES ('r1', 'attacker', 22000), ('r1', 'defender', 21000)")
    con.execute("INSERT INTO player_rounds VALUES ('r1', 'A1', TRUE), ('r1', 'D1', FALSE)")


def test_build_fights_boundaries_and_label():
    con = duckdb.connect(":memory:")
    _seed_base(con)
    con.execute(
        """
        INSERT INTO engagements VALUES
        ('r1', 10.0, 10000, 'damage', 'pre_plant', 'vandal', 'A1', 'attacker', 'D1', 'defender', 40, 0, 0, 100, 0, 'A Main'),
        ('r1', 11.0, 11000, 'damage', 'pre_plant', 'ghost',  'A1', 'attacker', 'D1', 'defender', 35, 0, 0, 100, 0, 'A Main'),
        ('r1', 12.0, 12000, 'kill',   'pre_plant', 'vandal', 'A1', 'attacker', 'D1', 'defender', NULL, 0, 0, 100, 0, 'A Main'),
        ('r1', 16.5, 16500, 'damage', 'pre_plant', 'vandal', 'A1', 'attacker', 'D1', 'defender', 30, 0, 0, 100, 0, 'A Main')
        """
    )

    df = build_fights(con)
    assert len(df) == 1
    row = df.iloc[0]
    assert row["t0"] == 10.0
    assert row["label"] == 1
    assert row["callout"] == "A Main"
    assert df.attrs["no_winner_count"] == 1


def test_ability_damage_excluded_from_open_but_counted_for_damage_window():
    con = duckdb.connect(":memory:")
    _seed_base(con)
    con.execute(
        """
        INSERT INTO engagements VALUES
        ('r1', 9.5, 9500, 'damage', 'pre_plant', 'paint-shells', 'A1', 'attacker', 'D1', 'defender', 20, 0, 0, 100, 0, 'A Main'),
        ('r1', 10.0, 10000, 'damage', 'pre_plant', 'vandal', 'A1', 'attacker', 'D1', 'defender', 40, 0, 0, 100, 0, 'A Main'),
        ('r1', 10.5, 10500, 'damage', 'pre_plant', 'shock-bolt', 'D1', 'defender', 'A1', 'attacker', 15, 100, 0, 0, 0, 'Tree'),
        ('r1', 11.0, 11000, 'kill',   'pre_plant', 'vandal', 'A1', 'attacker', 'D1', 'defender', NULL, 0, 0, 100, 0, 'A Main')
        """
    )

    df = build_fights(con, window_s=1.0)
    assert len(df) == 1
    row = df.iloc[0]
    assert row["t0"] == 10.0
    assert row["dmg_util_opener"] == 20.0
    assert row["dmg_util_other"] == 0.0


def test_cast_window_radius_and_spatial_quality_gate():
    con = duckdb.connect(":memory:")
    _seed_base(con)
    con.execute(
        """
        INSERT INTO engagements VALUES
        ('r1', 10.0, 10000, 'damage', 'pre_plant', 'vandal', 'A1', 'attacker', 'D1', 'defender', 40, 0, 0, 100, 0, 'A Main'),
        ('r1', 11.0, 11000, 'kill',   'pre_plant', 'vandal', 'A1', 'attacker', 'D1', 'defender', NULL, 0, 0, 100, 0, 'A Main')
        """
    )
    con.execute(
        """
        INSERT INTO casts VALUES
        ('r1', 9.5, 9500, 'pre_plant', 'attacker', 'flashpoint', 0, 0, TRUE),
        ('r1', 9.7, 9700, 'pre_plant', 'attacker', 'dark-cover', 10000, 0, TRUE),
        ('r1', 9.8, 9800, 'pre_plant', 'defender', 'recon-bolt', 50, 0, FALSE),
        ('r1', 10.2, 10200, 'pre_plant', 'defender', 'recon-bolt', 50, 0, TRUE)
        """
    )

    df = build_fights(con, window_s=1.0, radius=500.0)
    row = df.iloc[0]
    assert row["util_opener_flash_stun"] == 1
    assert row["util_opener_smoke"] == 0
    assert row["util_other_recon"] == 0


def test_alive_counts_include_revive_at_t0():
    con = duckdb.connect(":memory:")
    _seed_base(con)
    con.execute("""
        CREATE TABLE casts_revive(
            round_key VARCHAR, t_round DOUBLE, side VARCHAR, ability VARCHAR, phase VARCHAR, ts_ms BIGINT
        )
    """)
    con.execute("DROP TABLE casts")
    con.execute("""
        CREATE TABLE casts(
            round_key VARCHAR, t_round DOUBLE, ts_ms BIGINT, phase VARCHAR, side VARCHAR,
            ability VARCHAR, x DOUBLE, y DOUBLE, spatial_ok BOOLEAN
        )
    """)

    con.execute(
        """
        INSERT INTO engagements VALUES
        ('r1', 8.0, 8000, 'kill',   'pre_plant', 'vandal', 'D2', 'defender', 'A2', 'attacker', NULL, 10, 0, 20, 0, 'Mid'),
        ('r1', 10.0, 10000, 'damage', 'pre_plant', 'vandal', 'A1', 'attacker', 'D1', 'defender', 40, 0, 0, 100, 0, 'A Main'),
        ('r1', 11.0, 11000, 'kill',   'pre_plant', 'vandal', 'A1', 'attacker', 'D1', 'defender', NULL, 0, 0, 100, 0, 'A Main')
        """
    )
    con.execute(
        """
        INSERT INTO casts VALUES
        ('r1', 9.9, 9900, 'pre_plant', 'attacker', 'resurrection', 0, 0, TRUE)
        """
    )

    df = build_fights(con)
    row = df.iloc[0]
    assert row["opener_side_alive"] == 5


# Reviewer tests (step 4c review).

def test_gap_of_3s_ends_fight_without_winner_and_new_damage_starts_new_fight():
    con = duckdb.connect(":memory:")
    _seed_base(con)
    con.execute(
        """
        INSERT INTO engagements VALUES
        ('r1', 10.0, 10000, 'damage', 'pre_plant', 'vandal', 'A1', 'attacker', 'D1', 'defender', 40, 0, 0, 100, 0, 'A Main'),
        ('r1', 13.5, 13500, 'damage', 'pre_plant', 'vandal', 'D1', 'defender', 'A1', 'attacker', 40, 100, 0, 0, 0, 'A Site'),
        ('r1', 14.0, 14000, 'kill',   'pre_plant', 'vandal', 'D1', 'defender', 'A1', 'attacker', NULL, 100, 0, 0, 0, 'A Site')
        """
    )
    df = build_fights(con)
    assert len(df) == 1
    row = df.iloc[0]
    assert row["t0"] == 13.5
    assert row["opener_id"] == "D1"
    assert row["label"] == 1
    assert df.attrs["no_winner_count"] == 1


def test_other_weapon_comes_from_earlier_damage_and_same_side_damage_is_ignored():
    con = duckdb.connect(":memory:")
    _seed_base(con)
    con.execute(
        """
        INSERT INTO engagements VALUES
        ('r1', 5.0, 5000, 'damage', 'pre_plant', 'sheriff', 'D1', 'defender', 'A2', 'attacker', 50, 100, 0, 0, 0, 'Mid'),
        ('r1', 6.0, 6000, 'damage', 'pre_plant', 'vandal', 'A1', 'attacker', 'A2', 'attacker', 10, 0, 0, 5, 0, 'Mid'),
        ('r1', 10.0, 10000, 'damage', 'pre_plant', 'vandal', 'A1', 'attacker', 'D1', 'defender', 40, 0, 0, 100, 0, 'A Main'),
        ('r1', 11.0, 11000, 'kill',   'pre_plant', 'vandal', 'A1', 'attacker', 'D1', 'defender', NULL, 0, 0, 100, 0, 'A Main')
        """
    )
    df = build_fights(con)
    fight = df[df["t0"] == 10.0].iloc[0]
    assert fight["opener_weapon"] == "vandal"
    assert fight["other_weapon"] == "sheriff"
    assert not ((df["opener_id"] == "A1") & (df["other_id"] == "A2")).any()
