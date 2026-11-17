"""Stream every VALORANT GRID feed (+ ability supplement) into flat tables in cache/raw/.

Tables (one parquet per series per table):
  loadouts     one row per player per round at buy-phase end (agent, side, weapons, money)
  rounds       one row per round (winner team/side, freeze-end time)
  engagements  one row per damage/kill event (shooter + victim positions, weapon, time-in-round)
  casts        one row per ability cast from the supplement (precise 3D position + aim)
plus a per-series position-density grid per map, used to draw map outlines.

Usage:
  python -m pipeline.extract              # all series
  python -m pipeline.extract --limit 5    # quick sample
"""
from __future__ import annotations

import argparse
import bisect
import io
import multiprocessing as mp
import sys
import time
from datetime import datetime

import numpy as np
import orjson
import pandas as pd
import zstandard

from .config import DATA_DIR, RAW_DIR, MAP_BIN_CM

TABLES = ("loadouts", "rounds", "engagements", "casts")


def ts_ms(s: str) -> int:
    return int(datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp() * 1000)


def stream(path):
    with open(path, "rb") as raw:
        reader = zstandard.ZstdDecompressor().stream_reader(raw, read_size=1 << 20)
        for line in io.BufferedReader(reader, buffer_size=1 << 22):
            if line.strip():
                yield orjson.loads(line)


def _pos(obj):
    p = (obj.get("state") or {}).get("game", {}).get("position")
    return (p["x"], p["y"]) if p else (None, None)


def _current_game(series_state):
    games = series_state.get("games") or []
    live = [g for g in games if g.get("started") and not g.get("finished")]
    return (live or games or [None])[-1]


