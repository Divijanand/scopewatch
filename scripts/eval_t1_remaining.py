"""Step 4b utility-remaining ablation for T1 win probability.

    python -m scripts.eval_t1_remaining
"""
from __future__ import annotations

from datetime import datetime

from sklearn.ensemble import HistGradientBoostingClassifier

from engine.config import ROOT
from engine.model import evaluate as ev
from engine.model.features import build_states
from engine.model.winprob import FEATURES as BASELINE_FEATURES, split_by_series


def pick_columns(df, prefixes: list[str]) -> list[str]:
    cols = []
    for c in df.columns:
        if c in ("series_id", "round_key", "label"):
            continue
        if c in BASELINE_FEATURES:
            cols.append(c)
            continue
        if any(c == p or c.startswith(p) for p in prefixes):
            cols.append(c)
    return cols


def fit_predict(train_df, test_df, cols):
    model = HistGradientBoostingClassifier(random_state=42, categorical_features="from_dtype")
    model.fit(train_df[cols], train_df["label"])
    return model.predict_proba(test_df[cols])[:, 1]


def evaluate_slice(y, p, yb, pb, sid):
    m = ev.evaluate_binary(y, p)
    d = ev.paired_difference(y, pb, p, sid, n=1000, seed=42)
    mb = ev.evaluate_binary(yb, pb)
    helps = d["hi"] < 0 and m["ece"] <= mb["ece"] + 0.002
    return m, d, helps


def main():
    df = build_states()
    train_series, _, test_series = split_by_series(df, seed=42)
    train_df = df[df["series_id"].isin(train_series)].copy()
    test_df = df[df["series_id"].isin(test_series)].copy()

    remain_strict = ["remain_strict_"]
    remain_all = ["remain_all_"]
    step4 = ["role_", "aliveload_", "util_", "ult_", "score_", "map", "patch_index"]
    variants = [
        ("baseline", []),
        ("baseline+remain_strict", remain_strict),
        ("baseline+remain_all", remain_all),
        ("baseline+remain_strict+step4", remain_strict + step4),
    ]

    y = test_df["label"].to_numpy()
    sid = test_df["series_id"].to_numpy()
    cols_b = BASELINE_FEATURES
    p_base = fit_predict(train_df, test_df, cols_b)
    post = test_df["planted"].to_numpy().astype(bool)

    lines = [
        "# T1 utility remaining ablation (step 4b)",
        "",
        f"Run {datetime.now().isoformat(timespec='seconds')} on held-out **test series** only "
        f"({test_df['series_id'].nunique()} series, {len(test_df):,} states).",
        "",
        "## Overall",
        "",
        "| Variant | Log loss | Brier | AUC | Calibration error (ECE) | Δ log loss vs baseline | 90% range |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]

    post_rows = []
    overall_rows = []
    for name, pref in variants:
        cols = cols_b if name == "baseline" else pick_columns(train_df, pref)
        p = p_base if name == "baseline" else fit_predict(train_df, test_df, cols)
        m = ev.evaluate_binary(y, p)
        d = {"difference": 0.0, "lo": 0.0, "hi": 0.0} if name == "baseline" else ev.paired_difference(y, p_base, p, sid, n=1000, seed=42)
        auc = "nan" if m["auc"] is None else f"{m['auc']:.4f}"
        lines.append(f"| {name} | {m['log_loss']:.4f} | {m['brier']:.4f} | {auc} | {m['ece']:.4f} | {d['difference']:+.4f} | [{d['lo']:+.4f}, {d['hi']:+.4f}] |")

        yp, pp = y[post], p[post]
        ybp, pbp = y[post], p_base[post]
        sidp = sid[post]
        mp = ev.evaluate_binary(yp, pp)
        dp = {"difference": 0.0, "lo": 0.0, "hi": 0.0} if name == "baseline" else ev.paired_difference(yp, pbp, pp, sidp, n=1000, seed=42)
        post_rows.append((name, mp, dp))
        overall_rows.append((name, m, d))

    lines += [
        "",
        "## Post-plant only",
        "",
        "| Variant | Log loss | Brier | AUC | Calibration error (ECE) | Δ log loss vs baseline | 90% range |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for name, m, d in post_rows:
        auc = "nan" if m["auc"] is None else f"{m['auc']:.4f}"
        lines.append(f"| {name} | {m['log_loss']:.4f} | {m['brier']:.4f} | {auc} | {m['ece']:.4f} | {d['difference']:+.4f} | [{d['lo']:+.4f}, {d['hi']:+.4f}] |")

    lines += [
        "",
        "## Verdict",
        "",
        "A variant helps only if its 90% log-loss difference range is entirely below 0 and its calibration error is at most the baseline's + 0.002.",
        "",
    ]
    for label, rows_ in (("Overall", overall_rows), ("Post-plant", post_rows)):
        base_ece = rows_[0][1]["ece"]
        winners = [n for n, m, d in rows_[1:] if d["hi"] < 0 and m["ece"] <= base_ece + 0.002]
        lines.append(f"- {label}: " + (f"helps beyond noise: {', '.join(winners)}." if winners
                                       else "no variant helps beyond noise."))
    lines.append("- The coach-facing check (defender win rate with a smoke left vs none) runs only if post-plant helps.")
    (ROOT / "docs" / "EVAL_T1_REMAINING.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
