import pytest
import pandas as pd
import numpy as np
import duckdb
from engine.model import winprob
from engine.config import DB_PATH
import pickle
import os

def test_series_split():
    # Create dummy data with multiple series
    rows = []
    for s in range(100):
        rows.append({'series_id': f'S{s:03d}', 'label': 0})
    df = pd.DataFrame(rows)
    
    train, val, test = winprob.split_by_series(df, seed=42)
    
    # Proportions roughly 70/15/15
    assert len(train) == 70
    assert len(val) == 15
    assert len(test) == 15
    
    # No series in two splits
    assert len(set(train) & set(val)) == 0
    assert len(set(train) & set(test)) == 0
    assert len(set(val) & set(test)) == 0
    
    # Test stability
    train2, val2, test2 = winprob.split_by_series(df, seed=42)
    assert train == train2
    assert val == val2
    assert test == test2

def test_post_round_kill_excluded():
    con = duckdb.connect(":memory:")
    con.execute("CREATE TABLE rounds (round_key TEXT, series_id TEXT, winner_side TEXT)")
    con.execute("CREATE TABLE team_rounds (round_key TEXT, side TEXT, team_loadout INTEGER)")
    con.execute("CREATE TABLE engagements (round_key TEXT, t_round DOUBLE, vic_side TEXT, vic_id TEXT, kind TEXT, phase TEXT)")
    con.execute("CREATE TABLE objectives (round_key TEXT, t_round DOUBLE, kind TEXT)")
    con.execute("CREATE TABLE player_rounds (round_key TEXT, player_id TEXT, team_id TEXT, side TEXT, has_op BOOLEAN)")
    
    con.execute("INSERT INTO rounds VALUES ('G1:1', 'S1', 'attacker')")
    con.execute("INSERT INTO team_rounds VALUES ('G1:1', 'attacker', 20000), ('G1:1', 'defender', 20000)")
    # A kill in post_round
    con.execute("INSERT INTO engagements (round_key, t_round, vic_side, vic_id, kind, phase) VALUES ('G1:1', 100.0, 'defender', 'P6', 'kill', 'post_round')")
    
    original_connect = duckdb.connect
    duckdb.connect = lambda *args, **kwargs: con
    try:
        df = winprob.get_training_data()
    finally:
        duckdb.connect = original_connect

    # Should have no training rows because the only event is in post_round
    assert len(df) == 0

def test_feature_building():
    # Create a small synthetic dataset in a temporary DuckDB
    con = duckdb.connect(":memory:")
    
    # Minimal schema for what get_training_data uses
    con.execute("CREATE TABLE rounds (round_key TEXT, series_id TEXT, winner_side TEXT)")
    con.execute("CREATE TABLE team_rounds (round_key TEXT, side TEXT, team_loadout INTEGER)")
    con.execute("CREATE TABLE engagements (round_key TEXT, t_round DOUBLE, vic_side TEXT, vic_id TEXT, kind TEXT, phase TEXT)")
    con.execute("CREATE TABLE objectives (round_key TEXT, t_round DOUBLE, kind TEXT)")
    con.execute("CREATE TABLE player_rounds (round_key TEXT, player_id TEXT, team_id TEXT, side TEXT, has_op BOOLEAN)")
    
    # Round 1: Attacker wins, 1 kill in pre_plant
    con.execute("INSERT INTO rounds VALUES ('G1:1', 'S1', 'attacker')")
    con.execute("INSERT INTO team_rounds VALUES ('G1:1', 'attacker', 20000), ('G1:1', 'defender', 20000)")
    con.execute("INSERT INTO engagements (round_key, t_round, vic_side, vic_id, kind, phase) VALUES ('G1:1', 10.0, 'defender', 'P6', 'kill', 'pre_plant')")
    con.execute("INSERT INTO player_rounds VALUES ('G1:1', 'P1', 'T1', 'attacker', false)")

    # Call the function (I'll need to monkeypatch it or pass the connection)
    # Since winprob.get_training_data creates its own connection, I'll temporarily mock duckdb.connect
    
    original_connect = duckdb.connect
    duckdb.connect = lambda *args, **kwargs: con
    try:
        df = winprob.get_training_data()
    finally:
        duckdb.connect = original_connect

    assert len(df) == 1
    row = df.iloc[0]
    assert row['round_key'] == 'G1:1'
    assert row['attackers_alive'] == 5
    assert row['defenders_alive'] == 4
    assert row['label'] == 1

def test_model_ranking():
    # Test that model ranks 5v1 > 1v5
    features = winprob.FEATURES
    
    X = pd.DataFrame([
        [10, False, 0, 5, 1, 20000, 20000, False, False],
        [10, False, 0, 1, 5, 20000, 20000, False, False],
    ] * 50, columns=features)
    X['label'] = [1, 0] * 50
    
    model, baseline = winprob.fit_models(X)
    
    # Predict on the same or similar
    probs = winprob.predict_wp(model, X.iloc[:2])
    assert probs[0] > probs[1] # 5v1 should have higher win prob than 1v5
    
    # Test baseline too
    probs_b = winprob.predict_wp(baseline, X.iloc[:2])
    assert probs_b[0] > probs_b[1]
