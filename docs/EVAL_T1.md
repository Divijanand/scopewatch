# T1 evaluation: round win probability (step 1 baseline)

Run 2026-11-19 on the held-out **test series** (129 series, 48,584 states), with `engine/model/evaluate.py`. These are the numbers every later model has to beat (docs/ROADMAP_ML.md).

| Model | Log loss | Brier | AUC | Calibration error (ECE) |
|---|---|---|---|---|
| Logistic baseline (alive counts, planted) | 0.4092 | 0.1333 | 0.8916 | 0.0132 |
| Gradient boosting (current) | 0.3778 | 0.1237 | 0.9075 | 0.0052 |

**Is gradient boosting really better?** Log-loss difference -0.0313 (90% range over resampled series -0.0348 to -0.0277): **yes, beyond noise**.

## Reliability (gradient boosting)

| Predicted bin | Mean predicted | Actual | States |
|---|---|---|---|
| 0.0–0.1 | 0.029 | 0.028 | 8,447 |
| 0.1–0.2 | 0.148 | 0.160 | 3,982 |
| 0.2–0.3 | 0.252 | 0.252 | 3,510 |
| 0.3–0.4 | 0.343 | 0.339 | 3,479 |
| 0.4–0.5 | 0.454 | 0.438 | 2,710 |
| 0.5–0.6 | 0.551 | 0.551 | 3,833 |
| 0.6–0.7 | 0.651 | 0.631 | 2,885 |
| 0.7–0.8 | 0.750 | 0.747 | 4,047 |
| 0.8–0.9 | 0.854 | 0.861 | 4,402 |
| 0.9–1.0 | 0.973 | 0.976 | 11,289 |
