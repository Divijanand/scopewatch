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

def get_training_data(db_path=DB_PATH):
    con = duckdb.connect(str(db_path), read_only=True)
    
    # We need one row per kill or plant event.
    # Kill events from engagements table where kind='kill'
    # Plant events from objectives table where kind='plant'
    
    # Join with rounds and team_rounds to get context.
    # attacker side is always identified in team_rounds.
    
    # 1. Kill events
    kills_query = """
    SELECT 
        e.series_id,
        e.game_id,
        e.round_no,
        e.round_key,
        e.t_round as seconds_since_buy_phase_end,
        (e.phase = 'post_plant') as planted,
        CASE WHEN e.phase = 'post_plant' THEN e.t_plant ELSE 0 END as seconds_since_plant,
        r.winner_side = 'attacker' as attackers_won,
        -- Counts alive: 5 minus those who died before or at this event on each side
        -- We need to calculate alive counts. 
        -- Easier to do with a subquery or window function.
    FROM engagements e
    JOIN rounds r ON e.round_key = r.round_key
    WHERE e.kind = 'kill' AND e.phase IN ('pre_plant', 'post_plant')
    """
    
    # Actually, calculating alive counts on the fly in SQL is better.
    
    sql = """
    WITH events AS (
        -- Kill events
        SELECT 
            series_id, game_id, round_no, round_key, t_round, t_plant, phase, 'kill' as event_type, seq
        FROM engagements
        WHERE kind = 'kill' AND phase IN ('pre_plant', 'post_plant')
        
        UNION ALL
        
        -- Plant events
        SELECT 
            series_id, game_id, round_no, round_key, t_round, 0.0 as t_plant, 'post_plant' as phase, 'plant' as event_type, 999999 as seq
        FROM objectives
        WHERE kind = 'plant'
    ),
    event_state AS (
        SELECT 
            ev.*,
            r.winner_side = 'attacker' as attackers_won,
            tr_att.team_loadout as att_loadout,
            tr_def.team_loadout as def_loadout,
            tr_att.side as att_side_name, -- 'attacker'
            -- To get alive counts, we need to know who died.
            -- This is tricky in a single query without a lot of joins.
        FROM events ev
        JOIN rounds r ON ev.round_key = r.round_key
        JOIN team_rounds tr_att ON ev.round_key = tr_att.round_key AND tr_att.side = 'attacker'
        JOIN team_rounds tr_def ON ev.round_key = tr_def.round_key AND tr_def.side = 'defender'
    )
    SELECT * FROM event_state
    """
    # I'll pull the raw events and rounds/kills and do the state calculation in Python for clarity if SQL gets too hairy.
    # Actually, the requirement says "state just after it".
    
    # Let's get all kills in the round to calculate alive counts.
    all_kills = con.execute("SELECT round_key, t_round, vic_side, vic_id FROM engagements WHERE kind = 'kill'").df()
    plants = con.execute("SELECT round_key, t_round FROM objectives WHERE kind = 'plant'").df()
    rounds = con.execute("""
        SELECT r.round_key, r.series_id, r.winner_side, 
               tra.team_loadout as att_loadout, trd.team_loadout as def_loadout
        FROM rounds r
        JOIN team_rounds tra ON r.round_key = tra.round_key AND tra.side = 'attacker'
        JOIN team_rounds trd ON r.round_key = trd.round_key AND trd.side = 'defender'
    """).df()
    
    # We also need who has Op/Outlaw at start of round.
    # team_rounds has n_op, but we also need to track if they are alive.
    player_ops = con.execute("SELECT round_key, player_id, team_id, side, has_op FROM player_rounds WHERE has_op = true").df()

    con.close()
    
    # Building rows in Python
    rows = []
    
    for r in rounds.itertuples():
        r_kills = all_kills[all_kills['round_key'] == r.round_key].sort_values('t_round')
        r_plants = plants[plants['round_key'] == r.round_key]
        r_ops = player_ops[player_ops['round_key'] == r.round_key]
        
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
            # requirement: "state just after it"
            # If multiple events at same t, kills happen before plant in GRID typically,
            # but we want to be stable.
            events.append(('plant', p.t_round, p))
        
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

    # Split by series_id
    series_ids = list(df['series_id'].unique())
    train_series, test_val_series = train_test_split(series_ids, test_size=0.30, random_state=42)
    val_series, test_series = train_test_split(test_val_series, test_size=0.50, random_state=42)
    
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
                count = mask.sum()
                calibration.append((prob_bins[i], prob_bins[i+1], actual, count))
            else:
                calibration.append((prob_bins[i], prob_bins[i+1], np.nan, 0))
        return loss, brier, calibration

    b_loss, b_brier, b_cal = evaluate(baseline, X_test, y_test, baseline_features)
    m_loss, m_brier, m_cal = evaluate(model, X_test, y_test, features)
    
    # Write results to docs/MODEL_WINPROB.md
    with open("docs/MODEL_WINPROB.md", "w") as f:
        f.write("# Win-Probability Model Results\n\n")
        f.write("## Baseline (Logistic Regression on alive counts + planted)\n")
        f.write(f"- Log loss: {b_loss:.4f}\n")
        f.write(f"- Brier score: {b_brier:.4f}\n\n")
        f.write("| Bin | Actual Win Prob | Count |\n")
        f.write("|-----|-----------------|-------|\n")
        for low, high, actual, count in b_cal:
            f.write(f"| {low:.1f}-{high:.1f} | {actual:.4f} | {count} |\n")
            
        f.write("\n## HistGradientBoostingClassifier\n")
        f.write(f"- Log loss: {m_loss:.4f}\n")
        f.write(f"- Brier score: {m_brier:.4f}\n\n")
        f.write("| Bin | Actual Win Prob | Count |\n")
        f.write("|-----|-----------------|-------|\n")
        for low, high, actual, count in m_cal:
            f.write(f"| {low:.1f}-{high:.1f} | {actual:.4f} | {count} |\n")

if __name__ == "__main__":
    train_model()
