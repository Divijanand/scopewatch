# Junie brief: step 4, richer features for the round win-probability model

**Model:** GPT-5.3-codex. **Branch:** `deep-learning` (run `git switch deep-learning && git pull` first). Follow `AGENTS.md` strictly: never commit data or model files, and keep test fixtures synthetic.

## Goal
Add feature families to the round win-probability model (task T1 in `docs/ML_TAXONOMY.md`), measure what each family is worth, and keep the result **only if it beats the current model** by the rule in `docs/ROADMAP_ML.md` step 1.

## The one rule that matters most: no peeking at the future
Every feature for a state must use **only what was known at that moment**: events with a time at or before the state's event, never later ones, and never the round's result. A feature that leaks the future makes the model look great and be useless. Write a test for each family that proves a later event doesn't change an earlier state.

## Where things are
- The current model: `engine/model/winprob.py`. `get_training_data()` builds one state per kill and plant (with `AliveTracker` for revives). Also `split_by_series`, `fit_models`, `predict_wp`, `FEATURES`.
- The evaluation: `engine/model/evaluate.py` (`evaluate_binary`, `paired_difference`), and `scripts/eval_t1.py` as an example.
- Ability classes: `engine/abilities.py` (`kind_of`, `PLACEABLE`, `ULTS`, `WEAPON_ULTS`, `MODE`).
- Agent roles: `ROLE` in `scripts/data_audit.py`. **Move it** to `engine/roles.py` and import it from both places.
- The DuckDB store (`engine.config.DB_PATH`, read-only): `rounds`, `team_rounds`, `player_rounds` (agent, loadout_value, side, team_id), `engagements` (kills: ts_ms, t_round, phase, att/vic id, team and side), `casts` (ts_ms, t_round, phase, team_id, side, ability, slot), `objectives` (plants).

## Feature families to add (definitions are exact; follow them)
1. **Alive by role:** for each side, players alive per role (duelist, initiator, controller, sentinel). This extends `AliveTracker`; revives still bring a player back.
2. **Alive loadout:** for each side, the sum of `loadout_value` (at buy end) over players still alive. This is the economy that's still on the map.
3. **Utility used so far:** for each side, the count of casts this round, up to and including the state's time, by `kind_of` (smoke, flash, stun, info, movement) plus `placeable` (abilities in `PLACEABLE`). Casts in phase `buy` count (setups); `post_round` casts never do.
4. **Ults used so far:** for each side, the count of ultimate casts this round up to the state's time (abilities in `ULTS - WEAPON_ULTS`, phase `pre_plant` or `post_plant`).
5. **Score and round:** round number (`rounds.round_no`), whether it's overtime (round > 24), and each side's score **before this round** (wins in the same game's earlier rounds, mapped to this round's attacking and defending teams).
6. **Map:** categorical (`rounds.map`). Pass it as a categorical feature to `HistGradientBoostingClassifier`, not as one-hot.
7. **Patch:** `patch_index`, the order of the game's patch by date (0 = oldest).

## What to build
- `engine/model/features.py`: `build_states(db_path=DB_PATH) -> DataFrame`, with every column of the current training data plus the families above. Each family's columns have a fixed prefix (`role_`, `aliveload_`, `util_`, `ult_`, `score_`, `map`, `patch_index`) so ablations can select them. **Time budget: under 6 minutes** on the full store. Precompute per round with SQL or a groupby, then walk events once; no per-state scans.
- `scripts/eval_t1_features.py` writes `docs/EVAL_T1_FEATURES.md`, using only `engine/model/evaluate.py`, with the same series split as `split_by_series` (seed 42) and **only the test series** for numbers:
  - **Ablation table:** the current features (baseline), then the baseline plus each family on its own, then all families, then all minus each family. Columns: log loss, Brier, AUC, calibration error, and the paired-bootstrap log-loss difference against the baseline with its 90% range.
  - **Verdict:** the full model **ships** only if its log-loss difference range against the current model is entirely below 0 **and** its calibration error is at most the current one + 0.002. Say plainly whether it ships.
- If it ships, save it as `cache/v2/models/winprob_v2.pkl`. **Do not overwrite `winprob_hgb.pkl`**, and don't touch `engine/model/wpa.py` or anything the live app reads. Switching the app over is a separate, reviewed step.
- Add a PyCharm run configuration, "Evaluate T1 features", for `python -m scripts.eval_t1_features`.

## Tests (`tests/test_features.py`, synthetic only)
- For each family: a hand-built round where an event **after** a state would change the feature if leaked, and the state's value is unchanged.
- Alive by role: a revived sentinel counts again; a duelist's death lowers only `role_duelist` for its side.
- Alive loadout: drops by exactly the dead player's loadout.
- Score before the round: round 1 is 0–0; side mapping follows the teams when they swap sides at round 13.
- `build_states` keeps one row per kill and plant, and the same `label` and `series_id` as `winprob.get_training_data` on the same synthetic store.

## Done when
1. `python -m pytest tests -q` passes, all existing 95 tests plus yours.
2. `python -m scripts.eval_t1_features` runs end to end under 15 minutes and writes `docs/EVAL_T1_FEATURES.md` with real numbers only.
3. `git status` shows no data or model files staged.
4. `docs/ROADMAP_ML.md` step 4 has a short result line, and `AI_SHOWCASE.md` has a log row naming the model (GPT-5.3-codex).

Report back: the ablation table, the verdict, the run time, and anything in this brief you think is wrong.
