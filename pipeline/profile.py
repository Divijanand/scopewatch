"""Operator profile for one team: the numbers behind every Scopewatch view.

All rates come with their sample size and a Wilson 95% interval so small samples
read as uncertain instead of as confident percentages.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import duckdb
import numpy as np

from .config import DB_PATH

Z = 1.96


def wilson(k: int, n: int) -> dict:
    if n == 0:
        return dict(k=0, n=0, p=None, lo=None, hi=None)
    p = k / n
    d = 1 + Z * Z / n
    c = (p + Z * Z / (2 * n)) / d
    h = Z * math.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n)) / d
    return dict(k=k, n=n, p=round(p, 4), lo=round(max(0, c - h), 4), hi=round(min(1, c + h), 4))


@dataclass
class Filters:
    team_id: str
    map: str | None = None
    side: str | None = None  # 'attacker' | 'defender'
    since: str | None = None  # ISO date
    player_id: str | None = None

    def where(self, alias: str = "", team_col: str = "team_id", side_col: str = "side"):
        a = f"{alias}." if alias else ""
        w, p = [f"{a}{team_col} = ?"], [self.team_id]
        if self.map:
            w.append(f"{a}map = ?"); p.append(self.map)
        if self.side:
            w.append(f"{a}{side_col} = ?"); p.append(self.side)
        if self.since:
            w.append(f"{a}started_at >= ?::TIMESTAMP"); p.append(self.since)
        return " AND ".join(w), p


def connect(read_only=True):
    return duckdb.connect(DB_PATH.as_posix(), read_only=read_only)


def spawns(con, map_name: str) -> dict:
    """Spawn point per side for a map (median position when the buy phase starts)."""
    rows = con.execute("SELECT side, x, y FROM spawns WHERE map = ?", [map_name]).fetchall()
    return {s: (x, y) for s, x, y in rows}


def forwardness(x, y, own, enemy):
    """0 = at own spawn, 1 = at enemy spawn, 0.5 = equally far from both.

    A distance ratio rather than a projection on the spawn-to-spawn axis, because on
    three-site maps (Haven, Lotus) sites sit off to the side of that axis.
    """
    d_own = np.hypot(np.asarray(x) - own[0], np.asarray(y) - own[1])
    d_enemy = np.hypot(np.asarray(x) - enemy[0], np.asarray(y) - enemy[1])
    return d_own / (d_own + d_enemy)


def team_profile(f: Filters, con=None) -> dict:
    con = con or connect()
    w, p = f.where()

    # --- buy behaviour
    tot = con.execute(f"SELECT count(*), count(DISTINCT game_id) FROM op_rounds WHERE {w}", p).fetchone()
    with_op = con.execute(f"SELECT count(*) FROM op_rounds WHERE {w} AND n_op > 0", p).fetchone()[0]
    by_econ = con.execute(
        f"""SELECT economy, count(*) n, count(*) FILTER (WHERE n_op > 0) k,
                   count(*) FILTER (WHERE n_op > 0 AND won) k_won
            FROM op_rounds WHERE {w} GROUP BY economy ORDER BY economy""", p).fetchall()
    by_side = con.execute(
        f"""SELECT side, count(*) n, count(*) FILTER (WHERE n_op > 0) k
            FROM op_rounds WHERE {w} GROUP BY side""", p).fetchall()
    win_with = con.execute(
        f"""SELECT count(*) FILTER (WHERE n_op > 0 AND won), count(*) FILTER (WHERE n_op > 0),
                   count(*) FILTER (WHERE n_op = 0 AND won AND economy = 'full'),
                   count(*) FILTER (WHERE n_op = 0 AND economy = 'full')
            FROM op_rounds WHERE {w}""", p).fetchone()

    # --- carriers
    lw, lp = f.where()
    carriers = con.execute(
        f"""SELECT player_id, any_value(player_name) name, count(*) k,
                   mode(agent) top_agent, list(DISTINCT agent) agents
            FROM loadouts WHERE {lw} AND has_op GROUP BY player_id ORDER BY k DESC""", lp).fetchall()

    # --- possession shifts: when the round's carrier differs from that map's main carrier
    shifts = con.execute(
        f"""WITH r AS (
              SELECT game_id, round_no, unnest(op_player_ids) pid FROM op_rounds WHERE {w} AND n_op > 0),
            main AS (SELECT game_id, mode(pid) main_pid, count(*) n FROM r GROUP BY game_id)
            SELECT count(*) FILTER (WHERE r.pid <> m.main_pid), count(*)
            FROM r JOIN main m USING (game_id)""", p).fetchone()

    # --- engagements fired with the rifle
    ew, ep = f.where(alias="o", team_col="att_team", side_col="att_side")
    if f.player_id:
        ew += " AND o.att_id = ?"; ep.append(f.player_id)
    eng = con.execute(
        f"""SELECT o.game_id, o.round_no, o.map, o.kind, o.weapon, o.t_round, o.t_bucket, o.nth_for_team,
                   o.att_id, o.att_name, o.att_agent, o.att_side, o.att_x, o.att_y,
                   o.vic_name, o.vic_x, o.vic_y, (r.winner_team_id = o.att_team) AS won
            FROM op_eng o LEFT JOIN rounds r USING (game_id, round_no)
            WHERE {ew} ORDER BY o.ts_ms""", ep).fetchall()
    cols = ["game_id", "round_no", "map", "kind", "weapon", "t_round", "t_bucket", "nth", "att_id", "att_name",
            "agent", "side", "x", "y", "vic_name", "vx", "vy", "won"]
    eng = [dict(zip(cols, r)) for r in eng]

    # forwardness per engagement (needs a single map for a meaningful axis)
    league_fwd = {}
    if f.map:
        sp = spawns(con, f.map)
        if {"attacker", "defender"} <= sp.keys():
            def fwd_for(side, x, y):
                own, enemy = (sp["defender"], sp["attacker"]) if side == "defender" else (
                    sp["attacker"], sp["defender"])
                return forwardness(x, y, own, enemy)
            for e in eng:
                e["fwd"] = round(float(fwd_for(e["side"], e["x"], e["y"])), 3)
            # league baseline: every team's Operator engagements on this map, per side
            for side, xs, ys in con.execute(
                    """SELECT att_side, list(att_x), list(att_y) FROM op_eng
                       WHERE map = ? AND att_x IS NOT NULL GROUP BY att_side""", [f.map]).fetchall():
                league_fwd[side] = round(float(np.median(fwd_for(side, np.array(xs), np.array(ys)))), 3)

    kills = [e for e in eng if e["kind"] == "kill"]
    buckets = {}
    for b in ("0-20s", "20-40s", "40-60s", "60s+"):
        kb = [e for e in kills if e["t_bucket"] == b]
        buckets[b] = dict(kills=len(kb), share=wilson(len(kb), len(kills)))
    opening = [e for e in kills if e["nth"] == 1]

    return dict(
        filters=f.__dict__,
        sample=dict(rounds=tot[0], maps=tot[1], op_engagements=len(eng), op_kills=len(kills)),
        buy_rate=wilson(with_op, tot[0]),
        buy_by_economy={e: wilson(k, n) | dict(win_rate_with_op=wilson(kw, k)) for e, n, k, kw in by_econ},
        buy_by_side={s: wilson(k, n) for s, n, k in by_side},
        win_rate_with_op=wilson(win_with[0], win_with[1]),
        win_rate_full_buy_without_op=wilson(win_with[2], win_with[3]),
        carriers=[dict(player_id=a, name=b, rounds=k, share=wilson(k, with_op), top_agent=d, agents=e)
                  for a, b, k, d, e in carriers],
        possession_shift=wilson(shifts[0], shifts[1]),
        kill_timing=buckets,
        median_kill_t=float(np.median([e["t_round"] for e in kills])) if kills else None,
        league_fwd=league_fwd,
        engagements=eng,
    )
