"""Step 4c: evaluate fight-level utility features.

Run with:
    python -m scripts.eval_fights
"""
from __future__ import annotations

import time
from datetime import datetime

import duckdb
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier

from engine.config import DB_PATH, ROOT
from engine.metrics.core import bootstrap_mean
from engine.model import evaluate as ev
from engine.model.fights import add_utility, fight_core
from engine.model.winprob import split_by_series

CATEGORICAL = ["phase", "opener_weapon", "other_weapon", "opener_side", "map", "callout"]
BASE_COLS = [
    "planted", "seconds_since_buy_phase_end",
    "opener_side_alive", "other_side_alive",
    "opener_side_econ", "other_side_econ",
    "opener_has_op", "other_has_op",
] + CATEGORICAL
UTIL_COLS = [
    "util_opener_flash_stun", "util_opener_smoke", "util_opener_recon", "util_opener_ult",
    "util_other_flash_stun", "util_other_smoke", "util_other_recon", "util_other_ult",
    "dmg_util_opener", "dmg_util_other",
]
WINDOWS = (2.0, 4.0, 6.0)
RADII = (1500.0, 2500.0, 4000.0)
MIN_TEAM_FIGHTS = 200


def fit_predict(train_df, test_df, cols):
    model = HistGradientBoostingClassifier(random_state=42, categorical_features="from_dtype")
    model.fit(train_df[cols], train_df["label"])
    return model.predict_proba(test_df[cols])[:, 1]


