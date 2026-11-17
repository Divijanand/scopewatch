"""Draw each map's floor plan from where players have actually been.

No Riot map art is used: the outline is the union of every observed position
(damage, kills, ability casts) across ~2,000 pro maps, smoothed into a walkable mask.

Output (git-ignored): cache/maps/{map}.png + cache/maps/maps.json with bounds so the
front end can convert game units (cm) to pixels.
"""
from __future__ import annotations

import json

import numpy as np
from PIL import Image
from scipy import ndimage

from .config import CACHE_DIR, MAP_BIN_CM

OUT = CACHE_DIR / "maps"
SCALE = 3  # output pixels per density bin
THRESH = 0.08  # fraction of median traffic below which a bin counts as "never walked"
MAX_PINHOLE = 6  # bins (50cm each); smaller enclosed gaps are sampling noise, not walls

FLOOR = (38, 44, 56, 255)
EDGE = (120, 134, 160, 255)
TRAFFIC = np.array([70, 84, 110], dtype=np.float32)


def render(grid: np.ndarray) -> tuple[Image.Image, np.ndarray]:
    g = grid.astype(np.float32)
    # walkable = seen at least a few times after light smoothing; fill pinholes, drop specks
    smooth = ndimage.gaussian_filter(g, 0.7)
    # threshold relative to typical traffic so busy and quiet maps behave the same
    thr = max(0.5, THRESH * np.median(smooth[smooth > 0.05]))
    mask = smooth > thr
    mask = ndimage.binary_closing(mask, iterations=1)
    # fill only pinholes (tiny gaps in coverage); real walls/boxes stay as holes
    holes = ndimage.binary_fill_holes(mask) & ~mask
    hl, hn = ndimage.label(holes)
    if hn:
        hs = ndimage.sum(holes, hl, range(1, hn + 1))
        mask |= np.isin(hl, 1 + np.flatnonzero(hs <= MAX_PINHOLE))
    lab, n = ndimage.label(mask)
    if n > 1:
        sizes = ndimage.sum(mask, lab, range(1, n + 1))
        mask = np.isin(lab, 1 + np.flatnonzero(sizes >= 0.002 * sizes.sum()))
    edge = mask & ~ndimage.binary_erosion(mask)

    # subtle traffic shading inside the floor: busier lanes are slightly lighter
    t = np.log1p(ndimage.gaussian_filter(g, 2.0))
    t = t / (t.max() or 1)

    h, w = mask.shape
    img = np.zeros((h, w, 4), dtype=np.uint8)
    floor = np.array(FLOOR[:3], dtype=np.float32)
    shade = floor[None, None, :] * (1 - 0.6 * t[..., None]) + TRAFFIC * (0.6 * t[..., None])
    img[mask, :3] = shade[mask].astype(np.uint8)
    img[mask, 3] = 255
    img[edge] = EDGE
    # array is [x, y]; image rows go top->bottom, so transpose and flip so +y is up
    img = np.flipud(img.transpose(1, 0, 2))
    im = Image.fromarray(img, "RGBA").resize((h * SCALE, w * SCALE), Image.NEAREST)
    return im, mask


def main():
    z = np.load(CACHE_DIR / "map_density.npz")
    OUT.mkdir(parents=True, exist_ok=True)
    meta = {}
    for key in z.files:
        if not key.endswith("__grid"):
            continue
        name = key[: -len("__grid")]
        grid, b = z[key], z[f"{name}__bounds"]
        if grid.sum() < 5000:  # e.g. a map with almost no games: outline would be noise
            print(f"skip {name}: only {int(grid.sum())} samples")
            continue
        im, mask = render(grid)
        im.save(OUT / f"{name}.png", optimize=True)
        meta[name] = dict(
            minX=float(b[0]), minY=float(b[1]), maxX=float(b[2]), maxY=float(b[3]),
            binCm=MAP_BIN_CM, scale=SCALE, width=im.width, height=im.height,
            samples=int(grid.sum()), walkableFrac=round(float(mask.mean()), 3),
        )
        print(f"{name:10s} {im.width}x{im.height}px  samples={int(grid.sum()):>9,}")
    (OUT / "maps.json").write_text(json.dumps(meta, indent=1))


if __name__ == "__main__":
    main()
