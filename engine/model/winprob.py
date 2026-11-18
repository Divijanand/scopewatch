import duckdb
import pandas as pd
import numpy as np
import pathlib
import pickle
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss, brier_score_loss
from sklearn.model_selection import train_test_split
import os

from engine.config import DB_PATH, V2_DIR

MODEL_DIR = V2_DIR / "models"

def split_by_series(df, seed=42):
    series_ids = sorted(df['series_id'].unique())
    from sklearn.model_selection import train_test_split
    train_series, test_val_series = train_test_split(series_ids, test_size=0.30, random_state=seed)
    val_series, test_series = train_test_split(test_val_series, test_size=0.50, random_state=seed)
    return train_series, val_series, test_series

def get_training_data(db_path=DB_PATH):
    con = duckdb.connect(str(db_path), read_only=True)
    
    # 1. Kill events
    # Only pre_plant and post_plant
    all_kills = con.execute("""
        SELECT round_key, t_round, vic_side, vic_id 
        FROM engagements 
        WHERE kind = 'kill' AND phase IN ('pre_plant', 'post_plant')
        ORDER BY round_key, t_round
    """).df()
    
    plants = con.execute("SELECT round_key, t_round FROM objectives WHERE kind = 'plant' ORDER BY round_key, t_round").df()
    
    rounds = con.execute("""
        SELECT r.round_key, r.series_id, r.winner_side, 
               tra.team_loadout as att_loadout, trd.team_loadout as def_loadout
        FROM rounds r
        JOIN team_rounds tra ON r.round_key = tra.round_key AND tra.side = 'attacker'
        JOIN team_rounds trd ON r.round_key = trd.round_key AND trd.side = 'defender'
        ORDER BY r.round_key
    """).df()
    
    player_ops = con.execute("SELECT round_key, player_id, team_id, side, has_op FROM player_rounds WHERE has_op = true").df()

    con.close()
    
    # Group kills, plants, and ops by round_key for linear processing
    kills_by_round = {k: g for k, g in all_kills.groupby('round_key')}
    plants_by_round = {k: g for k, g in plants.groupby('round_key')}
    ops_by_round = {k: g for k, g in player_ops.groupby('round_key')}
    
    rows = []
    
    for r in rounds.itertuples():
        r_kills = kills_by_round.get(r.round_key, pd.DataFrame(columns=['t_round', 'vic_side', 'vic_id']))
        r_plants = plants_by_round.get(r.round_key, pd.DataFrame(columns=['t_round']))
        r_ops = ops_by_round.get(r.round_key, pd.DataFrame(columns=['side', 'player_id']))
        
        # Initial state
        att_alive = 5
        def_alive = 5
        att_ops = set(r_ops[r_ops['side'] == 'attacker']['player_id'])
        def_ops = set(r_ops[r_ops['side'] == 'defender']['player_id'])
        
        # Events: kills and plants
        events = []
        for k in r_kills.itertuples():
            events.append(('kill', k.t_round, k))
        for p in r_plants.itertuples():
            events.append(('plant', p.t_round, p))
        
        # Sort events by time, then kills before plants if at same time
        events.sort(key=lambda x: (x[1], 0 if x[0] == 'kill' else 1))
        
        is_planted = False
        plant_t = None
        
        for etype, t, edata in events:
            if etype == 'kill':
                if edata.vic_side == 'attacker':
                    att_alive -= 1
                    att_ops.discard(edata.vic_id)
                else:
                    def_alive -= 1
                    def_ops.discard(edata.vic_id)
            elif etype == 'plant':
                is_planted = True
                plant_t = t
            
            # State JUST AFTER the event
            rows.append({
                'series_id': r.series_id,
                'round_key': r.round_key,
                'seconds_since_buy_phase_end': t,
                'planted': is_planted,
                'seconds_since_plant': (t - plant_t) if is_planted else 0,
                'attackers_alive': att_alive,
                'defenders_alive': def_alive,
                'att_loadout_value': r.att_loadout,
                'def_loadout_value': r.def_loadout,
                'att_has_op': len(att_ops) > 0,
                'def_has_op': len(def_ops) > 0,
                'label': 1 if r.winner_side == 'attacker' else 0
            })
            
    return pd.DataFrame(rows)

