"""Operator setups and where the Operator dies, in callout language (engine/callouts.py)."""
from __future__ import annotations

from collections import Counter

import numpy as np

from .core import Filters, MetricDef, MetricResult, Rate, Unknown, metric, ranked
from .operator import OP

MIN_LEAGUE_ROUNDS = 20

SETUPS = MetricDef(
    id="op.setups", version=2, title="Where they play it",
    question="Where is the Operator/Outlaw when the team fires it for the first time in a round?",
    population="Team rounds on one map and side where the team fired an Operator/Outlaw (kill or hit) "
               "between buy-phase end and the round result",
    numerator="Rounds whose first Operator shot was taken from this callout",
    unit="rounds",
    caveats=("Callouts are the nearest community callout anchor the shooter could reach on the minimap; "
             "an approximation, not an official zone.",
             "First recorded Operator shot of the round: where the rifle fought, not necessarily where it set up.",
             "A first shot counts as a kill when the same player gets an Operator kill within 1 s.",
             "League share uses every team's rounds on the same map and side."),
)


def _first_shots(con, where: str, params: list):
    """One row per (team, round): the team's first Operator/Outlaw shot."""
    return con.execute(f"""
        WITH s AS (
          SELECT e.*, row_number() OVER (PARTITION BY e.round_key, e.att_team ORDER BY e.ts_ms, e.seq) rn,
                 bool_or(e.kind = 'kill') OVER (PARTITION BY e.round_key, e.att_id ORDER BY e.ts_ms
                                                RANGE BETWEEN CURRENT ROW AND 1000 FOLLOWING) killed
          FROM engagements e
          WHERE {where} AND e.weapon IN {OP} AND e.kind IN ('kill', 'damage')
            AND e.phase IN ('pre_plant', 'post_plant'))
        SELECT round_key, att_team, att_id, att_name, att_callout, vic_callout,
               CASE WHEN killed THEN 'kill' ELSE 'damage' END, t_round
        FROM s WHERE rn = 1""", params).fetchall()


def _need_map(res: MetricResult, f: Filters) -> bool:
    if not (f.map and f.side):
        res.warnings.append("Pick one map and one side to see callouts.")
        return False
    return True


@metric(SETUPS)
def setups(con, f: Filters) -> MetricResult:
    res = MetricResult(SETUPS, f)
    if not _need_map(res, f):
        return res
    w, p = f.where("e", team_col="att_team", side_col="att_side")
    if f.player_id:
        w += " AND e.att_id = ?"; p.append(f.player_id)
    rows = _first_shots(con, w, p)
    named = [r for r in rows if r[4]]
    if len(named) < len(rows):
        res.unknown.append(Unknown(len(rows) - len(named), "shooter position more than 25 m from any callout"))
    n = len(named)

    lw, lp = ["e.map = ?", "e.att_side = ?"], [f.map, f.side]
    if f.since:
        lw.append("e.started_at >= ?::TIMESTAMP"); lp.append(f.since)
    if f.until:
        lw.append("e.started_at < ?::TIMESTAMP"); lp.append(f.until)
    league = [r for r in _first_shots(con, " AND ".join(lw), lp) if r[4]]
    league_n = len(league)
    league_by = Counter(r[4] for r in league)

    by = {}
    for r in named:
        by.setdefault(r[4], []).append(r)
    for callout, rs in sorted(by.items(), key=lambda kv: (-len(kv[1]), str(kv[0]))):
        players = ranked(Counter(r[3] for r in rs))
        targets = ranked(Counter(r[5] for r in rs if r[5]), 2)
        res.breakdown.append(dict(
            bucket=callout, callout=callout, rate=Rate.of(len(rs), n),
            players=[dict(name=nm, k=k) for nm, k in players],
            targets=[dict(callout=c, k=k) for c, k in targets],
            kills=sum(1 for r in rs if r[6] == "kill"),
            median_t=round(float(np.median([r[7] for r in rs])), 1),
            league=Rate.of(league_by.get(callout, 0), league_n) if league_n >= MIN_LEAGUE_ROUNDS else None,
            round_keys=sorted({r[0] for r in rs}),
        ))
    if res.breakdown:
        top = res.breakdown[0]
        res.rate = top["rate"]
        res.supporting = top["round_keys"]
        res.contrary = sorted({r[0] for r in named} - set(top["round_keys"]))
    res.value = dict(league_rounds=league_n, rounds=n)
    res.maps = len({r[0].split(":")[0] for r in rows})
    return res


DEATHS = MetricDef(
    id="op.deaths", version=1, title="Where it dies",
    question="Where does the team's Operator/Outlaw holder die, and from where is the kill taken?",
    population="Deaths of a player who held an Operator/Outlaw at buy-phase end, on one map and side, "
               "between buy-phase end and the round result",
    numerator="Deaths at this callout",
    unit="deaths",
    caveats=("Holder = had the Operator/Outlaw at buy-phase end; they may have dropped or swapped it.",
             "Callouts are the nearest reachable community callout anchor, an approximation."),
)


@metric(DEATHS)
def deaths(con, f: Filters) -> MetricResult:
    res = MetricResult(DEATHS, f)
    if not _need_map(res, f):
        return res
    w, p = f.where("e", team_col="vic_team", side_col="vic_side")
    if f.player_id:
        w += " AND e.vic_id = ?"; p.append(f.player_id)
    rows = con.execute(f"""
        SELECT e.round_key, e.vic_name, e.vic_callout, e.att_callout, e.weapon, e.t_round, e.opening_kill
        FROM engagements e
        JOIN player_rounds pr ON pr.round_key = e.round_key AND pr.player_id = e.vic_id AND pr.has_op
        WHERE {w} AND e.kind = 'kill' AND e.phase IN ('pre_plant', 'post_plant')
        ORDER BY e.ts_ms""", p).fetchall()
    named = [r for r in rows if r[2]]
    if len(named) < len(rows):
        res.unknown.append(Unknown(len(rows) - len(named), "position more than 25 m from any callout"))
    n = len(named)
    by = {}
    for r in named:
        by.setdefault(r[2], []).append(r)
    for callout, rs in sorted(by.items(), key=lambda kv: (-len(kv[1]), str(kv[0]))):
        res.breakdown.append(dict(
            bucket=callout, callout=callout, rate=Rate.of(len(rs), n),
            from_=[dict(callout=c, k=k) for c, k in ranked(Counter(r[3] for r in rs if r[3]), 2)],
            weapons=[dict(weapon=wpn, k=k) for wpn, k in ranked(Counter(r[4] for r in rs), 2)],
            opening=sum(1 for r in rs if r[6]),
            median_t=round(float(np.median([r[5] for r in rs])), 1),
            round_keys=sorted({r[0] for r in rs}),
        ))
    if res.breakdown:
        top = res.breakdown[0]
        res.rate = top["rate"]
        res.supporting = top["round_keys"]
        res.contrary = sorted({r[0] for r in named} - set(top["round_keys"]))
    res.value = dict(first_death=Rate.of(sum(1 for r in named if r[6]), n))
    res.maps = len({r[0].split(":")[0] for r in rows})
    return res
