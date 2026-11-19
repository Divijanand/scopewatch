# ML taxonomy: what we predict, from what, how we measure it, and what we can't know

The reference for every model on the `deep-learning` branch. Numbers are corpus-wide aggregates measured on 2026-11-19 (dataset `496fa7f`, parser 2.0.1); no row-level data is in this repo.

## 1. Prediction tasks

| ID | Task | When it's asked | Target | Type | Use in the product |
|---|---|---|---|---|---|
| T1 | **Round win probability** | after every kill and plant | attackers win the round | binary, calibrated probability | Operator value (WPA), ult windows, execute value |
| T2 | **Next-round site** | buy-phase end, attack | site planted (A/B/C) or no plant | multiclass | "what will they do this round" |
| T3 | **Operator buy** | buy-phase end | team holds an Operator/Outlaw | binary | anti-strat prep |
| T4 | **Round win at buy end** | buy-phase end | round winner | binary | economy decisions, the baseline T1 starts from |
| T5 | **First-contact location** | buy-phase end | callout of the first fight | multiclass (sparse) | defensive setups, predictability |

T1 exists (gradient boosting, `engine/model/winprob.py`). T2–T5 are new. T4 is T1 at t=0, so it shares data and evaluation.

## 2. Feature families and how complete they are

| Family | Features | Available | Notes |
|---|---|---|---|
| **Clock** | seconds since buy end, phase, seconds since plant | all rounds | the round clock is our own definition (D-001) |
| **Alive state** | attackers alive, defenders alive, **alive by role** (duelist, initiator, controller, sentinel) | all kills (297,113) | roles come from the agent |
| **Economy** | team loadout, **per-player money and loadout**, eco/half/full | loadout known in **100%** of 84,980 team rounds (eco 12,082, half 9,674, full 63,224) | possession is the inventory at buy end; there are no purchase events |
| **Weapons** | Operator/Outlaw holders alive, sniper kills | 18,091 team rounds with one Operator, 320 with two | kill weapon known for **99.96%** (10,853 filled from the matching hit, D-016) |
| **Team comp** | agent set, roles, comp × map | agent known for **100%** of 425,288 player rounds (after dropping 1,228 phantom entries with no agent, D-021); **831** distinct comps | very sparse per comp: use role counts and agent embeddings, not one-hot comps |
| **Utility used** | casts so far this round by kind (smoke, flash, stun, recon, setup, movement), ults used | **1,509,064** casts; **99.9%** have a usable position; 37,422 ult casts | 12.6% of casts come from about 1 Hz sampling; landing spots only for damaging utility (D-015) |
| **Spatial** | positions by callout zone, map control, distance to site | both positions on **100%** of kills; callout named for **99.6%** | positions only at events, not continuous movement |
| **Objective** | planted, plant site, time since plant | 28,978 plants (68.2% of rounds), 8,462 defuses, 3,689 detonations | |
| **Context** | map, side, score, round number, patch, event, team identity | all rounds; **32 patches**, 39 events | team identity: pool small teams toward the league (hierarchical) |

**Class balance (T1):** attackers win 21,911 of 42,490 rounds (51.6%), so no reweighting is needed.

## 3. How we measure: accuracy and precision in our sense

A probability model is judged on probabilities, not on hits. "70% and wrong 3 times in 10" is a correct 70%.

| Measure | Question it answers | Applies to | Code (`engine/model/evaluate.py`) |
|---|---|---|---|
| **Log loss** | How surprised the model is by what happened (lower is better) | T1–T5 | `log_loss` |
| **Brier score** | Mean squared error of the probability | T1, T3, T4 | `brier` |
| **Calibration error (ECE)** and **reliability table** | When it says 70%, does it happen 70% of the time? | T1–T5 | `calibration` |
| **AUC** | Does it rank wins above losses? | T1, T3, T4 | `auc` |
| **Top-1 accuracy vs baseline** | Is the best guess right more often than "always their most common choice"? | T2, T5 | `top1`, `baseline_most_common` |
| **Paired bootstrap of the difference** | Is model B *really* better than A, or is it noise? | every comparison | `paired_difference` |
| **Interval coverage** | Do our "likely" ranges contain the truth as often as they claim? (accuracy of the ranges) | every range in the UI | `coverage` |
| **Interval width** | How tight the ranges are (precision of the ranges) | every range in the UI | `coverage` |

**The rules:**
- Every number comes from **series the model never saw**. Rounds in a series are linked, so we split, bootstrap and cross-validate by **series**, never by round.
- A model **ships only if** the paired-bootstrap 90% range of the log-loss difference against the current model is entirely better, **and** its calibration error is no worse.
- Every result is reported **next to its baseline**: the logistic model for T1, "most common choice" for T2 and T5, the league rate for T3.

## 4. Known limits (what no model here can learn)

| Limit | Why | What we do about it |
|---|---|---|
| **Positions only at events** | GRID records positions on kills, damage and casts, not continuous movement | spatial features come from event positions; no "map control over time" |
| **No utility landing spot** (except damage) | the feed records the cast, not where it lands | landing only from damage records; everything else is "cast from" |
| **No ult points** | the feed doesn't record ult charge | "ult available" is unknown; we use "ult used so far" |
| **No comms, crosshair or sound** | not in any feed | out of scope; the VOD covers it |
| **Patch drift** | 32 patches; agents get buffed and nerfed (Gekko) | patch as a feature, recent-weighted training, a drift check by patch |
| **Sparse comps and teams** | 831 comps; some teams have few maps | roles and embeddings; pool small teams toward the league |
| **Selection effects** | good teams pick the meta; teams ult when they're about to fight | compare against the league and within teams; association, never cause |
| **About 1 Hz sampling** in part of the supplement | VCT Americas 2025 | flagged per cast; position features weighted or dropped for it |
| **Survivorship** | e.g. "kept the Operator → won" | measure value at the decision (WPA), not after the outcome |

## 5. Data splits

- **Train / validation / test = 70 / 15 / 15 by series**, fixed seed (`split_by_series`). The test set is touched once per candidate model, never during tuning.
- **Patch-forward check:** train on older patches, test on the newest. This measures what drift costs.
- **The bootstrap resamples whole series from train only** (ensembles), or from test (ranges on the test measures). It never moves series between splits.

## 6. Synthetic data policy

Synthetic data **tests** the pipeline (every test in `tests/` is synthetic). As **training** data it's an experiment, not a default: a simulator's rules become the model's knowledge, and any weight shifts calibration toward the simulator. If it's tried, the synthetic weight is a setting (0, 0.1, 0.25, 0.5) chosen by **real held-out** log loss and calibration, and the result is reported even if the answer is 0. See ROADMAP_ML.md, step 5.
