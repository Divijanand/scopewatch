# Junie brief: step 5d part 1, findings backend (no UI)

**Model:** GPT-5.3-codex. **Branch:** `deep-learning` (`git pull` first). Follow `AGENTS.md`. **Don't search the codebase.** Everything you need is in this file and the files named below. Read only `engine/metrics/core.py` (`Rate`, `REGISTRY`), `engine/metrics/tempo.py` and `api/server.py` lines 120-140 (`_tendencies`). The why is in `JUNIE_STEP5D.md`; this part is only the backend.

## Files you create or change (nothing else)
1. `engine/report.py` (new)
2. `engine/metrics/tempo.py`: one new field
3. `api/server.py`: `_tendencies` adds the summary
4. `tests/test_report.py` (new)

## The shared rule (write once, in `report.py`)
A `Rate` dict is `{k, n, p, lo, hi, small_sample}`.

```python
def vs_league(r, league):
    """Beyond noise when the league rate is outside the team's range. Score = gap in half-range widths."""
    if not r or not league or r.get("p") is None or league.get("p") is None or r.get("small_sample"):
        return None
    if r["lo"] <= league["p"] <= r["hi"]:
        return None
    half = max((r["hi"] - r["lo"]) / 2, 1e-6)
    return abs(r["p"] - league["p"]) / half
```

`pct(x)` = `f"{round(x * 100)}%"`. Every headline contains the team's number, the league's and "(likely lo-hi%)".

## Findings, metric by metric (results are the `to_dict()` dicts already computed in `_tendencies`)
Each finding is a dict with these keys:
- `id`, `metric`, `title`, `headline`, `prepare`;
- `team`, `league` (as fractions), `n`, `lo`, `hi`, `score`;
- `evidence`: `{"metric": ..., "label": ...}`.

| Metric | Where to look | Title | Headline (fill in numbers) | Prepare line |
|---|---|---|---|---|
| `att.executes` | each `breakdown` item: `rate` vs `league`, site in `site` | "Site choice" | "They plant on {site} in X of attack rounds (likely a-b), league Y." | higher: "Expect {site}: they go there more than most teams." lower: "{site} is rare for them: they mostly go elsewhere." |
| `util.recon_timing` | `value.before_league_median` vs `{"p": 0.5}` (the new field below) | "Recon timing" | "Their first recon comes before the league's median time in X of rounds (likely a-b), against half for the league." | earlier: "Plan for an early dart: their timing is built on it." later: "Their first recon comes late: early pressure meets them before their info." |
| `util.recon_timing` | `value.late` vs `value.on_time`: a finding only when the ranges don't overlap; score = gap / mean half-width | "When recon comes late" | "When their first recon comes late they win X (likely a-b), against Y on time." | "Deny or delay their first recon." (only when late is lower) |
| `fights.dry_duels` | `value`: `diff`, `lo`, `hi`, `beyond_noise` (already computed); score = abs(diff) / ((hi - lo) / 2) | "Dry duels" | "With no utility around they win {abs(diff)*100:.1f} points {more/fewer} fights than the opener advantage predicts (likely a to b)." | more: "Don't take even dry duels: use utility first." fewer: "Their players lose dry duels: take the fight without utility." |
| `fights.dry_duels` | `breakdown` items with `bucket == "agent"` and `beyond_noise` | "Duels on {Agent}" | the same, for the agent | the same wording, naming the agent |
| `team.predictability` | `breakdown` items with `percentile >= 80` and not `small_sample`: `rate` vs `{"p": league_median}` | "Predictable: {label}" | "{label}: they pick {choice} in X of rounds (likely a-b), more predictable than {percentile}% of teams." | "Prepare for {choice}." |
| `op.wpa` | `value.mean`, `lo`, `hi` vs `league_mean` (points, not rates): beyond when `league_mean` is outside `[lo, hi]`; score = gap / half-range | "Operator value" | "An Operator round is worth {mean:+.1f} points of round-win chance to them (likely lo to hi), league {league_mean:+.1f}." | higher: "Their Operator is a real threat: plan to trade it or deny it." lower: "Their Operator costs them more than most: bait it." |
| `team.retakes` | `value.retake` vs `league_retake`; `value.plants_faced` vs `league_plants_faced` | "Retakes" / "Plants against them" | "They retake X of plants they face (likely a-b), league Y." / "Attackers plant in X of their defence rounds (likely a-b), league Y." | low retake: "Get the plant down: they rarely retake." high: "Plant safely: they retake well." / higher plant share: "Their site holds break: the plant goes down." |
| `team.post_plant` | `value.post_plant_win` vs `league_post_plant_win`; `value.pre_plant_losses` vs `league_pre_plant_losses` | "Post-plant" / "Where their attack fails" | "They win X after planting (likely a-b), league Y." / "X of their attack losses come with no plant (likely a-b), league Y." | low post-plant win: "Retake them: their post-plant is weak." / more pre-plant losses: "Hold the site entrance: their attack fails before the plant." |
| `team.economy` | `value.pistol` vs `league_pistol`; `value.bonus` vs `league_bonus`; `breakdown` items `rate` vs `league` (labels: full_vs_full "full buys against full buys", full_vs_anti "full buys against an eco or half", scrappy_vs_full "ecos and half buys against a full buy") | "Pistols" / "Bonus rounds" / "Buy rounds" | "They win X of pistol rounds (likely a-b), league Y." (and similar) | pistol high: "Their pistol rounds are strong: have a plan for the bonus." scrappy high: "Their ecos are dangerous: don't over-peek on anti-ecos." |
| `team.openings` | `value.first_blood`, `win_after_first_blood`, `win_after_first_death` vs `league_*` | "First blood" / "After first blood" / "After a first death" | "They get first blood in X of rounds (likely a-b), league Y." (and similar) | high first blood: "Expect early aggression: they take first contact." low win after first blood: "They don't convert first blood: stay calm after an early loss." high win after first death: "They come back from first deaths: don't relax after first blood." |
| `team.closing` | `value.comebacks` vs `league_comebacks`; `value.throws` vs `league_throws` | "Comebacks" / "Closing rounds" | "From a win chance of 20% or lower they come back in X (likely a-b), league Y." / "From 80% or higher they lose X (likely a-b), league Y." | high comebacks: "Close rounds out: they come back." high throws: "Keep pressure on: they let rounds slip." |

