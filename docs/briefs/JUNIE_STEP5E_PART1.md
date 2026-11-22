# Junie brief: step 5e part 1, the matchup backend (no UI)

**Model:** GPT-5.3-codex. **Branch:** `deep-learning` (`git pull` first). Follow `AGENTS.md`. **Don't search the codebase.** Everything you need is in this file. Read only `engine/report.py` (`vs_league`, `pct`), and `api/server.py` lines 64-76 (`envelope`, `filters`) and 125-141 (`_tendencies`). The why is in `JUNIE_STEP5E.md`; this part is only the backend.

**Terminal:** run each command on its own. Never append `; exit $LASTEXITCODE` or any `exit`.

## Files you create or change (nothing else)
1. `engine/matchup.py` (new): pure functions, no database access except `head_to_head`.
2. `api/server.py`: one new endpoint.
3. `tests/test_matchup.py` (new).

## Inputs
The endpoint calls the existing `_tendencies(team_id, map, side, since, until, None)` four times: team A on attack, A on defence, B on attack, B on defence. Each returns an envelope; its `data` is a dict of metric results keyed by metric id, plus `summary` (a list of findings) and `summary_note`. Nothing new is computed from raw tables except head to head.

A `Rate` dict is `{k, n, p, lo, hi, small_sample}`. The field paths below are exact.

## Facing pairs
"X attacks Y" pairs X's attack results (`xa`) with Y's defence results (`yd`). Build the five pairs for A attacks B, then the same five for B attacks A: ten in all.

| `id` | `title` | Attacker measure (from `xa`) | Attacker is better when | Defender measure (from `yd`) | Defender is better when |
|---|---|---|---|---|---|
| `plant_reach` | "Getting the plant down" | `team.post_plant` → `value.plant_share` vs `value.league_plant_share` | higher | `team.retakes` → `value.plants_faced` vs `value.league_plants_faced` | lower |
| `post_plant` | "After the plant" | `team.post_plant` → `value.post_plant_win` vs `value.league_post_plant_win` | higher | `team.retakes` → `value.retake` vs `value.league_retake` | higher |
| `first_blood` | "First blood" | `team.openings` → `value.first_blood` vs `value.league_first_blood` | higher | `team.openings` → `value.first_blood` vs `value.league_first_blood` | higher |
| `dry_duels` | "Dry duels" | `fights.dry_duels` → `value` (`diff`, `lo`, `hi`, `n`, `beyond_noise`) | `diff` > 0 | the same, from `yd` | `diff` > 0 |
| `ecos` | "Ecos against full buys" | `team.economy` → the `breakdown` item with `bucket == "scrappy_vs_full"`: `rate` vs `league` | higher | `team.economy` → the `breakdown` item with `bucket == "full_vs_anti"`: `rate` vs `league` | higher |

### The stance of one measure (write exactly this)

```python
MIN_N = 20

def stance(r, league, higher_is_better=True):
    """+1 beyond noise in this team's favour, -1 beyond noise against it, 0 within noise, None if too few rounds."""
    if not r or r.get("p") is None or (r.get("n") or 0) < MIN_N or r.get("small_sample"):
        return None
    if not league or league.get("p") is None:
        return None
    if r["lo"] <= league["p"] <= r["hi"]:
        return 0
    return 1 if (r["p"] > league["p"]) == higher_is_better else -1

def duel_stance(v):
    if not v or v.get("diff") is None or (v.get("n") or 0) < MIN_N:
        return None
    if not v.get("beyond_noise"):
        return 0
    return 1 if v["diff"] > 0 else -1
```

### The read (write exactly this)

```python
def read(s_att, s_def):
    if s_att is None or s_def is None:
        return "too_few"
    if s_att > s_def:
        return "attacker"
    if s_def > s_att:
        return "defender"
    return "even"
```

Never combine the two numbers into one probability.

### One pair in the response

