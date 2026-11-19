import pytest
import pandas as pd
import numpy as np
import duckdb
from engine.metrics import core
from engine.model import wpa
from engine.metrics import value
from engine.config import V2_DIR
from unittest.mock import MagicMock

def test_bootstrap_mean():
    # same seed gives same interval
    vals = [1.0, 2.0, 3.0, 4.0, 5.0] * 10
    groups = ['S1', 'S2', 'S3', 'S4', 'S5'] * 10
    lo1, hi1 = core.bootstrap_mean(vals, groups, seed=42)
    lo2, hi2 = core.bootstrap_mean(vals, groups, seed=42)
    assert lo1 == lo2
    assert hi1 == hi2
    
    # constant values give zero-width interval (or very close)
    vals_c = [10.0] * 50
    lo_c, hi_c = core.bootstrap_mean(vals_c, groups, seed=42)
    assert lo_c == 10.0
    assert hi_c == 10.0
    
    # interval contains the mean
    lo, hi = core.bootstrap_mean(vals, groups, seed=42)
    mean = np.mean(vals)
    assert lo <= mean <= hi

def test_wpa_logic():
    # Mock model that returns wp = attackers_alive / (attackers_alive + defenders_alive)
    model = MagicMock()
    def mock_predict(X):
        att = X['attackers_alive'].values
        dfnd = X['defenders_alive'].values
        return att / (att + dfnd)
    
    # winprob.predict_wp returns the probability of attackers winning
    with MagicMock() as mock_winprob:
        mock_winprob.predict_wp.side_effect = lambda m, df: mock_predict(df)
        mock_winprob.load_model.return_value = model
        # the real alive counting (revives included); no revives in this round
        from engine.model import winprob as real_winprob
        mock_winprob.AliveTracker = real_winprob.AliveTracker
        mock_winprob.load_revives.return_value = {}
        
        # Monkeypatch engine.model.winprob used in engine.model.wpa
        import engine.model.wpa as wpa_mod
        original_winprob = wpa_mod.winprob
        wpa_mod.winprob = mock_winprob
        
        try:
            # We'll mock the DuckDB connection to return our hand-built round
            con = MagicMock()
            
            # Rounds: one round G1:1
            rounds_df = pd.DataFrame([{
                'round_key': 'G1:1', 'series_id': 'S1', 'map': 'map1',
                'att_loadout': 5000, 'def_loadout': 5000
            }]).set_index('round_key')
            
            # Events:
            # t=10: Attacker P1 kills Defender P2 (5v4)
            # t=20: Defender P3 kills Attacker P1 (4v4)
            kills_df = pd.DataFrame([
                {'event_id': 'E1', 'round_key': 'G1:1', 't_round': 10.0, 'kind': 'kill', 'phase': 'pre_plant', 'weapon': 'operator',
                 'att_id': 'P1', 'att_team': 'T1', 'att_side': 'attacker', 'vic_id': 'P2', 'vic_team': 'T2', 'vic_side': 'defender',
                 'series_id': 'S1', 'seq': 1},
                {'event_id': 'E2', 'round_key': 'G1:1', 't_round': 20.0, 'kind': 'kill', 'phase': 'pre_plant', 'weapon': 'operator',
                 'att_id': 'P3', 'att_team': 'T2', 'att_side': 'defender', 'vic_id': 'P1', 'vic_team': 'T1', 'vic_side': 'attacker',
                 'series_id': 'S1', 'seq': 2},
            ])
            plants_df = pd.DataFrame(columns=['event_id', 'round_key', 't_round', 'kind', 'phase', 'weapon', 'att_id', 'att_team', 'att_side', 'vic_id', 'vic_team', 'vic_side', 'series_id', 'seq'])
            
            # Holders: P1 (Attacker) and P3 (Defender)
            player_ops_df = pd.DataFrame([
                {'round_key': 'G1:1', 'player_id': 'P1', 'player_name': 'Player1', 'team_id': 'T1', 'side': 'attacker', 'started_at': pd.Timestamp('2026-01-01')},
                {'round_key': 'G1:1', 'player_id': 'P3', 'player_name': 'Player3', 'team_id': 'T2', 'side': 'defender', 'started_at': pd.Timestamp('2026-01-01')},
            ])
            
            def mock_execute(query, params=None):
                q = query.lower()
                mock_res = MagicMock()
                if 'from engagements' in q: mock_res.df.return_value = kills_df
                elif 'from objectives' in q: mock_res.df.return_value = plants_df
                elif 'from rounds' in q: mock_res.df.return_value = rounds_df.reset_index()
                elif 'from player_rounds' in q: mock_res.df.return_value = player_ops_df
                return mock_res
            
            con.execute.side_effect = mock_execute
            
            # Patch duckdb.connect to return our mock
            import duckdb as duckdb_mod
            original_connect = duckdb_mod.connect
            duckdb_mod.connect = lambda *a, **kw: con
            
            # Patch to_parquet to avoid writing files
            mock_to_parquet = MagicMock()
            original_to_parquet = pd.DataFrame.to_parquet
            def side_effect(df, path, *args, **kwargs):
                mock_to_parquet(df, path)
            pd.DataFrame.to_parquet = side_effect
            
            try:
                wpa_mod.build_event_wp()
                    
                call_args_list = mock_to_parquet.call_args_list
                # Second call is holder_wpa.parquet
                holders_saved = None
                for call in call_args_list:
                    df_arg = call.args[0]
                    if 'wpa_pp' in df_arg.columns:
                        holders_saved = df_arg
                        break
                assert holders_saved is not None
                # P1 (Attacker): Kill E1 (5/9 - 0.5 = 1/18), Death E2 (0.5 - 5/9 = -1/18)
                # Total WPA = 1/18 - 1/18 = 0.
                p1 = holders_saved[holders_saved['player_id'] == 'P1'].iloc[0]
                assert p1['wpa_pp'] == pytest.approx(0)
                
                # P3 (Defender): Death of P1 at E2 is caused by P3.
                # E2: dwp = 0.5 - 5/9 = -1/18 (attacker perspective)
                # Defender perspective: -dwp = 1/18.
                # WPA = 1/18 * 100 = 5.55...
                p3 = holders_saved[holders_saved['player_id'] == 'P3'].iloc[0]
                assert p3['wpa_pp'] == pytest.approx(1/18 * 100)
                
            finally:
                duckdb_mod.connect = original_connect
                pd.DataFrame.to_parquet = original_to_parquet
        finally:
            wpa_mod.winprob = original_winprob

