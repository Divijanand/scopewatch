"""Step 5 synthetic-data weighting experiment for T1.

    python -m scripts.eval_synthetic
"""
from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier

from engine.config import ROOT
from engine.model import evaluate as ev
from engine.model.simulate import compare_to_real, fit_simulator, simulate
from engine.model.winprob import FEATURES, get_training_data, load_model, split_by_series


def fit_predict(train_df: pd.DataFrame, test_df: pd.DataFrame, sample_weight=None):
    model = HistGradientBoostingClassifier(random_state=42)
    model.fit(train_df[FEATURES], train_df["label"], sample_weight=sample_weight)
    return model.predict_proba(test_df[FEATURES])[:, 1], model


def build_weighted_train(real_train: pd.DataFrame, synth_states: pd.DataFrame, w: float):
    synth = synth_states.copy()
    real_ids = set(real_train["series_id"].astype(str).tolist())
    synth_ids = set(synth["series_id"].astype(str).tolist())
    if real_ids & synth_ids:
        raise ValueError("Synthetic series_id collided with real series_id")
    train = pd.concat([real_train, synth], ignore_index=True)
    weights = np.concatenate([np.ones(len(real_train), dtype=float), np.full(len(synth), float(w), dtype=float)])
    return train, weights


def synthetic_states(sim, n_states: int, seed: int = 0) -> pd.DataFrame:
    """As many synthetic states as `n_states`, from whole simulated rounds (one simulator, one seed).
    A pilot run estimates states per round; the last round is cut to hit the count exactly."""
    pilot = simulate(sim, n_rounds=2000, seed=seed)
    per_round = max(1.0, len(pilot) / 2000)
    n_rounds = int(np.ceil(n_states / per_round * 1.1)) + 100
    synth = simulate(sim, n_rounds=n_rounds, seed=seed)
    while len(synth) < n_states:            # rare: the estimate fell short
        n_rounds = int(n_rounds * 1.2)
        synth = simulate(sim, n_rounds=n_rounds, seed=seed)
    return synth.iloc[:n_states].reset_index(drop=True)


def main():
    states = get_training_data()
    train_series, _, test_series = split_by_series(states, seed=42)
    train_df = states[states["series_id"].isin(train_series)].copy()
    test_df = states[states["series_id"].isin(test_series)].copy()

    sim = fit_simulator(train_df)
    synth = synthetic_states(sim, len(train_df))

    y = test_df["label"].to_numpy()

    p0, _ = fit_predict(train_df, test_df)
    production = load_model()
    if production is not None:
        # w = 0 is the production model: same features, split, seed and estimator
        p_prod = production.predict_proba(test_df[FEATURES])[:, 1]
        assert np.allclose(p0, p_prod), "w = 0 doesn't reproduce the production model's test predictions"
    m0 = ev.evaluate_binary(y, p0)

    rows = [
        dict(weight="0", log_loss=m0["log_loss"], brier=m0["brier"], auc=m0["auc"], ece=m0["ece"],
             diff=0.0, lo=0.0, hi=0.0)
    ]
    best_w = 0.0
    best_ll = m0["log_loss"]
    best_helped = False

    for w in (0.1, 0.25, 0.5):
        train_w, sw = build_weighted_train(train_df, synth, w)
        p, _ = fit_predict(train_w, test_df, sample_weight=sw)
        m = ev.evaluate_binary(y, p)
        d = ev.paired_difference(y, p0, p, test_df["series_id"].to_numpy(), n=1000, seed=42)
        helped = d["hi"] < 0 and m["ece"] <= m0["ece"] + 0.002
        if m["log_loss"] < best_ll:
            best_ll = m["log_loss"]
            best_w = w
            best_helped = helped
        rows.append(dict(weight=str(w), log_loss=m["log_loss"], brier=m["brier"], auc=m["auc"], ece=m["ece"],
                         diff=d["difference"], lo=d["lo"], hi=d["hi"]))

    p_synth, _ = fit_predict(synth, test_df)
    m_synth = ev.evaluate_binary(y, p_synth)
    d_synth = ev.paired_difference(y, p0, p_synth, test_df["series_id"].to_numpy(), n=1000, seed=42)
    rows.append(dict(weight="synth_only", log_loss=m_synth["log_loss"], brier=m_synth["brier"], auc=m_synth["auc"],
                     ece=m_synth["ece"], diff=d_synth["difference"], lo=d_synth["lo"], hi=d_synth["hi"]))

    realism = compare_to_real(synth, train_df)

    lines = [
        "# Step 5: synthetic data weighting experiment",
        "",
        f"Run {datetime.now().isoformat(timespec='seconds')} on held-out test series only "
        f"({test_df['series_id'].nunique()} series, {len(test_df):,} states).",
        "",
        "## Simulator realism vs real training states",
        "",
        "| Metric | Synthetic | Real |",
        "|---|---:|---:|",
    ]
    for r in realism.itertuples(index=False):
        lines.append(f"| {r.metric} | {r.synthetic:.4f} | {r.real:.4f} |")

    lines += [
        "",
        "## Held-out results",
        "",
        "| Synthetic weight | Log loss | Brier | AUC | Calibration error (ECE) | Δ log loss vs w=0 | 90% range |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for r in rows:
        auc = "nan" if r["auc"] is None else f"{r['auc']:.4f}"
        lines.append(
            f"| {r['weight']} | {r['log_loss']:.4f} | {r['brier']:.4f} | {auc} | {r['ece']:.4f} | "
            f"{r['diff']:+.4f} | [{r['lo']:+.4f}, {r['hi']:+.4f}] |"
        )

    if best_helped:
        verdict = f"Synthetic data helps: weight **{best_w}** beats real data alone beyond noise."
    elif best_w != 0:
        verdict = (f"The lowest log loss is at weight {best_w}, but not beyond noise. **Real data alone is best**; "
                   "synthetic data stays a testing tool.")
    else:
        verdict = "**Real data alone is best**: every synthetic weight is worse. Synthetic data stays a testing tool."
    lines += [
        "",
        "## Verdict",
        "",
        f"- {verdict}",
        "- Rule: a weight helps only if its 90% log-loss range is entirely below 0 and its calibration error is at "
        "most w = 0's + 0.002.",
        "- w = 0 is checked to reproduce the production model's test predictions exactly.",
        f"- Synthetic states: {len(synth):,} from one simulator fit on train series only (seed 0); "
        "the test series never reach the simulator.",
    ]

    out = ROOT / "docs" / "EVAL_SYNTHETIC.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {out}: best weight {best_w}, helps = {'yes' if best_helped else 'no'}")


if __name__ == "__main__":
    main()
