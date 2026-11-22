# Junie brief: step 5d, "Prepare for these" summary and the team scouting report

**Model:** GPT-5.3-codex. **Branch:** `deep-learning` (`git pull` first; start only once step 5c is committed). Follow `AGENTS.md`: never commit data or model files, fixtures synthetic only. Read `engine/metrics/core.py`, `api/server.py` (`_tendencies`, `envelope`), `web/src/App.tsx` and `web/src/Findings.tsx` first.

## Why
This is our edge. Other teams will consolidate stats into one dashboard; a coach doesn't want 25 cards, they want **what to prepare for**. Every card we have already knows its league comparison and its range, so we can say which findings are real and which are noise. Most tools can't. This step turns our cards into a short, ranked, evidence-backed list at the top of the page, and turns the page from an "Operator report" into the team's scouting report.

## 1. Findings from metrics (`engine/report.py`)
- A `Finding` dataclass:
  - `id`, `metric` (the metric id), `title` (2-4 words, for example "Recon timing");
  - `headline`: one plain sentence with the team's number and the league's, for example "Their first recon comes before the league's median in 78% of rounds (likely 70-84%), against 50% for the league";
  - `prepare`: one sentence on what an opponent can plan around, phrased as preparation, never as cause. For example: "Plan for an early dart: their timing is built on it."
  - `team`, `league`, `n`, `lo`, `hi` (the numbers behind the headline); `beyond_noise: bool`; `score: float`;
  - `evidence`: the metric id plus which rounds to open (`supporting` or `contrary`), and the label for the button.
- For each metric that can produce findings, a function `findings_<metric>(result_dict, side) -> list[Finding]`, registered in a dict in `report.py`. Start with these, each only when its comparison is **beyond noise**:
  - `att.executes`: a site the team plants on more or less often than the league (the team's Wilson range excludes the league rate).
  - `util.recon_timing`: add a field to the metric: `before_league_median = Rate.of(rounds whose first recon comes before the league's median, rounds with a recon)`. A finding when its range excludes 0.5. Also the late-recon split when the late and on-time ranges don't overlap.
  - `fights.dry_duels`: overall, or one agent, when the range excludes 0.
  - `team.predictability`: the most predictable habit when its percentile is 80 or more and it isn't small-sample.
  - `op.*` cards: wherever a card already has a league comparison with a range (check `op.opening`, `op.kill_timing`, `op.forwardness`, `op.wpa`), one finding when it's beyond noise.
  - The step 5c cards (`team.retakes`, `team.post_plant`, `team.economy`, `team.openings`, `team.closing`): every rate compared with the league, when the team's range excludes the league rate.
- **Score and ranking:** `score = |team − league| / half-width of the team's range` (how many range-widths away from the league; a clear, large gap ranks first). Ties go by metric order in a fixed list that puts the most actionable first: executes, recon, retakes, post-plant, economy, openings, Operator, duels, predictability, closing.
- `summarize(results, side, k=5)`: at most 5 findings, at most 2 from one metric, highest score first.
  - If none is beyond noise, return an empty list and a note: "Nothing stands out beyond noise on this map and side: they play close to the league average." That is a real answer and the UI shows it.
  - Never make up a finding to fill the list.
- Language rules from `AGENTS.md`: associated with, observed, nearest callout. Never "caused", "always" or "exact". No player is "at fault" (say "most of their opening deaths come from the entry role", not a name plus blame).

## 2. API
- `_tendencies` adds `summary` (the list of findings as dicts) and `summary_note` to the envelope's data. Computing them must add under 50 ms. They're built from the results already computed, so no new queries.
- `docs/METRICS.md` gets a short section on how findings are chosen. Add it to `scripts/gen_metrics_doc.py`, so it's regenerated rather than hand-edited.

## 3. The page becomes the team's scouting report (`web/src/App.tsx`, a new `web/src/Summary.tsx`)
- **Header:** "{Team} scouting report", then "{Map}, {side}" underneath, replacing "Operator report…".
- **Tabs:** **Report** (new, the default), **Operator**, **Utility**.
- **Report tab:**
  - **"Prepare for these"** first: up to 5 findings, each showing:
    - the title;
    - the headline, with the number bold and the league number next to it;
    - the `prepare` line;
    - a small range bar (team range against a league tick; reuse the `Bar` styling);
    - "Show the rounds", which opens the existing evidence drawer. VOD links appear there already when saved.
    - If the summary is empty, show the note instead.
  - Then the cards grouped under plain section headings:
    - Attack: executes, post-plant, recon timing;
    - Defence: retakes;
    - Economy;
    - Openings and duels: openings, dry duels;
    - Closing rounds.

    Move the existing card components rather than duplicating them. Hide side-only sections on the other side.
  - The map view isn't needed on this tab.
- **Operator tab:** what it shows today, minus the cards that moved to Report.
- **Phone width:** the summary must read well at 375 px wide. Check it with the browser's device toolbar, and say in your report that you did.

## 4. Tests (`tests/test_report.py`, synthetic result dicts)
- A comparison inside the noise produces no finding; one outside it does.
- At most 5 findings and at most 2 per metric; ordered by score, with ties by the metric order.
- An empty summary returns the note.
- Each headline contains the team's number and the league's.
- A finding's evidence points at a metric id that exists in `REGISTRY`.
- The language check: no headline or `prepare` line contains "caused", "always", "exact" or "fault". Test every template with a sample.

## Don't run the long jobs
Run `python -m pytest tests -q`, `cd web && npx tsc -b` and `npm --prefix web run build` only. You may start the API and web dev server once to check the page, and you may call the tendencies endpoint for one team, map and side and report the timing. Don't paste any team's numbers into docs.

## Done when
- All tests pass, the web app builds, `git status` shows no data or model files, and nothing is committed.
- `docs/ROADMAP_ML.md` has a step 5d section (after 5c, before 6): what it adds and "implemented, awaiting review". `AI_SHOWCASE.md` has a log row naming the model.
- Your report lists every finding template you wrote, and any metric where you couldn't find a beyond-noise comparison.
