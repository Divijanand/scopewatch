"""How predictable a team is: for each habit, how often the opponent's best guess would be right,
compared with every other team on the same map and side.

A habit is one choice per round (where they first make contact, when, which site they plant, where the
Operator takes its first shot). "Best guess" = their most common choice; its share of rounds is how often
always guessing it would be right. Small samples inflate that share, so teams under MIN_ROUNDS aren't
compared and the team's own result is flagged.
"""
from __future__ import annotations

from collections import Counter

import numpy as np

from .core import Filters, MetricDef, MetricResult, Rate, metric, ranked
from .executes import plant_sites
from .operator import OP

MIN_ROUNDS = 12
TIME_BUCKETS = [(0, 15, "0–15s"), (15, 30, "15–30s"), (30, 45, "30–45s"), (45, 10_000, "45s+")]

PREDICTABILITY = MetricDef(
    id="team.predictability", version=1, title="How predictable they are",
    question="If an opponent always guessed this team's most common choice, how often would they be right, "
             "compared with other teams on this map and side?",
    population="The team's rounds on one map and side; each habit counts the rounds where it was observed",
    numerator="Rounds where the team made its most common choice",
    unit="rounds",
    caveats=("Habits: where the first fight involving the team happens (nearest callout of the team's player), "
             "when it happens (15 s windows), which site they plant on attack, and where the first Operator shot "
             "is taken.",
             "The score is the share of other teams they are more predictable than, averaged over the habits with "
             f"enough rounds. Teams with fewer than {MIN_ROUNDS} rounds for a habit aren't compared.",
             "A small sample makes anyone look predictable: the team's own result is flagged below "
             f"{MIN_ROUNDS} rounds.",
             "Predictable isn't bad on its own: a default that wins is a default for a reason. It's what an "
             "opponent can prepare for."),
)


def _choices(con, map_name, side, since, until):
    """{habit: {team_id: [(round_key, choice)]}} for every team on this map and side."""
    w, p = ["e.map = ?"], [map_name]
    if since:
        w.append("e.started_at >= ?::TIMESTAMP"); p.append(since)
    if until:
        w.append("e.started_at < ?::TIMESTAMP"); p.append(until)
    where = " AND ".join(w)
    out = {"contact_where": {}, "contact_when": {}, "site": {}, "sniper_spot": {}}

    # first fight per (round, team on this side): the team's player's callout and the time
    rows = con.execute(f"""
        WITH f AS (
          SELECT e.round_key, e.ts_ms, e.seq, e.t_round,
                 CASE WHEN e.att_side = ? THEN e.att_team ELSE e.vic_team END AS team,
                 CASE WHEN e.att_side = ? THEN e.att_callout ELSE e.vic_callout END AS callout
          FROM engagements e
          WHERE {where} AND e.kind IN ('kill', 'damage') AND e.phase = 'pre_plant'
            AND (e.att_side = ? OR e.vic_side = ?))
        SELECT round_key, team, arg_min(callout, (ts_ms, seq)), arg_min(t_round, (ts_ms, seq))
        FROM f GROUP BY 1, 2 ORDER BY 1, 2""", [side, side] + p + [side, side]).fetchall()
    for rk, team, callout, t in rows:
        if callout:
            out["contact_where"].setdefault(team, []).append((rk, callout))
        if t is not None:
            label = next(lb for lo, hi, lb in TIME_BUCKETS if lo <= t < hi) if t >= 0 else TIME_BUCKETS[0][2]
            out["contact_when"].setdefault(team, []).append((rk, label))

    # first sniper shot per (round, team on this side)
    rows = con.execute(f"""
        SELECT round_key, att_team, arg_min(att_callout, (ts_ms, seq))
        FROM engagements e
        WHERE {where} AND e.att_side = ? AND e.weapon IN {OP} AND e.kind IN ('kill', 'damage')
          AND e.phase IN ('pre_plant', 'post_plant')
        GROUP BY 1, 2 ORDER BY 1, 2""", p + [side]).fetchall()
    for rk, team, callout in rows:
        if callout:
            out["sniper_spot"].setdefault(team, []).append((rk, callout))

    # plant site on attack
    if side == "attacker":
        tw, tp = ["t.map = ?", "t.side = 'attacker'"], [map_name]
        if since:
            tw.append("t.started_at >= ?::TIMESTAMP"); tp.append(since)
        if until:
            tw.append("t.started_at < ?::TIMESTAMP"); tp.append(until)
        rows = con.execute(f"""
            SELECT t.round_key, t.team_id, arg_min(o.x, o.ts_ms), arg_min(o.y, o.ts_ms)
            FROM team_rounds t JOIN objectives o ON o.round_key = t.round_key AND o.kind = 'plant' AND o.team_id = t.team_id
            WHERE {' AND '.join(tw)} AND o.x IS NOT NULL
            GROUP BY 1, 2 ORDER BY 1, 2""", tp).fetchall()
        sites = plant_sites(map_name, [r[2] for r in rows], [r[3] for r in rows])
        for (rk, team, _, _), s in zip(rows, sites):
            if s:
                out["site"].setdefault(team, []).append((rk, f"{s} site"))
    return out


