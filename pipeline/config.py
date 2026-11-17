"""Paths. The GRID data repo lives NEXT TO this project, never inside it."""
import os
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA_DIR = pathlib.Path(
    os.environ.get("STL_DATA_DIR", ROOT.parent / "stl-hackathon-2026-grid-starter")
).resolve()
CACHE_DIR = ROOT / "cache"  # git-ignored: everything derived from the data goes here
RAW_DIR = CACHE_DIR / "raw"
DB_PATH = CACHE_DIR / "scopewatch.duckdb"

# Bin size (game units = cm) for the position-density grids used to draw map outlines.
MAP_BIN_CM = 50

SNIPERS = {"operator", "outlaw", "marshal"}
OPERATOR_LIKE = {"operator", "outlaw"}  # long-range rifles that define an "AWPer"-style role

if ROOT in DATA_DIR.parents or DATA_DIR == ROOT:
    raise RuntimeError("STL_DATA_DIR must be outside the project repo (license: never commit data)")
