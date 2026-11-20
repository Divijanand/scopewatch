# Junie brief: step 4b, continue (after review)

**Model:** GPT-5.3-codex. **Branch:** `deep-learning` (`git pull` first). Read `docs/briefs/JUNIE_STEP4B.md` first: everything in it still applies, except the two changes below. Follow `AGENTS.md`.

## Where it stands
- Done: `engine/model/charges.py` with `estimate_charges(con)`. Keep it, with the changes below.
- Not done: `docs/ABILITY_CHARGES.md`, the `remain_` features, `scripts/eval_t1_remaining.py`, `tests/test_remaining.py`, the run configuration, the roadmap note and the showcase log row.
- **Do not run `scripts.eval_t1_features` or any other evaluation.** Last time it used up your actions and changed `docs/EVAL_T1_FEATURES.md` (reverted). Run `python -m pytest tests -q` only.

## Change 1: the "reusable" rule (the first brief's rule was wrong)
`share_above` (share of player-rounds above the 95th percentile) is at most about 5% **by definition**, so `share_above > 0.05` almost never fires. On the real data it flags nothing that recharges, such as Omen's Dark Cover (typical 4 uses) or Sova's Recon Bolt.

New rule: an ability is `reusable` when **the 99th percentile is above the 95th**, or its `MODE` is `placed`. A count that keeps going past the typical value means recharges, pickups or reactivations, so "remaining" isn't reliable. Add `p50`, `p95`, `p99` and `max` columns, and keep `share_above` as information.

## Change 2: one use, not every event
Some abilities log several events per use: Astra's stars, Neon's High Gear, Raze's Blast Pack, Cypher's cage, Sova's Shock Bolt. **Before counting**, merge casts of the same ability by the same player in the same round that are less than 1.0 s apart (keep the first). Do it in one helper, used by both `estimate_charges` and the `remain_` features, so that what we estimate and what we subtract agree.

## Tests to add (on top of the first brief's list)
- The 1.0 s merge: two casts 0.4 s apart count once; 1.5 s apart count twice.
- The p99 > p95 rule marks an ability as reusable, and a fixed-count ability isn't.

## Done when
As in the first brief. In your report, list how many abilities are reusable under the new rule, and any estimate that still looks wrong.
