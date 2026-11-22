# Junie brief: step 5d part 2, the Report tab and "Prepare for these" (UI only)

**Model:** GPT-5.3-codex. **Branch:** `deep-learning` (`git pull` first; start once part 1 is committed). **Don't search the codebase.** Read only `web/src/App.tsx`, `web/src/Findings.tsx` and `web/src/api.ts`. The API now returns `data.summary` (a list of findings) and `data.summary_note` in the tendencies response. Each finding has:
- `id`, `metric`, `title`, `headline`, `prepare`;
- `team`, `league`, `n`, `lo`, `hi`, `score`;
- `unit`: `"rate"` (a share from 0 to 1), `"points"` (Operator value, in round-win points, can be negative) or `"diff"` (dry duels: a difference from what's expected, as a fraction, can be negative);
- `evidence: {metric, label}`.

## Files you change (nothing else)
- `web/src/api.ts`: types for `Finding`, plus `summary`/`summary_note` on the tendencies response.
- `web/src/Summary.tsx` (new): the "Prepare for these" block.
- `web/src/App.tsx`: the header, tabs and Report tab.
- `web/src/Findings.tsx`: split into sections. Move the existing card JSX; don't rewrite cards.
- `web/src/index.css`: only new classes for the summary.

## What to build
1. **Header:** `{team.name}` as the h1, then "Scouting report{map && ` for ${cap(map)}`}{side && `, ${side word}`}". This replaces "Operator report…" at App.tsx line 148.
2. **Tabs:** `Report` (new, the default view), `Operator`, `Utility`. `view` state becomes `'report' | 'operator' | 'utility'`, defaulting to `'report'`.
3. **Report tab** (no map view):
   - `<Summary>` first: the heading "Prepare for these", then one item per finding:
     - the title (small);
     - the headline;
     - the `prepare` line, emphasised;
     - a thin bar from `lo` to `hi` with a tick at `league` (reuse the `.bar`, `.bar-range` and `.bar-league` classes). For `unit === "rate"` the scale is 0 to 1. For `"points"` and `"diff"` the scale is symmetric around 0: `lim = max(|lo|, |hi|, |league|)` times 1.2, and position = `(x + lim) / (2 * lim)`. The headline already carries the numbers, so no axis labels;
     - a "Show the rounds" button calling `onEvidence({ metric: f.evidence.metric, claim: f.headline, supportingLabel: 'Supporting', contraryLabel: 'Contrary' })`.

     When the list is empty, show `summary_note` as one sentence.
   - Then the cards under section headings: **Attack** (executes, post-plant, recon timing), **Defence** (retakes), **Economy**, **Openings and duels** (openings, dry duels), **Closing rounds**. Hide Attack on defence and Defence on attack.
   - Do this by giving `Findings` a `sections` prop: `'report'` renders only those cards, grouped; `'operator'` renders only the Operator cards. Move JSX blocks; keep each card's code as it is.
4. **Operator tab:** the map view and the Operator cards, as today.
5. **Phone width:** at 375 px the summary must read in one column with no horizontal scroll. Check it in the browser's device toolbar once.

## Terminal commands
Run each command on its own, for example `npx tsc -b`. Don't append `; exit $LASTEXITCODE` or any `exit`: in part 1 that left you waiting two hours on a command that takes 8 seconds.

## Stop when
`cd web && npx tsc -b` and `npm run build` pass, and `python -m pytest tests -q` still passes. You may start the API and web servers once to look at the page. Don't commit. Add an `AI_SHOWCASE.md` row: "Step 5d part 2 (Report tab)", naming the model.
