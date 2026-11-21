# Step 4c: fight-level utility evaluation

Run 2026-11-20T19:57:08 on held-out **test series** only (129 series, 43,431 fights with a winner).
All series: 289,430 fights with a winner; 92,004 more ended with no kill within 3 s (24.1% of all fights). The opener (first gun damage) wins 82.9% of fights with a winner.

Utility window 4 s before the fight, casts within 2,500 units of either fighter.

| Variant | Log loss | Brier | AUC | Calibration error (ECE) | Δ log loss vs baseline | 90% range |
|---|---:|---:|---:|---:|---:|---:|
| baseline (no utility features) | 0.4135 | 0.1299 | 0.6958 | 0.0024 | +0.0000 | [+0.0000, +0.0000] |
| full (with utility features) | 0.4122 | 0.1295 | 0.6995 | 0.0042 | -0.0013 | [-0.0018, -0.0008] |

## Sensitivity (utility window and radius)

| Window (s) | Radius | Δ log loss vs baseline | 90% range | Helps |
|---:|---:|---:|---:|:---:|
| 2 | 1,500 | -0.0013 | [-0.0017, -0.0009] | yes |
| 2 | 2,500 | -0.0014 | [-0.0018, -0.0009] | no |
| 2 | 4,000 | -0.0012 | [-0.0016, -0.0008] | no |
| 4 | 1,500 | -0.0014 | [-0.0018, -0.0009] | yes |
| 4 | 2,500 | -0.0013 | [-0.0018, -0.0008] | yes |
| 4 | 4,000 | -0.0014 | [-0.0019, -0.0009] | yes |
| 6 | 1,500 | -0.0012 | [-0.0017, -0.0008] | yes |
| 6 | 2,500 | -0.0014 | [-0.0020, -0.0009] | yes |
| 6 | 4,000 | -0.0016 | [-0.0021, -0.0010] | yes |

## Verdict

Utility helps only if the full model's 90% log-loss difference range is entirely below 0 and its calibration error is at most the baseline's + 0.002.

- Main setting (4 s, 2,500 units): utility features help beyond noise: **yes**.
- Sensitivity: helps in 7 of 9 window and radius settings.
- Runtime: 188 s.

## Coach-facing: flash or stun before the fight

League: flashed or stunned 0.847 [0.844, 0.850] (n=46,923); dry 0.826 [0.824, 0.827] (n=242,507).

- Teams with at least 200 fights each way: 65. Flashed rate above dry with ranges that don't overlap: 8; below: 0; ranges overlap: 57.
- Observed association, not cause: teams flash when they intend to fight. Ranges are 90% series-bootstrap t intervals (D-020).

The per-team table is written to `cache/v2/reports/fights_by_team.md` (git-ignored; derived from licensed data).
