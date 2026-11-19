"""Copy exactly what the running app reads into cache/demo/v2, for the hosted demo's container.

    python -m scripts.bundle_demo [--with-vod]

cache/ is git-ignored, so the bundle never reaches GitHub. It goes only into the private container image
the host builds (Fly.io's private registry), served behind the judges' password (api/auth.py).
--with-vod also copies your saved VOD links (cache/v2/user.sqlite) so judges get the timestamps.
"""
from __future__ import annotations

import argparse
import shutil

from engine.config import CACHE_DIR, MAPS_DIR, V2_DIR

OUT = CACHE_DIR / "demo" / "v2"


def needed(with_vod: bool):
    files = [V2_DIR / "scopewatch.duckdb",
             V2_DIR / "models" / "event_wp.parquet",
             V2_DIR / "models" / "holder_wpa.parquet",
             MAPS_DIR / "maps.json",
             MAPS_DIR / "minimaps" / "valorant-api-maps.json"]
    files += sorted(MAPS_DIR.glob("*.png"))
    if with_vod and (V2_DIR / "user.sqlite").exists():
        files.append(V2_DIR / "user.sqlite")
    return files


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--with-vod", action="store_true", help="include your saved VOD links")
    args = ap.parse_args()
    files = needed(args.with_vod)
    missing = [f for f in files if not f.exists()]
    if missing:
        raise SystemExit("Missing, build these first:\n  " + "\n  ".join(str(m) for m in missing))
    if OUT.exists():
        shutil.rmtree(OUT)
    total = 0
    for src in files:
        dst = OUT / src.relative_to(V2_DIR)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        total += dst.stat().st_size
    print(f"Bundled {len(files)} files, {total / 1e6:.0f} MB, into {OUT}")


if __name__ == "__main__":
    main()
