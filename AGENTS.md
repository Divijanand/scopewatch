# Rules for coding agents (Junie, JetBrains Air, Claude Code)

Scopewatch is a VALORANT scouting tool built on licensed GRID esports data. Read this before changing anything.

## Data license: never break these
- **Never commit GRID data or anything derived from it at row level**: no `*.zst`, `*.jsonl`, `*.parquet`, `*.duckdb`, `*.sqlite`, `*.npz`, nothing under `cache/`, nothing from `stl-hackathon-2026-grid-starter/`. `.gitignore` covers these; check `git status` before every commit and never `git add -A`.
- Test fixtures are **synthetic**: invented teams, players and coordinates in GRID's shape (`tests/synth.py`), never extracts of the corpus.
- Minimap images are Riot artwork fetched into `cache/`. Never commit them.
- No betting or commercial use of the data.

## Layout
- `engine/ingest/`: streaming ingest with an undo stack for GRID reversals. Writes per-series parquet into `cache/v2/raw/`.
- `engine/store.py`: builds the DuckDB analytical store, then names positions with callouts (`engine/callouts.py`).
- `engine/metrics/`: versioned metrics registered with `@metric`. Each returns `MetricResult` with `n/N`, unknowns, Wilson ranges and supporting/contrary round keys. Team rates use `Rate.over(measure, hits, units)`, which widens the range for rounds of one game repeating each other (D-025); plain `Rate.of` is only for league rates.
- `engine/maps.py`, `engine/minimaps.py`, `engine/spatial.py`: map images and versioned world→pixel transforms.
- `engine/vod.py`: the analyst's VOD links, kept in a separate SQLite file.
- `api/server.py`: FastAPI. Every response is an envelope with coverage, warnings and definition versions.
- `web/`: React + Vite + TypeScript.
- `docs/`: decisions (`DECISIONS.md`, numbered D-xxx), validation, metric definitions (`METRICS.md` is generated: `python -m scripts.gen_metrics_doc`).

## How to work
- Run the tests: `python -m pytest tests -q`. Typecheck the UI: `cd web && npx tsc -b`
- A new metric needs: a `MetricDef` with population, numerator and caveats; a contract test on hand-built tables; a regenerated `docs/METRICS.md`; and a line in `docs/IMPLEMENTATION_STATUS.md`.
- A decision that changes what a number means gets a `D-xxx` entry in `docs/DECISIONS.md` with evidence.
- Only claim what was checked. `docs/IMPLEMENTATION_STATUS.md` separates working, partial and planned work.
- Language in the UI: say observed, associated with, nearest callout, cast near. Never say caused, exact landing, always.
- Missing geometry stays missing (null, never 0,0). Small samples are labelled, never hidden.