def train_model():
    df = get_training_data()
    if df.empty:
        print("No training data found.")
        return

    train_series, val_series, test_series = split_by_series(df)
    
    train_df = df[df['series_id'].isin(train_series)]
    val_df = df[df['series_id'].isin(val_series)]
    test_df = df[df['series_id'].isin(test_series)]
    
    features = [
        'seconds_since_buy_phase_end', 'planted', 'seconds_since_plant',
        'attackers_alive', 'defenders_alive', 'att_loadout_value', 'def_loadout_value',
        'att_has_op', 'def_has_op'
    ]
    
    X_train = train_df[features]
    y_train = train_df['label']
    X_val = val_df[features]
    y_val = val_df['label']
    X_test = test_df[features]
    y_test = test_df['label']
    
    # Models
    baseline = LogisticRegression(random_state=42)
    baseline_features = ['attackers_alive', 'defenders_alive', 'planted']
    baseline.fit(X_train[baseline_features], y_train)
    
    model = HistGradientBoostingClassifier(random_state=42)
    model.fit(X_train, y_train)
    
    # Save model
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    with open(MODEL_DIR / "winprob_hgb.pkl", "wb") as f:
        pickle.dump(model, f)
    with open(MODEL_DIR / "winprob_baseline.pkl", "wb") as f:
        pickle.dump(baseline, f)
        
    # Evaluation
    def evaluate(m, X, y, feat):
        probs = m.predict_proba(X[feat])[:, 1]
        loss = log_loss(y, probs)
        brier = brier_score_loss(y, probs)
        
        # Calibration table
        prob_bins = np.linspace(0, 1, 11)
        bin_indices = np.digitize(probs, prob_bins[1:-1])
        calibration = []
        for i in range(10):
            mask = bin_indices == i
            if mask.any():
                actual = y[mask].mean()
                mean_pred = probs[mask].mean()
                count = mask.sum()
                calibration.append((prob_bins[i], prob_bins[i+1], mean_pred, actual, count))
            else:
                calibration.append((prob_bins[i], prob_bins[i+1], np.nan, np.nan, 0))
        return loss, brier, calibration

    b_loss, b_brier, b_cal = evaluate(baseline, X_test, y_test, baseline_features)
    m_loss, m_brier, m_cal = evaluate(model, X_test, y_test, features)
    
    # Write results to docs/MODEL_WINPROB.md using absolute path
    from engine.config import ROOT
    report_path = ROOT / "docs" / "MODEL_WINPROB.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(report_path, "w") as f:
        f.write("# Win-Probability Model Results\n\n")
        f.write("## Baseline (Logistic Regression on alive counts + planted)\n")
        f.write(f"- Log loss: {b_loss:.4f}\n")
        f.write(f"- Brier score: {b_brier:.4f}\n\n")
        f.write("| Bin | Mean Pred | Actual Win Prob | Count |\n")
        f.write("|-----|-----------|-----------------|-------|\n")
        for low, high, mean_pred, actual, count in b_cal:
            f.write(f"| {low:.1f}-{high:.1f} | {mean_pred:.4f} | {actual:.4f} | {count} |\n")
            
        f.write("\n## HistGradientBoostingClassifier\n")
        f.write(f"- Log loss: {m_loss:.4f}\n")
        f.write(f"- Brier score: {m_brier:.4f}\n\n")
        f.write("| Bin | Mean Pred | Actual Win Prob | Count |\n")
        f.write("|-----|-----------|-----------------|-------|\n")
        for low, high, mean_pred, actual, count in m_cal:
            f.write(f"| {low:.1f}-{high:.1f} | {mean_pred:.4f} | {actual:.4f} | {count} |\n")

if __name__ == "__main__":
    train_model()