def _prepare(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for c in CATEGORICAL:
        df[c] = df[c].fillna("unknown").astype(str).astype("category")
    return df


def compare(fights: pd.DataFrame, train_series, test_series):
    train_df = fights[fights["series_id"].isin(train_series)]
    test_df = fights[fights["series_id"].isin(test_series)]
    y = test_df["label"].to_numpy()
    p_base = fit_predict(train_df, test_df, BASE_COLS)
    p_full = fit_predict(train_df, test_df, BASE_COLS + UTIL_COLS)
    m_base = ev.evaluate_binary(y, p_base)
    m_full = ev.evaluate_binary(y, p_full)
    diff = ev.paired_difference(y, p_base, p_full, test_df["series_id"].to_numpy(), n=1000, seed=42)
    helps = diff["hi"] < 0 and m_full["ece"] <= m_base["ece"] + 0.002
    return test_df, m_base, m_full, diff, helps


def _rate(df):
    lo, hi = bootstrap_mean(df["label"].tolist(), df["series_id"].tolist(), n=1000, seed=42)
    return f"{df['label'].mean():.3f} [{lo:.3f}, {hi:.3f}]"


def team_names() -> dict[str, str]:
    con = duckdb.connect(str(DB_PATH), read_only=True)
    rows = con.execute("""
        SELECT team1_id, team1_name FROM games UNION SELECT team2_id, team2_name FROM games
    """).fetchall()
    con.close()
    return {str(i): n for i, n in rows if i is not None and n}


def _interval(df):
    lo, hi = bootstrap_mean(df["label"].tolist(), df["series_id"].tolist(), n=1000, seed=42)
    return df["label"].mean(), lo, hi


def coach_table(fights: pd.DataFrame) -> tuple[list[str], list[str]]:
    """Per team, the opener's win rate after their team flashed or stunned near the fight vs dry fights.
    All fights (not only test series): this is a descriptive table, not a model score.

    Returns (per-team lines, private) and (league-level summary lines, safe for docs/)."""
    flashed = fights["util_opener_flash_stun"] > 0
    league_f, league_d = fights[flashed], fights[~flashed]
    league = f"League: flashed or stunned {_rate(league_f)} (n={len(league_f):,}); dry {_rate(league_d)} (n={len(league_d):,})."
    team_lines = [league, "", "| Team | Flashed or stunned before | n | Dry | n |", "|---|---:|---:|---:|---:|"]
    names = team_names()
    counts = {"higher": 0, "lower": 0, "overlap": 0}
    for team, g in fights.groupby("opener_team"):
        gf, gd = g[g["util_opener_flash_stun"] > 0], g[g["util_opener_flash_stun"] == 0]
        if len(gf) < MIN_TEAM_FIGHTS or len(gd) < MIN_TEAM_FIGHTS:
            continue
        mf, lof, hif = _interval(gf)
        md, lod, hid = _interval(gd)
        counts["higher" if lof > hid else "lower" if hif < lod else "overlap"] += 1
        team_lines.append(f"| {names.get(str(team), team)} ({team}) | {mf:.3f} [{lof:.3f}, {hif:.3f}] | {len(gf):,} "
                          f"| {md:.3f} [{lod:.3f}, {hid:.3f}] | {len(gd):,} |")
    n_teams = sum(counts.values())
    note = "Observed association, not cause: teams flash when they intend to fight. Ranges are 90% series-bootstrap t intervals (D-020)."
    summary = [
        league,
        "",
        f"- Teams with at least {MIN_TEAM_FIGHTS} fights each way: {n_teams}. Flashed rate above dry with ranges that "
        f"don't overlap: {counts['higher']}; below: {counts['lower']}; ranges overlap: {counts['overlap']}.",
        f"- {note}",
    ]
    return team_lines + ["", note], summary


def main():
    started = time.time()
    con = duckdb.connect(str(DB_PATH), read_only=True)
    core = fight_core(con)
    if core.empty:
        raise RuntimeError("No fight rows built; cannot evaluate step 4c.")
    train_series, _, test_series = split_by_series(core, seed=42)

    main_fights = _prepare(add_utility(core, con, window_s=4.0, radius=2500.0))
    test_df, m_base, m_full, diff, helped = compare(main_fights, train_series, test_series)

    def auc(m):
        return "nan" if m["auc"] is None else f"{m['auc']:.4f}"

    lines = [
        "# Step 4c: fight-level utility evaluation",
        "",
        f"Run {datetime.now().isoformat(timespec='seconds')} on held-out **test series** only "
        f"({test_df['series_id'].nunique()} series, {len(test_df):,} fights with a winner).",
        f"All series: {len(core):,} fights with a winner; {core.attrs['no_winner_count']:,} more ended with no kill "
        f"within 3 s ({core.attrs['no_winner_share']:.1%} of all fights). The opener (first gun damage) wins "
        f"{core['label'].mean():.1%} of fights with a winner.",
        "",
        "Utility window 4 s before the fight, casts within 2,500 units of either fighter.",
        "",
        "| Variant | Log loss | Brier | AUC | Calibration error (ECE) | Δ log loss vs baseline | 90% range |",
        "|---|---:|---:|---:|---:|---:|---:|",
        f"| baseline (no utility features) | {m_base['log_loss']:.4f} | {m_base['brier']:.4f} | {auc(m_base)} | {m_base['ece']:.4f} | +0.0000 | [+0.0000, +0.0000] |",
        f"| full (with utility features) | {m_full['log_loss']:.4f} | {m_full['brier']:.4f} | {auc(m_full)} | {m_full['ece']:.4f} | {diff['difference']:+.4f} | [{diff['lo']:+.4f}, {diff['hi']:+.4f}] |",
        "",
        "## Sensitivity (utility window and radius)",
        "",
        "| Window (s) | Radius | Δ log loss vs baseline | 90% range | Helps |",
        "|---:|---:|---:|---:|:---:|",
    ]
    grid_helps = 0
    for w in WINDOWS:
        for r in RADII:
            fights = _prepare(add_utility(core, con, window_s=w, radius=r))
            _, _, _, d, h = compare(fights, train_series, test_series)
            grid_helps += int(h)
            lines.append(f"| {w:.0f} | {r:,.0f} | {d['difference']:+.4f} | [{d['lo']:+.4f}, {d['hi']:+.4f}] | {'yes' if h else 'no'} |")
    con.close()

    lines += [
        "",
        "## Verdict",
        "",
        "Utility helps only if the full model's 90% log-loss difference range is entirely below 0 and its calibration error is at most the baseline's + 0.002.",
        "",
        f"- Main setting (4 s, 2,500 units): utility features help beyond noise: **{'yes' if helped else 'no'}**.",
        f"- Sensitivity: helps in {grid_helps} of {len(WINDOWS) * len(RADII)} window and radius settings.",
        f"- Runtime: {time.time() - started:.0f} s.",
    ]
    if helped:
        team_lines, summary = coach_table(main_fights)
        # Per-team rates are derived from GRID data: they stay in cache/ (git-ignored), never in docs/.
        private = ROOT / "cache" / "v2" / "reports" / "fights_by_team.md"
        private.parent.mkdir(parents=True, exist_ok=True)
        private.write_text("# Fights by team (private, not for the repo)\n\n" + "\n".join(team_lines) + "\n", encoding="utf-8")
        lines += ["", "## Coach-facing: flash or stun before the fight", ""] + summary + [
            "",
            "The per-team table is written to `cache/v2/reports/fights_by_team.md` (git-ignored; derived from licensed data).",
        ]
    else:
        lines += ["- The coach-facing table runs only if utility helps."]

    out = ROOT / "docs" / "EVAL_FIGHTS.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {out}: utility helps = {'yes' if helped else 'no'}, {grid_helps}/9 settings")


if __name__ == "__main__":
    main()
