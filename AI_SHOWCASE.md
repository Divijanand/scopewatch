# How AI and JetBrains tools built Scopewatch

A running log, written as the work happens. Each entry names the tool, the task, and what changed, with the commit.

## Tools
- **PyCharm 2025.3** (hackathon All Products Pack): the project's IDE. Every pipeline step is a **shared run configuration** in `.idea/runConfigurations/` (12 so far: ingest, store, maps, minimaps, API, web dev, tests, win-probability training, Operator value, and one per ML evaluation). A teammate cloning the repo gets the whole pipeline as one-click runs. The clean project interpreter caught missing dependencies on day one.
- **Junie** (JetBrains AI Ultimate, in PyCharm's AI Assistant → Agents): built four features or ML steps from written briefs (`docs/briefs/`), following `AGENTS.md` and `.junie/guidelines.md`. Model: Junie's default until 2026-11-19, then **GPT-5.3-codex**. Every task and review round is logged below.
- **Claude Code** (Anthropic): engine, metrics, map calibration, UI and docs; wrote Junie's briefs and reviewed every Junie result. Commits are co-authored.
- **JetBrains Air**: not used yet. Organisers confirmed in the hackathon Discord that Air can run Junie, Codex and Claude Code side by side over ACP; if we use it, it's logged here.

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
| 2026-11-19 | Junie (GPT-5.3-codex) | ML step 4: feature families (role, alive loadout, utility used, ults used, score, map, patch), ablation script, tests, run configuration. Hit its action limit while running the long evaluation itself | `4f0f9dd` |
| 2026-11-19 | Claude Code (review of Junie) | Its baseline (0.3788) didn't match production (0.3778). Traced to counting alive players from the roster, which held phantom entries (no agent, no events). Fixed in the store for everyone (D-021); Junie's fix brief made it reuse the production alive tracker, with a row-for-row parity test | `add0d47`, `4f0f9dd` |
| 2026-11-19 | Claude Code | Re-ran Junie's ablation: no feature family helps beyond noise; features match production on all 323,903 states | `ee48193` |
| 2026-11-20 | Junie (GPT-5.3-codex) | Step 4b, first pass: charge estimates only, then re-ran the step 4 evaluation the brief said not to, and stopped | sent back |
| 2026-11-20 | Claude Code (review) | Found that **our own brief** was wrong: the "reusable" rule (share above the 95th percentile > 5%) can't fire by construction. Also found abilities logging several events per use (Neon's High Gear up to 124 a round). New brief with both fixes | `31f3a35` |
| 2026-11-20 | Junie (GPT-5.3-codex) | Step 4b, second pass: utility-remaining implementation: charge estimation with 1.0s cast merge + reusable rule update, remain features, synthetic tests, and PyCharm run configuration; review added a written verdict and 4 rule tests. Result: no gain beyond noise | `b69fde0`, `fe8b11f` |
| 2026-11-20 | Junie (GPT-5.3-codex) | Step 4c implementation: fight-level builder with pre-fight utility windows, synthetic leakage tests, and `eval_fights` script + run configuration wiring. Junie stopped at its action limit before evaluating. Review: builder rewritten to run once in 3 min (was 30+), fixed same-millisecond kill ordering that lost ~7,500 fights, categorical columns that would have crashed the model, per-side instead of per-team coach table, and kept per-team numbers out of the repo. Result: utility before a fight helps beyond noise | `ea0d56d` + review commit after it |
| 2026-11-21 | Junie (GPT-5.3-codex) | Step 5: round simulator, synthetic-weight experiment, stress tests, tests and run configurations. Step 5b: recon timing and dry duel metrics, both cards, the fights file, Skye's dog added to recon. Stopped at its action limit before the agent-pair script and two run configurations | step 5 and 5b commits |
| 2026-11-22 | Junie (GPT-5.3-codex) | Step 5c: the five fundamentals metrics (about 500 lines), rule tests, API wiring and first cards. Hit its action limit twice; stopped before the league script | step 5c Junie commit |
| 2026-11-22 | Claude Code (review) | Saved Junie's files first, so its work and the review are separate commits. Found: half-against-half could never match, bonus rounds looked up the pistol by map instead of game, league closing rates mixed both teams' views, a test wrote `event_wp.parquet` into the repo root, league numbers came from the real store even in tests, and league numbers were recomputed on every request (now cached, 0.2 s). Cards rewritten to the brief; league script added; league tables explain where a rate is 50% or equal by construction | step 5c review commit |
| 2026-11-21 | Claude Code (review) | Step 5: synthetic rounds had per-row guessed labels ("attackers win if at least as many alive") instead of the round's result, and the kill rate ignored time at risk; simulator rewritten, rule tests added. A new check that w = 0 reproduces production failed and exposed a production model older than the D-021 rebuild: retrained. Step 5b: a team's "first recon" could be the enemy's, dry duels used the opener's side and agent in fights the enemy opened, a test overwrote the real fights file with 3 synthetic rows, and the duel card said "above expected" without a number or range. All fixed; agent-pair table and run configs added. Results: real data alone is best; stress tests pass except a 1v5 late post-plant state | step 5 and 5b commits |
| 2026-11-21 | Claude Code (review) | Lesson for us: we edited Junie's files before saving a copy, so Junie's original step 5/5b work and the review share one commit per step this time | — |
| 2026-11-22 | Junie (GPT-5.3-codex) | Step 5d part 1 (findings backend): backend findings summary scaffold, recon-before-league-median field, tendencies summary wiring, and backend tests | 2f810dc |
| 2026-11-22 | Claude Code (review) | Junie's terminal hung for two hours on a typecheck that takes 8 s (the command ended with `exit`, which likely closed the shell it was waiting on), with 4 of 10 templates written. Committed Junie's work as it was, then added the six missing templates (Operator value, retakes, post-plant, economy, openings, closing). A run on real reports found a crash Junie's synthetic tests missed: a habit with no league percentile (`None`) broke the whole report. Fixed and tested | step 5d part 1 review commit |
| 2026-11-22 | Junie (GPT-5.3-codex) | Step 5d part 2 (Report tab): new Report default tab, summary panel with evidence links, report/operator findings split, and UI wiring/tests checks | 3e9adb1 |
| 2026-11-22 | Claude Code (review) | Step 5d part 2: the app read `data.tendencies`, which the API never sends, so the Report tab would have been empty; the typecheck passed only because the new type matched the bug. Section headings were empty blocks in the wrong order (dry duels under Attack, post-plant under Defence, executes after Closing, two headings doubled). Regrouped the cards for real, moved predictability to the Report tab, shrank the evidence buttons, used en dashes and real minus signs in headlines, and fixed a header overflow at 375 px. Checked in the browser on both sides and at phone width | step 5d part 2 review commit |
| 2026-11-22 | Junie (GPT-5.3-codex) | Step 5e part 1 (matchup backend): matchup backend helpers, `/api/matchup` endpoint, head-to-head query, and contract tests | working tree |

