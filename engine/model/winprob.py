import duckdb
import pandas as pd
import numpy as np
import pathlib
import pickle
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss, brier_score_loss
import os

from engine.config import DB_PATH, V2_DIR

MODEL_DIR = V2_DIR / "models"

def split_by_series(df, seed=42):
    series_ids = sorted(df['series_id'].unique())
    from sklearn.model_selection import train_test_split
    train_series, test_val_series = train_test_split(series_ids, test_size=0.30, random_state=seed)
    val_series, test_series = train_test_split(test_val_series, test_size=0.50, random_state=seed)
    return train_series, val_series, test_series

FEATURES = [
    'seconds_since_buy_phase_end', 'planted', 'seconds_since_plant',
    'attackers_alive', 'defenders_alive', 'att_loadout_value', 'def_loadout_value',
    'att_has_op', 'def_has_op'
]
BASELINE_FEATURES = ['attackers_alive', 'defenders_alive', 'planted']

def fit_models(train_df):
    X_train = train_df[FEATURES]
    y_train = train_df['label']
    
    baseline = LogisticRegression(random_state=42)
    baseline.fit(X_train[BASELINE_FEATURES], y_train)
    
    model = HistGradientBoostingClassifier(random_state=42)
    model.fit(X_train, y_train)
    
    return model, baseline

def load_model(name="winprob_hgb.pkl"):
    path = MODEL_DIR / name
    if not path.exists():
        return None
    with open(path, "rb") as f:
        return pickle.load(f)

def predict_wp(model, states_df):
    """P(attackers win) for a DataFrame with the existing feature columns."""
    # Handle cases where model might be the baseline (using fewer features)
    if isinstance(model, LogisticRegression):
        X = states_df[BASELINE_FEATURES]
    else:
        X = states_df[FEATURES]
    return model.predict_proba(X)[:, 1]

REVIVES = ("resurrection", "not-dead-yet")   # Sage revives a teammate; Clove revives herself


class AliveTracker:
    """Players alive per side, robust to revives.

    A Sage Resurrection or Clove Not Dead Yet brings a dead player back, so the same player can die twice in a
    round (495 times in the corpus, always after a revive by their team). Counting kills would then go below zero.
    Instead: alive = 5 - distinct dead players + revives not yet "used up" by a second death, clamped to 0..5.
    """

    def __init__(self):
        self.dead = {"attacker": set(), "defender": set()}
        self.revived = {"attacker": 0, "defender": 0}

    def kill(self, side, victim):
        if side not in self.dead:
            return
        if victim in self.dead[side]:
            # they were revived earlier and died again: that revive is used up
            self.revived[side] = max(0, self.revived[side] - 1)
        else:
            self.dead[side].add(victim)

    def revive(self, side):
        if side in self.dead and len(self.dead[side]) - self.revived[side] > 0:
            self.revived[side] += 1

    def alive(self, side):
        return max(0, min(5, 5 - len(self.dead[side]) + self.revived[side]))


def load_revives(con):
    """{round_key: [(t_round, side)]} for revive casts during the round."""
    df = con.execute(f"""
        SELECT round_key, t_round, side FROM casts
        WHERE ability IN {REVIVES} AND phase IN ('pre_plant', 'post_plant') AND side IS NOT NULL
        ORDER BY round_key, ts_ms""").df()
    return {k: list(zip(g["t_round"], g["side"])) for k, g in df.groupby("round_key")}


def get_training_data(db_path=DB_PATH):
    con = duckdb.connect(str(db_path), read_only=True)
    revives_by_round = load_revives(con)

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
        alive = AliveTracker()
        att_ops = set(r_ops[r_ops['side'] == 'attacker']['player_id'])
        def_ops = set(r_ops[r_ops['side'] == 'defender']['player_id'])

        # Events: kills and plants make training rows; revives only change who is alive
        events = []
        for k in r_kills.itertuples():
            events.append(('kill', k.t_round, k))
        for p in r_plants.itertuples():
            events.append(('plant', p.t_round, p))
        for t, side in revives_by_round.get(r.round_key, []):
            events.append(('revive', t, side))

        # Sort events by time; at the same time: kills, then revives, then plants
        order = {'kill': 0, 'revive': 1, 'plant': 2}
        events.sort(key=lambda x: (x[1], order[x[0]]))

        is_planted = False
        plant_t = None

        for etype, t, edata in events:
            if etype == 'revive':
                alive.revive(edata)
                continue
            if etype == 'kill':
                alive.kill(edata.vic_side, edata.vic_id)
                if edata.vic_side == 'attacker':
                    att_ops.discard(edata.vic_id)
                else:
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
                'attackers_alive': alive.alive('attacker'),
                'defenders_alive': alive.alive('defender'),
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
    test_df = df[df['series_id'].isin(test_series)]
    
    model, baseline = fit_models(train_df)
    
    # Save model
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    with open(MODEL_DIR / "winprob_hgb.pkl", "wb") as f:
        pickle.dump(model, f)
    with open(MODEL_DIR / "winprob_baseline.pkl", "wb") as f:
        pickle.dump(baseline, f)
        
    # Evaluation
    def evaluate(m, df):
        probs = predict_wp(m, df)
        y = df['label']
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

    b_loss, b_brier, b_cal = evaluate(baseline, test_df)
    m_loss, m_brier, m_cal = evaluate(model, test_df)
    
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
