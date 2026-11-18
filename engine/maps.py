"""Map outlines from observed positions (v2 paths). Rendering logic: see pipeline.maps.render.

Calibration note: outlines and events share GRID's coordinate system, so the transform is the
identity plus a fixed raster scale; validation checks landmarks (spawns, plants) land on the floor.
"""
from __future__ import annotations

import json

import numpy as np

from pipeline.maps import SCALE, render
from .config import MAP_BIN_CM, MAPS_DIR, RAW_DIR


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


def main():
    MAPS_DIR.mkdir(parents=True, exist_ok=True)
    meta = {}
    for name, (b, grid) in sorted(combined_grids().items()):
        if grid.sum() < 5000:
            print(f"skip {name}: only {int(grid.sum())} samples")
            continue
        im, mask = render(grid)
        im.save(MAPS_DIR / f"{name}.png", optimize=True)
        np.save(MAPS_DIR / f"{name}.mask.npy", mask)  # for landmark validation
        meta[name] = dict(minX=float(b[0]), minY=float(b[1]), maxX=float(b[2]), maxY=float(b[3]),
                          binCm=MAP_BIN_CM, scale=SCALE, width=im.width, height=im.height,
                          samples=int(grid.sum()), walkableFrac=round(float(mask.mean()), 3))
        print(f"{name:10s} {im.width}x{im.height}px samples={int(grid.sum()):>9,}")
    (MAPS_DIR / "maps.json").write_text(json.dumps(meta, indent=1))


if __name__ == "__main__":
    main()
