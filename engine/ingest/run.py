"""Ingest every VALORANT series into canonical parquet tables, with a source manifest.

* Streaming: files are never decompressed to disk.
* Idempotent: a series is skipped when its feed + supplement checksums and the parser version
  match a successful manifest entry. `--force` re-ingests everything.
* Malformed lines are quarantined (counted, first few line numbers kept), never fatal.
* Every series records reconciliation counts (events in, reversals, rows created / voided / out,
  casts excluded by reason) in the manifest.

Usage:
  python -m engine.ingest.run                 # all series, incremental
  python -m engine.ingest.run --limit 5       # first 5
  python -m engine.ingest.run --series 2972936 --force
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import multiprocessing as mp
import sys
import time
from datetime import datetime, timezone

import numpy as np
import orjson
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import zstandard

from ..config import DATA_DIR, MAP_BIN_CM, MANIFEST_PATH, PARSER_VERSION, RAW_DIR, V2_DIR, dataset_revision
from ..schema import MANIFEST, SCHEMAS
from .reducer import SeriesReducer


def sha1(path) -> str | None:
    if not path.exists():
        return None
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def stream_jsonl_zst(path, counts, label):
    """Yield parsed JSON objects; quarantine lines that don't parse."""
    with open(path, "rb") as raw:
        reader = zstandard.ZstdDecompressor().stream_reader(raw, read_size=1 << 20)
        for lineno, line in enumerate(io.BufferedReader(reader, buffer_size=1 << 22), 1):
            if not line.strip():
                continue
            try:
                yield orjson.loads(line)
            except orjson.JSONDecodeError:
                counts[f"quarantined.{label}"] += 1
                bad = counts.setdefault("_quarantine_lines", [])
                if len(bad) < 5:
                    bad.append(f"{label}:{lineno}")


def feed_path(sid):
    return DATA_DIR / "val" / f"events_{sid}_grid.jsonl.zst"


def supp_path(sid):
    return DATA_DIR / "val-ability-supplements" / f"{sid}.jsonl.zst"


def ingest_series(sid: str) -> dict:
    t0 = time.time()
    entry = dict(series_id=sid, feed_sha1=sha1(feed_path(sid)), supp_sha1=sha1(supp_path(sid)),
                 parser_version=PARSER_VERSION, dataset_revision=dataset_revision(),
                 ingested_at=datetime.now(timezone.utc).isoformat(timespec="seconds"), error=None)
    try:
        red = SeriesReducer(sid)
        for env in stream_jsonl_zst(feed_path(sid), red.counts, "feed"):
            red.feed(env)
        if supp_path(sid).exists():
            red.add_casts(stream_jsonl_zst(supp_path(sid), red.counts, "supplement"))
        else:
            red.counts["supplement_missing"] = 1
        tables = red.finish()
        for name, rows in tables.items():
            d = RAW_DIR / name
            d.mkdir(parents=True, exist_ok=True)
            pq.write_table(pa.Table.from_pylist(rows, schema=SCHEMAS[name]), d / f"{sid}.parquet")
        # per-series density grid: re-ingesting a series replaces its own grid, never double-counts
        save = {}
        for (m, b), h in density_grids(red.points).items():
            save[f"{m}__grid"] = h
            save[f"{m}__bounds"] = np.array(b, dtype=np.float64)
        dd = RAW_DIR / "density"
        dd.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(dd / f"{sid}.npz", **save)
        entry.update(status="ok")
    except Exception as err:  # one bad series never stops the batch
        red = None
        entry.update(status="failed", error=f"{type(err).__name__}: {err}")
    counts = dict(red.counts) if red else {}
    if red:
        counts["event_types_seen"] = dict(red.types)
    entry["counts_json"] = json.dumps(counts, default=str)
    entry["seconds"] = round(time.time() - t0, 2)
    return entry


def density_grids(points):
    out = {}
    for (m, b), pts in points.items():
        if not pts or b is None:
            continue
        x0, y0, x1, y1 = b
        nx, ny = int((x1 - x0) // MAP_BIN_CM) + 1, int((y1 - y0) // MAP_BIN_CM) + 1
        arr = np.asarray(pts, dtype=np.float32)
        h, _, _ = np.histogram2d(arr[:, 0], arr[:, 1], bins=[nx, ny], range=[[x0, x1], [y0, y1]])
        out[(m, b)] = h.astype(np.uint32)
    return out


def load_manifest() -> pd.DataFrame:
    if MANIFEST_PATH.exists():
        return pd.read_parquet(MANIFEST_PATH)
    return pd.DataFrame(columns=MANIFEST.names)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--series", nargs="*")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--workers", type=int, default=max(1, mp.cpu_count() - 2))
    args = ap.parse_args(argv)

    index = pd.read_csv(DATA_DIR / "val" / "series.csv", dtype={"series_id": str})
    ids = args.series or index.series_id.tolist()
    if args.limit:
        ids = ids[: args.limit]

    man = load_manifest()
    done = {}
    if not args.force and len(man):
        ok = man[(man.status == "ok") & (man.parser_version == PARSER_VERSION)]
        done = {r.series_id: (r.feed_sha1, r.supp_sha1) for r in ok.itertuples()}
    todo = [s for s in ids if done.get(s) != (sha1(feed_path(s)), sha1(supp_path(s)))]
    print(f"{len(ids)} series requested, {len(ids) - len(todo)} unchanged (skipped), {len(todo)} to ingest",
          flush=True)
    if not todo:
        return

    V2_DIR.mkdir(parents=True, exist_ok=True)
    entries = []
    t0 = time.time()
    with mp.Pool(args.workers) as pool:
        for n, entry in enumerate(pool.imap_unordered(ingest_series, todo), 1):
            entries.append(entry)
            if n % 25 == 0 or n == len(todo):
                print(f"[{n}/{len(todo)}] {time.time() - t0:.0f}s", flush=True)

    new = pd.DataFrame(entries, columns=MANIFEST.names)
    man = pd.concat([man[~man.series_id.isin(new.series_id)], new], ignore_index=True)
    pq.write_table(pa.Table.from_pandas(man, schema=MANIFEST, preserve_index=False), MANIFEST_PATH)

    failed = new[new.status != "ok"]
    print(f"done: {len(new) - len(failed)} ok, {len(failed)} failed")
    for r in failed.head(20).itertuples():
        print("  FAIL", r.series_id, r.error, file=sys.stderr)


if __name__ == "__main__":
    main()
