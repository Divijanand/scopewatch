"""Step 3: are our ranges honest, and does a bootstrap ensemble help? Writes docs/EVAL_BOOTSTRAP.md.

    python -m scripts.step3_bootstrap
"""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

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
            "| Case | Series | Rounds per series | Ours: t interval | Percentile (old default) | Naive (rounds as independent) | Our mean width |",
            "|---|---|---|---|---|---|---|"]
    for label, g, per in [("Big sample (a team across all maps)", 60, 8), ("Typical (one map, one side)", 15, 8),
                          ("Small (few series)", 6, 8), ("Very small", 4, 8)]:
        r = bootstrap.simulate_coverage(n_sims=600, n_groups=g, per_group=per, seed=g)
        out.append(f"| {label} | {g} | {per} | {r['series_coverage']:.0%} | {r['percentile_coverage']:.0%} | "
                   f"{r['naive_coverage']:.0%} | {r['mean_width']:.3f} |")
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

    # spread vs how often a state was seen in training, on the log-odds scale, within similar predictions
    key = ["attackers_alive", "defenders_alive", "planted"]
    seen = train.groupby(key).size().rename("train_n").reset_index()
    t = test[key].copy()
    t["p"] = ens["mean"]
    t["logit_std"] = ens["logit_std"]
    t = t.merge(seen, on=key, how="left").fillna({"train_n": 0})
    rare_cut = float(np.quantile(t["train_n"], 0.10))
    t["rarity"] = np.where(t["train_n"] <= rare_cut, "rare", "common")
    t["pband"] = pd.cut(t["p"], [0, 0.1, 0.3, 0.7, 0.9, 1.0], labels=["0-10%", "10-30%", "30-70%", "70-90%", "90-100%"],
                        include_lowest=True)
    out += ["### Does the spread say \"I don't know\" where it should?", "",
            "Disagreement between the 20 models (standard deviation of their log-odds), for game states that are "
            f"**rare** in training (the rarest 10% of test states: seen {int(rare_cut):,} times or fewer) against "
            "**common** ones, compared within the same band of predicted win chance:", "",
            "| Predicted win chance | Rare: states | Rare: median spread | Common: states | Common: median spread | Rare / common |",
            "|---|---|---|---|---|---|"]
    ratios = []
    for band, grp in t.groupby("pband", observed=True):
        r, c = grp[grp.rarity == "rare"], grp[grp.rarity == "common"]
        if len(r) >= 20 and len(c) >= 20:
            mr, mc = float(np.median(r.logit_std)), float(np.median(c.logit_std))
            ratios.append(mr / mc if mc else np.nan)
            out.append(f"| {band} | {len(r):,} | {mr:.3f} | {len(c):,} | {mc:.3f} | {mr / mc:.2f}x |")
    verdict = ("**Yes.** Within every band with enough states, the models disagree more about rare states, so the "
               "spread can back an \"uncertain\" flag." if ratios and min(ratios) > 1.1 else
               "**Partly or not.** The rare/common ratio isn't clearly above 1 in every band, so the spread is not "
               "used as an \"uncertain\" flag." )
    out += ["", verdict, ""]

    (ROOT / "docs" / "EVAL_BOOTSTRAP.md").write_text("\n".join(out) + "\n", encoding="utf-8")
    print("Wrote docs/EVAL_BOOTSTRAP.md")


if __name__ == "__main__":
    main()
