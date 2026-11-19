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
| 2026-11-18 | Junie | Review fixes: post-round kills no longer leak the label (test log loss 0.3757 → 0.3794, the expected small drop), linear row building, dead SQL removed, split moved into a tested function, calibration shows mean predicted vs actual | `3ac136b` |
| 2026-11-18 | Claude Code (second review) | Retrained independently: report reproduces exactly; 58 tests pass. Two test-quality issues left for the next Junie task | `3ac136b` |
| 2026-11-18 | Junie | Operator value (WPA): fit/load/predict API, event scoring, holder WPA, series bootstrap, metric, tests | `0ab7120` |
| 2026-11-18 | Claude Code (review of Junie) | Found: metric never registered (the API would fail on restart), 2–2.7 s per call, player filter ignored, an empty test | sent back to Junie |
| 2026-11-18 | Junie | Fixes: registered, precomputed holder WPA (0.14–0.19 s), player filter, real logic test with a stub model, deterministic event order | `0ab7120` |
| 2026-11-18 | Claude Code (integration) | Credited Tour de Force in WPA, rebuilt the scores, made every ranking deterministic (repeat loads differed on ties), cached reports per filter | `2910dbe` |
| 2026-11-18 | Claude Code | Operator value in the report: headline in points of round-win chance, league comparison, range scale, per-player values | `3ab0119` |
| 2026-11-18 | Claude Code | Ultimates: 10 s window value vs league, enemy-ult Operator deaths, Ultimates layer; vectorised Junie's bootstrap (same resamples, ~100x faster) | `5f4af7e` |
| 2026-11-18 | Claude Code | Predictability score: best-guess share per habit against every team on the map and side | `4fb9f43` |
| 2026-11-18 | Claude Code | Password-protected demo container and deploy guide; production build exposed a weak typecheck command and a real callout-selection bug, both fixed | `ef4b1fe` |
| 2026-11-19 | Claude Code | Deployed to Fly.io: read the installer before running it, set the password through a masked prompt piped to `fly secrets import` (never on screen), scaled to one machine, checked every path returns 401 on the live site | `9e5b1e7` |
| 2026-11-19 | Claude Code | `deep-learning` branch: ML taxonomy (tasks, feature availability measured on the corpus, measures, limits, splits, synthetic-data policy), roadmap, evaluation module; first official T1 numbers reproduce Junie's report exactly | `41708b3` |

## What we learned working with Junie

Our honest experience, as feedback for JetBrains. Junie ran inside PyCharm 2025.3 on the hackathon's JetBrains AI Ultimate licence, as the "Junie" agent in AI Assistant → Agents. Model: _fill in from Junie's settings_.

### How we worked
Every Junie task was a **written brief**: goal, files, constraints, what "done" means, and the exact checks to run. Junie followed the project's `AGENTS.md` (data-licence rules, test and doc checklist). **Claude Code reviewed every result** against the brief, by reading the diff, running the tests and **re-running the outputs independently**. Findings went back to Junie as the next brief. Three features went through this loop:

| Junie task | Review rounds | What review caught | Outcome |
|---|---|---|---|
| Round win-probability model | 2 | Label leakage (kills after the round was decided became training rows); a per-round loop scanning the whole kill table; dead half-written SQL; a test that exercised scikit-learn instead of our code | Fixed by Junie. An independent retrain reproduced its report byte for byte. Test log loss 0.379 vs 0.410 for the baseline, calibration error 0.005 |
| Operator value (win probability added) | 2 | The metric was never registered, so the API would have crashed on its next restart; 2–2.7 s per call; the player filter ignored; an empty placeholder test | Fixed by Junie: registered, precomputed (0.14–0.19 s), filtered, with a real logic test on a stub model |
| Follow-up fixes on both | – | A test that printed "Wrote 2 events" looked like it had overwritten real data; on inspection it had safely mocked the write (our false alarm) | No change needed; recorded honestly |

### What Junie was good at
- **Turning a precise brief into a complete first version fast**: model, split, evaluation report, tests and a PyCharm run configuration in one pass.
- **Following project rules it was given.** It never committed data, kept fixtures synthetic, and used the run configurations.
- **Taking review feedback well:** every listed issue in a fix brief was addressed, and its numbers were reproducible.

### Where review mattered
- **"Done" isn't "wired in".** The biggest miss was code that worked in isolation but wasn't connected (the unregistered metric). Tests that import a module directly didn't notice. We now have a test that every metric the report uses is registered.
- **Tests that pass without testing anything.** Twice a test checked a library rather than our code, or was an empty `pass`. Briefs now name the behaviour each test must prove.
- **Performance isn't in the brief unless you put it there.** The first WPA version was correct but 10× too slow for a live report. Briefs now state a time budget (e.g. "under 0.3 s").
- **Our own rules can be wrong.** `AGENTS.md` told agents to typecheck with a command that turned out not to check the app files at all. The production build exposed it, along with a real UI bug, and we fixed the rule for Junie and for us. The agent's rule file is code too, and needs review.

### Friction we hit
- **The Junie agent's first install was broken on Windows.** Its bundled Java runtime was extracted without its `lib` folder (`could not open ...\runtime\lib\jvm.cfg`). Reinstalling from settings reused the broken folder. Deleting `%LOCALAPPDATA%\JetBrains\acp-agents\junie\<version>` and installing again fixed it.
- **Licensing took a few tries:** a student licence can't host AI Ultimate, so we switched PyCharm to the hackathon All Products Pack subscription first.

### What we'd tell other teams
Write briefs like tickets for a strong new teammate: exact files, a definition of done, numbers to hit, and checks to run. Then review the output the way you'd review a person's pull request: run it, reproduce its numbers, and look for what isn't connected. Junie plus a reviewing agent with a written rulebook got us further, faster, than either alone.