Skip a template when its direction has no prepare line in the table.

## `summarize(results: dict, side: str | None, k: int = 5) -> tuple[list[dict], str | None]`
- Run every function above on the results present, ignoring any metric that's missing or has no value.
- Sort by score (highest first); break ties by this metric order: `att.executes`, `util.recon_timing`, `team.retakes`, `team.post_plant`, `team.economy`, `team.openings`, `op.wpa`, `fights.dry_duels`, `team.predictability`, `team.closing`.
- Keep at most 2 per metric and at most `k` in total.
- If none: return `([], "Nothing stands out beyond noise on this map and side: they play close to the league average.")`.

## The new field in `tempo.py`
In `recon_timing`, after the league baseline is known: `before_league_median = Rate.of(rounds whose first recon is before the league median, rounds with a recon)`. Add it to `res.value`, and add one line to `tests/test_tempo.py` checking it.

## API
In `_tendencies`, after the loop: `summary, note = report.summarize(results, side)`. Add `summary` and `summary_note` to the data passed to `envelope` (keep the existing keys unchanged). Check `web/src/api.ts` still typechecks (`cd web && npx tsc -b`). Don't change any UI file in this part.

## Tests (`tests/test_report.py`, hand-built dicts only)
- A rate whose range contains the league rate gives no finding; one whose range excludes it gives a finding.
- At most 5 findings and at most 2 per metric; ordered by score, with ties by the metric order.
- No findings gives the note.
- Every headline contains the team's number and the league's.
- No headline or prepare line, for any template, contains "caused", "always", "exact" or "fault". Build one finding per template to check.

## Stop when
`python -m pytest tests -q` passes and `npx tsc -b` passes. Don't run the server or anything long. Don't commit. Add an `AI_SHOWCASE.md` row: "Step 5d part 1 (findings backend)", naming the model.
