"""Step 3: are our ranges honest, and does a bootstrap ensemble help? Writes docs/EVAL_BOOTSTRAP.md.

    python -m scripts.step3_bootstrap
"""
from __future__ import annotations

from datetime import date

import numpy as np

from engine.config import ROOT
from engine.model import bootstrap, evaluate as ev, winprob

K = 20


def main():
    out = ["# Step 3: bootstrapping without breaking accuracy or precision", "",
           f"Run {date.today()} with `python -m scripts.step3_bootstrap`. Aggregates only.", ""]

    # ---------------------------------------------------------------- 1. are our ranges honest?
    out += ["## 1. Are our ranges honest? (coverage of the series bootstrap)", "",
            "Simulated data with a known true mean and the same structure as ours: rounds grouped in series that "
            "share an offset. A 90% range should contain the truth about 90% of the time. For contrast, a naive "
            "bootstrap resamples single rounds as if they were independent.", "",
            "| Case | Series | Rounds per series | Series bootstrap coverage | Naive bootstrap coverage | Mean width |",
            "|---|---|---|---|---|---|"]
    for label, g, per in [("Big sample (a team across all maps)", 60, 8), ("Typical (one map, one side)", 15, 8),
                          ("Small (few series)", 6, 8)]:
        r = bootstrap.simulate_coverage(n_sims=300, n_groups=g, per_group=per, seed=g)
        out.append(f"| {label} | {g} | {per} | {r['series_coverage']:.0%} | {r['naive_coverage']:.0%} | "
                   f"{r['mean_width']:.3f} |")
    out += ["", "Read the coverage against the 90% target: the series bootstrap should be close; the naive one shows "
            "what ignoring series costs. See ROADMAP_ML.md step 3 for the interpretation of each run.", ""]

    # ---------------------------------------------------------------- 2. ensemble
    df = winprob.get_training_data()
    train_s, _, test_s = winprob.split_by_series(df)
    train, test = df[df.series_id.isin(train_s)], df[df.series_id.isin(test_s)]
    single = winprob.load_model()
    models = bootstrap.train_ensemble(train, k=K, seed=0)
    ens = bootstrap.predict_ensemble(models, test)
    y = test["label"].to_numpy()
    p_single = winprob.predict_wp(single, test)
    a, b = ev.evaluate_binary(y, p_single), ev.evaluate_binary(y, ens["mean"])
    diff = ev.paired_difference(y, p_single, ens["mean"], test["series_id"].to_numpy(), n=1000)
    out += [f"## 2. Bootstrap ensemble ({K} models, each on a resample of the training series)", "",
            f"Held-out test series: {len(test_s)} series, {len(test):,} states.", "",
            "| Model | Log loss | Brier | AUC | Calibration error |", "|---|---|---|---|---|",
            f"| Single gradient-boosted model | {a['log_loss']:.4f} | {a['brier']:.4f} | {a['auc']:.4f} | {a['ece']:.4f} |",
            f"| Ensemble mean | {b['log_loss']:.4f} | {b['brier']:.4f} | {b['auc']:.4f} | {b['ece']:.4f} |",
            "",
            f"Ensemble minus single, log loss: {diff['difference']:+.4f} (90% range {diff['lo']:+.4f} to {diff['hi']:+.4f}): "
            + ("**better beyond noise**." if diff["b_better"] else "**not better beyond noise**; the ensemble's value is "
               "the spread below, not accuracy."), ""]

    # spread vs how often a state was seen in training
    key = ["attackers_alive", "defenders_alive", "planted"]
    seen = train.groupby(key).size().rename("train_n").reset_index()
    t = test[key].copy()
    t["spread"] = ens["hi"] - ens["lo"]
    t = t.merge(seen, on=key, how="left").fillna({"train_n": 0})
    bands = [(0, 200, "fewer than 200 (thin)"), (200, 2000, "200 to 2,000"), (2000, 20000, "2,000 to 20,000"),
             (20000, 10**9, "more than 20,000")]
    out += ["### Does the spread say \"I don't know\" where it should?", "",
            "Width of the 5th–95th percentile band across the ensemble, by how often that game state appears in "
            "training:", "", "| State seen in training | Test states | Median band width (points of win chance) |",
            "|---|---|---|"]
    for lo, hi, label in bands:
        m = (t.train_n >= lo) & (t.train_n < hi)
        if m.any():
            out.append(f"| {label} | {int(m.sum()):,} | {100 * float(np.median(t.spread[m])):.1f} |")
    out += ["", "Band width is in probability points, so states predicted near 0% or 100% look narrow; compare on the "
            "log-odds scale before treating the spread as an 'uncertain' signal.", ""]

    (ROOT / "docs" / "EVAL_BOOTSTRAP.md").write_text("\n".join(out) + "\n", encoding="utf-8")
    print("Wrote docs/EVAL_BOOTSTRAP.md")


if __name__ == "__main__":
    main()
