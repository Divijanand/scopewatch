"""Series reducer: turns one GRID event stream (+ ability supplement) into canonical rows.

Design
------
* An explicit state machine: game -> round -> phase (buy / pre_plant / post_plant).
* Reversals: GRID undoes events with "!" actions and unwinds them in exact reverse order
  (verified on real rollbacks, see docs/DATA_CAPABILITIES.md). Every applied event is pushed
  on an undo stack with a snapshot of the state before it. A reversal pops its matching event
  (same type minus "!", same actor id, same target id), voids every row that event produced,
  and restores the snapshot if it was the top of the stack. Anything else is counted, not guessed.
* Reconciliation counters say exactly what happened to every input event.
"""
from __future__ import annotations

import bisect
import collections
import copy
from dataclasses import dataclass, field
from datetime import datetime

from ..config import FRAME_LIMIT_LOW_RATE_MS, FRAME_LIMIT_MS
from ..schema import SCHEMAS


def ts_ms(s: str) -> int:
    return int(datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp() * 1000)


def _pos(obj):
    p = ((obj or {}).get("state") or {}).get("game", {}).get("position")
    return (p["x"], p["y"]) if p else (None, None)


def _current_game(series_state):
    games = (series_state or {}).get("games") or []
    live = [g for g in games if g.get("started") and not g.get("finished")]
    return (live or games or [None])[-1]


@dataclass
class State:
    game_id: str | None = None
    map: str | None = None
    bounds: tuple | None = None
    round_no: int | None = None
    round_start_ms: int | None = None
    freeze_end_ms: int | None = None
    plant_ms: int | None = None
    round_end_ms: int | None = None

    def phase(self, now):
        if self.round_end_ms is not None and now >= self.round_end_ms:
            return "post_round"
        if self.freeze_end_ms is None or now < self.freeze_end_ms:
            return "buy"
        return "post_plant" if self.plant_ms is not None and now >= self.plant_ms else "pre_plant"


@dataclass
class Applied:
    key: tuple
    event_id: str
    before: State
    rows: list = field(default_factory=list)  # (table, row) produced by this event


