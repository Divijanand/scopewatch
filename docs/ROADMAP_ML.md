# ML roadmap (branch `deep-learning`)

What we're building, in order, and why. Definitions are in [ML_TAXONOMY.md](ML_TAXONOMY.md). Each step ends with something measurable, and each result is logged in `AI_SHOWCASE.md` and `docs/`.

## Step 1: define accuracy and precision (done 2026-11-19)
- `engine/model/evaluate.py`: log loss, Brier, calibration (reliability table and ECE), AUC, top-1 accuracy against the "most common choice" baseline, a paired series-bootstrap of the difference between two models, and interval coverage and width.
- **Done when:** every model on this branch is reported with the same function, against its baseline, on the same held-out series.
- **Result:** [EVAL_T1.md](EVAL_T1.md). The current gradient-boosted T1 beats the logistic baseline beyond noise (log loss 0.3794 vs 0.4098; 90% range of the difference −0.034 to −0.027) with calibration error 0.005. That's the bar for steps 4–6. Run with `python -m scripts.eval_t1`.

## Step 2: what happens, how often, and the limits
- A data audit script producing `docs/DATA_AUDIT.md`: feature availability (first pass in ML_TAXONOMY.md §2), rare states (1v4 retakes, eco wins, 5v5 post-plants), drift by patch (win rates and feature distributions), the 1 Hz series, reversals.
- **Done when:** every feature family has an availability figure, and every task has a list of the states it rarely sees.

## Step 3: bootstrapping without breaking accuracy or precision (done 2026-11-19)
- Resample **whole series** (block bootstrap), only from the split being measured; the test set never changes.
- Two uses: **ranges** on every reported number, and **bootstrap ensembles** (20–50 models on resampled training series) that give a spread per prediction. Wide spread = "the model doesn't know this state".
- **Done when:** our 90% ranges contain the held-out truth about 90% of the time (`coverage`). If they don't, the bootstrap is wrong and we fix it before going on.
- **First pass** ([EVAL_BOOTSTRAP.md](EVAL_BOOTSTRAP.md)):
  - Series bootstrap coverage is 86–88% (80% with few series), against 70–74% for the naive one. That's close, but under 90%.
  - A 20-model ensemble improves log loss slightly beyond noise (0.3778 → 0.3770).
  - The ensemble spread is **not yet** a usable "uncertain" signal: rare states got narrower bands in probability points.
- **Follow-ups, both closed:**
  - (a) ranges now use a t interval with a small-sample correction: 88–91% coverage from 4 to 60 series, against 75–87% for the percentile interval (D-020);
  - (b) on the log-odds scale, within the same band of predicted win chance, the models disagree 1.08–1.25× more about rare states. That's the right direction but a weak signal, so the spread isn't a product flag; thin states are flagged by training count.

## Step 4: everything, not only the Operator
- Add the feature families in ML_TAXONOMY.md §2 to the gradient-boosted model first: per-player economy, alive by role, utility used so far, ults used, comp (roles and embeddings), score and round number, map, patch.
- Ablations: each family on and off, so we know what each one is worth.
- **Done when:** a richer T1 beats the current model on held-out series by the step 1 rule, and T2/T3 have first models against their baselines.
- **First result** (Junie, reviewed; [EVAL_T1_FEATURES.md](EVAL_T1_FEATURES.md)): no family improves T1 beyond noise, and the full model doesn't ship. Score and round number do carry weight inside the full set (removing them costs +0.0020 log loss, range +0.0005 to +0.0035). The ablation baseline (0.3773) differs from EVAL_T1 (0.3778) only through training settings: its features match production row for row (323,903 states). That's expected for *utility used*: utility's effect mostly shows up in kills, which the model already sees through who's alive, and a count of casts says nothing about how good they were. This is not a verdict on utility; steps 4b and 4c test it where it acts.

