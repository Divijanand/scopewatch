# Junie brief: step 5e part 2, the Matchup tab (UI only)

**Model:** GPT-5.3-codex. **Branch:** `deep-learning` (`git pull` first; start once part 1 is committed). **Don't search the codebase.** Read only `web/src/App.tsx`, `web/src/Summary.tsx`, `web/src/api.ts` and the `.bar` rules in `web/src/index.css`.

**Terminal:** run each command on its own. Never append `; exit $LASTEXITCODE` or any `exit`.

## The API (from part 1)
`GET /api/matchup?team_a=&team_b=&map=&since=&until=` returns, in `data`:
- `team_a`, `team_b`: `{id, name}`; `map`;
- `pairs`: ten items, each `{id, title, attacker, defender, att, dfn, unit, read, edge, sentence}`, where `att` and `dfn` are `{p, lo, hi, n, league, stance}` (any may be `null`), `unit` is `"rate"` or `"diff"`, `read` is `"attacker" | "defender" | "even" | "too_few"`, and `edge` is a team id or `null`. The first five are A attacking B; the last five are B attacking A;
- `top`: `{a: Finding[], b: Finding[]}`, each finding as in step 5d plus `side`;
- `head_to_head`: `{series_id, game_id, map, date, event, stage, a_rounds, b_rounds, winner}[]`;
- `note`: a string or `null`.

## Files you change (nothing else)
- `web/src/api.ts`: types `MatchupPair`, `Matchup`, and `api.matchup(q)`.
- `web/src/Matchup.tsx` (new).
- `web/src/App.tsx`: the tab and the "against" picker.
- `web/src/index.css`: only new classes starting with `.mu-`.

## What to build
1. **Tab:** a fourth tab, `Matchup`, after Utility. `view` gains `'matchup'`. The side buttons and the map view are hidden on this tab.
2. **"Against" picker** (only on the Matchup tab): a `<select>` labelled "against" listing the catalog's teams except the current one. Default: the first team in the catalog that isn't the current team. State `opponent` in App; reset it when the team changes if it equals the new team.
3. **No map picked:** show "Pick a map to compare the two teams." and don't call the API.
4. **Top lines:** two columns, "What stands out about {A}" and "What stands out about {B}", each listing its `top` findings: the title (small), the headline, and the prepare line in bold, with "on attack"/"on defence" after the title. An empty list shows "Nothing beyond noise on this map." The columns stack at under 700 px.
5. **Facing pairs:** two groups, "{A} attacking, {B} defending" (pairs 0-4) and "{B} attacking, {A} defending" (pairs 5-9). Each pair is one row:
   - the `title`, then the `sentence`;
   - two thin bars, one per side, labelled with the team name. Reuse the scale from `Summary.tsx`'s `pos()` (rate: 0 to 1; diff: symmetric around 0), with the league tick;
   - the read as a short tag: "Edge to {team name}" for `attacker`/`defender`, "Even", or "Too few rounds". Style the edge tag in `--ink`, the others in `--ink-3`. No green or red.
   - Rows whose `read` is `too_few` aren't drawn as rows: list their titles in one line at the end of the group, "Too few rounds to compare: Ecos against full buys." (On real data the eco pair is too few in most matchups.)
6. **Head to head:** a short table: date, event, map, score as "{a_rounds}–{b_rounds}", winner's name. The current map's rows in bold. If empty, show `note`.
7. **Phone width:** at 375 px, one column and no sideways scroll. Check it once in the browser's device toolbar.

## Stop when
`cd web`, then `npx tsc -b`, then `npm run build` pass, and `python -m pytest tests -q` still passes. You may start the API and web servers once to look at the page. Don't commit. Add an `AI_SHOWCASE.md` row: "Step 5e part 2 (Matchup tab)", naming the model.