_CACHE: dict = {}


def league_choices(con, map_name, side, since, until):
    key = (map_name, side, since, until)
    if key not in _CACHE:
        _CACHE[key] = _choices(con, map_name, side, since, until)
    return _CACHE[key]


LABELS = {
    "contact_where": "Where they first make contact",
    "contact_when": "When they first make contact",
    "site": "Which site they plant",
    "sniper_spot": "Where the Operator takes its first shot",
}


def top_share(pairs):
    c = Counter(ch for _, ch in pairs)
    (choice, k), = ranked(c, 1)
    return choice, k, len(pairs)


@metric(PREDICTABILITY)
def predictability(con, f: Filters) -> MetricResult:
    res = MetricResult(PREDICTABILITY, f)
    if not (f.map and f.side):
        res.warnings.append("Pick one map and one side to see how predictable they are.")
        return res
    league = league_choices(con, f.map, f.side, f.since, f.until)
    percentiles = []
    for habit, by_team in league.items():
        mine = by_team.get(f.team_id)
        if not mine:
            continue
        choice, k, n = top_share(mine)
        share = k / n
        others = [top_share(v) for t, v in by_team.items() if t != f.team_id and len(v) >= MIN_ROUNDS]
        other_shares = [kk / nn for _, kk, nn in others]
        pct = None
        if other_shares and n >= MIN_ROUNDS:
            pct = round(100 * sum(1 for s in other_shares if s < share) / len(other_shares))
            percentiles.append(pct)
        res.breakdown.append(dict(
            bucket=habit, habit=habit, label=LABELS[habit], choice=choice, rate=Rate.over(f"team.predictability.{habit}", [x for x in mine if x[1] == choice], mine),
            runner_up=[dict(choice=c, k=kk) for c, kk in ranked(Counter(ch for _, ch in mine), 3)[1:]],
            league_median=round(float(np.median(other_shares)), 3) if other_shares else None,
            league_teams=len(other_shares), percentile=pct, small_sample=n < MIN_ROUNDS,
            round_keys=sorted(rk for rk, ch in mine if ch == choice),
        ))
    res.breakdown.sort(key=lambda b: (b["percentile"] is None, -(b["percentile"] or 0), b["habit"]))
    res.value = dict(score=round(float(np.mean(percentiles))) if percentiles else None,
                     habits_scored=len(percentiles), min_rounds=MIN_ROUNDS)
    if res.breakdown:
        top = res.breakdown[0]
        res.rate = top["rate"]
        res.supporting = top["round_keys"]
        tw, tp = f.where("t")
        all_rounds = {r for (r,) in con.execute(f"SELECT round_key FROM team_rounds t WHERE {tw}", tp).fetchall()}
        res.contrary = sorted(all_rounds - set(top["round_keys"]))
    return res
