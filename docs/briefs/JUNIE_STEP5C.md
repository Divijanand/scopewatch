# Junie brief: step 5c, team fundamentals cards (retakes, post-plant, economy, openings, closing rounds)

**Model:** GPT-5.3-codex. **Branch:** `deep-learning` (`git pull` first; start only once step 5b is committed). Follow `AGENTS.md`: never commit data or model files, fixtures synthetic only. Read `engine/metrics/executes.py` (the pattern to copy), `engine/metrics/core.py` (`MetricDef`, `Rate.of`, `Filters`) and `engine/model/winprob.py` (`AliveTracker`, `load_revives`) first.

## Why
Our cards so far are deep on the Operator and utility but miss the fundamentals a coach asks about first when scouting an opponent: can they retake, is their post-plant safe, where do their rounds come from on the economy, how do they open rounds, and do they close them out. Professional match analysis (for example rib.gg's match reports, which we read for inspiration; no data is taken from them) explains series with exactly these measures, always against the league average. Everything here comes from our own GRID tables.

Each card is a descriptive metric for one team (`Filters`: team, map, side, dates) with its league comparison. Rates use `Rate.of` (Wilson range, small-sample flag). A team "differs from the league" only when its range excludes the league rate. Association, not cause.

## Shared definitions (write them once, test them)
- **Numbers at the plant:** each side's alive count at the plant time, from `AliveTracker` with kills and revives (`load_revives`) at or before the plant `t_round`, kill before revive at equal times, as `winprob` does. Buckets from the attackers' view: **ahead** (more alive than the defenders), **even**, **behind**.
- **Pistol rounds:** `round_no` 1 and 13 (12-round halves). **Bonus round:** the round after a pistol (2 and 14), counted only when the team won that pistol. Overtime (round 25 onwards) is never a pistol.
- **Economy:** `team_rounds.economy` (`full`, `half`, `eco`) for the team and for its opponent in the same round.
- **First blood:** the round's first kill in phases `pre_plant` or `post_plant` (`engagements`, ordered by `ts_ms, seq`). A trade kill is still the second kill.
- Put these helpers in `engine/metrics/fundamentals.py` and compute league numbers once per map and side, cached (`lru_cache`).

## The cards (all in `engine/metrics/fundamentals.py`)
1. **`team.retakes`** (defence): plants the team faced and how many it retook (defender win), overall and by numbers at the plant, each with the league rate. Evidence: lost retakes in `supporting`, won ones in `contrary`.
2. **`team.post_plant`** (attack): the share of attack rounds that reach a plant, and the win rate after a plant, overall and by numbers at the plant, against the league. Also the share of the team's attack-round losses that came **before** a plant, against the league, so the card can say "their attack fails before the plant, not after".
3. **`team.economy`** (both sides):
   - win rate in four matchups: full against full, full against the opponent's eco or half (the anti-eco), their eco or half against a full buy, and half against half;
   - pistol win rate, and bonus conversion after a pistol win.
   Each with n and the league rate.
4. **`team.openings`** (both sides): how often the team gets first blood, its round win rate after getting first blood and after giving it up, against the league. A per-player breakdown: first kills, first deaths, and first deaths in rounds the team lost. Use neutral wording in the card ("most of their opening deaths come from the entry role"). It shows where openings go wrong, not who's to blame.
5. **`team.closing`** (both sides), from `cache/v2/models/event_wp.parquet` (`wp_before`, `wp_after` are the attackers' win chance; flip for defence):
   - **comebacks:** rounds where the team's win chance fell to 0.20 or lower at some event and they still won;
   - **throws:** rounds where it reached 0.80 or higher and they lost;
   - each as a share of the rounds that reached that point, against the league. Evidence: the rounds themselves.
   - If the file is missing, return a warning ("Run python -m engine.model.wpa first"), never an error (the same pattern as `engine/metrics/value.py`). If `scripts/bundle_demo.py` lists model files one by one and this one is missing, add it.

Register all five in `api/server.py` `OP_METRICS` and add cards in `web/src/Findings.tsx` that read like the executes card. Each card is one plain sentence, then the numbers with n, and it's hidden when n is under 20 rounds. Example sentences (format only, invented numbers):
- "They retake 31% of plants [24, 39] against the league's 24%; down a player at the plant it's 9%."
- "Their attack fails before the plant: 64% of attack losses come with no plant, league 55%."
- "They win 18% of their ecos against full buys, the league 11%."
- Defence-only cards show only when the side filter is defence, attack-only only on attack; both-sides cards always.

## League summary (`scripts/league_fundamentals.py` writes `docs/LEAGUE_FUNDAMENTALS.md`)
League-level only, never a team name or id in `docs/`:
- retake and post-plant win rates by numbers at the plant;
- the four economy matchups;
- pistol and bonus rates;
- the first-blood conversion;
- the comeback and throw rates.

All by map. Ranges are series-bootstrap t intervals from `engine/metrics/core.bootstrap_mean` (D-020), since rounds in one series aren't independent. Add a PyCharm run configuration "League fundamentals".

## Tests (`tests/test_fundamentals.py`, synthetic)
- Numbers at the plant: a kill at the plant time counts, a revive before the plant puts the player back, and a kill after the plant doesn't count.
- Pistols are rounds 1 and 13 only. A bonus counts only after a won pistol. Round 25 isn't a pistol.
- First blood uses `seq` to order kills at the same millisecond.
- Retakes: a defuse counts as a retake, and a detonation or an elimination of the defenders doesn't.
- Closing: the defender view flips the win chance; a round that never reaches 0.20 isn't in the comeback denominator.
- A missing `event_wp.parquet` gives a warning, not an exception.

## Don't run the long jobs
Run `python -m pytest tests -q` and `npm --prefix web run build` only. The reviewer runs `scripts.league_fundamentals`. You may call each card once for one team, map and side on the real store if each takes under 30 s, and report the timings (not the numbers).

## Done when
- All tests pass (existing plus new), the web app builds, `git status` shows no data or model files, and nothing is committed.
- `docs/ROADMAP_ML.md` has a step 5c section (after 5b, before 6): one line per card and "implemented, awaiting review". `AI_SHOWCASE.md` has a log row naming the model (GPT-5.3-codex).
- Your report lists anything in the data that made a rule above hard to follow, and what you did about it.
