# Step 3: bootstrapping without breaking accuracy or precision

Run 2026-11-19 with `python -m scripts.step3_bootstrap`. Aggregates only.

## 1. Are our ranges honest? (coverage of the series bootstrap)

Simulated data with a known true mean and the same structure as ours: rounds grouped in series that share an offset. A 90% range should contain the truth about 90% of the time. For contrast, a naive bootstrap resamples single rounds as if they were independent.

| Case | Series | Rounds per series | Series bootstrap coverage | Naive bootstrap coverage | Mean width |
|---|---|---|---|---|---|
| Big sample (a team across all maps) | 60 | 8 | 86% | 71% | 0.076 |
| Typical (one map, one side) | 15 | 8 | 88% | 74% | 0.148 |
| Small (few series) | 6 | 8 | 80% | 68% | 0.218 |

Resampling whole series is far closer to honest than treating rounds as independent, which claims 90% and delivers about 70%. But the series bootstrap still **undercovers**: 86–88% at normal sample sizes and 80% with few series. That's a known weakness of the simple percentile bootstrap. Next: a small-sample correction (or BCa intervals) to bring it to 90%, re-checked with this same simulation. Until then the UI's small-sample flag and "no range under 10" rule stay.

## 2. Bootstrap ensemble (20 models, each on a resample of the training series)

Held-out test series: 129 series, 48,584 states.

| Model | Log loss | Brier | AUC | Calibration error |
|---|---|---|---|---|
| Single gradient-boosted model | 0.3778 | 0.1237 | 0.9075 | 0.0052 |
| Ensemble mean | 0.3770 | 0.1233 | 0.9081 | 0.0050 |

Ensemble minus single, log loss: -0.0008 (90% range -0.0015 to -0.0002): **better beyond noise**.

### Does the spread say "I don't know" where it should?

Width of the 5th–95th percentile band across the ensemble, by how often that game state appears in training:

| State seen in training | Test states | Median band width (points of win chance) |
|---|---|---|
| 200 to 2,000 | 5,545 | 0.5 |
| 2,000 to 20,000 | 43,039 | 6.5 |

**Not as expected.** Rarely seen states got *narrower* bands, not wider. The likely reason is that rare states are lopsided (5v1, 1v4), where every model predicts close to 0% or 100%, so they can't disagree by many points. Measured in probability points, the spread mostly tracks how close the prediction is to 50%. Next: measure the spread on the log-odds scale, and compare states with similar predictions. Until then, the ensemble spread isn't used as an "uncertain" flag in the product.