class SeriesExtractor:
    def __init__(self, sid: str):
        self.sid = sid
        self.rows = {t: [] for t in TABLES}
        self.game_id = None
        self.map = None
        self.bounds = None
        self.round_no = None
        self.round_start = None  # ms, start of the round (freeze time begins)
        self.freeze_end = None  # ms, buy phase ends: t_round is measured from here
        # (game_id) -> sorted list of (freeze_end_ms, round_no) for joining casts
        self.round_index: dict[str, list[tuple[int, int]]] = {}
        self.game_map: dict[str, str] = {}
        # (game_id, round_no, player_id) -> (team_id, side, agent)
        self.who: dict[tuple, tuple] = {}
        self.points: dict[tuple, list] = {}  # (map, bounds) -> list of xy

    # ---------- helpers
    def _add_pt(self, x, y):
        if x is not None and self.map:
            self.points.setdefault((self.map, self.bounds), []).append((x, y))

    def _t_round(self, now):
        return None if self.freeze_end is None else (now - self.freeze_end) / 1000.0

    def _sync_game(self, gm):
        if not gm:
            return
        self.game_id = gm["id"]
        m = gm.get("map") or {}
        if m.get("name"):
            self.map = m["name"]
            b = m.get("bounds") or {}
            if b:
                self.bounds = (b["min"]["x"], b["min"]["y"], b["max"]["x"], b["max"]["y"])
            self.game_map[self.game_id] = self.map

    # ---------- main loop
    def run(self):
        feed = DATA_DIR / "val" / f"events_{self.sid}_grid.jsonl.zst"
        for env in stream(feed):
            now = ts_ms(env["occurredAt"])
            for e in env["events"]:
                t = e["type"]
                if e.get("includesFullState") and e.get("seriesState"):
                    self._sync_game(_current_game(e["seriesState"]))
                if t == "game-started-round":
                    self.round_no = e["target"]["state"]["sequenceNumber"]
                    self.round_start = now
                    self.freeze_end = None
                elif t == "round-ended-freezetime":
                    self.freeze_end = now
                    self.round_no = e["actor"]["state"]["sequenceNumber"]
                    self.round_index.setdefault(self.game_id, []).append((now, self.round_no))
                    self._loadouts(e, now)
                elif t == "team-won-round":
                    st = e["actor"]["state"]
                    self.rows["rounds"].append(dict(
                        series_id=self.sid, game_id=self.game_id, map=self.map, round_no=self.round_no,
                        winner_team_id=st.get("id"), winner_side=st.get("side"),
                        freeze_end_ms=self.freeze_end, end_ms=now,
                        win_type=(e.get("target") or {}).get("id"),
                    ))
                elif t in ("player-damaged-player", "player-killed-player"):
                    self._engagement(e, t, now)
                elif t.startswith("player-"):
                    for k in ("actor", "target"):
                        o = e.get(k) or {}
                        if o.get("type") == "player":
                            self._add_pt(*_pos(o))
        self._casts()
        for k in self.round_index:
            self.round_index[k].sort()
        return self

    def _loadouts(self, e, now):
        gm = _current_game(e["seriesState"])
        if not gm:
            return
        for tm in gm.get("teams", []):
            for p in tm.get("players", []):
                items = [i["id"] for i in (p.get("inventory") or {}).get("items", [])]
                agent = (p.get("character") or {}).get("id")
                self.who[(self.game_id, self.round_no, p["id"])] = (tm["id"], tm.get("side"), agent)
                pos = p.get("position") or {}
                self.rows["loadouts"].append(dict(
                    series_id=self.sid, game_id=self.game_id, map=self.map, round_no=self.round_no,
                    team_id=tm["id"], team_name=tm.get("name"), side=tm.get("side"),
                    team_money=tm.get("money"), team_loadout=tm.get("loadoutValue"),
                    player_id=p["id"], player_name=p.get("name"), agent=agent,
                    money=p.get("money"), loadout_value=p.get("loadoutValue"),
                    items="|".join(items), x=pos.get("x"), y=pos.get("y"), freeze_end_ms=now,
                ))

    def _engagement(self, e, t, now):
        a, v = e["actor"], e["target"]
        ast, vst = a.get("state") or {}, v.get("state") or {}
        ax, ay = _pos(a)
        vx, vy = _pos(v)
        self._add_pt(ax, ay)
        self._add_pt(vx, vy)
        rd = (a.get("stateDelta") or {}).get("round") or {}
        if t == "player-killed-player":
            weapon = next(iter(rd.get("weaponKills") or {}), None)
            dmg, hit = None, None
        else:
            src = rd.get("damageDealtSources") or []
            weapon = src[0]["source"]["name"] if src else None
            tg = rd.get("damageDealtTargets") or []
            hit = tg[0]["target"]["name"] if tg else None
            dmg = rd.get("damageDealt")
        self.rows["engagements"].append(dict(
            series_id=self.sid, game_id=self.game_id, map=self.map, round_no=self.round_no,
            kind="kill" if t.endswith("killed-player") else "damage",
            ts_ms=now, t_round=self._t_round(now), weapon=weapon, damage=dmg, hit=hit,
            att_id=a.get("id"), att_name=ast.get("name"), att_team=ast.get("teamId"), att_side=ast.get("side"),
            att_x=ax, att_y=ay,
            vic_id=v.get("id"), vic_name=vst.get("name"), vic_team=vst.get("teamId"), vic_side=vst.get("side"),
            vic_x=vx, vic_y=vy,
        ))

    def _casts(self):
        path = DATA_DIR / "val-ability-supplements" / f"{self.sid}.jsonl.zst"
        if not path.exists():
            return
        for r in stream(path):
            if r["quality"] == "missing_both" or not r.get("interpolated"):
                continue
            src = r["interpolated"]
            if r["quality"] == "gap_exceeded":  # README: use the closer frame instead
                fb, fa = r.get("frame_before"), r.get("frame_after")
                cands = [f for f in (fb, fa) if f]
                src = min(cands, key=lambda f: abs(f["offset_ms"]))
            now = ts_ms(r["occurred_at"])
            gid = r["game_id"]
            idx = self.round_index.get(gid, [])
            i = bisect.bisect_right(idx, (now, 10**9)) - 1
            # cast before the first freeze-end of the game -> pre-round; keep with round None
            freeze_end, rno = idx[i] if i >= 0 else (None, None)
            team, side, agent = self.who.get((gid, rno, r["player_id"]), (None, None, None))
            p, vw = src["position"], src["view"]
            mp_ = self.game_map.get(gid)
            self.rows["casts"].append(dict(
                series_id=self.sid, game_id=gid, map=mp_, round_no=rno,
                ts_ms=now, t_round=None if freeze_end is None else (now - freeze_end) / 1000.0,
                player_id=r["player_id"], team_id=team, side=side, agent=agent,
                ability=r.get("ability"), slot=r.get("slot"), in_grid=r["in_grid"], quality=r["quality"],
                x=p["x"], y=p["y"], z=p["z"], vx=vw["x"], vy=vw["y"], vz=vw["z"],
            ))

    def map_grids(self):
        """(map, bounds) -> 2D histogram of every observed position."""
        out = {}
        for (m, b), pts in self.points.items():
            if not pts or b is None:
                continue
            x0, y0, x1, y1 = b
            nx, ny = int((x1 - x0) // MAP_BIN_CM) + 1, int((y1 - y0) // MAP_BIN_CM) + 1
            arr = np.asarray(pts, dtype=np.float32)
            h, _, _ = np.histogram2d(arr[:, 0], arr[:, 1], bins=[nx, ny], range=[[x0, x1], [y0, y1]])
            out[(m, b)] = h.astype(np.uint32)
        # cast positions are the most precise: add them too
        for r in self.rows["casts"]:
            for (m, b), h in out.items():
                if m == r["map"]:
                    x0, y0, x1, y1 = b
                    i, j = int((r["x"] - x0) // MAP_BIN_CM), int((r["y"] - y0) // MAP_BIN_CM)
                    if 0 <= i < h.shape[0] and 0 <= j < h.shape[1]:
                        h[i, j] += 1
        return out


def process(sid: str):
    t0 = time.time()
    try:
        ex = SeriesExtractor(str(sid)).run()
    except Exception as err:  # keep the batch going; report at the end
        return sid, None, f"{type(err).__name__}: {err}", 0.0
    for name, rows in ex.rows.items():
        if rows:
            d = RAW_DIR / name
            d.mkdir(parents=True, exist_ok=True)
            pd.DataFrame(rows).to_parquet(d / f"{sid}.parquet", index=False)
    return sid, ex.map_grids(), None, time.time() - t0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--series", nargs="*", default=None)
    ap.add_argument("--workers", type=int, default=max(1, mp.cpu_count() - 2))
    args = ap.parse_args(argv)

    series = pd.read_csv(DATA_DIR / "val" / "series.csv", dtype={"series_id": str})
    ids = args.series or series.series_id.tolist()
    if args.limit:
        ids = ids[: args.limit]
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    grids: dict[tuple, np.ndarray] = {}
    errors = []
    t0 = time.time()
    with mp.Pool(args.workers) as pool:
        for n, (sid, g, err, dt) in enumerate(pool.imap_unordered(process, ids), 1):
            if err:
                errors.append((sid, err))
            else:
                for k, h in g.items():
                    grids[k] = grids[k] + h if k in grids and grids[k].shape == h.shape else grids.get(k, h)
            if n % 25 == 0 or n == len(ids):
                print(f"[{n}/{len(ids)}] {time.time() - t0:.0f}s elapsed", flush=True)

    # one density grid per map: keep the most common bounds for that map
    by_map: dict[str, tuple] = {}
    for (m, b), h in grids.items():
        if m not in by_map or h.sum() > by_map[m][1].sum():
            by_map[m] = (b, h)
    np.savez_compressed(
        RAW_DIR.parent / "map_density.npz",
        **{f"{m}__grid": h for m, (b, h) in by_map.items()},
        **{f"{m}__bounds": np.array(b, dtype=np.float64) for m, (b, h) in by_map.items()},
    )
    print(f"done: {len(ids) - len(errors)} ok, {len(errors)} failed, maps={sorted(by_map)}")
    for sid, err in errors[:20]:
        print("  FAIL", sid, err, file=sys.stderr)


if __name__ == "__main__":
    main()