def test_metric_registration():
    from engine.metrics.core import REGISTRY
    from api.server import OP_METRICS
    assert "op.wpa" in REGISTRY
    for m_id in OP_METRICS:
        assert m_id in REGISTRY

def test_op_wpa_metric(tmp_path):
    # Setup a mock DuckDB and holder_wpa.parquet
    con = duckdb.connect(":memory:")
    
    # S1: P1 has OP. 
    # Round 1: P1 kills P2 (Defender). P1 is Attacker. WPA = +10pp.
    # Round 2: P1 dies. P1 is Attacker. WPA = -10pp.
    # Round 3: P1 kills P2 (Attacker). P1 is Defender. WPA = +10pp.
    
    df_holders = pd.DataFrame([
        {'round_key': 'G1:1', 'series_id': 'S1', 'player_id': 'P1', 'player_name': 'Player1', 'team_id': 'T1', 'side': 'attacker', 'map': 'map1', 'started_at': pd.Timestamp('2026-01-01 10:00:00'), 'wpa_pp': 10.0},
        {'round_key': 'G1:2', 'series_id': 'S1', 'player_id': 'P1', 'player_name': 'Player1', 'team_id': 'T1', 'side': 'attacker', 'map': 'map1', 'started_at': pd.Timestamp('2026-01-01 10:05:00'), 'wpa_pp': -10.0},
        {'round_key': 'G2:3', 'series_id': 'S2', 'player_id': 'P1', 'player_name': 'Player1', 'team_id': 'T1', 'side': 'defender', 'map': 'map1', 'started_at': pd.Timestamp('2026-01-01 11:00:00'), 'wpa_pp': 10.0},
    ])
    
    pq_path = tmp_path / "holder_wpa.parquet"
    df_holders.to_parquet(pq_path)
    
    # Monkeypatch the path in value module
    original_path = value.HOLDER_WPA_PARQUET
    value.HOLDER_WPA_PARQUET = pq_path
    
    try:
        f = value.Filters(team_id='T1', map='map1')
        res = value.get_op_wpa(con, f)
        
        # P1 Rounds: G1:1 (+10pp), G1:2 (-10pp), G2:3 (+10pp)
        # Total WPA = 10 - 10 + 10 = 10.
        # Mean WPA = 10 / 3 = 3.33...
        assert res.value['n'] == 3
        assert res.value['mean'] == pytest.approx(3.33, abs=0.01)
        assert res.value['league_mean'] == pytest.approx(3.33, abs=0.01)
        
        # Breakdown check
        assert len(res.breakdown) == 1
        assert res.breakdown[0]['player_id'] == 'P1'
        assert res.breakdown[0]['small_sample'] is True
    finally:
        value.HOLDER_WPA_PARQUET = original_path
