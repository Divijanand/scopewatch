"""Name positions with map callouts ("A Drop", "Mid Market").

Source: valorant-api.com /v1/maps `callouts` (community-provided). Each callout is one anchor
point in native game coordinates, not an area, so a position gets the name of the nearest anchor
that it can actually reach on the minimap floor:

  1. take the 3 nearest anchors within MAX_DIST_CM;
  2. pick the first whose straight path to the position stays on the minimap floor
     (so a player behind a wall isn't named after the room on the other side);
  3. if none has a clear path, keep the nearest one;
  4. beyond MAX_DIST_CM the position stays unnamed (None), never guessed.

This is an approximation and is labelled as one in the UI ("nearest callout").
"""
from __future__ import annotations

import json

import numpy as np
from PIL import Image
from scipy.spatial import cKDTree

from .config import MAPS_DIR
from .minimaps import INDEX

MAX_DIST_CM = 2500       # 25 m: further than that from every anchor -> unnamed
K = 3
PATH_SAMPLES = 40
PATH_MAX_BLOCKED = 2     # boxes/props are holes on the minimap; tolerate a couple of samples


def name_of(c) -> str:
    sup, reg = c["superRegionName"], c["regionName"]
    if sup in ("Attacker Side", "Defender Side"):
        return f"{sup.split()[0]} {reg}"      # "Attacker Spawn"
    return f"{sup} {reg}"                       # "A Drop", "Mid Market"


def load() -> dict[str, list[dict]]:
    """{map: [{name, x, y}]} for every map with callouts."""
    if not INDEX.exists():
        return {}
    out = {}
    for m in json.loads(INDEX.read_text())["data"]:
        cs = m.get("callouts") or []
        if cs:
            out[m["displayName"].lower()] = [dict(name=name_of(c), x=c["location"]["x"], y=c["location"]["y"])
                                             for c in cs]
    return out


class Labeller:
    def __init__(self, map_name: str, anchors: list[dict], floor: np.ndarray | None = None, transform=None):
        self.map = map_name
        self.names = np.array([a["name"] for a in anchors])
        self.xy = np.array([[a["x"], a["y"]] for a in anchors], float)
        self.tree = cKDTree(self.xy)
        self.floor, self.t = floor, transform

    @classmethod
    def for_map(cls, map_name: str, anchors: list[dict]):
        meta = json.loads((MAPS_DIR / "maps.json").read_text()).get(map_name) if (MAPS_DIR / "maps.json").exists() else None
        floor = t = None
        if meta and (MAPS_DIR / f"{map_name}.png").exists():
            floor = np.asarray(Image.open(MAPS_DIR / f"{map_name}.png"))[:, :, 3] > 0
            t = meta["transform"]
        return cls(map_name, anchors, floor, t)

    def _px(self, x, y):
        t = self.t
        return t["a"] * x + t["b"] * y + t["c"], t["d"] * x + t["e"] * y + t["f"]

    def _clear(self, x, y, ax, ay):
        """True where the straight path from (x, y) to (ax, ay) stays on the minimap floor."""
        if self.floor is None:
            return np.ones(len(x), bool)
        h, w = self.floor.shape
        s = np.linspace(0, 1, PATH_SAMPLES)[:, None]
        px0, py0 = self._px(x, y)
        px1, py1 = self._px(ax, ay)
        cx = np.clip((px0 + (px1 - px0) * s).astype(int), 0, w - 1)
        cy = np.clip((py0 + (py1 - py0) * s).astype(int), 0, h - 1)
        return (~self.floor[cy, cx]).sum(0) <= PATH_MAX_BLOCKED

    def label(self, x, y):
        """Arrays of (callout name or None, distance in metres or nan)."""
        x = np.asarray(x, float)
        y = np.asarray(y, float)
        names = np.full(len(x), None, dtype=object)
        dist_m = np.full(len(x), np.nan)
        ok = ~(np.isnan(x) | np.isnan(y))
        if not ok.any():
            return names, dist_m
        k = min(K, len(self.xy))
        d, idx = self.tree.query(np.c_[x[ok], y[ok]], k=k, distance_upper_bound=MAX_DIST_CM)
        d, idx = d.reshape(len(d), k), idx.reshape(len(idx), k)
        chosen = np.full(len(d), -1)
        chosen_d = np.full(len(d), np.nan)
        for j in range(k):                       # nearest first; first with a clear path wins
            valid = (idx[:, j] < len(self.xy)) & (chosen < 0)
            if not valid.any():
                continue
            sub = np.nonzero(valid)[0]
            a = self.xy[idx[sub, j]]
            clear = self._clear(x[ok][sub], y[ok][sub], a[:, 0], a[:, 1])
            chosen[sub[clear]] = idx[sub[clear], j]
            chosen_d[sub[clear]] = d[sub[clear], j]
        fallback = (chosen < 0) & (idx[:, 0] < len(self.xy))
        chosen[fallback] = idx[fallback, 0]
        chosen_d[fallback] = d[fallback, 0]
        got = chosen >= 0
        out_names = np.full(len(d), None, dtype=object)
        out_names[got] = self.names[chosen[got]]
        names[ok] = out_names
        dist_m[np.nonzero(ok)[0][got]] = chosen_d[got] / 100.0
        return names, dist_m


def annotate(con) -> dict:
    """Add att_callout / vic_callout to the engagements table. Returns per-map coverage stats."""
    import pandas as pd

    anchors = load()
    parts, stats = [], {}
    maps = [m for (m,) in con.execute("SELECT DISTINCT map FROM engagements").fetchall()]
    for m in maps:
        pos = con.execute("""SELECT DISTINCT x, y FROM (
                               SELECT att_x x, att_y y FROM engagements WHERE map = ? AND att_x IS NOT NULL
                               UNION SELECT vic_x, vic_y FROM engagements WHERE map = ? AND vic_x IS NOT NULL)""",
                          [m, m]).df()
        if m not in anchors or pos.empty:
            continue
        lab = Labeller.for_map(m, anchors[m])
        n, dm = lab.label(pos.x.values, pos.y.values)
        pos["map"], pos["callout"], pos["callout_dist_m"] = m, n, dm
        parts.append(pos)
        stats[m] = dict(positions=len(pos), named=round(float(pd.notna(n).mean()), 4),
                        median_dist_m=round(float(np.nanmedian(dm)), 1) if np.isfinite(dm).any() else None)
    if not parts:
        return stats
    lookup = pd.concat(parts, ignore_index=True)
    con.register("callout_lookup_df", lookup)
    con.execute("CREATE OR REPLACE TABLE pos_callouts AS SELECT map, x, y, callout, callout_dist_m FROM callout_lookup_df")
    con.unregister("callout_lookup_df")
    cols = {r[0] for r in con.execute("DESCRIBE engagements").fetchall()}
    base = ("SELECT * EXCLUDE (att_callout, vic_callout) FROM engagements" if "att_callout" in cols
            else "SELECT * FROM engagements")
    con.execute(f"""
        CREATE OR REPLACE TABLE engagements AS
        SELECT e.*, a.callout AS att_callout, v.callout AS vic_callout
        FROM ({base}) e
        LEFT JOIN pos_callouts a ON a.map = e.map AND a.x = e.att_x AND a.y = e.att_y
        LEFT JOIN pos_callouts v ON v.map = e.map AND v.x = e.vic_x AND v.y = e.vic_y""")
    return stats
