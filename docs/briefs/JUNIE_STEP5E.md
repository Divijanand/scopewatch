# Junie brief: step 5e, the matchup view (our team against the opponent on one map)

**Model:** GPT-5.3-codex. **Branch:** `deep-learning` (`git pull` first; start only once step 5d is committed). Follow `AGENTS.md`. Read `engine/report.py` (step 5d) and the step 5c fundamentals metrics first.

## Why
A category 1 scouting tool prepares one team for one opponent. Step 5d says what stands out about a team against the league. This step puts two teams side by side on one map: where the opponent's habits meet ours. Example: "When they plant, they win 81% (league 74%). When you face a plant, you retake 18% (league 24%). Plan to stop the plant, not to retake."

## 1. Backend (`engine/matchup.py`, `GET /api/matchup?team_a=&team_b=&map=&since=&until=`)
- Run the existing metrics for both teams on the map, per side; nothing new is computed from raw tables. Cache by arguments, the same way as `_tendencies`.
- **Facing pairs:** each is one team's attack measure against the other team's defence measure, in both directions (A attacks B, B attacks A):
  - post-plant win rate (`team.post_plant`) against the retake rate (`team.retakes`);
  - share of attack rounds reaching a plant against the share of the defender's rounds where the attackers reached a plant (add this to `team.retakes` if it isn't there: plants faced over defence rounds);
  - first blood rate on attack against first blood rate on defence (`team.openings`);
  - dry duel difference (`fights.dry_duels`) for each team on its side;
  - the eco against full-buy win rate for each team (`team.economy`), as "who punishes whose ecos".
- Each pair gives both numbers with their ranges and the league rates, and a `read`:
  - **"edge to A" or "edge to B"** only when one side is beyond noise in its favour against the league and the other side isn't beyond noise against it;
  - otherwise **"even"**, or **"too few rounds"** when either n is under 20.

  Don't combine the two numbers into a made-up probability.
- **Head to head:** the series between them in the data (date, event, maps, score), newest first, with a link to each map's rounds in the evidence drawer. Say plainly when there are none.
- **Top lines:** each team's step 5d summary for the map, both sides, so the view opens with "what stands out about them" and "what stands out about you".

## 2. Page (`web/src/Matchup.tsx`, a **Matchup** tab)
- A second team picker labelled "against", defaulting to the team chosen before, or the first team if none. Cloud9 is team A by default; either team can be changed.
- At the top, the two summaries side by side; stacked at phone width.
- Then one row per facing pair: a sentence in plain words, both numbers with ranges, the league tick, and the read ("Edge to Cloud9", "Even", "Too few rounds").
- Then head to head.
- Use the existing `Bar` styling and the evidence drawer. Keep it to one screen of reading on a laptop.

## 3. Tests (`tests/test_matchup.py`, synthetic result dicts)
- The read rule: edge only when one side is beyond noise in its favour and the other isn't against it; "too few rounds" under n = 20; otherwise even.
- The two directions are mirrored correctly: A's attack is against B's defence, and the reverse.
- Head to head returns only series both teams played, newest first.
- The endpoint returns 404 for an unknown team and 422 when both teams are the same.

## Don't run the long jobs
Run the tests, `npx tsc -b` and the web build. You may open the page once for one pair of teams and report the response time (not the numbers).

## Done when
- All tests pass, the web app builds, `git status` shows no data or model files, and nothing is committed.
- `docs/ROADMAP_ML.md` has a step 5e section and `AI_SHOWCASE.md` a log row naming the model.
- `docs/IMPLEMENTATION_STATUS.md` has a line for the matchup view (without any team's numbers).
