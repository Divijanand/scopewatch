"""Where a team puts its utility: Sentinel setups first, then smokes, flashes and recon.

Positions are the caster's position at the cast (ability supplement), named with the nearest
reachable community callout. For placeables set up in the buy phase the caster stands next to
the setup, so the callout is a close proxy; for thrown utility it's where it was thrown from,
never where it landed (UTILITY_SPATIAL_SEMANTICS.md).
"""
from __future__ import annotations

from collections import Counter
from functools import lru_cache

import numpy as np

from ..abilities import GROUPS, sql_list
from ..callouts import Labeller, load as load_callouts
from .core import Filters, MetricDef, MetricResult, Rate, Unknown, metric

TOP = 12

PLACEMENTS = MetricDef(
    id="util.placements", version=1, title="Utility setups",
    question="Where does the team put each ability on this map and side, and in how many rounds?",
    population="The team's rounds on one map and side",
    numerator="Rounds with at least one cast of this ability from this callout",
    unit="rounds",
    caveats=("Position = where the caster stood when using the ability (ability supplement). For setups placed "
             "in the buy phase that is next to the setup; thrown utility lands elsewhere, and the feed doesn't "
             "record where.",
             "Callout = nearest community callout the caster could reach on the minimap; an approximation.",
             "Casts whose position failed the quality policy (UTILITY_SPATIAL_SEMANTICS.md) are counted as unknown, "
             "never placed on the map.",
             "VCT Americas 2025 positions are sampled about once a second, so they're less precise.",
             "Casts after the round result are left out."),
)


@lru_cache(maxsize=32)
def labeller(map_name: str):
    anchors = load_callouts().get(map_name)
    return Labeller.for_map(map_name, anchors) if anchors else None


def name_positions(map_name: str, xs, ys):
    lab = labeller(map_name)
    if lab is None or len(xs) == 0:
        return [None] * len(xs)
    names, _ = lab.label(np.asarray(xs, float), np.asarray(ys, float))
    return list(names)


def casts_in_scope(con, f: Filters, group: str | None = None, ability: str | None = None):
    w, p = f.where("c")
    if f.player_id:
        w += " AND c.player_id = ?"; p.append(f.player_id)
    if ability:
        w += " AND c.ability = ?"; p.append(ability)
    elif group in GROUPS:
        w += f" AND c.ability IN {sql_list(GROUPS[group])}"
    return con.execute(f"""
        SELECT c.round_key, c.ability, c.agent, c.player_id, pr.player_name, c.t_round, c.phase,
               c.x, c.y, c.vx, c.vy, c.spatial_ok, c.low_rate
        FROM casts c
        LEFT JOIN player_rounds pr ON pr.round_key = c.round_key AND pr.player_id = c.player_id
        WHERE {w} AND c.round_key IS NOT NULL AND coalesce(c.phase, '') <> 'post_round'
        ORDER BY c.ts_ms""", p).fetchall()


@metric(PLACEMENTS)
def placements(con, f: Filters, group: str = "setup") -> MetricResult:
    res = MetricResult(PLACEMENTS, f)
    if not (f.map and f.side):
        res.warnings.append("Pick one map and one side to see utility setups.")
        return res
    tw, tp = f.where("t")
    n = con.execute(f"SELECT count(*) FROM team_rounds t WHERE {tw}", tp).fetchone()[0]
    rows = casts_in_scope(con, f, group=group)
    placed = [r for r in rows if r[11] and r[7] is not None]
    if len(placed) < len(rows):
        res.unknown.append(Unknown(len(rows) - len(placed), "cast position failed the quality policy"))
    names = name_positions(f.map, [r[7] for r in placed], [r[8] for r in placed])

    by = {}
    for r, nm in zip(placed, names):
        by.setdefault((r[1], nm or "away from any callout"), []).append(r)
    for (ab, callout), rs in sorted(by.items(), key=lambda kv: -len({r[0] for r in kv[1]})):
        rounds = sorted({r[0] for r in rs})
        res.breakdown.append(dict(
            bucket=f"{ab}@{callout}", ability=ab, agent=Counter(r[2] for r in rs).most_common(1)[0][0],
            callout=callout, rate=Rate.of(len(rounds), n),
            players=[dict(name=nm, k=k) for nm, k in Counter(r[4] for r in rs if r[4]).most_common(2)],
            median_t=round(float(np.median([r[5] for r in rs if r[5] is not None])), 1) if any(r[5] is not None for r in rs) else None,
            buy_phase=sum(1 for r in rs if r[6] == "buy"), casts=len(rs),
            low_rate=sum(1 for r in rs if r[12]),
            round_keys=rounds,
        ))
    res.breakdown = res.breakdown[:TOP]
    by_ability = Counter()
    for ab in {r[1] for r in placed}:
        by_ability[ab] = len({r[0] for r in placed if r[1] == ab})
    res.value = dict(group=group, rounds=n,
                     abilities=[dict(ability=a, rate=Rate.of(k, n)) for a, k in by_ability.most_common()])
    if res.breakdown:
        top = res.breakdown[0]
        res.rate = top["rate"]
        res.supporting = top["round_keys"]
        res.contrary = sorted({r for (r,) in con.execute(f"SELECT round_key FROM team_rounds t WHERE {tw}", tp).fetchall()}
                              - set(top["round_keys"]))
    res.maps = len({r[0].split(":")[0] for r in rows})
    return res
