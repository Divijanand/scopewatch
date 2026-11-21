# Junie brief: step 4c, fight-level models (where utility acts)

**Model:** GPT-5.3-codex. **Branch:** `deep-learning` (`git pull` first). Follow `AGENTS.md`: never commit data or model files, fixtures synthetic only. Read `docs/ROADMAP_ML.md` steps 4, 4b and 4c first.

## Why
Steps 4 and 4b showed that utility (used or still held) doesn't improve the **round** win model beyond noise. Utility's effect mostly arrives as kills, which the round model already sees. So we measure it one level down: **who wins a fight**, given whose utility was thrown just before it.

## 1. Fights (`engine/model/fights.py`, `build_fights(con) -> DataFrame`)
From `engagements` (kinds `damage` and `kill`, phases `pre_plant` and `post_plant`):
- **Guns only start fights.** Add `GUNS` to `engine/weapons.py`: classic, shorty, frenzy, ghost, sheriff, bandit, stinger, spectre, bucky, judge, bulldog, guardian, phantom, vandal, marshal, outlaw, operator, ares, odin, plus the weapon ults blade-storm, tour-de-force and overdrive. Damage from abilities (mollies, Nanoswarm, Shock Bolt and so on) is **not** a fight. It's a feature (below).
- A fight is between **one pair of players on opposite sides**. It starts at the first gun damage between them, in either direction. It ends when one kills the other (the winner is the killer) or when 3.0 s pass with no damage between them (no winner). A later gun damage between the same pair starts a new fight.
- Keep fights with a winner for the model. Report how many had no winner.
- Columns, all known **at the fight's start time `t0`** (no peeking past it):
  - ids: `series_id`, `round_key`, `t0`, `opener_id`, `other_id` (the opener dealt the first damage), opener's side;
  - `label` = 1 if the opener wins;
  - state: `phase`/planted, seconds since buy end, opener-side alive and other-side alive (reuse `winprob.AliveTracker`, including revives), each side's team economy;
  - weapons: the opener's weapon; the other player's weapon if they dealt damage earlier in the round, else `unknown`. Whether each holds an Operator (`player_rounds.has_op`);
  - place: the map, and the callout at the fight (`att_callout` of the first damage);
  - **utility before the fight**, for each of the opener's team and the other team, in the window `[t0 − W, t0]`:
    - counts by kind (flash/stun, smoke, recon, ult) of casts by that team whose **caster position** is within `R` of either fighter's position at `t0`. Use casts' `x, y` and require `spatial_ok`;
    - `dmg_util_<team>`: ability damage dealt by that team to the other fighter in the window.
  - Default `W` = 4.0 s, `R` = 2,500 units. Make both arguments.

## 2. Model and evaluation (`scripts/eval_fights.py` writes `docs/EVAL_FIGHTS.md`)
Use only `engine/model/evaluate.py`, the same series split (`split_by_series`, seed 42), test series only.
- **Baseline:** `HistGradientBoostingClassifier(random_state=42)` on everything except the utility columns. **Full:** the same plus the utility columns.
- Report log loss, Brier, AUC, calibration error and the paired-bootstrap log-loss difference with its 90% range. "Utility helps" uses the usual rule: the range is entirely below 0, and calibration error is at most the baseline's + 0.002.
- **Sensitivity:** repeat the full-vs-baseline difference for `W` in {2, 4, 6} s and `R` in {1500, 2500, 4000}. That's 9 rows: difference and range only.
- **Coach-facing table, only if utility helps:** for each team with at least 200 fights, the opener's win rate when their team flashed or stunned near the fight just before, against dry fights. Each with n, and the league rate for both. Ranges come from `engine/metrics/core.bootstrap_mean` grouped by series (the t interval, D-020). Label it association, not cause: teams flash when they intend to fight.
- Add a PyCharm run configuration "Evaluate fights".

## 3. Tests (`tests/test_fights.py`, synthetic)
- Fight boundaries: a kill ends a fight; a 3.0 s gap ends one with no winner; a new damage after that starts a new one. The opener is whoever damaged first.
- Ability damage alone never starts a fight, but it counts in `dmg_util_*` when it lands in the window.
- A cast after `t0` never counts (no leakage). A cast outside `R`, or without `spatial_ok`, doesn't count.
- The alive counts at `t0` handle a revive.

## Don't run the full evaluation
Run `python -m pytest tests -q` only; the reviewer runs `scripts.eval_fights`. Once the tests pass, you may run `build_fights` once on the real store **if it takes under 2 minutes**, and report the number of fights, the share with no winner, and the opener's win rate. Don't run anything else long.

## Done when
- All tests pass (existing plus new). `git status` shows no data or model files. Nothing is committed.
- `docs/ROADMAP_ML.md` step 4c has a one-line "implemented, awaiting evaluation" note. `AI_SHOWCASE.md` has a log row naming the model (GPT-5.3-codex).
- Your report lists anything in the data that made a rule above hard to follow, and what you did about it.