```python
dict(id=..., title=..., attacker=X_id, defender=Y_id,
     att=dict(p=..., lo=..., hi=..., n=..., league=..., stance=...),
     dfn=dict(p=..., lo=..., hi=..., n=..., league=..., stance=...),
     unit="rate",          # "diff" for dry_duels; then p = diff and league = 0.0
     read="attacker" | "defender" | "even" | "too_few",
     edge=X_id | Y_id | None,      # the team named by read; None for even and too_few
     sentence=...)
```

A missing metric or measure gives `p`, `lo`, `hi` and `n` as `None`, stance `None`, and read `"too_few"`. Never raise.

### Sentences (fill in names and `pct`; `{X}`/`{Y}` are team names)
| `id` | `sentence` |
|---|---|
| `plant_reach` | "{X} plant in {x} of attack rounds (league {lx}); attackers plant in {y} of {Y}'s defence rounds (league {ly})." |
| `post_plant` | "{X} win {x} after planting (league {lx}); {Y} retake {y} of plants (league {ly})." |
| `first_blood` | "{X} get first blood in {x} of attack rounds (league {lx}); {Y} get it in {y} of defence rounds (league {ly})." |
| `dry_duels` | "In dry duels {X} on attack are {dx} points against expected; {Y} on defence are {dy}." (`dx` = `f"{diff*100:+.1f}"`) |
| `ecos` | "{X}'s ecos against a full buy win {x} (league {lx}); {Y}'s full buys against an eco win {y} (league {ly})." |

When a number is `None`, write "too few rounds" in its place.

## Top lines
`top_lines(att_data, def_data, k=3)`: take `summary` from both, add `side` ("attacker" or "defender") to each finding (copy the dict), sort by `score` highest first, keep `k`.

## Head to head
`head_to_head(con, a, b, since=None, until=None, limit=10)`: games between the two teams from the `games` table (`team1_id`, `team2_id` in either order), newest `started_at` first. Columns: `series_id`, `game_id`, `map`, `started_at`, `event`, `stage`, `winner_team_id`. Add each team's rounds won from `team_rounds` (`count(*) FILTER (WHERE won)` grouped by `game_id`, `team_id`). Return dicts: `series_id`, `game_id`, `map`, `date` (ISO date string), `event`, `stage`, `a_rounds`, `b_rounds`, `winner` (team id). Apply `since`/`until` to `started_at` when given.

## The endpoint
```
GET /api/matchup?team_a=&team_b=&map=&since=&until=
```
- `map` is required. Raise 422 when `team_a == team_b`. Unknown teams: call `filters(...)` for each, which raises 404.
- Cache with `@lru_cache(maxsize=128)` on a helper, like `_tendencies`.
- Return `envelope(dict(team_a=dict(id=a, name=...), team_b=dict(id=b, name=...), map=map, pairs=[10 pairs], top=dict(a=[...], b=[...]), head_to_head=[...], note=...))`. Names come from `teams.name`. `note` is "They haven't met in this data." when head to head is empty, else `None`.

## Tests (`tests/test_matchup.py`, hand-built dicts; only head to head uses a tiny in-memory DuckDB)
- `stance`: inside the range gives 0; above the league with higher-is-better gives +1; the same with lower-is-better gives -1; `n` under 20 gives `None`.
- `read`: (+1, 0) is "attacker"; (0, -1) is "attacker"; (+1, +1) is "even"; (None, +1) is "too_few".
- Mirroring: with A's attack strong on `post_plant` and B's defence average, the A-attacks-B pair reads "attacker" with `edge == A`, and the B-attacks-A pair uses B's attack and A's defence results (check `attacker == B`).
- `plant_reach` uses lower-is-better for the defender: a defender facing fewer plants than the league, beyond noise, has stance +1.
- A missing metric gives "too_few" and doesn't raise.
- Head to head returns only games both teams played, newest first, with the right round counts.
- Endpoint: 422 for the same team twice; 404 for an unknown team (use FastAPI's `TestClient` and monkeypatch `filters` if the real store isn't available; skip with `pytest.importorskip` if needed).
- No sentence contains "caused", "always", "exact" or "fault".

## Stop when
`python -m pytest tests -q` passes. Don't run the server or anything long. Don't commit. Add an `AI_SHOWCASE.md` row: "Step 5e part 1 (matchup backend)", naming the model.
