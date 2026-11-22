# Step 5: synthetic data weighting experiment

Run 2026-11-21T22:14:58 on held-out test series only (129 series, 48,584 states).

## Simulator realism vs real training states

| Metric | Synthetic | Real |
|---|---:|---:|
| attacker_win_rate | 0.4973 | 0.5169 |
| plant_rate | 0.6169 | 0.6844 |
| kills_per_round | 6.6397 | 6.9234 |
| states_per_round | 7.2566 | 7.6267 |
| share_1v1 | 0.0203 | 0.0222 |
| share_1v2 | 0.0266 | 0.0279 |
| share_2v1 | 0.0276 | 0.0288 |

## Held-out results

| Synthetic weight | Log loss | Brier | AUC | Calibration error (ECE) | Δ log loss vs w=0 | 90% range |
|---|---:|---:|---:|---:|---:|---:|
| 0 | 0.3773 | 0.1234 | 0.9078 | 0.0053 | +0.0000 | [+0.0000, +0.0000] |
| 0.1 | 0.3782 | 0.1237 | 0.9075 | 0.0060 | +0.0009 | [+0.0001, +0.0017] |
| 0.25 | 0.3785 | 0.1237 | 0.9075 | 0.0077 | +0.0012 | [+0.0003, +0.0022] |
| 0.5 | 0.3800 | 0.1241 | 0.9070 | 0.0100 | +0.0027 | [+0.0014, +0.0039] |
| synth_only | 0.3972 | 0.1299 | 0.8983 | 0.0165 | +0.0198 | [+0.0169, +0.0229] |

## Verdict

- **Real data alone is best**: every synthetic weight is worse. Synthetic data stays a testing tool.
- Rule: a weight helps only if its 90% log-loss range is entirely below 0 and its calibration error is at most w = 0's + 0.002.
- w = 0 is checked to reproduce the production model's test predictions exactly.
- Synthetic states: 228,779 from one simulator fit on train series only (seed 0); the test series never reach the simulator.