## Step 4b: utility remaining (what each team still has)
- **Question:** who wins from here, given what each side still has, not what it has used? In a post-plant 2v2, whether the defense still holds a smoke and a flash for the retake should matter, and who's alive can't show it.
- **Features:** per side, smokes, flashes and stuns, recon, and ults still available. Each agent's kit charges (from the agent's ability list and charges per round) minus what they've cast this round, counting only living players. Charges per ability are a small, cited table in `engine/abilities.py`. Where a charge count is uncertain (abilities that recharge over time), it's flagged and tested both ways.
- **No peeking:** only casts at or before the state's time.
- **Done when:** the ablation against the step 4 baseline is reported, **overall and for post-plant states separately**, where utility for the retake should matter most. A coach-facing number follows only if it beats the baseline beyond noise there. For example: "for this team, holding a smoke for the retake is worth +X points".
- **Result** (Junie, reviewed; [EVAL_T1_REMAINING.md](EVAL_T1_REMAINING.md), charges in [ABILITY_CHARGES.md](ABILITY_CHARGES.md)): utility still held does **not** improve T1 beyond noise, overall or post-plant (post-plant Δ −0.0002, range −0.0010 to +0.0007). Charges are estimated from the data, not typed in: cast events less than 1 s apart count as one use, and an ability is "reusable" when its 99th percentile is above its 95th. That flags most of the kit (recharging smokes, Sova's Recon Bolt), so only 10 smoke, flash and recon abilities count in the strict version. Reading: who's alive, the clock and the plant already carry what utility left would add, or our charge counts are too rough to show it. Step 4c measures utility at the fight instead.

## Step 4c: fight-level models (where utility acts)
- **Question:** who wins this fight, given what happened just before it? This measures utility before it turns into a kill.
- **Data:** a fight = the first damage between two players until one dies or 3 s pass with no damage. Fights come from `engagements` (attacker, victim and timing are all there). Features: whose utility was cast within the few seconds before (flash or stun, smoke, recon, ult; caster near the fight using caster positions; for damaging utility, the hit itself), numbers advantage at the moment, weapons, economy, side, plant, map, and who peeked first where position data allows.
- **Model and evaluation:** gradient boosting on fights; series split; step 1 measures; baseline = the same model without the utility features.
- **What a coach gets:** "when this team flashes before peeking A Main they win the fight X% against Y% dry". Shown with the n behind it, compared with the league, as association, not cause. Teams flash when they intend to fight, which is why the league comparison and the matched baseline matter.
- **Done when:** the utility features' effect on fight outcomes is measured beyond noise (or shown not to be), and the per-team "with utility vs without" numbers have honest ranges (D-020).
- **Result** (Junie, reviewed; [EVAL_FIGHTS.md](EVAL_FIGHTS.md)): **utility before a fight helps beyond noise**, the first family on this branch that does. On 289,430 fights, adding whose flashes, smokes, recon, ults and ability damage came just before improves held-out log loss by 0.0013 (range 0.0008 to 0.0018), in 7 of 9 window and radius settings; the other 2 also improve log loss but calibration slips past the +0.002 limit. The effect is small next to who shot first (the opener wins 82.9% of fights). League-wide, the opener wins 84.7% of fights after their team flashed or stunned near it against 82.6% dry; 8 of 65 teams show a gap beyond noise, none the reverse. Per-team numbers stay out of the repo (derived data); association, not cause.

## Step 5: synthetic data, as a controlled experiment
- Our position: synthetic data **tests**; as **training** data it's an experiment. A simulator's rules become what the model learns, and any weight shifts calibration toward the simulator.
- If we run it: synthetic weight ∈ {0, 0.1, 0.25, 0.5}, everything else fixed, judged **only** on real held-out log loss and calibration. We publish the curve, including if the best weight is 0. A fixed weight of 0.5 would be a guess, so we don't hard-code it.
- Synthetic data is also useful for **stress tests** of trained models: does a 1v5 post-plant with 3 s left look sensible?
- **Result** (Junie, reviewed; [EVAL_SYNTHETIC.md](EVAL_SYNTHETIC.md), [STRESS_T1.md](STRESS_T1.md)): **real data alone is best.** A simulator fit only on train series gets close to reality (attacker win 49.7% vs 51.7%, plant rate 62% vs 68%, kills per round 6.6 vs 6.9), yet every synthetic weight makes held-out log loss worse beyond noise (+0.0009 at 0.1, +0.0027 at 0.5) and calibration worse; trained on synthetic data alone the model loses 0.020. Synthetic data stays a testing tool. Stress tests on the production model all pass (alive-count monotonicity, post-plant clock 0.51 → 0.94 in a 1v1, extremes), but one rare state is wrong: 1v5 three seconds before detonation gets 0.47, while the 24 similar training states went to the attackers 75% of the time and the defenders can't finish a 7 s defuse. The review also found the production model predated the D-021 store rebuild; it was retrained on the current store (the experiment checks w = 0 reproduces it exactly).

## Step 5b: two scouting cards (recon timing, dry duels)
- **Why:** how coaches build a game plan. Information costs time and charges, so whoever spends recon first gives their timing away; once utility is traded, rounds come down to the duels left over. Step 4c showed utility before a fight matters; these cards make it readable for one opponent.
- **Recon timing** (`util.recon_timing`): when the team throws its first recon on a map and side, against the league; on attack, how long after it they plant or take their first fight; and their round win rate when the first recon comes late (after the league's 75th percentile) or not at all. Late recon is sometimes a slow default, not a denial: the feed doesn't record a dart being destroyed.
- **Dry duels** (`fights.dry_duels`): fights with no utility from either side in the 4 s before, scored as actual minus the league's opener win rate for the same map, side, alive counts and plant, so who shot first is accounted for. By who opened and by the team's agent. League agent pairs in [AGENT_DUELS.md](AGENT_DUELS.md): 133 pairs with 300+ dry fights, 27 beyond noise where about 13 would be by chance; Chamber leads most of them, which includes his guns and the Operator.
- **Status:** implemented by Junie (GPT-5.3-codex), reviewed and fixed (2026-11-21). Both cards are in the app.

## Step 6: deep learning, then rinse and repeat
- **Model:** a sequence model over a round's events in order (time, event type, who, where, economy, utility), with players as a set (order-free) and agents and callouts as embeddings. Start small (GRU or a 2-layer transformer).
- **Comparison:** against the step 4 gradient-boosted model, with the step 1 rule. It ships only if it wins **and** is at least as well calibrated (with temperature scaling on the validation series if needed).
- **Loop:** every run logged (config, data version, metrics) in an experiments table; tuning only on validation series; the test set touched once per candidate.

## Related: a proper backend and database
- **Keep** DuckDB for analytics: it's columnar and read-heavy, which is why reports take 0.2 s.
- **Add:**
  - an app database with migrations for what people create: VOD links, saved scouting cards and notes, users. SQLite now, Postgres if it's shared;
  - the API split into routers and services with typed responses;
  - a job runner so ingest, training and WPA builds are tracked;
  - an experiment registry for step 6.
- Good to run in parallel with steps 1–3, since it barely overlaps them.

## Ownership
| Item | Owner |
|---|---|
| Steps 1–3 | Claude Code + Junie (reviewed) |
| Backend and app database | Caden (proposed) |
| Steps 4–6 | after step 3, split by whoever is free |
| Video and write-up | Divij |
