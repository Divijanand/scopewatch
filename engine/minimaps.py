"""Real in-game minimaps with the community world->minimap calibration.

Source: valorant-api.com /v1/maps (unofficial, community-run). Each map has a minimap image
(Riot Games artwork, 1024x1024 RGBA) and four numbers that map game coordinates to the image:

    u = y * xMultiplier + xScalarToAdd        (note the axis swap: image x comes from game y)
    v = x * yMultiplier + yScalarToAdd
    pixel = (u * 1024, v * 1024)

GRID reports native game units, so this transform applies to GRID positions unchanged. We don't
trust it on faith: maps.main() checks every map against independent landmarks (spike plants,
buy-phase spawns) exactly as it did for our own outlines, and the result goes in config/maps/.

The images are Riot IP. They're fetched into git-ignored cache/ and never committed
(MAP_ASSET_POLICY.md). Fetch once with:  python -m engine.minimaps
"""
from __future__ import annotations

import hashlib
import json
import sys
import urllib.request
from datetime import date

import numpy as np
from PIL import Image

from .config import MAPS_DIR
from .spatial import Affine

SOURCE = "https://valorant-api.com/v1/maps"
SRC_DIR = MAPS_DIR / "minimaps"
INDEX = SRC_DIR / "valorant-api-maps.json"
PAD = 24  # px of margin kept around the playable area when cropping

# palette: playable floor in the sheet's paper tone, walls/edges in ink (index.css)
FLOOR = np.array([250, 251, 253])
INK = np.array([34, 50, 74])


def fetch() -> None:
    """Download the map index and every minimap that has a calibration."""
    SRC_DIR.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(SOURCE, headers={"User-Agent": "scopewatch-map-fetch"})
    raw = urllib.request.urlopen(req, timeout=30).read()
    data = json.loads(raw)["data"]
    for m in data:
        if not (m.get("displayIcon") and m.get("xMultiplier")):
            continue
        path = SRC_DIR / f"{m['displayName'].lower()}.png"
        req = urllib.request.Request(m["displayIcon"], headers={"User-Agent": "scopewatch-map-fetch"})
        path.write_bytes(urllib.request.urlopen(req, timeout=30).read())
        print(f"{m['displayName']:10s} {path.stat().st_size:7d} bytes")
    INDEX.write_bytes(raw)
    (SRC_DIR / "retrieved.txt").write_text(str(date.today()))


def _index():
    if not INDEX.exists():
        return {}
    return {m["displayName"].lower(): m for m in json.loads(INDEX.read_text())["data"]}


def restyle(im: Image.Image) -> Image.Image:
    """Recolour the minimap into the drafting-sheet palette, keeping its shapes and shading.

    In the source, the floor is a flat grey (luminance ~118), raised areas are lighter and the
    wall/edge strokes are white. Here the floor becomes paper, raised areas a light ink wash and
    the strokes ink. The original alpha is kept so out-of-bounds stays transparent.
    """
    a = np.asarray(im.convert("RGBA")).astype(float)
    lum = 0.299 * a[..., 0] + 0.587 * a[..., 1] + 0.114 * a[..., 2]
    op = a[..., 3] > 0
    base = np.median(lum[op]) if op.any() else 118.0
    k = np.clip((lum - base) / (255.0 - base), 0, 1)[..., None]  # 0 = floor, 1 = stroke
    rgb = FLOOR + (INK - FLOOR) * np.where(k > 0.9, 1.0, k * 0.55)
    out = np.dstack([rgb, a[..., 3]]).astype(np.uint8)
    return Image.fromarray(out, "RGBA")


def build(name: str):
    """Return (image, Affine, asset_info) for a map, or None if no minimap is available."""
    meta = _index().get(name)
    src = SRC_DIR / f"{name}.png"
    if not meta or not src.exists() or not meta.get("xMultiplier"):
        return None
    raw = Image.open(src).convert("RGBA")
    size = raw.width  # square, 1024
    alpha = np.asarray(raw)[:, :, 3]
    ys, xs = np.nonzero(alpha)
    x0, y0 = max(int(xs.min()) - PAD, 0), max(int(ys.min()) - PAD, 0)
    x1, y1 = min(int(xs.max()) + PAD, size), min(int(ys.max()) + PAD, size)
    im = restyle(raw.crop((x0, y0, x1, y1)))
    t = Affine(a=0.0, b=size * meta["xMultiplier"], c=size * meta["xScalarToAdd"] - x0,
               d=size * meta["yMultiplier"], e=0.0, f=size * meta["yScalarToAdd"] - y0)
    retrieved = (SRC_DIR / "retrieved.txt").read_text().strip() if (SRC_DIR / "retrieved.txt").exists() else None
    asset = dict(
        source="valorant-api.com /v1/maps displayIcon (community-hosted Riot Games minimap)",
        source_url=meta["displayIcon"], map_url=meta.get("mapUrl"), map_uuid=meta.get("uuid"),
        retrieved=retrieved, sha1_original=hashlib.sha1(src.read_bytes()).hexdigest(),
        official=False, third_party=True,
        terms="Riot Games IP, used under Riot's fan-content policy (Legal Jibber Jabber); "
              "not redistributed: fetched into git-ignored cache/",
        crop=[x0, y0, x1, y1], restyled="recoloured to the Scopewatch palette; shapes unchanged",
        calibration_source=dict(xMultiplier=meta["xMultiplier"], yMultiplier=meta["yMultiplier"],
                                xScalarToAdd=meta["xScalarToAdd"], yScalarToAdd=meta["yScalarToAdd"],
                                provided_by="valorant-api.com (community)"),
    )
    return im, t, asset


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--offline":
        print(sorted(_index()))
    else:
        fetch()
