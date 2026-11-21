# Junie brief: step 5b, two scouting cards (recon timing, duels after the utility trade)

**Model:** GPT-5.3-codex. **Branch:** `deep-learning` (`git pull` first; start only once step 5 is committed). Follow `AGENTS.md`: never commit data or model files, fixtures synthetic only. Read `docs/ROADMAP_ML.md` step 4c, `engine/metrics/executes.py` (the pattern to copy) and `engine/model/fights.py` first.

## Why
This is how coaches build a game plan. Information costs time and charges. If the enemy has to spend their recon early, they either hit blind or wait for it to come back, and waiting gives the timing away. Once both sides have spent their utility, the round comes down to who wins the duels left over. Step 4c measured that utility before a fight matters (a small effect, beyond noise). These two cards turn it into something a coach reads in five seconds about **one opponent**:

1. **Recon timing:** when does this team throw its first recon, and how soon after it do they commit?
2. **Dry duels:** with no utility around, how does this team (and each agent pair, league-wide) do in 1v1 fights, against what the opener advantage alone predicts?

Both are descriptive metrics (rates with honest ranges), not models. Label everything as association, not cause.

## 0. Recon set
`engine/abilities.INFO` is the recon set. Skye's `trailblazer` (her dog, 6,046 casts) is missing from it. Add it, with a one-line test. Check the other abilities in `casts` with more than 1,000 uses that gather information. Add any that clearly do (a recon dart, drone, dog, or reveal), and list each one you add or skip, with the reason, in your report.

## 1. Recon timing (`engine/metrics/tempo.py`, metric `util.recon_timing`)
Use the same structure as `executes.py`: a `MetricDef` with a plain-English question, population, numerator and caveats; `@metric`; and a `Filters` team, map and side.
- **Population:** the team's rounds on the map and side, from the end of the buy phase (`t_round` 0) until the round ends. Only casts in phases `pre_plant` and `post_plant`.
- **First recon:** the team's earliest recon cast in the round. Report:
  - the median and interquartile range of its time, and the share of rounds with no recon before the plant or the round end;
  - which agent throws it first (a breakdown by agent, with counts).
- **Commit after recon** (attack only): for rounds with a plant, the median and IQR of the time from first recon to the plant. For all attack rounds, the median and IQR of the time from first recon to first contact, meaning the team's first gun damage dealt or taken in `engagements`. Use `engine/weapons.GUNS`, as fights do.
- **League comparison:** the same medians for all teams on that map and side, so the card can say "earlier than the league by 6 s". Compute the league once per map and side, and cache it (`lru_cache`).
- **When their recon comes late:** split the team's rounds into first recon on time (at or before the league's 75th percentile for that map and side) and late (after it, or none). Give the round win rate for each with `Rate.of`, which gives the Wilson range and the small-sample flag. Caveat: late recon is often a choice, such as a slow default, not always a denial. The feed doesn't record a recon being destroyed.
- **Evidence:** `supporting` is the late-recon rounds the team lost and `contrary` is the late-recon rounds it won, so the existing evidence view can open them.
- Register it in `api/server.py` `OP_METRICS` and add a card in `web/src/Findings.tsx` that reads like the executes card. In one sentence, then numbers. This is the format only; the numbers are invented:
  - "On attack their first recon goes out at about 15 s (league 21 s), and they plant about 18 s later. When it comes late they win 38% [30, 47] of rounds against 52% [47, 57]."

  Show the n. Hide the card when n is under 20 rounds (`MIN_LEAGUE` in `executes.py` uses the same threshold).

## 2. Dry duels (`engine/metrics/duels.py`, metric `fights.dry_duels`)
- **Fights file:** add a build CLI to `engine/model/fights.py` (`python -m engine.model.fights`).
  - It runs `fight_core` and `add_utility(window_s=4.0, radius=2500.0)`, adds `opener_agent` and `other_agent` from `player_rounds` (on round_key and player_id), and writes `V2_DIR / "models" / "fights.parquet"`.
  - Use the same pattern as `holder_wpa.parquet` in `engine/metrics/value.py`: the metric reads the file, and if it's missing it returns a warning ("Run python -m engine.model.fights first"), never an error.
  - If `scripts/bundle_demo.py` lists model files one by one, add this file to the list.
- **Dry fight:** every `util_*` and `dmg_util_*` column is 0 for both sides.
- **Expected win rate:** the opener wins most fights (82.9% league-wide), so a raw win rate mostly measures who shot first. Compare the team to the league opener rate in the same state instead:
  - **expected** = the league's dry-fight opener win rate in the fight's cell (opener-side alive and other-side alive, each capped at 5; planted; whether this team opened). For fights the team didn't open, use 1 minus that rate;
  - the card's number is **actual − expected** over the team's dry fights, with a 90% range from `engine/metrics/core.bootstrap_mean` grouped by series (the t interval, D-020).
- **Team card:**
  - dry fights as opener, and dry fights where the enemy opened, each with n, actual, expected and the difference;
  - a breakdown by the team's agent, same columns, for agents with at least 50 dry fights;
  - one sentence (format only, invented numbers): "In dry duels they win 3 points more than expected [+1, +5], mostly on Chamber."
- **League agent-pair table** (`scripts/agent_duels.py`, writes `docs/AGENT_DUELS.md`):
  - for each unordered agent pair with at least 300 dry fights, the difference from expected for the first agent, and its 90% range;
  - pairs sorted by the size of the difference; it says "beyond noise" only when the range excludes 0.

  League-level only: no team names or team ids in `docs/`. A per-team version, if you want one for checking, goes to `cache/v2/reports/` (git-ignored, licensed data).
- Register the metric and add a card next to the recon card.

## 3. Tests (synthetic)
- `tests/test_tempo.py`:
  - first recon is the earliest recon cast, with other abilities ignored;
  - a round with no recon counts toward the "no recon" share;
  - recon-to-plant only for rounds with a plant;
  - the on-time and late split at the league's 75th percentile;
  - `trailblazer` counts as recon.
- `tests/test_duels.py`:
  - a fight with any utility value above 0 is not dry;
  - expected uses 1 minus the rate when the team didn't open;
  - actual − expected is 0 when the team plays exactly at the league rates;
  - agent columns join on round_key and player_id;
  - a missing fights file gives a warning, not an exception.

## Don't run the long jobs
Run `python -m pytest tests -q` and `npm --prefix web run build` (it must build) only. The reviewer runs `python -m engine.model.fights` (about 3 minutes) and `scripts.agent_duels`. You may call `util.recon_timing` for one team, map and side on the real store if it takes under 30 s, and put the result in your report.

## Done when
- All tests pass (existing plus new), the web app builds, `git status` shows no data or model files, and nothing is committed.
- PyCharm run configurations "Build fights file" and "Agent duels".
- `docs/ROADMAP_ML.md` has a step 5b section (before step 6): one line each for the two cards and "implemented, awaiting review". `AI_SHOWCASE.md` has a log row naming the model (GPT-5.3-codex).
- Your report lists anything in the data that made a rule above hard to follow, and what you did about it.
