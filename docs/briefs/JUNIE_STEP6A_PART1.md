# Junie brief: step 6a part 1, the map overview backend (no UI)

**Model:** GPT-5.3-codex. **Branch:** `deep-learning` (`git pull` first). Follow `AGENTS.md`. **Don't search the codebase.** Read only `engine/metrics/utility.py` (`layer_items`, lines 126-177), `api/server.py` (`filters`, `envelope`, `_spawns`, `utility_layer`), `engine/metrics/core.py` (`Rate`, `Filters`) and `tests/test_utility.py` (its fixture).

**Terminal:** run each command on its own. Never append `; exit $LASTEXITCODE` or any `exit`.

**Why:** the Report tab opens on text. The brief for our category asks for "Opponent A uses Sentinel utility at (X,Y) on Map B 60% of the time". This part finds those spots; part 2 draws them as the first thing on the page.

## Files you create or change (nothing else)
1. `engine/overview.py` (new).
2. `api/server.py`: one new endpoint and its import.
3. `tests/test_overview.py` (new).

## `engine/overview.py`

```python
SPOT_GROUPS = ("setup", "damage", "recon", "flash")
PER_GROUP = 3
MIN_SPOT_ROUNDS = 5
AWAY = "away from any callout"

def utility_spots(con, f: Filters) -> list[dict]
def site_plants(con, f: Filters, executes_result) -> list[dict]
def overview(con, f: Filters) -> dict
```

### `utility_spots`
- Needs `f.map` and `f.side`; without either, return `[]`.
- `scope` = every `round_key` of the team: `w, p = f.where("t")`, then `SELECT round_key FROM team_rounds t WHERE {w}`. If it's empty, return `[]`.
- For each group in `SPOT_GROUPS`: `items, _, _ = layer_items(con, f, group=group)`. An item is `(round_key, ability, agent, player, t, x, y, callout, extra)`.
- Skip items whose `callout` is `AWAY`, or whose `x` or `y` is `None`.
- Group by `(ability, callout)`. The rounds of a spot are its **distinct** round keys (two traps in one round count once).
- Keep spots with at least `MIN_SPOT_ROUNDS` rounds. Sort by rounds (most first), then ability, then callout. Keep the first `PER_GROUP` of each group.
- Each spot: `dict(kind="utility", group=group, ability=..., agent=<most common agent>, callout=..., mode=extra["mode"], x=<median x, rounded to 1>, y=<median y, rounded to 1>, rate=Rate.over("util.placements.spot", rounds, scope), round_keys=<sorted rounds>)`.
- **Use `Rate.over`, never `Rate.of`.** `Rate.over` widens the range because rounds of one game repeat each other (D-025).
- Median: `float(np.median(...))`. Most common agent: `ranked(Counter(...), 1)[0][0]` from `engine.metrics.core`.

### `site_plants`
- Return `[]` unless `f.side == "attacker"`.
- `executes_result` is the `MetricResult` of `REGISTRY["att.executes"][1](con, f)`. For each item of its `.breakdown` (keys `site`, `rate`, `league`, `round_keys`), find the median plant position:
  `SELECT median(x), median(y) FROM objectives WHERE kind = 'plant' AND x IS NOT NULL AND round_key IN (SELECT unnest(?))`
- Each site: `dict(kind="site", site=..., x=..., y=..., rate=<the breakdown's rate>, league=<the breakdown's league, may be None>, round_keys=<sorted>)`. Skip a site with no position.

### `overview`
`dict(spots=utility_spots(con, f), sites=site_plants(con, f, REGISTRY["att.executes"][1](con, f)) if f.side == "attacker" else [])`

## Endpoint
`GET /api/overview?team_id=&map=&side=&since=&until=` in `api/server.py`, after `spatial_operator`:
- `map` is required. `side` is `SIDE`.
- Build `f = filters(team_id, map, side, since, until)`.
- Return `envelope(dict(**overview_data, spawns=...), f)`, with `spawns` built exactly as `spatial_operator` builds it. `Rate` objects must reach JSON as dicts: convert each `rate` and `league` with `dataclasses.asdict` (skip `None`). Remove `round_keys` from every spot and site, and add `rounds=len(round_keys)` instead.

## Tests (`tests/test_overview.py`)
Copy the fixture from `tests/test_utility.py`. Set `MIN_SPOT_ROUNDS` low with `monkeypatch` where needed.
1. Two traps in one round count once.
2. A spot with fewer than `MIN_SPOT_ROUNDS` rounds is left out.
3. At most `PER_GROUP` spots per group, most rounds first, ties broken by ability then callout.
4. `rate.n` is the number of the team's rounds in scope, and another team's casts aren't counted.
5. No side: `utility_spots` returns `[]` and `overview(...)["sites"]` is `[]`.

## Stop when
`python -m pytest tests -q` passes, and `/api/overview` returns spots for one team, map and side when you start the API once. Don't commit. Add an `AI_SHOWCASE.md` row: "Step 6a part 1 (map overview backend)", naming the model.
