"""Ultimates: which ones a team uses, when, and what the 10 seconds after are worth.

A use is the ult's cast record, or for weapon ults with no reliable cast (Tour de Force, Blade Storm,
Overdrive) its first damage hit in the round. Each use opens a 10 s window; kills and deaths in that
window are counted for the team, and their change in round-win chance (engine/model/wpa.py scores)
is summed from the team's side.
"""
from __future__ import annotations

from collections import Counter

import numpy as np

from ..abilities import ULTS, WEAPON_ULTS, sql_list
from ..config import V2_DIR
from .core import Filters, MetricDef, MetricResult, Rate, bootstrap_mean, metric, ranked

WINDOW_MS = 10_000
MIN_BOOT = 10
EVENT_WP = V2_DIR / "models" / "event_wp.parquet"

ULT_USAGE = MetricDef(
    id="ult.usage", version=1, title="Ultimates",
    question="Which ultimates does the team use on this map and side, when, and what happens in the 10 s after?",
    population="The team's rounds on one map and side where they fielded the ult's agent",
    numerator="Rounds with at least one use of the ultimate",
    unit="rounds",
    caveats=("Tour de Force, Blade Storm and Overdrive have no reliable cast record: their use is their first damage "
             "hit, so uses that never hit anyone aren't seen.",
             "The 10 s after an ult credits every kill and death in that window to the ult. Teams often ult when "
             "they were going to fight anyway, so this is association, not cause.",
             "Win-chance swing uses the win-probability model (no positions). Rounds where an ult is used aren't "
             "random: compare against the league on the same map and side, not against zero.",
             "Uses after the round result are left out, and so are ult casts in the buy phase: about half of all "
             "Viper's Pit casts are recorded there and no other ult is, which looks like a recording artefact."),
)


def _clauses(f: Filters, team: bool, cols: dict):
    w, p = [], []
    if team:
        w.append(f"{cols['team']} = ?"); p.append(f.team_id)
        if f.player_id:
            w.append(f"{cols['player']} = ?"); p.append(f.player_id)
    if f.map:
        w.append(f"{cols['map']} = ?"); p.append(f.map)
    if f.side:
        w.append(f"{cols['side']} = ?"); p.append(f.side)
    if f.since:
        w.append(f"{cols['date']} >= ?::TIMESTAMP"); p.append(f.since)
    if f.until:
        w.append(f"{cols['date']} < ?::TIMESTAMP"); p.append(f.until)
    return " AND ".join(w) or "TRUE", p


def ult_uses(con, f: Filters, team: bool = True):
    """(round_key, series_id, team_id, side, ability, agent, player, ts_ms, t_round, phase, x, y, won).
    Filters are applied inside each source before any join, so only this team's (or this map's) ults are read."""
    cw, cp = _clauses(f, team, dict(team="c.team_id", player="c.player_id", map="c.map", side="c.side", date="c.started_at"))
    ew, ep = _clauses(f, team, dict(team="e.att_team", player="e.att_id", map="e.map", side="e.att_side", date="e.started_at"))
    return con.execute(f"""
        WITH c AS (
          SELECT c.round_key, c.series_id, c.team_id, c.side, c.ability, c.agent, c.player_id, c.ts_ms, c.t_round,
                 c.phase, CASE WHEN c.spatial_ok THEN c.x END AS x, CASE WHEN c.spatial_ok THEN c.y END AS y
          FROM casts c
          WHERE {cw} AND c.ability IN {sql_list(ULTS - WEAPON_ULTS)} AND c.phase IN ('pre_plant', 'post_plant')),
        w AS (
          SELECT e.round_key, any_value(e.series_id) series_id, any_value(e.att_team) team_id, any_value(e.att_side) side,
                 e.weapon AS ability, any_value(e.att_agent) agent, e.att_id AS player_id, min(e.ts_ms) ts_ms,
                 arg_min(e.t_round, e.ts_ms) t_round, arg_min(e.phase, e.ts_ms) phase,
                 arg_min(e.att_x, e.ts_ms) x, arg_min(e.att_y, e.ts_ms) y
          FROM engagements e
          WHERE {ew} AND e.weapon IN {sql_list(WEAPON_ULTS)} AND e.kind IN ('damage', 'kill')
            AND e.phase IN ('pre_plant', 'post_plant')
          GROUP BY e.round_key, e.att_id, e.weapon),
        u AS (SELECT * FROM c UNION ALL SELECT * FROM w)
        SELECT u.round_key, u.series_id, u.team_id, u.side, u.ability, u.agent, pr.player_name, u.ts_ms, u.t_round,
               u.phase, u.x, u.y, (r.winner_team_id = u.team_id) AS won
        FROM u
        JOIN rounds r ON r.round_key = u.round_key
        LEFT JOIN player_rounds pr ON pr.round_key = u.round_key AND pr.player_id = u.player_id
        ORDER BY u.round_key, u.ts_ms""", cp + ep).fetchall()