## What we learned working with Junie

Our honest experience, as feedback for JetBrains. Junie ran inside PyCharm 2025.3 on the hackathon's JetBrains AI Ultimate licence, as the "Junie" agent in AI Assistant → Agents. Model: **Junie's default**, the selected option in Settings → Tools → Junie → Models, which JetBrains describes as its best price-performance model. PyCharm's log on both days we used Junie (2026-11-18 and 19) shows that default as `gemini-3-flash-preview`. We didn't switch to any of the frontier models on offer (Claude Opus 4.6, Claude Sonnet 4.6, GPT-5.3-codex, GPT-5.4, GPT-5.2, Gemini 3.1 Pro Preview), and "Think More" was off, so everything above is what the default produced. **From 2026-11-19, Junie runs on GPT-5.3-codex** (chosen for coding, at about 1.5–2× the default's credits). That also makes our review independent: Junie writes with an OpenAI model and Claude Code reviews. Future log entries name the model per task, so the default and the frontier model can be compared.

### How we worked
Every Junie task was a **written brief**: goal, files, constraints, what "done" means, and the exact checks to run. Junie followed the project's `AGENTS.md` (data-licence rules, test and doc checklist). **Claude Code reviewed every result** against the brief, by reading the diff, running the tests and **re-running the outputs independently**. Findings went back to Junie as the next brief. Four tasks went through this loop, plus one round of follow-up fixes:

| Junie task | Review rounds | What review caught | Outcome |
|---|---|---|---|
| Round win-probability model | 2 | Label leakage (kills after the round was decided became training rows); a per-round loop scanning the whole kill table; dead half-written SQL; a test that exercised scikit-learn instead of our code | Fixed by Junie. An independent retrain reproduced its report byte for byte. Test log loss 0.379 vs 0.410 for the baseline, calibration error 0.005 |
| Operator value (win probability added) | 2 | The metric was never registered, so the API would have crashed on its next restart; 2–2.7 s per call; the player filter ignored; an empty placeholder test | Fixed by Junie: registered, precomputed (0.14–0.19 s), filtered, with a real logic test on a stub model |
| ML step 4: richer win-probability features | 2 | A baseline 0.001 off production, traced to phantom roster entries in our own store; Junie had run a several-minute evaluation itself and run out of actions | Store fixed for everyone (D-021); Junie reused the production alive tracker; parity test proves the features match row for row |
| ML step 4b: utility still held | 2 | A rule in **our** brief that couldn't work; repeated cast events; thin tests (one test, checks like "≥ 0") | Junie implemented the corrected brief; review added a written verdict and one test per rule |
| Follow-up fixes on both | – | A test that printed "Wrote 2 events" looked like it had overwritten real data; on inspection it had safely mocked the write (our false alarm) | No change needed; recorded honestly |

### What Junie was good at
- **Turning a precise brief into a complete first version fast**: model, split, evaluation report, tests and a PyCharm run configuration in one pass.
- **Following project rules it was given.** It never committed data, kept fixtures synthetic, and used the run configurations.
- **Taking review feedback well:** every listed issue in a fix brief was addressed, and its numbers were reproducible.

### Where review mattered
- **"Done" isn't "wired in".** The biggest miss was code that worked in isolation but wasn't connected (the unregistered metric). Tests that import a module directly didn't notice. We now have a test that every metric the report uses is registered.
- **Tests that pass without testing anything.** Twice a test checked a library rather than our code, or was an empty `pass`. Briefs now name the behaviour each test must prove.
- **Performance isn't in the brief unless you put it there.** The first WPA version was correct but 10× too slow for a live report. Briefs now state a time budget (e.g. "under 0.3 s").
- **Our own briefs can be wrong too.** In step 4b the reviewer's brief had a rule that couldn't fire; Junie implemented it faithfully. Checking the brief's rules on the real data before sending it is now part of writing one.
- **Our own rules can be wrong.** `AGENTS.md` told agents to typecheck with a command that turned out not to check the app files at all. The production build exposed it, along with a real UI bug, and we fixed the rule for Junie and for us. The agent's rule file is code too, and needs review.

### Friction we hit
- **Action limits and long jobs.** Twice Junie spent its action budget running a several-minute evaluation, and once it did after the brief said not to. Briefs now end with "run the tests only; the reviewer runs the evaluation", and the reviewer runs long jobs in the background.
- **Seeing which model ran.** The Junie panel didn't say which model "default" meant; we found `gemini-3-flash-preview` in PyCharm's log. Showing the model per task in the panel would help teams report honestly.
- **The Junie agent's first install was broken on Windows.** Its bundled Java runtime was extracted without its `lib` folder (`could not open ...\runtime\lib\jvm.cfg`). Reinstalling from settings reused the broken folder. Deleting `%LOCALAPPDATA%\JetBrains\acp-agents\junie\<version>` and installing again fixed it.
- **Licensing took a few tries:** a student licence can't host AI Ultimate, so we switched PyCharm to the hackathon All Products Pack subscription first.

### What we'd tell other teams
Write briefs like tickets for a strong new teammate: exact files, a definition of done, numbers to hit, and checks to run. Then review the output the way you'd review a person's pull request: run it, reproduce its numbers, and look for what isn't connected. Junie plus a reviewing agent with a written rulebook got us further, faster, than either alone.
