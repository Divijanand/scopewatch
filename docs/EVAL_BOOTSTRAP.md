# Step 3: bootstrapping without breaking accuracy or precision

Run 2026-11-19 with `python -m scripts.step3_bootstrap`. Aggregates only.

## 1. Are our ranges honest? (coverage of the series bootstrap)

Simulated data with a known true mean and the same structure as ours: rounds grouped in series that share an offset. A 90% range should contain the truth about 90% of the time. For contrast, a naive bootstrap resamples single rounds as if they were independent.

| Case | Series | Rounds per series | Ours: t interval | Percentile (old default) | Naive (rounds as independent) | Our mean width |
|---|---|---|---|---|---|---|
| Big sample (a team across all maps) | 60 | 8 | 88% | 87% | 70% | 0.078 |
| Typical (one map, one side) | 15 | 8 | 91% | 88% | 70% | 0.165 |
| Small (few series) | 6 | 8 | 89% | 79% | 68% | 0.287 |
| Very small | 4 | 8 | 90% | 75% | 69% | 0.396 |

Our t interval (t with G−1 degrees of freedom × bootstrap standard error × √(G/(G−1))) stays at **88–91%** from 4 to 60 series. The plain percentile interval we used before falls to 79% at 6 series and 75% at 4. Treating rounds as independent claims 90% and delivers about 70%. With 600 simulations per row, each coverage figure is within about ±1.3 points. **Follow-up (a) closed:** every range in Scopewatch now uses the t interval (D-020).

## 2. Bootstrap ensemble (20 models, each on a resample of the training series)

Held-out test series: 129 series, 48,584 states.

| Model | Log loss | Brier | AUC | Calibration error |
|---|---|---|---|---|
| Single gradient-boosted model | 0.3778 | 0.1237 | 0.9075 | 0.0052 |
| Ensemble mean | 0.3770 | 0.1233 | 0.9081 | 0.0050 |

Ensemble minus single, log loss: -0.0008 (90% range -0.0015 to -0.0002): **better beyond noise**.

### Does the spread say "I don't know" where it should?

Disagreement between the 20 models (standard deviation of their log-odds), for game states that are **rare** in training (the rarest 10% of test states: seen 1,823 times or fewer) against **common** ones, compared within the same band of predicted win chance:

| Predicted win chance | Rare: states | Rare: median spread | Common: states | Common: median spread | Rare / common |
|---|---|---|---|---|---|
| 0-10% | 2,338 | 0.237 | 6,107 | 0.198 | 1.20x |
| 10-30% | 289 | 0.211 | 7,319 | 0.170 | 1.25x |
| 30-70% | 341 | 0.199 | 12,513 | 0.165 | 1.20x |
| 70-90% | 318 | 0.186 | 8,076 | 0.172 | 1.08x |
| 90-100% | 1,843 | 0.209 | 9,440 | 0.193 | 1.08x |

**Right direction, weak signal.** In every band of predicted win chance the models disagree more about rare states, by 1.08–1.25×. But the effect is small, and "rare" here still means up to 1,823 training states, because the very thinnest states barely appear in the test series. **Follow-up (b) closed:** the ensemble spread is not used as an "uncertain" flag in the product. Thin states are flagged by their training count instead (DATA_AUDIT.md).

