"""Engine configuration. The GRID data repo lives NEXT TO this project, never inside it."""
from __future__ import annotations

import functools
import os
import pathlib
import subprocess

PARSER_VERSION = "2.0.1"  # bump when ingest output semantics change; forces re-ingest

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA_DIR = pathlib.Path(
    os.environ.get("STL_DATA_DIR", ROOT.parent / "stl-hackathon-2026-grid-starter")
).resolve()
CACHE_DIR = pathlib.Path(os.environ.get("SCOPEWATCH_CACHE", ROOT / "cache")).resolve()
V2_DIR = CACHE_DIR / "v2"
RAW_DIR = V2_DIR / "raw"
MANIFEST_PATH = V2_DIR / "manifest.parquet"
DB_PATH = V2_DIR / "scopewatch.duckdb"
MAPS_DIR = V2_DIR / "maps"

MAP_BIN_CM = 50
OPERATOR_LIKE = ("operator", "outlaw")

# Supplement quality policy (S5): max distance from cast to the frame we trust
FRAME_LIMIT_MS = 500
FRAME_LIMIT_LOW_RATE_MS = 1200

if ROOT in DATA_DIR.parents or DATA_DIR == ROOT:
    raise RuntimeError("STL_DATA_DIR must be outside the project repo (license: never commit data)")


@functools.lru_cache(maxsize=1)
def dataset_revision() -> str:
    """Commit of the local data checkout, or 'unknown' if it isn't a git checkout."""
    try:
        out = subprocess.run(["git", "-C", str(DATA_DIR), "rev-parse", "HEAD"],
                             capture_output=True, text=True, timeout=10)
        return out.stdout.strip() or "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"
