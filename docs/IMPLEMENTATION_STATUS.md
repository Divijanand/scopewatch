# Implementation status

Working, partial, and planned items. Only "Working" items are claimed anywhere else (README, Devpost story, video).

## Working (engine v2)

| Item | Evidence |
|---|---|
| Streaming ingest of all 857 series with an undo stack for reversals, phase clocks (buy, pre/post-plant, post-round), position-repeat flags, cast quality policy | `engine/ingest`; 857 ok / 0 failed; 70 tests in total |
| Source manifest: per-series checksums, parser version, dataset commit, reconciliation counts; idempotent re-runs; quarantine of malformed lines | `cache/v2/manifest.parquet`; re-run skips unchanged series; `test_malformed_lines_are_quarantined_not_fatal` |
| Analytical store with round facts (win type, plant), team rounds with `inventory_known`, opening kills, spawns | `engine/store.py` |
| Metric registry: 13 versioned metrics (11 Operator, 1 execute, 1 utility) with n/N, unknowns, Wilson intervals, supporting/contrary round keys | `engine/metrics`; 6 contract tests on hand-built tables; `docs/METRICS.md` generated from code |
| Coverage report per filter (rounds, dates, patches, unknown inventory, retracted records, position repeats, cast quality) | `engine/coverage.py` |
| API response times under the 500 ms goal (0.24–0.48 s) | VALIDATION.md, Performance |
| API with envelopes (`data, coverage, warnings, definition_versions, dataset_revision, parser_version, filter_hash`): catalog, coverage, tendencies, spatial layer, paginated evidence, round context | `api/server.py`; endpoint check on real data |
| UI: findings with sample sizes and ranges, "Show the rounds" evidence drawer (supporting / contrary), round timeline, "How this is measured", coverage strip, player and time filters linked to the map | Browser check 2026-11-17: Cloud9, Lotus defense, OXY 12 of 15 Operator rounds → 12 rounds → round 30 timeline |
| Utility view: setups, smokes, flashes and stuns, and recon as a heatmap of cast positions with aim ticks; findings in callout language with round counts; filter by ability or by spot; rounds behind each spot | `engine/metrics/utility.py`, `web/src/Utility.tsx`; `tests/test_utility.py`; browser check 2026-11-18, Sentinels Haven defense: Zellsis's Cyber Cage at C Site in 27 of 62 rounds |
| Round win-probability model (built by Junie): gradient boosting against a logistic baseline, split by series; test log loss 0.379 vs 0.410 | `engine/model/winprob.py`, `docs/MODEL_WINPROB.md`; review fixes applied by Junie (no post-round leakage, linear row building); test log loss 0.379 vs 0.410 baseline, report reproduces on retrain |
| Operator value (WPA, built by Junie): every sniper kill (Operator, Outlaw, Tour de Force) is credited with ΔWP and every holder death is charged; team, league and player means, 90% series-bootstrap intervals for n ≥ 10 | `engine/model/wpa.py`, `engine/metrics/value.py`; `tests/test_wpa.py`; 323,903 events and 18,779 holder rounds scored; 0.14–0.19 s per call. Not shown in the UI yet |
| Every agent's whole kit in the Utility view: all 111 abilities classified by what their position means (placed, landing, direction, thrown, self, unplaced) | `engine/abilities.py` MODE, `engine/metrics/utility.py`; `tests/test_utility.py`; browser check 2026-11-18, Sentinels Sova on Haven defense |
| Weaponless kills filled from the matching damage event: 10,853 of 10,976 (Tour de Force 2,205, ult and ability kills); 123 stay unknown | `engine/weapons.py`, run in `engine/store.py`; `tests/test_weapons.py` |
| Deterministic rankings: ties broken by name everywhere, no SQL mode(); repeat runs give identical reports | `engine/metrics/core.ranked`; `test_ranking_breaks_ties_by_name_not_by_arrival_order` |
| Report cache: one computation per filter while the server runs (about 1 s first load, 0.2 s after) | `api/server.py` `_tendencies` |
| Site executes on attack: site share vs league, pace, site-entry time and callouts, utility before the plant (per round and by ability), how defending Operators fared | `engine/metrics/executes.py`; `tests/test_executes.py`; browser check 2026-11-18, Cloud9 Lotus attack: A in 55 of 155, entry ~24 s at A Main/A Root, defending Operators died without a kill in 7 of 9 |
| VOD links: paste a VOD and time one round; every round and kill in that map gets a watch link (YouTube/Twitch open at the second); re-time at any round | `engine/vod.py`, `/api/vod/*`; `tests/test_vod_gamble.py`; browser check 2026-11-18 (test link synced at round 23, then removed) |
| The Operator as a gamble: what it buys (kept / traded / lost, with league share), escapes after a kill (movement abilities, per agent), how it gets broken (flash/stun, smoke, swarmed, duel) | `engine/metrics/gamble.py`, `engine/abilities.py`; browser check: Cloud9 Lotus defense loses it without an Operator kill in 9 of 15 rounds vs 36% league |
| Findings in callout language: where the first Operator shot is taken (with league share) and where the holder dies; callout names on the map; click a callout to show those rounds | `engine/callouts.py`, `engine/metrics/setups.py`; `tests/test_callouts.py`; browser check 2026-11-18, G2 Lotus defense: C Main in 7 of 24 rounds |
| In-game minimaps with versioned transforms; all 13 maps pass the landmark check; uncalibrated maps flagged in the UI | `engine/minimaps.py`, `config/maps/`; MAP_CALIBRATION.md; browser check of Lotus and Haven 2026-11-18 |

## Partial


## Not started (planned, Gates D–F)

- Saved scouting cards with notes (separate SQLite) and packet export.
- Cohort comparison (recent vs older) and a time-range filter in the UI.
- Playwright run of the core journey.
- Judged build behind a login (D-003), methodology, AI_SHOWCASE.md, demo script.

## Retired

`pipeline/` (v1 prototype) stays for reference and for `pipeline.maps.render`, which v2 reuses. v1 didn't undo in-game reversals.
