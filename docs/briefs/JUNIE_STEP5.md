# Junie brief: step 5, synthetic data as a controlled experiment

**Model:** GPT-5.3-codex. **Branch:** `deep-learning` (`git pull` first). Follow `AGENTS.md`: never commit data or model files, fixtures synthetic only. Read `docs/ROADMAP_ML.md` step 5 and `docs/ML_TAXONOMY.md` §6 first.

## Why
Our position is that synthetic data is for **testing**, and that **training** on it is an experiment: a simulator's rules become what the model learns. Step 5 runs that experiment honestly. We train the round win model (T1, the production features in `engine/model/winprob.FEATURES`) on real data plus synthetic rounds at a few weights, and judge **only on real held-out series**. We publish the curve even if the best weight is 0. We also use the simulator's job as a test tool: stress-testing the trained model on situations it rarely sees.

## 1. A simple round simulator (`engine/model/simulate.py`)
- `fit_simulator(states: DataFrame) -> Simulator` fits every rate from the states you pass it. **Only train-series states are ever passed** (from `winprob.get_training_data()` and `split_by_series(seed=42)`), so the test set can't leak into synthetic data. Make that impossible to get wrong: the experiment script does the split, and the simulator never touches the store.
- What it estimates, all from those states, with add-one smoothing so no rate is exactly 0 or 1:
  - **who gets the next kill**, by (attackers alive, defenders alive, planted, economy bucket). For the economy bucket, compare team loadouts: attackers ahead by > 5,000, behind by > 5,000, or even;
  - **time to the next kill**: an exponential with a rate per (attackers alive, defenders alive, planted);
  - **plant before the next kill**: a probability per (attackers alive, defenders alive), with plant times drawn from the real plant-time distribution;
  - **defuse** once attackers are all dead after a plant: the probability by defenders alive and time left. Fit it from post-plant rounds that ended with the attackers dead.
- **Game rules are constants with a comment, checked on our data (2026-11-20):**
  - the round lasts 100 s before a plant (the 99.9th percentile of pre-plant kill times is 99.96 s), and time running out with no plant means defenders win;
  - the spike detonates 45.0 s after the plant (every detonation in the data is 45.0–45.02 s), and detonation means attackers win;
  - a side with nobody alive loses, except after a plant, where the defuse rule decides.
- Round starts (loadouts, Operator holders) are drawn from real **train** round starts, as a whole row, so they stay realistic together.
- `simulate(sim, n_rounds, seed) -> DataFrame` returns states with exactly `winprob.FEATURES` plus `label`, `series_id` (`synth-<k>`) and `round_key`. A row is written after every kill and plant, the same as `get_training_data()`. It's deterministic for a given seed.
- **Check it against reality:** `compare_to_real(sim_states, real_states)` returns attacker win rate, plant rate, kills per round, and the share of 1v1/1v2/2v1 states, for both. The experiment reports this table first. If the simulator is far off, that's the explanation for any result.

## 2. The experiment (`scripts/eval_synthetic.py` writes `docs/EVAL_SYNTHETIC.md`)
Using only `engine/model/evaluate.py`, the same series split, test series only.
- Synthetic rounds: as many synthetic **states** as real training states, from one fitted simulator (seed 0).
- For each synthetic weight `w` in {0, 0.1, 0.25, 0.5}: train `HistGradientBoostingClassifier(random_state=42)` on real train states (weight 1) plus synthetic states (weight `w`, via `sample_weight`). `w = 0` must reproduce the production model's test numbers. Assert it in the script.
- Also train on synthetic states **only**, as a reference row, so we see how far the simulator alone gets.
- Report log loss, Brier, AUC and calibration error for each, and the paired-bootstrap log-loss difference against `w = 0` with its 90% range. A weight "helps" only by the usual rule: the range is entirely below 0, and calibration error is at most `w = 0`'s + 0.002.
- **Verdict**, written by the script from the numbers: the best weight, and whether it beats 0 beyond noise. If it doesn't, say so plainly: real data alone is best, and synthetic data stays a testing tool.

## 3. Stress tests (`scripts/stress_t1.py` writes `docs/STRESS_T1.md`)
Hand-built states with expectations a coach would agree with. Run them against the production model (`cache/v2/models/winprob_hgb.pkl`, loaded with `winprob.load_model()`) and against the best synthetic-weight model if one helped. For each check, report pass or fail with the predicted numbers:
- **More attackers alive is never worse:** for each defender count and plant status, P(attackers win) doesn't fall as attackers alive goes 1→5. Report any violation larger than 0.02.
- **The same for defenders:** P(attackers win) doesn't rise as defenders alive goes 1→5.
- **Post-plant clock:** with the spike down and 1 attacker against 1 defender, P(attackers win) at 40 s after the plant is at least P at 5 s after the plant.
- **Extremes:** 5 attackers alive, 0 defenders: P > 0.95. 0 attackers alive with no plant: P < 0.05.
- **Rare states:** 1 attacker against 5 defenders post-plant with 3 s to detonation (42 s after the plant): print the prediction and the number of training states within one alive player of it, so we see how thin it is. No pass or fail here.

## 4. Tests (`tests/test_simulate.py`, synthetic)
- The rules: a side with nobody alive and no plant loses; detonation at 45 s gives an attacker win; a timeout with no plant gives a defender win; alive counts never go below 0 or above 5.
- Same seed, same output; a different seed, different output.
- `fit_simulator` on a tiny hand-built states table gives the expected smoothed next-kill rate.
- The experiment's weighting puts weight `w` on synthetic rows and 1 on real ones. Test the helper that builds the training set and weights.
- Synthetic `series_id`s never collide with real ones.

## Don't run the long jobs
Run `python -m pytest tests -q` only. The reviewer runs `scripts.eval_synthetic` and `scripts.stress_t1`. You may run `simulate` once for 1,000 rounds and `compare_to_real` against real train states **if it takes under 1 minute**, and put that table in your report.

## Done when
- All tests pass (existing plus new). `git status` shows no data or model files. Nothing is committed.
- PyCharm run configurations "Evaluate synthetic data" and "Stress test T1".
- `docs/ROADMAP_ML.md` step 5 has a one-line "implemented, awaiting evaluation" note. `AI_SHOWCASE.md` has a log row naming the model (GPT-5.3-codex).
- Your report lists anything in the data that made a rule above hard to follow, and what you did about it.
