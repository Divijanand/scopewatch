# Junie guidelines

Follow [AGENTS.md](../AGENTS.md) at the repo root: the data-license rules there are hard limits.

Before finishing a task:
1. `python -m pytest tests -q` passes.
2. `cd web && npx tsc -b` passes if `web/` changed.
3. `git status` shows no data files (`*.parquet`, `*.duckdb`, `*.sqlite`, `cache/`, minimap PNGs).
4. New or changed metrics: `python -m scripts.gen_metrics_doc` and a line in `docs/IMPLEMENTATION_STATUS.md`.
