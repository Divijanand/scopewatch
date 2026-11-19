"""Step 1 baseline: the current round win-probability model (T1) against its logistic baseline, on the
held-out test series, with the measures in docs/ML_TAXONOMY.md. Writes docs/EVAL_T1.md (aggregates only).

    python -m scripts.eval_t1
"""
from __future__ import annotations

from datetime import date

from engine.config import ROOT
from engine.model import evaluate as ev
from engine.model import winprob


def main():
    df = winprob.get_training_data()
    _, _, test_series = winprob.split_by_series(df)
    test = df[df["series_id"].isin(test_series)]
    model = winprob.load_model()
    baseline = winprob.load_model("winprob_baseline.pkl")
    if model is None or baseline is None:
        raise SystemExit("Train first: python -m engine.model.winprob")
    y = test["label"].to_numpy()
    p_model = winprob.predict_wp(model, test)
    p_base = winprob.predict_wp(baseline, test)
    m, b = ev.evaluate_binary(y, p_model), ev.evaluate_binary(y, p_base)
    diff = ev.paired_difference(y, p_base, p_model, test["series_id"].to_numpy(), n=1000)

    def row(name, r):
        return f"| {name} | {r['log_loss']:.4f} | {r['brier']:.4f} | {r['auc']:.4f} | {r['ece']:.4f} |"

    lines = [
        "# T1 evaluation: round win probability (step 1 baseline)",
        "",
        f"Run {date.today()} on the held-out **test series** ({len(test_series)} series, {m['n']:,} states), "
        "with `engine/model/evaluate.py`. These are the numbers every later model has to beat (docs/ROADMAP_ML.md).",
        "",
        "| Model | Log loss | Brier | AUC | Calibration error (ECE) |",
        "|---|---|---|---|---|",
        row("Logistic baseline (alive counts, planted)", b),
        row("Gradient boosting (current)", m),
        "",
        f"**Is gradient boosting really better?** Log-loss difference {diff['difference']:+.4f} "
        f"(90% range over resampled series {diff['lo']:+.4f} to {diff['hi']:+.4f}): "
        + ("**yes, beyond noise**." if diff["b_better"] else "**not beyond noise**."),
        "",
        "## Reliability (gradient boosting)",
        "",
        "| Predicted bin | Mean predicted | Actual | States |",
        "|---|---|---|---|",
    ]
    for t in m["reliability"]:
        if t["n"]:
            lines.append(f"| {t['lo']:.1f}–{t['hi']:.1f} | {t['predicted']:.3f} | {t['actual']:.3f} | {t['n']:,} |")
    (ROOT / "docs" / "EVAL_T1.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:12]))


if __name__ == "__main__":
    main()
