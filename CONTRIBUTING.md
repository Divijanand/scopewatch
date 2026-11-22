# Working on Scopewatch together

Two people, plus Junie and Claude Code, on one codebase. These rules keep that safe.

## Before your first change
1. **Register for the hackathon on Devpost and join the team.** The GRID data licence covers registered participants, so don't download or use the data before that.
2. **Set up** with the steps in the README under "Running it". You get your own copy of the GRID data and your own `cache/`; none of it is ever shared through git.
3. **JetBrains:** redeem your own hackathon codes (All Products Pack, then JetBrains AI Ultimate) and open the repo in PyCharm. In AI Assistant and Junie settings, **turn off data sharing / training on your inputs**; the data licence requires it.
4. **Read [AGENTS.md](AGENTS.md).** Junie, Air and Claude Code follow it, and so do we.

## The non-negotiables
- **Never commit data.** No `*.parquet`, `*.duckdb`, `*.sqlite`, `*.npz`, `*.zst`, `*.jsonl`, minimap PNGs or anything under `cache/`. Run `git status` before every commit, never `git add -A`, and add files by name.
- **The live demo is open** since 2026-11-21 (D-022). If a password is ever put back, never share it in git, Discord or chat.
- **Tests use synthetic data**: invented teams and coordinates, never extracts of the corpus.

## How we work now that there are two of us
- **Branch, then pull request.** Don't push to `main` directly. Use `git switch -c <your-name>/<what>`, push, and open a PR. The other person (or Claude Code) reviews before merging.
- **Before asking for review:** `python -m pytest tests -q` passes, and `cd web && npx tsc -b` passes if you changed the UI.
- **Pull before you start:** `git pull --rebase origin main`. Shared hotspots are `api/server.py` (the report's metric list) and `web/src/Findings.tsx`. Say which of these you're editing so you don't collide.
- **New metric checklist:** a `MetricDef` with population, numerator and caveats; a contract test on hand-built tables; `python -m scripts.gen_metrics_doc`; a line in `docs/IMPLEMENTATION_STATUS.md`. A decision that changes what a number means gets a `D-xxx` entry in `docs/DECISIONS.md`.
- **Log AI work in [AI_SHOWCASE.md](AI_SHOWCASE.md)**, as it happens: date, tool (Junie, Air, Claude Code, PyCharm), task, result and commit. It's part of what's judged, so keep it honest, including what went wrong.

## Who's doing what
The open list lives in `docs/IMPLEMENTATION_STATUS.md` under "Not started". Before you start an item, put your name next to it there (in a small PR, or tell the other person), so two people never build the same thing.
