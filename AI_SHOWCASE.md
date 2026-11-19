# How AI and JetBrains tools built Scopewatch

A running log, written as the work happens. Each entry names the tool, the task, and what changed, with the commit.

## Tools
- **Claude Code** (Anthropic): engine v1–v2, metrics, map calibration, UI, docs. Commits are co-authored.
- **PyCharm**: shared run configurations are in the repo; _usage to be logged as it happens._
- **Junie** (in PyCharm, JetBrains AI Ultimate): builds features from a written task and follows `AGENTS.md`; Claude Code reviews its output.
- **JetBrains Air**: _to be logged._

## Log

| Date | Tool | Task | Result |
|---|---|---|---|
| 2026-11-17 | Claude Code | Engine v2: reversal-safe ingest, metric registry, evidence API and UI | `21ef371` |
| 2026-11-18 | Claude Code | In-game minimaps with landmark calibration | `4874190` |
| 2026-11-18 | Claude Code | Callout-based findings, VOD links, Operator gamble, site executes | `cd81af1`, `c2de0a9`, `e5a351d` |
| 2026-11-18 | Claude Code | PyCharm run configurations, AGENTS.md for Junie/Air | `2d4b96f` |
| 2026-11-18 | PyCharm | Clean project venv exposed missing Pillow/scipy in requirements.txt; fixed | `5679dcd` |
| 2026-11-18 | Junie | Round win-probability model: features, series split, gradient boosting vs logistic baseline, calibration report, tests, run configuration | `0096f50` |
| 2026-11-18 | Claude Code (review of Junie) | Found label leakage from post-round kills, a slow per-round loop, dead SQL, and a split test that tested scikit-learn instead of our code; sent back to Junie as a follow-up task | `0096f50` (issues listed) |
| 2026-11-18 | Claude Code | Utility view: setup heatmaps with aim ticks, callout findings, ability filters | `88034bc` |
| 2026-11-18 | Junie | Review fixes: post-round kills no longer leak the label (test log loss 0.3757 → 0.3794, the expected small drop), linear row building, dead SQL removed, split moved into a tested function, calibration shows mean predicted vs actual | _this commit_ |
| 2026-11-18 | Claude Code (second review) | Retrained independently: report reproduces exactly; 58 tests pass. Two test-quality issues left for the next Junie task | `3ac136b` |
| 2026-11-18 | Junie | Operator value (WPA): fit/load/predict API, event scoring, holder WPA, series bootstrap, metric, tests | `0ab7120` |
| 2026-11-18 | Claude Code (review of Junie) | Found: metric never registered (the API would fail on restart), 2–2.7 s per call, player filter ignored, an empty test | sent back to Junie |
| 2026-11-18 | Junie | Fixes: registered, precomputed holder WPA (0.14–0.19 s), player filter, real logic test with a stub model, deterministic event order | `0ab7120` |
| 2026-11-18 | Claude Code (integration) | Credited Tour de Force in WPA, rebuilt the scores, made every ranking deterministic (repeat loads differed on ties), cached reports per filter | `2910dbe` |
| 2026-11-18 | Claude Code | Operator value in the report: headline in points of round-win chance, league comparison, range scale, per-player values | `3ab0119` |
| 2026-11-18 | Claude Code | Ultimates: 10 s window value vs league, enemy-ult Operator deaths, Ultimates layer; vectorised Junie's bootstrap (same resamples, ~100x faster) | `5f4af7e` |
| 2026-11-18 | Claude Code | Predictability score: best-guess share per habit against every team on the map and side | _this commit_ |