class SeriesReducer:
    def __init__(self, series_id: str):
        self.sid = str(series_id)
        self.state = State()
        self.stack: list[Applied] = []
        self.rows = {t: [] for t in SCHEMAS}
        self.voided: set[int] = set()  # id() of voided row dicts
        self.reversed_event_ids: set[str] = set()
        self.counts = collections.Counter()
        self.types = collections.Counter()
        self.game_map: dict[str, str] = {}
        self.last_pos: dict[str, tuple] = {}
        self.points: dict[tuple, list] = collections.defaultdict(list)  # (map, bounds) -> xy, for outlines
        self._cur: Applied | None = None
        self._seq = 0

    # ------------------------------------------------------------------ helpers
    def _emit(self, table: str, **row):
        row.setdefault("series_id", self.sid)
        row.setdefault("game_id", self.state.game_id)
        row.setdefault("map", self.state.map)
        row.setdefault("round_no", self.state.round_no)
        self.rows[table].append(row)
        if self._cur is not None:
            self._cur.rows.append((table, row))
        self.counts[f"rows_created.{table}"] += 1

    def _t_round(self, now):
        return None if self.state.freeze_end_ms is None else (now - self.state.freeze_end_ms) / 1000.0

    def _t_plant(self, now):
        p = self.state.plant_ms
        return None if p is None or now < p else (now - p) / 1000.0

    def _fresh(self, pid, x, y):
        """True if this player's position equals the last one we saw (stationary or stale)."""
        if x is None or pid is None:
            return None
        rep = self.last_pos.get(pid) == (x, y)
        self.last_pos[pid] = (x, y)
        if self.state.map and self.state.bounds:
            self.points[(self.state.map, self.state.bounds)].append((x, y))
        return rep

    def _sync_game(self, gm):
        if not gm:
            return
        self.state.game_id = gm["id"]
        m = gm.get("map") or {}
        if m.get("name"):
            self.state.map = m["name"]
            b = m.get("bounds") or {}
            if b:
                self.state.bounds = (b["min"]["x"], b["min"]["y"], b["max"]["x"], b["max"]["y"])
            self.game_map[gm["id"]] = m["name"]

    # ------------------------------------------------------------------ feed
    def feed(self, env: dict):
        now = ts_ms(env["occurredAt"])
        for e in env.get("events") or []:
            t = e.get("type") or ""
            self.types[t] += 1
            self.counts["events_in"] += 1
            self._seq += 1
            a, g = e.get("actor") or {}, e.get("target") or {}
            if t.startswith("grid-") and "-!" in t:
                # GRID also retracts its own markers (grid-!validated-series ...); no rows or state involved
                self.counts[f"markers_reversed.{t}"] += 1
                continue
            if "-!" in t:
                self._reverse((t.replace("-!", "-", 1), a.get("id"), g.get("id")), e)
                continue
            if t.startswith("grid-"):
                # feed-control markers (grid-invalidated-series, grid-validated-series, ...): GRID emits
                # them right before unwinding; they change no state and are never reversed, so they stay
                # off the undo stack (otherwise every following reversal looks non-LIFO).
                self.counts[f"markers.{t}"] += 1
                continue
            applied = Applied(key=(t, a.get("id"), g.get("id")), event_id=e.get("id"),
                              before=copy.copy(self.state))
            self._cur = applied
            try:
                self._apply(t, e, now)
            finally:
                self._cur = None
            self.stack.append(applied)

    def _reverse(self, key, e):
        self.counts["reversals_in"] += 1
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i].key == key:
                ap = self.stack.pop(i)
                for table, row in ap.rows:
                    self.voided.add(id(row))
                    self.counts[f"rows_voided.{table}"] += 1
                self.reversed_event_ids.add(ap.event_id)
                if i == len(self.stack):  # it was the top: exact LIFO, state can be restored
                    self.state = ap.before
                    self.counts["reversals_lifo"] += 1
                else:
                    self.counts["reversals_non_lifo"] += 1
                return
        self.counts["reversals_unmatched"] += 1

    def _apply(self, t, e, now):
        if e.get("includesFullState") and e.get("seriesState"):
            self._sync_game(_current_game(e["seriesState"]))
        s = self.state
        if t == "series-started-game":
            s.game_id = (e.get("target") or {}).get("id") or s.game_id
            s.round_no = s.round_start_ms = s.freeze_end_ms = s.plant_ms = s.round_end_ms = None
        elif t == "game-started-round":
            s.round_no = (e["target"].get("state") or {}).get("sequenceNumber")
            s.round_start_ms, s.freeze_end_ms, s.plant_ms, s.round_end_ms = now, None, None, None
        elif t == "round-started-freezetime":
            self._spawns(e)
        elif t == "round-ended-freezetime":
            s.freeze_end_ms = now
            rno = (e["actor"].get("state") or {}).get("sequenceNumber")
            if rno is not None:
                s.round_no = rno
            self._emit("round_clock", round_start_ms=s.round_start_ms, freeze_end_ms=now, event_id=e.get("id"))
            self._player_rounds(e, now)
        elif t == "team-won-round":
            st = e["actor"].get("state") or {}
            self._emit("rounds", winner_team_id=st.get("id"), winner_side=st.get("side"),
                       freeze_end_ms=s.freeze_end_ms, plant_ms=s.plant_ms, end_ms=now, event_id=e.get("id"))
            s.round_end_ms = now
        elif t in ("player-damaged-player", "player-killed-player"):
            self._engagement(t, e, now)
        elif t in ("player-completed-plantBomb", "player-completed-defuseBomb", "player-completed-explodeBomb"):
            kind = {"player-completed-plantBomb": "plant", "player-completed-defuseBomb": "defuse",
                    "player-completed-explodeBomb": "detonate"}[t]
            if kind == "plant":
                s.plant_ms = now
            a = e.get("actor") or {}
            x, y = _pos(a)
            self._emit("objectives", event_id=e.get("id"), kind=kind, ts_ms=now, t_round=self._t_round(now),
                       player_id=a.get("id"), team_id=(a.get("state") or {}).get("teamId"), x=x, y=y)
        elif t in ("player-pickedUp-item", "player-dropped-item"):
            a, g = e.get("actor") or {}, e.get("target") or {}
            self._emit("inventory_events", event_id=e.get("id"),
                       kind="pickup" if "pickedUp" in t else "drop", ts_ms=now, t_round=self._t_round(now),
                       player_id=a.get("id"), team_id=(a.get("state") or {}).get("teamId"), item=g.get("id"))
        elif t.startswith("player-"):
            for k in ("actor", "target"):
                o = e.get(k) or {}
                if o.get("type") == "player":
                    self._fresh(o.get("id"), *_pos(o))

    def _spawns(self, e):
        gm = _current_game(e.get("seriesState"))
        if not gm:
            return
        rno = (e["actor"].get("state") or {}).get("sequenceNumber")
        for tm in gm.get("teams", []):
            for p in tm.get("players", []):
                pos = p.get("position")
                if pos:
                    self._emit("spawns", round_no=rno, team_id=tm["id"], side=tm.get("side"), player_id=p["id"],
                               x=pos["x"], y=pos["y"], event_id=e.get("id"))

    def _player_rounds(self, e, now):
        gm = _current_game(e.get("seriesState"))
        if not gm:
            self.counts["freeze_end_without_state"] += 1
            return
        for tm in gm.get("teams", []):
            for p in tm.get("players", []):
                items = [i["id"] for i in (p.get("inventory") or {}).get("items", [])]
                pos = p.get("position") or {}
                self._emit("player_rounds", team_id=tm["id"], team_name=tm.get("name"), side=tm.get("side"),
                           team_money=tm.get("money"), team_loadout=tm.get("loadoutValue"),
                           player_id=p["id"], player_name=p.get("name"),
                           agent=(p.get("character") or {}).get("id"), money=p.get("money"),
                           loadout_value=p.get("loadoutValue"), items="|".join(items),
                           x=pos.get("x"), y=pos.get("y"), freeze_end_ms=now, event_id=e.get("id"))

    def _engagement(self, t, e, now):
        a, v = e.get("actor") or {}, e.get("target") or {}
        ast, vst = a.get("state") or {}, v.get("state") or {}
        ax, ay = _pos(a)
        vx, vy = _pos(v)
        rd = (a.get("stateDelta") or {}).get("round") or {}
        if t == "player-killed-player":
            weapon = next(iter(rd.get("weaponKills") or {}), None)
            dmg = hit = None
        else:
            src = rd.get("damageDealtSources") or []
            weapon = src[0]["source"]["name"] if src else None
            tg = rd.get("damageDealtTargets") or []
            hit = tg[0]["target"]["name"] if tg else None
            dmg = rd.get("damageDealt")
        if weapon is None:
            self.counts["engagement_weapon_unknown"] += 1
        self._emit("engagements", event_id=e.get("id"), seq=self._seq,
                   kind="kill" if t == "player-killed-player" else "damage",
                   ts_ms=now, t_round=self._t_round(now), t_plant=self._t_plant(now), phase=self.state.phase(now),
                   weapon=weapon, damage=dmg, hit=hit,
                   att_id=a.get("id"), att_name=ast.get("name"), att_team=ast.get("teamId"), att_side=ast.get("side"),
                   att_x=ax, att_y=ay, att_pos_repeat=self._fresh(a.get("id"), ax, ay),
                   vic_id=v.get("id"), vic_name=vst.get("name"), vic_team=vst.get("teamId"), vic_side=vst.get("side"),
                   vic_x=vx, vic_y=vy, vic_pos_repeat=self._fresh(v.get("id"), vx, vy))

    # ------------------------------------------------------------------ supplement
    def add_casts(self, records):
        """Join supplement casts to rounds using the (non-voided) round clocks."""
        # index rounds by their START so buy-phase casts land in their own round (negative clock)
        clocks = collections.defaultdict(list)
        freeze = {}
        for r in self.live("round_clock"):
            start = r["round_start_ms"] if r["round_start_ms"] is not None else r["freeze_end_ms"]
            clocks[r["game_id"]].append((start, r["round_no"]))
            freeze[(r["game_id"], r["round_no"])] = r["freeze_end_ms"]
        ends = {(r["game_id"], r["round_no"]): r["end_ms"] for r in self.live("rounds")}
        plants = {}
        for r in self.live("objectives"):
            if r["kind"] == "plant":
                plants[(r["game_id"], r["round_no"])] = r["ts_ms"]
        who = {(r["game_id"], r["round_no"], r["player_id"]): (r["team_id"], r["side"], r["agent"])
               for r in self.live("player_rounds")}
        for k in clocks:
            clocks[k].sort()
        for rec in records:
            self.counts["casts_in"] += 1
            if rec.get("grid_event_id") and rec["grid_event_id"] in self.reversed_event_ids:
                self.counts["casts_excluded.reversed_in_grid"] += 1
                continue
            now = ts_ms(rec["occurred_at"])
            gid = rec["game_id"]
            idx = clocks.get(gid, [])
            i = bisect.bisect_right(idx, (now, 10 ** 9)) - 1
            rno = idx[i][1] if i >= 0 else None
            freeze_end = freeze.get((gid, rno))
            if rno is None:
                self.counts["casts_round_unknown"] += 1
            plant = plants.get((gid, rno))
            team, side, agent = who.get((gid, rno, rec.get("player_id")), (None, None, None))
            src, pos_source, dt, low_rate = self._cast_geometry(rec)
            if src is None:
                self.counts["casts_no_geometry"] += 1
            p = (src or {}).get("position") or {}
            vw = (src or {}).get("view") or {}
            limit = FRAME_LIMIT_LOW_RATE_MS if low_rate else FRAME_LIMIT_MS
            spatial_ok = src is not None and dt is not None and dt <= limit
            gmap = self.game_map.get(gid)
            if spatial_ok and gmap and p.get("x") is not None:
                for (m, b) in list(self.points):  # casts are the most precise positions: add to outlines
                    if m == gmap:
                        self.points[(m, b)].append((p["x"], p["y"]))
                        break
            t_round = None if freeze_end is None else (now - freeze_end) / 1000.0
            end = ends.get((gid, rno))
            if end is not None and now > end:
                phase = "post_round"
            elif t_round is None or t_round < 0:
                phase = "buy"
            else:
                phase = "post_plant" if plant is not None and now >= plant else "pre_plant"
            self.rows["casts"].append(dict(
                series_id=self.sid, game_id=gid, map=self.game_map.get(gid), round_no=rno,
                grid_event_id=rec.get("grid_event_id"), in_grid=rec.get("in_grid"), ts_ms=now, t_round=t_round,
                t_plant=None if plant is None or now < plant else (now - plant) / 1000.0, phase=phase,
                player_id=rec.get("player_id"), team_id=team, side=side, agent=agent,
                ability=rec.get("ability"), slot=rec.get("slot"), quality=rec.get("quality"),
                pos_source=pos_source, pos_dt_ms=dt, low_rate=low_rate, spatial_ok=spatial_ok,
                x=p.get("x"), y=p.get("y"), z=p.get("z"), vx=vw.get("x"), vy=vw.get("y"), vz=vw.get("z")))
            self.counts["rows_created.casts"] += 1

    @staticmethod
    def _cast_geometry(rec):
        """Pick the position to trust, per the supplement README's quality semantics."""
        fb, fa, q = rec.get("frame_before"), rec.get("frame_after"), rec.get("quality")
        low_rate = bool(fb and fa and (fa["offset_ms"] - fb["offset_ms"]) > 600)
        near = [f for f in (fb, fa) if f]
        dt = min((abs(f["offset_ms"]) for f in near), default=None)
        if q == "ok" and rec.get("interpolated"):
            return rec["interpolated"], "interpolated", dt, low_rate
        if q == "gap_exceeded" and near:  # caster likely died: use the closer real frame
            f = min(near, key=lambda f: abs(f["offset_ms"]))
            return f, "frame_before" if f is fb else "frame_after", abs(f["offset_ms"]), low_rate
        if q in ("missing_after", "missing_before") and rec.get("interpolated"):
            return rec["interpolated"], q, dt, low_rate
        return None, None, None, low_rate

    # ------------------------------------------------------------------ output
    def live(self, table):
        return [r for r in self.rows[table] if id(r) not in self.voided]

    def finish(self) -> dict:
        out = {t: self.live(t) for t in self.rows}
        for t, rows in out.items():
            self.counts[f"rows_out.{t}"] = len(rows)
        self.counts["event_types"] = len(self.types)
        return out
