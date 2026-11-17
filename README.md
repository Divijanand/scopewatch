# Scopewatch

**Operator tendency & sniper profiler for VALORANT coaches.** Built for the Cloud9 x JetBrains *Sky's The Limit* 2026 hackathon (Category 1: VALORANT Tactical Scouting).

Scopewatch shows a coach, at a glance, how an opponent uses the Operator:
- **Who carries it**: buy rate by side and economy, and how the rifle moves between players and agents.
- **Where they fight from**: shooter→victim angle lines and density on a map drawn from pro positional data.
- **When**: aggressive early picks vs. late passive holds, bucketed by time since the buy phase ended.
- **How sure we are**: every claim shows its sample size (rounds, engagements, maps).

> Status: early development. The data pipeline works; the web UI is in progress.

## How it works

```
GRID feeds (.jsonl.zst) ──► pipeline/extract.py ──► cache/raw/*.parquet ──► DuckDB ──► API ──► web UI
ability supplement      ─┘                      └─► cache/map_density.npz ──► pipeline/maps.py ──► map outlines
```

Map outlines are generated from where players have been across ~2,000 pro maps, so no game art is used.

## Running it

The licensed GRID data is **not** in this repo. Clone it next to this project:

```
your-folder/
├── stl-hackathon-2026-grid-starter/   # GRID data (never committed)
└── scopewatch/                        # this repo
```

```bash
git clone --filter=blob:none --sparse https://github.com/cloud9esports/stl-hackathon-2026-grid-starter.git
cd stl-hackathon-2026-grid-starter && git sparse-checkout set val val-ability-supplements meta && cd ..
cd scopewatch
pip install -r requirements.txt
python -m pipeline.extract        # ~10 min on 10 cores, writes cache/ (git-ignored)
python -m pipeline.maps           # map outlines
```

Set `STL_DATA_DIR` if the data lives somewhere else.

## Data license

Match data is provided by GRID and is © GRID eSports GmbH and Riot Games, Inc. It's used under the hackathon data license. This repo contains only code: `cache/` and every data or derived file type is git-ignored. Not endorsed by Riot Games.

## Built with JetBrains

_To fill in: which JetBrains IDE, Junie and Air features were used, and for what._

## License

MIT, see [LICENSE](LICENSE).
