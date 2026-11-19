# T1 evaluation: round win probability (step 1 baseline)

Run 2026-11-19 on the held-out **test series** (129 series, 48,584 states), with `engine/model/evaluate.py`. These are the numbers every later model has to beat (docs/ROADMAP_ML.md).

| Model | Log loss | Brier | AUC | Calibration error (ECE) |
|---|---|---|---|---|
| Logistic baseline (alive counts, planted) | 0.4098 | 0.1335 | 0.8912 | 0.0130 |
| Gradient boosting (current) | 0.3794 | 0.1239 | 0.9070 | 0.0050 |

**Is gradient boosting really better?** Log-loss difference -0.0303 (90% range over resampled series -0.0337 to -0.0269): **yes, beyond noise**.

## Reliability (gradient boosting)

| Predicted bin | Mean predicted | Actual | States |
|---|---|---|---|
| 0.0–0.1 | 0.031 | 0.029 | 8,430 |
| 0.1–0.2 | 0.146 | 0.155 | 3,939 |
| 0.2–0.3 | 0.252 | 0.258 | 3,567 |
| 0.3–0.4 | 0.344 | 0.336 | 3,583 |
| 0.4–0.5 | 0.455 | 0.443 | 2,648 |
| 0.5–0.6 | 0.552 | 0.550 | 3,770 |
| 0.6–0.7 | 0.651 | 0.644 | 2,944 |
| 0.7–0.8 | 0.750 | 0.745 | 4,056 |
| 0.8–0.9 | 0.854 | 0.857 | 4,335 |
| 0.9–1.0 | 0.971 | 0.975 | 11,312 |
