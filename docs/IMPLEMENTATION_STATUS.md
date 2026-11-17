# Implementation status

Working, partial, and planned items. Only "Working" items are claimed anywhere else (README, Devpost story, video).

## Working (v1 prototype)

| Item | Evidence |
|---|---|
| Streaming extraction of all 857 VALORANT series, 10 workers, ~20 min | 857 ok / 0 failed (`cache_extract.log`) |
| Tables: loadouts, rounds, engagements, casts, spawns; rolled-back *maps* dropped via `meta/games.csv` | Row counts printed by `pipeline.build` |
| Data-drawn map outlines for 12 maps | Haven outline shows lanes, courtyard, walls (visual check) |
| Operator team profile with Wilson intervals | Checked by hand on Sentinels / Cloud9 / Cloud9 GC (Lotus) |
| FastAPI + React UI: team, map, side filters; sightline map; findings column | Browser check 2026-11-17 |

## Known gaps in v1 (fixed by engine v2)

1. In-game reversals (`!` events) not undone (DATA_CAPABILITIES): reversed kills, hits and rounds count.
2. No source manifest, parser version, reconciliation counts or quarantine; re-runs overwrite silently.
3. Round clock has only buy-phase end; no plant clock or phase (pre-plant / post-plant).
4. Metrics are ad-hoc SQL in `profile.py`: no registry, version, eligibility rule, or unknown counts.
5. No evidence drill-down (supporting / contrary rounds), no round context.
6. No tests or synthetic fixtures.
7. Position freshness not tracked.

## Engine v2 plan

Gates follow the master spec §20.

### Gate A: evidence and capability (in progress)
- [x] Source register, dataset commit
- [x] Sample capability audit (40 stratified series) → DATA_CAPABILITIES.md
- [x] First branch decision (D-001)
- [ ] Full-corpus audit counts produced by the v2 ingest itself

### Gate B: canonical data
- `engine/ingest`: series reducer as an explicit state machine (game → round → phase), LIFO reversal undo, plant/defuse phase, freshness flags, per-series reconciliation counts (input events, accepted, reversed, excluded with reason), quarantine for malformed records.
- `engine/schema.py`: typed Arrow schemas for canonical tables, with nullable fields and explicit unknowns.
- Source manifest: file checksum, dataset commit, parser version. Re-import is idempotent (skip unchanged series).
- Synthetic fixtures (hand-written, never copied from the corpus) + pytest for reversals, restarts, side swaps, overtime, phase clocks, duplicate team names.

### Gate C: working coaching slice
- `engine/metrics`: a registry of versioned metric definitions (id, version, population, numerator, denominator, unknowns, unit).
- Evidence API: every result returns its round keys; drawer with supporting and contrary rounds; round timeline view.
- Coverage panel per filter (rounds, maps, dates, patches, quality, exclusions).
- Typed response envelope: `data, coverage, warnings, definition_version, dataset_revision, filter_hash`.

### Gate D: submission quality
- Utility branch: placeable-ability origins (trapwires, alarm bots, Vyse walls, Chamber trips first), aim arrows labelled "cast aim direction", quality-policy toggle.
- Saved scouting cards with notes (separate SQLite, not the analytical DuckDB), packet export.
- Cohort comparison (recent vs older, map vs map) and Cloud9 self-scout.
- Playwright run of the core journey; performance measured.

### Gate E/F: differentiator and submission
- Pick one: anti-strat hypothesis cards, or setup-change detection.
- Methodology, validation report, AI_SHOWCASE.md, demo script, judged build behind a login (D-003).
