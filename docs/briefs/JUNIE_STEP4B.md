# Junie brief: step 4b, utility remaining (what each team still has)

**Model:** GPT-5.3-codex. **Branch:** `deep-learning` (`git pull` first). Follow `AGENTS.md`: never commit data or model files, fixtures synthetic only.

## Why
Step 4 found that *utility used so far* doesn't improve the round win model beyond noise. Utility's effect mostly shows up in kills, which the model already sees. What who's-alive *can't* show is what a team **still holds**. In a post-plant 2v2, a defense that still has a smoke and a flash for the retake should be in better shape than one that has nothing. Read `docs/ROADMAP_ML.md` step 4b and `docs/EVAL_T1_FEATURES.md` first.

## The hard part: we don't know exactly what each player bought
The feed has no purchase events, so a player's charges at round start are unknown. Don't hand-type a charge table from memory. **Estimate it from the data, and say how confident each estimate is.**

1. New `engine/model/charges.py` with `estimate_charges(con) -> DataFrame`, one row per ability:
   - For every (round, player, ability), count casts in phases `buy`, `pre_plant` and `post_plant`.
   - `typical_charges` = the **95th percentile** of that count, over player-rounds where the player cast the ability at least once.
   - `share_above` = the share of those player-rounds with more casts than `typical_charges`.
   - `reusable` = True when `share_above > 0.05`, or the ability's `MODE` in `engine/abilities.py` is `placed` (setups can be picked up and placed again). For these, "remaining" is uncertain.
   - Also return `n_player_rounds` per ability.
2. Write the table to `docs/ABILITY_CHARGES.md` (aggregates only): ability, agent, typical charges, share above, reusable, n. A human checks it against the game later; **don't** silently overwrite estimates with remembered numbers.

## Features (prefix `remain_`)
For each side, at each state (only casts **at or before** the state's time; no peeking at the future):
- `remain_<side>_smoke`, `remain_<side>_flash` (flash plus stun), `remain_<side>_recon`, `remain_<side>_ult`: summed over **living** players, `max(0, typical_charges − casts so far)` for each ability in that player's kit whose `kind_of` matches. Kit = the abilities that agent has in `casts` (as `engine/metrics/utility.agent_kit` does). A dead player contributes 0; a revived player counts again.
- Ults: 1 if the living player's ult hasn't been cast this round, else 0. We don't know ult points, so this is "not used yet", not "ready"; say so in the docstring.
- **Two versions**, so we can see if the uncertainty matters:
  - **strict:** count only abilities with `reusable == False`;
  - **all:** count every ability, with reusable ones capped at `typical_charges`.

Add them to `build_states` in `engine/model/features.py` (or a helper it calls), keeping every existing column unchanged. The parity test with production must still pass.

## Evaluation (`scripts/eval_t1_remaining.py` writes `docs/EVAL_T1_REMAINING.md`)
Using only `engine/model/evaluate.py`, the same series split (seed 42), test series only:
- Variants: baseline (production features), baseline + remain (strict), baseline + remain (all), and baseline + remain (strict) + the step 4 families.
- Report each **overall** and **for post-plant states only** (`planted == True`). The post-plant subset is where we expect an effect.
- For each variant against the baseline: log loss, Brier, AUC, calibration error, and the paired-bootstrap log-loss difference with its 90% range.
- **Verdict**, written plainly: does utility remaining help beyond noise overall, and post-plant? A variant "helps" only if its 90% range is entirely below 0 and calibration error is at most the baseline's + 0.002.
- **Coach-facing check, only if post-plant helps:** among post-plant states with the same alive counts (e.g. 2v2), the actual defender win rate with at least one remaining smoke against none, with n for each. That's the number a coach would read.
- Add a PyCharm run configuration "Evaluate T1 utility remaining".

## Tests (`tests/test_remaining.py`, synthetic)
- `estimate_charges` on a hand-built table: the 95th percentile, the share above, and the `placed` rule.
- Remaining drops by exactly 1 on a cast; never below 0; a later cast doesn't change an earlier state (no leakage).
- A dead player's charges stop counting; a revived player's count again.
- An ult counts as remaining until it's cast.
- Strict excludes reusable abilities; all includes them, capped.

## Don't run the full evaluation
It takes several minutes and used up your action limit last time. Run `python -m pytest tests -q` only; the reviewer runs `scripts.eval_t1_remaining`. Do run `estimate_charges` once if it takes under 1 minute, and include `docs/ABILITY_CHARGES.md` in your report.

## Done when
- All tests pass (existing plus new). `git status` shows no data or model files. Nothing is committed.
- `docs/ABILITY_CHARGES.md` exists, and your report lists any ability whose estimate looks wrong to you, and why.
- `docs/ROADMAP_ML.md` step 4b has a one-line "implemented, awaiting evaluation" note. `AI_SHOWCASE.md` has a log row naming the model (GPT-5.3-codex).
