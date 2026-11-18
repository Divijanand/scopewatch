"""Map outlines from observed positions, plus a versioned transform and landmark calibration per map.

Outline: the union of observed positions (engagements, other player events, quality-passing casts)
across the corpus, smoothed and thresholded (pipeline.maps.render). No third-party art.

Calibration: outlines share GRID's coordinate system, so world->pixel is exact by construction.
What can still go wrong is the *outline* (missing floor, wrong map version, axis handling), so we
validate the displayed image end to end with independent landmarks that were never used to draw it:
  - spike plant positions (objectives)    must fall on the drawn floor
  - spawn positions at buy-phase start     must fall on the drawn floor
Outputs:
  cache/v2/maps/{map}.png + maps.json      (git-ignored: derived from the data)
  config/maps/{map}-{version}.json         (committed: transform + aggregate calibration stats only)
"""
from __future__ import annotations

import hashlib
import json
from datetime import date

import duckdb
import numpy as np
from PIL import Image
from scipy import ndimage

from pipeline.maps import SCALE, render
from .config import DB_PATH, MAP_BIN_CM, MAPS_DIR, RAW_DIR, ROOT
from .spatial import bounds_transform

CONFIG_DIR = ROOT / "config" / "maps"
ASSET_VERSION = "outline-v1"
TOLERANCE_PX = 4            # ~0.7 m at 50 cm / 3 px: plants on a box edge still count
PASS_RATE = 0.97            # share of landmarks that must land on the floor


def combined_grids():
    """Sum per-series density grids (cache/v2/raw/density/*.npz) per map, using each map's common bounds."""
    acc = {}
    for path in sorted((RAW_DIR / "density").glob("*.npz")):
        z = np.load(path)
        for key in z.files:
            if key.endswith("__grid"):
                m = key[: -len("__grid")]
                b = tuple(z[f"{m}__bounds"])
                acc.setdefault(m, {})
                acc[m][b] = acc[m][b] + z[key] if b in acc[m] else z[key].astype(np.uint64)
    # a map's bounds can differ across map versions: keep the bounds with the most samples
    return {m: max(((b, g) for b, g in by_b.items()), key=lambda bg: bg[1].sum()) for m, by_b in acc.items()}


def landmarks(con, name):
    plants = con.execute("SELECT x, y FROM objectives WHERE map = ? AND kind = 'plant' AND x IS NOT NULL",
                         [name]).fetchall()
    spawns = con.execute(f"""SELECT x, y FROM read_parquet('{(RAW_DIR / 'spawns').as_posix()}/*.parquet')
                             WHERE map = ? AND x IS NOT NULL USING SAMPLE 20000 ROWS""", [name]).fetchall()
    return {"spike_plants": plants, "spawn_positions": spawns}


def validate(img: Image.Image, t, pts):
    """Share of landmarks on the drawn floor (alpha > 0) within TOLERANCE_PX, and off-floor distances."""
    floor = np.asarray(img)[:, :, 3] > 0
    dist = ndimage.distance_transform_edt(~floor)  # px to nearest floor pixel
    h, w = floor.shape
    on = off_img = 0
    off_d = []
    for x, y in pts:
        px, py = t.apply(x, y)
        c, r = int(px), int(py)
        if not (0 <= c < w and 0 <= r < h):
            off_img += 1
            continue
        if dist[r, c] <= TOLERANCE_PX:
            on += 1
        else:
            off_d.append(float(dist[r, c]))
    n = len(pts)
    return dict(n=n, on_floor=on, on_floor_rate=round(on / n, 4) if n else None, off_image=off_img,
                off_floor_median_px=round(float(np.median(off_d)), 1) if off_d else 0.0)


def main():
    MAPS_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(DB_PATH.as_posix(), read_only=True) if DB_PATH.exists() else None
    meta = {}
    for name, (b, grid) in sorted(combined_grids().items()):
        if grid.sum() < 5000:
            print(f"skip {name}: only {int(grid.sum())} samples")
            continue
        im, mask = render(grid)
        path = MAPS_DIR / f"{name}.png"
        im.save(path, optimize=True)
        sha = hashlib.sha1(path.read_bytes()).hexdigest()
        bhash = hashlib.sha1(np.array(b).tobytes()).hexdigest()[:6]
        version = f"{ASSET_VERSION}-b{bhash}"
        t = bounds_transform(*b, im.width, im.height)

        checks, status = {}, "not_validated"
        if con is not None:
            checks = {k: validate(im, t, v) for k, v in landmarks(con, name).items()}
            rates = [c["on_floor_rate"] for c in checks.values() if c["n"]]
            status = "validated" if rates and min(rates) >= PASS_RATE else "needs_review"

        cfg = dict(
            map=name, map_version=version, transform_version=f"{name}-{version}",
            asset=dict(source="original: drawn from observed GRID positions (engine/maps.py)",
                       official=False, third_party=False, file=f"cache/v2/maps/{name}.png", sha1=sha,
                       width=im.width, height=im.height, terms="original work, MIT with this repo"),
            coordinate_units="GRID native game units (cm), +y up",
            world_bounds=dict(minX=b[0], minY=b[1], maxX=b[2], maxY=b[3]), bin_cm=MAP_BIN_CM, scale=SCALE,
            world_to_pixel=t.to_dict(),
            calibration=dict(method="independent landmarks on the drawn floor", tolerance_px=TOLERANCE_PX,
                             pass_rate=PASS_RATE, checks=checks, status=status, reviewed=str(date.today())),
            known_limits=["2D projection: elevated areas overlap lower ones",
                          "outline pools all map versions in the corpus that share these bounds"],
        )
        (CONFIG_DIR / f"{name}-{version}.json").write_text(json.dumps(cfg, indent=1))
        meta[name] = dict(minX=b[0], minY=b[1], maxX=b[2], maxY=b[3], binCm=MAP_BIN_CM, scale=SCALE,
                          width=im.width, height=im.height, samples=int(grid.sum()),
                          walkableFrac=round(float(mask.mean()), 3), transform=t.to_dict(),
                          transform_version=cfg["transform_version"], calibration_status=status)
        rate = lambda k: checks.get(k, {}).get("on_floor_rate")  # noqa: E731
        print(f"{name:9s} {im.width}x{im.height}px  plants on floor {rate('spike_plants')}  "
              f"spawns on floor {rate('spawn_positions')}  -> {status}")
    (MAPS_DIR / "maps.json").write_text(json.dumps(meta, indent=1))


if __name__ == "__main__":
    main()
