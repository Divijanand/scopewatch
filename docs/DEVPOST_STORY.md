## Inspiration

Before every match, VALORANT coaches scrub hours of VOD to answer the same few questions about the other team's Operator player. Who's on it this map? Do they take an aggressive opening duel or sit back on a passive angle? Does the rifle go to someone else when they're out of money? The Operator decides rounds with one shot, so knowing its habits is one of the highest-value pieces of prep a team can do. It's also one of the most tedious.

The Cloud9 brief asked for exactly this, with one rule we liked: **no chatbot**. Coaches should see the answer and the evidence behind it in seconds. That became our design goal.

## What it does

Scopewatch builds an Operator scouting report for any team in the GRID dataset (VCT Americas, Masters and Game Changers across all regions, 2025–26):

- **Who carries it.** Operator and Outlaw buy rate by side and by team economy, which player and agent carries it, and how the rifle moves between players across a match.
- **Where they fight from.** Every Operator engagement drawn as a shooter→victim line on the map, so a coach sees the *angle* being held, not just a blob. Density shading shows the favourite spots.
- **When.** Engagements bucketed by time since the buy phase ended, separating early aggressive picks from late passive holds.
- **How sure we are.** Every percentage carries its sample, e.g. *"holds A-Main 64% of defensive Operator rounds (n = 47 rounds, 9 maps)"*, so coaches can tell a habit from noise.
- **Filters** for opponent, map, side, player, agent, patch and round-time window.
- _TODO: anti-strat card per opponent + Cloud9 self-scout mode, once built._

## How we built it

**Data pipeline (Python).** GRID ships each series as a compressed event stream, about 160 GB once decompressed for VALORANT alone. We stream every file line by line without ever writing it out uncompressed, and run 10 worker processes in parallel. Each series is reduced to four tables:

- **Loadouts:** one row per player per round at the end of the buy phase: agent, side, money, inventory. This tells us who bought the Operator.
- **Engagements:** every damage and kill event with shooter and victim positions, weapon and time-in-round.
- **Casts:** every ability cast from the Cloud9 spatial supplement, with precise 3D position and aim direction.
- **Rounds:** winner, side and timing.

We query the tables with DuckDB.

**Time in round.** All timing is measured from the end of the buy phase, not the start of the round, so a "15-second peek" means the same thing every round:

$$t_{\text{round}} = t_{\text{event}} - t_{\text{freeze end}}$$

**Maps without map art.** We didn't want to use game assets, so Scopewatch **draws each map's floor plan from the data itself**. Every observed player position across ~2,000 pro maps goes into a 50 cm grid. We smooth it, threshold it, close small gaps and fill holes, and the walkable area appears on its own: lanes, sites and chokes.

**Front end.** _TODO: describe the web stack and views once built._

**Confidence.** Every team rate has a 95% Wilson range. Rounds of one game repeat each other (same plan, same opponent), so the range uses $n / (1 + (m - 1)\rho)$ rounds instead of $n$, where $m$ is the number of rounds per game and $\rho$ is measured league-wide for each measure. We tested it: split a team's games in two and the halves should disagree beyond 95% in 5% of cases. They disagreed in 19.1% with ordinary ranges and 7.0% with ours.

$$\hat p \pm z\sqrt{\frac{\hat p(1-\hat p)}{n}} \;\rightarrow\; \frac{\hat p + \frac{z^2}{2n} \pm z\sqrt{\frac{\hat p(1-\hat p)}{n} + \frac{z^2}{4n^2}}}{1+\frac{z^2}{n}}$$

## Built with JetBrains

**PyCharm** is where the project lives. Every step of the pipeline, from ingest through the store, maps, model training and each ML evaluation, is a shared run configuration in the repo (20 of them), so a teammate clones it and runs everything from the toolbar.

**Junie** built our features and ML steps from written briefs: the round win-probability model, Operator value (win probability added), the model experiments (richer features, utility still held, fight-level data, synthetic rounds and stress tests), recon timing and dry duels, the five team-fundamentals cards, the Report tab's findings and the Matchup tab. We ran Junie like a teammate taking tickets: every task is a brief in `docs/briefs/` with files, rules, a definition of done and checks to run, and `AGENTS.md` carries the data-licence rules it must never break. Partway through, Junie switched from its default model to GPT-5.3-codex.

**Claude Code**, outside the IDE, did the rest, and it's more than review. It wrote the engine rewrite, the map, utility, ultimate and predictability views and the deployment; it wrote the briefs; it reviewed every Junie result and fixed what it found, sometimes by finishing or rewriting the code; and it built the statistical checks (D-020, D-024, D-025). Review caught real problems: label leakage, a metric that worked alone but wasn't wired in, a tab that read a field the API never sends. It also caught our own: an impossible rule in one brief, and a headline feature that turned out to be mostly chance until we tested and fixed it.

The full log, with the model, the task, what review found and the commit for every step, is in [AI_SHOWCASE.md](../AI_SHOWCASE.md), including our honest feedback for JetBrains: what Junie did well, where review mattered, and the friction we hit.

## Challenges we ran into

- **Positions only exist at events.** GRID records a player's position when something happens (a shot, a kill, an ability), not continuously. So we frame insights as *where they fight from* rather than *where they stand*, and lean on engagement geometry instead of pretending we have full tracking.
- **The feeds rewrite history.** Maps get restarted after technical issues, and the feed rolls back events with special "undo" events. Without handling this, abandoned maps would double-count rounds.
- **Mixed sampling rates.** VCT Americas 2025 positions are sampled once per second instead of five times, so precision differs by event. The supplement's quality flags (`ok`, `gap_exceeded`, …) decide which position to trust for each cast.
- **Partial snapshots.** Most events carry only what changed, not the full game state, so the extractor tracks round, side and agent context itself as it streams.
- **The data license.** The data can't be committed or redistributed, so the repo holds only code. The pipeline reads from a sibling folder, and every derived file type is git-ignored.

## Accomplishments that we're proud of

- A pipeline that processes the full VALORANT corpus (857 series, 2,078 maps) on a laptop. _TODO: final runtime._
- Map outlines generated purely from pro positional data.
- _TODO_

## What we learned

_TODO: fill in at the end._

## What's next for Scopewatch

- Extend the same profiler to Sentinel utility (trapwires, alarm bots), reusing the cast data.
- Self-scouting: run Cloud9's own matches through it to find our predictable habits before opponents do.
- _TODO_
