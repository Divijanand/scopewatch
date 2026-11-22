# Implementation status

Working, partial, and planned items. Only "Working" items are claimed anywhere else (README, Devpost story, video).

## Working (engine v2)

| Item | Evidence |
|---|---|
| Streaming ingest of all 857 series with an undo stack for reversals, phase clocks (buy, pre/post-plant, post-round), position-repeat flags, cast quality policy | `engine/ingest`; 857 ok / 0 failed; 83 tests in total |
| Source manifest: per-series checksums, parser version, dataset commit, reconciliation counts; idempotent re-runs; quarantine of malformed lines | `cache/v2/manifest.parquet`; re-run skips unchanged series; `test_malformed_lines_are_quarantined_not_fatal` |
| Analytical store with round facts (win type, plant), team rounds with `inventory_known`, opening kills, spawns | `engine/store.py` |
| Metric registry: 16 versioned metrics (12 Operator, 1 execute, 1 utility, 1 ultimates, 1 predictability) with n/N, unknowns, Wilson intervals, supporting/contrary round keys | `engine/metrics`; 6 contract tests on hand-built tables; `docs/METRICS.md` generated from code |
| Coverage report per filter (rounds, dates, patches, unknown inventory, retracted records, position repeats, cast quality) | `engine/coverage.py` |
| API response times under the 500 ms goal (0.24–0.48 s) | VALIDATION.md, Performance |
| API with envelopes (`data, coverage, warnings, definition_versions, dataset_revision, parser_version, filter_hash`): catalog, coverage, tendencies, spatial layer, paginated evidence, round context | `api/server.py`; endpoint check on real data |
| UI: findings with sample sizes and ranges, "Show the rounds" evidence drawer (supporting / contrary), round timeline, "How this is measured", coverage strip, player and time filters linked to the map | Browser check 2026-11-17: Cloud9, Lotus defense, OXY 12 of 15 Operator rounds → 12 rounds → round 30 timeline |
| Utility view: setups, smokes, flashes and stuns, and recon as a heatmap of cast positions with aim ticks; findings in callout language with round counts; filter by ability or by spot; rounds behind each spot | `engine/metrics/utility.py`, `web/src/Utility.tsx`; `tests/test_utility.py`; browser check 2026-11-18, Sentinels Haven defense: Zellsis's Cyber Cage at C Site in 27 of 62 rounds |
| Round win-probability model (built by Junie): gradient boosting against a logistic baseline, split by series; test log loss 0.379 vs 0.410 | `engine/model/winprob.py`, `docs/MODEL_WINPROB.md`; review fixes applied by Junie (no post-round leakage, linear row building); test log loss 0.379 vs 0.410 baseline, report reproduces on retrain |
| Operator value (WPA, built by Junie): every sniper kill (Operator, Outlaw, Tour de Force) is credited with ΔWP and every holder death is charged; team, league and player means, 90% series-bootstrap intervals for n ≥ 10 | `engine/model/wpa.py`, `engine/metrics/value.py`; `tests/test_wpa.py`; 323,903 events and 18,779 holder rounds scored; 0.14–0.19 s per call. Shown first in the Operator report with a range scale and per-player values (most rounds first; one-round players get no range); browser check 2026-11-18, Cloud9 Lotus defense: −3.3 points (likely −11.2 to +6.3) vs +2.3 league |
| Hosted demo build: password on every path but /health, refuses to start without a password, noindex, one container (API + built web app), data bundle script, Fly.io config, background warm-up of Cloud9 views | `api/auth.py`, `Dockerfile`, `fly.toml`, `scripts/bundle_demo.py`, `docs/DEPLOY.md`; `tests/test_auth.py`; local run from the bundle checked route by route. **Live at https://scopewatch-c9.fly.dev** since 2026-11-19 (one machine); without the password every path except /health returns 401 on the live site; owner login confirmed |
| Predictability score: for four habits, how often an opponent's best guess would be right, compared with every team on the map and side; overall score; rounds behind each habit | `engine/metrics/predictability.py`; `tests/test_predictability.py`; browser check 2026-11-18, Cloud9 Lotus attack: 25 (A site 55 of 120 vs typical 47%) |
| Ultimates: usage per ult (rounds with that agent, timing, after a plant), kills, deaths and win-chance swing in the 10 s after, league comparison and range; Ultimates map layer; Operator deaths during an enemy ult | `engine/metrics/ultimates.py`, `op.how_it_dies` v2; `tests/test_ultimates.py`; browser check 2026-11-18, Cloud9 Lotus attack: Fade ult −16.3 (−27.8 to −4.7) vs league 0.0 |
| Every agent's whole kit in the Utility view: all 111 abilities classified by what their position means (placed, landing, direction, thrown, self, unplaced) | `engine/abilities.py` MODE, `engine/metrics/utility.py`; `tests/test_utility.py`; browser check 2026-11-18, Sentinels Sova on Haven defense |
| Weaponless kills filled from the matching damage event: 10,853 of 10,976 (Tour de Force 2,205, ult and ability kills); 123 stay unknown | `engine/weapons.py`, run in `engine/store.py`; `tests/test_weapons.py` |
| Deterministic rankings: ties broken by name everywhere, no SQL mode(); repeat runs give identical reports | `engine/metrics/core.ranked`; `test_ranking_breaks_ties_by_name_not_by_arrival_order` |
| Report cache: one computation per filter while the server runs (about 1 s first load, 0.2 s after) | `api/server.py` `_tendencies` |
| Site executes on attack: site share vs league, pace, site-entry time and callouts, utility before the plant (per round and by ability), how defending Operators fared | `engine/metrics/executes.py`; `tests/test_executes.py`; browser check 2026-11-18, Cloud9 Lotus attack: A in 55 of 155, entry ~24 s at A Main/A Root, defending Operators died without a kill in 7 of 9 |
| Recon timing (`util.recon_timing`): the team's first recon (recon set now includes Skye's dog), league comparison, recon-to-plant and recon-to-first-fight on attack, round win rate when first recon is late or missing | `engine/metrics/tempo.py`; `tests/test_tempo.py`; card checked in the browser 2026-11-21 on one team, map and side (both sides), about 2 s per cold request |
| Dry duels (`fights.dry_duels`): fights with no utility around, actual minus the league's opener rate for the same state, by who opened and by the team's agent, with series-bootstrap ranges; league agent-pair table in `docs/AGENT_DUELS.md` | `engine/metrics/duels.py`, `engine/model/fights.py` (writes git-ignored `cache/v2/models/fights.parquet`), `scripts/agent_duels.py`; `tests/test_duels.py`; card checked in the browser 2026-11-21 |
| Team fundamentals (`team.retakes`, `team.post_plant`, `team.economy`, `team.openings`, `team.closing`): each against the league with Wilson ranges, by numbers at the plant where it applies; league tables by map in `docs/LEAGUE_FUNDAMENTALS.md` | `engine/metrics/fundamentals.py`, `scripts/league_fundamentals.py`; `tests/test_fundamentals.py`; cards checked in the browser 2026-11-22 on one team and map, both sides; about 0.2 s per request once league numbers are cached |
| VOD links: paste a VOD and time one round; every round and kill in that map gets a watch link (YouTube/Twitch open at the second); re-time at any round | `engine/vod.py`, `/api/vod/*`; `tests/test_vod_gamble.py`; browser check 2026-11-18 (test link synced at round 23, then removed) |
| The Operator as a gamble: what it buys (kept / traded / lost, with league share), escapes after a kill (movement abilities, per agent), how it gets broken (flash/stun, smoke, swarmed, duel) | `engine/metrics/gamble.py`, `engine/abilities.py`; browser check: Cloud9 Lotus defense loses it without an Operator kill in 9 of 15 rounds vs 36% league |
| Findings in callout language: where the first Operator shot is taken (with league share) and where the holder dies; callout names on the map; click a callout to show those rounds | `engine/callouts.py`, `engine/metrics/setups.py`; `tests/test_callouts.py`; browser check 2026-11-18, G2 Lotus defense: C Main in 7 of 24 rounds |
| In-game minimaps with versioned transforms; all 13 maps pass the landmark check; uncalibrated maps flagged in the UI | `engine/minimaps.py`, `config/maps/`; MAP_CALIBRATION.md; browser check of Lotus and Haven 2026-11-18 |

