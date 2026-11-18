# Implementation status

Working, partial, and planned items. Only "Working" items are claimed anywhere else (README, Devpost story, video).

## Working (engine v2)

| Item | Evidence |
|---|---|
| Streaming ingest of all 857 series with an undo stack for reversals, phase clocks (buy, pre/post-plant, post-round), position-repeat flags, cast quality policy | `engine/ingest`; 857 ok / 0 failed; 33 tests in total |
| Source manifest: per-series checksums, parser version, dataset commit, reconciliation counts; idempotent re-runs; quarantine of malformed lines | `cache/v2/manifest.parquet`; re-run skips unchanged series; `test_malformed_lines_are_quarantined_not_fatal` |
| Analytical store with round facts (win type, plant), team rounds with `inventory_known`, opening kills, spawns | `engine/store.py` |
| Metric registry: 6 versioned Operator metrics with n/N, unknowns, Wilson intervals, supporting/contrary round keys | `engine/metrics`; 6 contract tests on hand-built tables; `docs/METRICS.md` generated from code |
| Coverage report per filter (rounds, dates, patches, unknown inventory, retracted records, position repeats, cast quality) | `engine/coverage.py` |
| API response times under the 500 ms goal (0.24–0.48 s) | VALIDATION.md, Performance |
| API with envelopes (`data, coverage, warnings, definition_versions, dataset_revision, parser_version, filter_hash`): catalog, coverage, tendencies, spatial layer, paginated evidence, round context | `api/server.py`; endpoint check on real data |
| UI: findings with sample sizes and ranges, "Show the rounds" evidence drawer (supporting / contrary), round timeline, "How this is measured", coverage strip, player and time filters linked to the map | Browser check 2026-11-17: Cloud9, Lotus defense, OXY 12 of 15 Operator rounds → 12 rounds → round 30 timeline |
| Versioned map transforms and landmark calibration; uncalibrated maps flagged in the UI | `config/maps/`; MAP_CALIBRATION.md; browser check of the Summit warning |

## Partial

- Utility branch: casts are ingested with a quality policy (1.5M rows) but there are no metrics or UI yet.
- `engagement_weapon_unknown`: 11,024 damage/kill events have no weapon source (likely ability damage); not yet characterised.

## Not started (planned, Gates D–F)

- Utility metrics and map layer (placeable-ability origins first; aim arrows labelled "cast aim direction").
- Saved scouting cards with notes (separate SQLite) and packet export.
- Cohort comparison (recent vs older) and a time-range filter in the UI.
- Playwright run of the core journey.
- Judged build behind a login (D-003), methodology, AI_SHOWCASE.md, demo script.

## Retired

`pipeline/` (v1 prototype) stays for reference and for `pipeline.maps.render`, which v2 reuses. v1 didn't undo in-game reversals.
