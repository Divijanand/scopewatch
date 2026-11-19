# Junie brief: step 4 fix, make the baseline match production

**Model:** GPT-5.3-codex. **Branch:** `deep-learning`. Follow `AGENTS.md`. Your step 4 work (`engine/model/features.py`, `engine/roles.py`, `scripts/eval_t1_features.py`, `tests/test_features.py`) is still uncommitted in the working tree; build on it.

## What review found
Your ablation's **baseline** scored log loss 0.3788, while the production model with the same features and seed scores **0.3778** (`docs/EVAL_T1.md`). So `build_states` doesn't produce the same baseline features as `winprob.get_training_data`.

The cause is the alive count. `build_states` counts alive players from the round's roster (`RoundTracker.alive_count`). Production uses `winprob.AliveTracker`: each side starts at 5, minus distinct dead players, plus revives not yet used up, clamped to 0–5. Rosters didn't always have 5 players: 1,181 side-rounds listed 6 or 7, because of phantom entries (no agent, $0 loadout, no events). The store now drops phantoms (D-021, `engine/store.py`), but the two methods must still agree **by construction**, not by luck.

## What to change
1. In `build_states`, compute these baseline columns **exactly as `winprob.get_training_data` does**: `attackers_alive` and `defenders_alive` with `winprob.AliveTracker` (fed the same kill and revive events, same ordering), plus `att_has_op` and `def_has_op` with the same rule. Reuse the code; don't re-implement it. Keep `RoundTracker` for the role and loadout families only.
2. **Event order** must match production for kills, revives and plants: kills, then revives, then plants at the same time. Casts may come first (they only feed the util and ult counts).
3. Your revive rule for roles and loadout (bring back the most recently dead teammate) is a reasonable guess, since the feed doesn't say who Sage revived. Keep it, and write that assumption in the docstring.

## Tests (add to `tests/test_features.py`, synthetic only)
- **Parity:** on one synthetic store with kills, a plant, a revive and a player dying twice, `build_states` and `winprob.get_training_data` give **identical** rows (same count and order) and identical values in every shared column: `series_id, round_key, seconds_since_buy_phase_end, planted, seconds_since_plant, attackers_alive, defenders_alive, att_loadout_value, def_loadout_value, att_has_op, def_has_op, label`.
- **A six-player roster** (an extra entry with no agent) doesn't change `attackers_alive`.

## Don't run the full evaluation
Last time Junie hit its action limit waiting on the 7–8 minute `scripts.eval_t1_features` run. **Don't run it.** Run `python -m pytest tests -q` only. The reviewer (Claude Code) runs the full evaluation and checks the baseline reproduces 0.3778.

## Done when
- `python -m pytest tests -q` passes (all existing tests plus the new ones).
- `git status` shows no data or model files.
- Nothing is committed. Report back the diff summary and the test result.