def window_effects(con, uses):
    """For each use: (kills for, deaths, win-chance swing in points or None) in the 10 s after."""
    if not uses:
        return []
    import pandas as pd
    df = pd.DataFrame([dict(i=i, round_key=u[0], team_id=u[2], side=u[3], ts=u[7]) for i, u in enumerate(uses)])
    con.register("ult_uses_df", df)
    try:
        has_wp = EVENT_WP.exists()
        wp_join = (f"LEFT JOIN read_parquet('{EVENT_WP.as_posix()}') wp ON wp.event_id = e.event_id"
                   if has_wp else "")
        wp_expr = ("sum(CASE WHEN u.side = 'attacker' THEN wp.wp_after - wp.wp_before "
                   "ELSE wp.wp_before - wp.wp_after END) * 100" if has_wp else "NULL")
        rows = con.execute(f"""
            SELECT u.i,
                   count(*) FILTER (WHERE e.att_team = u.team_id AND e.vic_team <> u.team_id) AS kills,
                   count(*) FILTER (WHERE e.vic_team = u.team_id) AS deaths,
                   {wp_expr} AS swing
            FROM ult_uses_df u
            LEFT JOIN engagements e ON e.round_key = u.round_key AND e.kind = 'kill'
                 AND e.ts_ms >= u.ts AND e.ts_ms <= u.ts + {WINDOW_MS}
                 AND e.phase IN ('pre_plant', 'post_plant')
            {wp_join}
            GROUP BY u.i ORDER BY u.i""").fetchall()
    finally:
        con.unregister("ult_uses_df")
    out = [(0, 0, None)] * len(uses)
    for i, k, d, s in rows:
        out[i] = (k or 0, d or 0, round(float(s), 2) if s is not None else (0.0 if has_wp else None))
    return out


_LEAGUE_CACHE: dict = {}


def _league(con, map_name, side, since, until):
    key = (map_name, side, since, until, EVENT_WP.stat().st_mtime if EVENT_WP.exists() else None)
    if key not in _LEAGUE_CACHE:
        uses = ult_uses(con, Filters(team_id="", map=map_name, side=side, since=since, until=until), team=False)
        league = {}
        for u, e in zip(uses, window_effects(con, uses)):
            if e[2] is not None:
                league.setdefault(u[4], []).append(e[2])
        _LEAGUE_CACHE[key] = league
    return _LEAGUE_CACHE[key]


@metric(ULT_USAGE)
def ult_usage(con, f: Filters) -> MetricResult:
    res = MetricResult(ULT_USAGE, f)
    if not (f.map and f.side):
        res.warnings.append("Pick one map and one side to see ultimates.")
        return res
    uses = ult_uses(con, f)
    effects = window_effects(con, uses)

    # denominators: rounds where the team fielded the ult's agent
    pw, pp = f.where("p")
    agent_rounds = {}
    for agent, rk in con.execute(f"SELECT DISTINCT agent, round_key FROM player_rounds p WHERE {pw}", pp).fetchall():
        agent_rounds.setdefault(agent, set()).add(rk)

    # league: every team on this map and side, swing per use of each ult (cached: the data is read-only)
    league = _league(con, f.map, f.side, f.since, f.until)

    by = {}
    for u, e in zip(uses, effects):
        by.setdefault(u[4], []).append((u, e))
    for ab, items in sorted(by.items(), key=lambda kv: (-len({x[0][0] for x in kv[1]}), kv[0])):
        agent = ranked(Counter(x[0][5] for x in items), 1)[0][0]
        rounds = sorted({x[0][0] for x in items})
        fielded = agent_rounds.get(agent, set()) | set(rounds)
        swings = [x[1][2] for x in items if x[1][2] is not None]
        series = [x[0][1] for x in items if x[1][2] is not None]
        lo = hi = None
        if len(swings) >= MIN_BOOT and len(set(series)) > 1:      # one series has no range
            lo, hi = bootstrap_mean(swings, series)
        lg = league.get(ab, [])
        won_with = [r for r in rounds if any(x[0][12] for x in items if x[0][0] == r)]
        res.breakdown.append(dict(
            bucket=ab, ability=ab, agent=agent, rate=Rate.over("util.ults.used", rounds, fielded), uses=len(items),
            players=[dict(name=nm, k=k) for nm, k in ranked(Counter(x[0][6] for x in items if x[0][6]), 2)],
            median_t=round(float(np.median([x[0][8] for x in items if x[0][8] is not None])), 1),
            post_plant=sum(1 for x in items if x[0][9] == "post_plant"),
            kills=sum(x[1][0] for x in items), deaths=sum(x[1][1] for x in items),
            swing=round(float(np.mean(swings)), 2) if swings else None,
            swing_lo=round(lo, 2) if lo is not None else None, swing_hi=round(hi, 2) if hi is not None else None,
            league_swing=round(float(np.mean(lg)), 2) if lg else None, league_uses=len(lg),
            won=Rate.over("util.ults.won", won_with, rounds),
            seen_only_on_hit=ab in WEAPON_ULTS,
            round_keys=rounds,
        ))
    res.value = dict(window_s=WINDOW_MS / 1000, scored=EVENT_WP.exists())
    if not EVENT_WP.exists():
        res.warnings.append("Win-chance swing needs the WPA scores: run python -m engine.model.wpa.")
    if res.breakdown:
        top = res.breakdown[0]
        res.rate = top["rate"]
        res.supporting = top["round_keys"]
        res.contrary = sorted(agent_rounds.get(top["agent"], set()) - set(top["round_keys"]))
    res.maps = len({u[0].split(":")[0] for u in uses})
    return res