## Partial


## Not started (claim one by adding your name)

**Must-have for the submission (pass/fail)**
- Demo video, 3 minutes, public on YouTube, no copyrighted music. Owner: _unclaimed_
- Devpost write-up: story, which JetBrains tools did what, methodology. Owner: _unclaimed_
- Before judging (Jan 27): keep one demo machine running (`min_machines_running = 1`); judges' login in Devpost's judges-only field. Owner: _unclaimed_

**Features and evidence**
- Next-round predictor (site, Operator buy) with small samples pulled toward the league, tested against "always guess their most common choice". Owner: _unclaimed_
- Deep-learning comparison: a sequence model against the gradient-boosted win-probability model on held-out series; ship only if it wins. Owner: _unclaimed_
- vlr.gg cross-check by hand: about 20 maps' kills and rounds against public scoreboards, written up in VALIDATION.md. Owner: _unclaimed_
- Saved scouting cards with notes, and a one-page packet export per map. Owner: _unclaimed_
- Recent-vs-older comparison and a date-range filter in the UI. Owner: _unclaimed_
- Playwright run of the core journey. Owner: _unclaimed_
- Miks's abilities classified (they show as "used from" until then). Owner: _unclaimed_

## Retired

`pipeline/` (v1 prototype) stays for reference and for `pipeline.maps.render`, which v2 reuses. v1 didn't undo in-game reversals.
