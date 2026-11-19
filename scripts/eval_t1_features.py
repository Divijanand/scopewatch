"""Step 4 feature-family ablation for T1 win probability.

    python -m scripts.eval_t1_features
"""
from __future__ import annotations

from datetime import datetime
import pickle
import time

from sklearn.ensemble import HistGradientBoostingClassifier

from engine.config import ROOT, V2_DIR
from engine.model import evaluate as ev
from engine.model.features import build_states
from engine.model.winprob import FEATURES as BASELINE_FEATURES, split_by_series

MODEL_DIR = V2_DIR / "models"

FAMILIES = {
    "role": ["role_"],
    "aliveload": ["aliveload_"],
    "util": ["util_"],
    "ult": ["ult_"],
    "score": ["score_"],
    "map": ["map"],
    "patch": ["patch_index"],
}


def pick_columns(df, include: list[str]) -> list[str]:
    cols = []
    for c in df.columns:
        if c in ("series_id", "round_key", "label"):
            continue
        if c in BASELINE_FEATURES:
            cols.append(c)
            continue
        if any(c == p or c.startswith(p) for p in include):
            cols.append(c)
    return cols


def fit_predict(train_df, test_df, cols):
    model = HistGradientBoostingClassifier(random_state=42, categorical_features="from_dtype")
    model.fit(train_df[cols], train_df["label"])
    return model.predict_proba(test_df[cols])[:, 1], model


def evaluate_variant(name, include, train_df, test_df, y, p_base):
    cols = pick_columns(train_df, include)
    p, model = fit_predict(train_df, test_df, cols)
    m = ev.evaluate_binary(y, p)
    diff = ev.paired_difference(y, p_base, p, test_df["series_id"].to_numpy(), n=1000, seed=42)
    return dict(name=name, cols=cols, model=model, metrics=m, diff=diff)


def main():
    t0 = time.perf_counter()
    df = build_states()
    train_series, _, test_series = split_by_series(df, seed=42)
    train_df = df[df["series_id"].isin(train_series)].copy()
    test_df = df[df["series_id"].isin(test_series)].copy()

    y = test_df["label"].to_numpy()
    p_base, _ = fit_predict(train_df, test_df, BASELINE_FEATURES)
    base_metrics = ev.evaluate_binary(y, p_base)

    variants = []
    variants.append(dict(name="baseline", cols=BASELINE_FEATURES, model=None,
                         metrics=base_metrics, diff=dict(difference=0.0, lo=0.0, hi=0.0)))
    for fam in FAMILIES:
        variants.append(evaluate_variant(f"baseline+{fam}", FAMILIES[fam], train_df, test_df, y, p_base))

    all_prefixes = [p for prefixes in FAMILIES.values() for p in prefixes]
    full = evaluate_variant("all_families", all_prefixes, train_df, test_df, y, p_base)
    variants.append(full)
    for fam in FAMILIES:
        kept = [p for k, v in FAMILIES.items() if k != fam for p in v]
        variants.append(evaluate_variant(f"all_minus_{fam}", kept, train_df, test_df, y, p_base))

    baseline_ece = base_metrics["ece"]
    ships = full["diff"]["hi"] < 0 and full["metrics"]["ece"] <= baseline_ece + 0.002
    runtime_s = time.perf_counter() - t0

    lines = [
        "# T1 feature-family ablation (step 4)",
        "",
        f"Run {datetime.now().isoformat(timespec='seconds')} on held-out **test series** only "
        f"({test_df['series_id'].nunique()} series, {len(test_df):,} states).",
        "",
        "| Variant | Log loss | Brier | AUC | Calibration error (ECE) | Δ log loss vs baseline | 90% range |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for v in variants:
        m, d = v["metrics"], v["diff"]
        auc = "nan" if m["auc"] is None else f"{m['auc']:.4f}"
        lines.append(
            f"| {v['name']} | {m['log_loss']:.4f} | {m['brier']:.4f} | {auc} | {m['ece']:.4f} | "
            f"{d['difference']:+.4f} | [{d['lo']:+.4f}, {d['hi']:+.4f}] |"
        )

    lines += [
        "",
        "## Verdict",
        "",
        f"- Full model ships: **{'yes' if ships else 'no'}**.",
        "- Rule: 90% log-loss difference range vs baseline must be entirely below 0 and "
        "ECE must be at most baseline + 0.002.",
        f"- Runtime: {runtime_s:.1f} seconds.",
    ]
    out = ROOT / "docs" / "EVAL_T1_FEATURES.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")

    if ships:
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        with (MODEL_DIR / "winprob_v2.pkl").open("wb") as f:
            pickle.dump(full["model"], f)

    print("\n".join(lines[:14]))


if __name__ == "__main__":
    main()
