"""Step 5 stress tests for T1 win probability.

    python -m scripts.stress_t1
"""
from __future__ import annotations

from datetime import datetime

import pandas as pd

from engine.config import ROOT
from engine.model.winprob import FEATURES, get_training_data, load_model, predict_wp, split_by_series


def _state(a, d, planted=False, sec_buy=40.0, sec_plant=0.0):
    return dict(
        seconds_since_buy_phase_end=float(sec_buy),
        planted=bool(planted),
        seconds_since_plant=float(sec_plant),
        attackers_alive=int(a),
        defenders_alive=int(d),
        att_loadout_value=20000.0,
        def_loadout_value=20000.0,
        att_has_op=False,
        def_has_op=False,
    )


def _predict(model, rows):
    df = pd.DataFrame(rows)
    for c in FEATURES:
        if c not in df.columns:
            df[c] = 0
    return predict_wp(model, df[FEATURES])


def main():
    model = load_model()
    if model is None:
        raise RuntimeError("Production model not found at cache/v2/models/winprob_hgb.pkl")

    lines = [
        "# Step 5: stress tests for T1",
        "",
        f"Run {datetime.now().isoformat(timespec='seconds')}.",
        "",
        "| Check | Pass | Details |",
        "|---|---|---|",
    ]

    # More attackers alive is never worse (tolerance 0.02 violations).
    violations = []
    for planted in (False, True):
        for d in range(1, 6):
            probs = _predict(model, [_state(a, d, planted=planted, sec_plant=10.0 if planted else 0.0) for a in range(1, 6)])
            for i in range(1, len(probs)):
                if probs[i] + 0.02 < probs[i - 1]:
                    violations.append((planted, d, i, float(probs[i - 1]), float(probs[i])))
    lines.append(f"| More attackers alive never worse | {'yes' if not violations else 'no'} | violations={len(violations)} |")
    details = [f"- More attackers: {'planted' if pl else 'not planted'}, {d} defenders, {i}->{i + 1} attackers alive: "
               f"{lo:.3f} -> {hi:.3f}" for pl, d, i, lo, hi in violations]

    # More defenders alive is never better for attackers.
    violations = []
    for planted in (False, True):
        for a in range(1, 6):
            probs = _predict(model, [_state(a, d, planted=planted, sec_plant=10.0 if planted else 0.0) for d in range(1, 6)])
            for i in range(1, len(probs)):
                if probs[i] > probs[i - 1] + 0.02:
                    violations.append((planted, a, i, float(probs[i - 1]), float(probs[i])))
    lines.append(f"| More defenders alive never better for attackers | {'yes' if not violations else 'no'} | violations={len(violations)} |")
    details += [f"- More defenders: {'planted' if pl else 'not planted'}, {a} attackers, {i}->{i + 1} defenders alive: "
                f"{lo:.3f} -> {hi:.3f}" for pl, a, i, lo, hi in violations]

    # Post-plant clock: 40s after plant >= 5s after plant in 1v1.
    p5, p40 = _predict(model, [_state(1, 1, planted=True, sec_buy=30.0, sec_plant=5.0),
                               _state(1, 1, planted=True, sec_buy=65.0, sec_plant=40.0)])
    lines.append(f"| Post-plant clock monotonic (1v1) | {'yes' if p40 >= p5 else 'no'} | p5={p5:.3f}, p40={p40:.3f} |")

    # Extremes.
    p_win, p_lose = _predict(model, [_state(5, 0, planted=False), _state(0, 5, planted=False)])
    lines.append(f"| Extreme 5v0 > 0.95 | {'yes' if p_win > 0.95 else 'no'} | p={p_win:.3f} |")
    lines.append(f"| Extreme 0v5 no plant < 0.05 | {'yes' if p_lose < 0.05 else 'no'} | p={p_lose:.3f} |")

    if details:
        lines += ["", "## Violations larger than 0.02", "", *details]

    # Rare state: print only, with how many training states look like it.
    rare = _predict(model, [_state(1, 5, planted=True, sec_buy=80.0, sec_plant=42.0)])[0]
    states = get_training_data()
    train_series, _, _ = split_by_series(states, seed=42)
    tr = states[states["series_id"].isin(train_series)]
    near = tr[tr["planted"].astype(bool) & tr["attackers_alive"].between(0, 2) & tr["defenders_alive"].between(4, 5)]
    late = near[near["seconds_since_plant"].between(37.0, 45.0)]
    lines += [
        "",
        "## Rare state (no pass or fail)",
        "",
        f"- 1 attacker against 5 defenders, spike down, 3 s to detonation (42 s after the plant): "
        f"predicted attacker win = {rare:.3f}.",
        f"- Training states within one alive player of it (0-2 attackers, 4-5 defenders, planted): {len(near):,}; "
        f"of those, {len(late):,} are 37-45 s after the plant, and the attackers won {late['label'].mean():.1%} of them."
        if len(late) else "- No training states within one alive player of it late in the post-plant.",
        "- Defenders this far behind on time must defuse within 3 s, which takes 7 s, so the round is the attackers' "
        "unless the defuse started earlier (a half defuse). The state features don't know about a defuse in progress.",
    ]

    out = ROOT / "docs" / "STRESS_T1.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:14]))


if __name__ == "__main__":
    main()
