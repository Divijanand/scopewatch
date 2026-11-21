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

**Confidence.** _TODO if implemented: Wilson score intervals on every rate, so small samples are visibly uncertain:_

$$\hat p \pm z\sqrt{\frac{\hat p(1-\hat p)}{n}} \;\rightarrow\; \frac{\hat p + \frac{z^2}{2n} \pm z\sqrt{\frac{\hat p(1-\hat p)}{n} + \frac{z^2}{4n^2}}}{1+\frac{z^2}{n}}$$

## Built with JetBrains

**PyCharm** is where the project lives. Every step of the pipeline, from ingest through the store, maps, model training and each ML evaluation, is a shared run configuration in the repo (12 of them), so a teammate clones it and runs everything from the toolbar.

**Junie** built four of our features and ML steps: the round win-probability model, Operator value (win probability added), and two rounds of model experiments (richer features, and utility still held). We ran Junie like a teammate taking tickets: every task was a written brief in `docs/briefs/` with files, rules, a definition of done and checks to run, and `AGENTS.md` carried the data-licence rules it must never break. Claude Code reviewed each result the way you'd review a pull request: it read the diff, ran the tests and reproduced the numbers independently. Review caught real problems (label leakage, a metric that worked alone but wasn't wired in, a baseline 0.001 off that led us to fix our own store) and once caught a mistake in our own brief. Junie switched from its default model to GPT-5.3-codex on day three, so one model writes and another reviews.

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
