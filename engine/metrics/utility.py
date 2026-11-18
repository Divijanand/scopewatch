"""Where a team puts its utility, layer by layer, each with the position that actually means something:

  setups (placeables)   caster position: buy-phase setups sit next to the player who placed them
  damage (mollies etc.) where it hurt an enemy (victim positions from GRID damage events), linked to the throw
  smokes                walls drawn along the aim from the caster; map-placed smokes have no position, so
                        only how often and when
  flashes, recon        caster position ("used from"); they land elsewhere

All positions are named with the nearest reachable community callout (UTILITY_SPATIAL_SEMANTICS.md).
"""
from __future__ import annotations

from collections import Counter
from functools import lru_cache

import numpy as np

from ..abilities import DAMAGE_THROWN, GROUPS, mode_of, sql_list
from ..callouts import Labeller, load as load_callouts
from .core import Filters, MetricDef, MetricResult, Rate, Unknown, metric, ranked

TOP = 12
WALL_DIR_CM = 2000   # 20 m along the aim: only used to name the direction a wall runs, not its length

PLACEMENTS = MetricDef(
    id="util.placements", version=2, title="Utility",
    question="Where does the team put each ability on this map and side, and in how many rounds?",
    population="The team's rounds on one map and side",
    numerator="Rounds with at least one use of this ability at this callout",
    unit="rounds",
    caveats=("Setups, flashes and recon: position = where the caster stood (ability supplement). Setups placed in "
             "the buy phase sit next to it; thrown flashes and recon land elsewhere.",
             "Mollies and damaging utility: position = where it hurt an enemy (median of the hit players' "
             "positions), linked to the throw. Uses that hit nobody are invisible: this shows where it worked, "
             "not every throw.",
             "Walls (Viper, Harbor, Neon, Phoenix): drawn from the caster along the aim direction; the length "
             "isn't measured.",
             "Map-placed smokes (Omen, Brimstone, Clove, Astra, Harbor Cove, Viper orb) have no position in the "
             "feed: only how often and when they're used.",
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


def scope_abilities(group: str | None = None, agent_kit=None) -> set:
    if agent_kit is not None:
        return set(agent_kit)
    return set(GROUPS.get(group or "setup", ()))


def casts_in_scope(con, f: Filters, group: str | None = None, ability: str | None = None, abilities=None):
    w, p = f.where("c")
    if f.player_id:
        w += " AND c.player_id = ?"; p.append(f.player_id)
    if ability:
        w += " AND c.ability = ?"; p.append(ability)
    elif abilities is not None:
        if not abilities:
            return []
        w += f" AND c.ability IN {sql_list(abilities)}"
    elif group in GROUPS:
        w += f" AND c.ability IN {sql_list(GROUPS[group])}"
    return con.execute(f"""
        SELECT c.round_key, c.ability, c.agent, c.player_id, pr.player_name, c.t_round, c.phase,
               c.x, c.y, c.vx, c.vy, c.spatial_ok, c.low_rate
        FROM casts c
        LEFT JOIN player_rounds pr ON pr.round_key = c.round_key AND pr.player_id = c.player_id
        WHERE {w} AND c.round_key IS NOT NULL AND coalesce(c.phase, '') <> 'post_round'
        ORDER BY c.ts_ms""", p).fetchall()


def landings_in_scope(con, f: Filters, abilities=None):
    """One row per use of damaging thrown utility that hit an enemy: where it landed (median position of
    the enemies it hurt) and where it was thrown from (the thrower's matching cast, via an as-of join)."""
    abilities = set(abilities) if abilities is not None else set(DAMAGE_THROWN)
    if not abilities:
        return []
    w, p = f.where("e", team_col="att_team", side_col="att_side")
    if f.player_id:
        w += " AND e.att_id = ?"; p.append(f.player_id)
    w += f" AND e.weapon IN {sql_list(abilities)}"
    return con.execute(f"""
        WITH d AS (SELECT e.round_key, e.ts_ms, e.t_round, e.att_id, e.att_name, e.att_agent, e.weapon,
                          e.vic_x, e.vic_y, e.vic_callout
                   FROM engagements e
                   WHERE {w} AND e.vic_team <> e.att_team AND e.vic_x IS NOT NULL
                     AND e.phase IN ('pre_plant', 'post_plant')),
             c AS (SELECT round_key, player_id, ability, ts_ms AS cts, t_round AS ct, x, y, spatial_ok, low_rate
                   FROM casts WHERE round_key IN (SELECT DISTINCT round_key FROM d)),
             j AS (SELECT d.*, c.cts, c.ct, c.x AS fx, c.y AS fy, c.spatial_ok, c.low_rate
                   FROM d ASOF LEFT JOIN c ON d.round_key = c.round_key AND d.att_id = c.player_id
                                          AND d.weapon = c.ability AND d.ts_ms >= c.cts)
        SELECT round_key, weapon, any_value(att_agent), att_id, any_value(att_name),
               coalesce(any_value(ct), min(t_round)) AS t, median(vic_x), median(vic_y), list(vic_callout),
               any_value(fx) FILTER (WHERE spatial_ok), any_value(fy) FILTER (WHERE spatial_ok),
               count(*) AS hits, coalesce(bool_or(low_rate), FALSE)
        FROM j
        GROUP BY round_key, weapon, att_id, coalesce(cts, ts_ms // 4000)
        ORDER BY round_key, t""", p).fetchall()


def wall_endpoint(x, y, vx, vy, dist_cm=WALL_DIR_CM):
    if vx is None or vy is None:
        return None, None
    n = (vx * vx + vy * vy) ** 0.5 or 1.0
    return x + vx / n * dist_cm, y + vy / n * dist_cm


def layer_items(con, f: Filters, group: str | None = None, agent_kit=None):
    """Everything drawn for these abilities, each by its own mode (abilities.MODE), as
    (round_key, ability, agent, player, t, x, y, callout, extra); plus casts left off the map and the
    casts of unplaced abilities (timing only)."""
    abilities = scope_abilities(group, agent_kit)
    landing = {a for a in abilities if mode_of(a) == "landing"}
    others = abilities - landing
    items = []

    rows = landings_in_scope(con, f, landing)
    from_names = name_positions(f.map, [r[9] if r[9] is not None else np.nan for r in rows],
                                [r[10] if r[10] is not None else np.nan for r in rows])
    for r, fn_ in zip(rows, from_names):
        landed = ranked(Counter(c for c in (r[8] or []) if c), 1)
        items.append((r[0], r[1], r[2], r[4], r[5], r[6], r[7], landed[0][0] if landed else "away from any callout",
                      dict(mode="landing", from_callout=fn_, fx=r[9], fy=r[10], hits=r[11], low_rate=bool(r[12]))))

    rows = casts_in_scope(con, f, abilities=others)
    unplaced_casts = [r for r in rows if mode_of(r[1]) == "unplaced"]
    drawable = [r for r in rows if mode_of(r[1]) != "unplaced"]
    placed = [r for r in drawable if r[11] and r[7] is not None]
    left_off = len(drawable) - len(placed)
    names = name_positions(f.map, [r[7] for r in placed], [r[8] for r in placed])
    dir_idx = [i for i, r in enumerate(placed) if mode_of(r[1]) == "direction"]
    toward = [None] * len(placed)
    if dir_idx:
        ends = [wall_endpoint(placed[i][7], placed[i][8], placed[i][9], placed[i][10]) for i in dir_idx]
        named = name_positions(f.map, [e[0] if e[0] is not None else np.nan for e in ends],
                               [e[1] if e[1] is not None else np.nan for e in ends])
        for i, nm in zip(dir_idx, named):
            toward[i] = nm
    for r, nm, tw_ in zip(placed, names, toward):
        items.append((r[0], r[1], r[2], r[4], r[5], r[7], r[8], nm or "away from any callout",
                      dict(mode=mode_of(r[1]), toward=tw_, buy=r[6] == "buy", vx=r[9], vy=r[10],
                           low_rate=bool(r[12]))))
    return items, left_off, unplaced_casts


def agent_rounds(con, f: Filters):
    """{agent: [round_keys]} for the agents the team fielded in scope."""
    w, p = f.where("p")
    out = {}
    for agent, rk in con.execute(f"SELECT DISTINCT agent, round_key FROM player_rounds p WHERE {w} AND agent IS NOT NULL",
                                 p).fetchall():
        out.setdefault(agent, []).append(rk)
    return out


def agent_kit(con, agent: str) -> list:
    return [a for (a,) in con.execute("SELECT DISTINCT ability FROM casts WHERE agent = ? AND ability IS NOT NULL "
                                      "ORDER BY 1", [agent]).fetchall()]


@metric(PLACEMENTS)
def placements(con, f: Filters, group: str | None = "setup", agent: str | None = None) -> MetricResult:
    res = MetricResult(PLACEMENTS, f)
    if not (f.map and f.side):
        res.warnings.append("Pick one map and one side to see utility.")
        return res
    by_agent = agent_rounds(con, f)
    res.value["agents"] = [dict(agent=a, rounds=len(rks)) for a, rks in sorted(by_agent.items(), key=lambda kv: (-len(kv[1]), str(kv[0])))]
    tw, tp = f.where("t")
    team_rounds = [r for (r,) in con.execute(f"SELECT round_key FROM team_rounds t WHERE {tw}", tp).fetchall()]
    if agent:
        kit = agent_kit(con, agent)
        scope = sorted(set(by_agent.get(agent, [])))
        items, left_off, unplaced = layer_items(con, f, agent_kit=kit)
        res.value["kit"] = [dict(ability=a, mode=mode_of(a)) for a in kit]
    else:
        scope = team_rounds
        items, left_off, unplaced = layer_items(con, f, group=group)
    n = len(scope)
    if left_off:
        res.unknown.append(Unknown(left_off, "cast position failed the quality policy"))

    timing = []
    for ab in sorted({r[1] for r in unplaced}):
        rs = [r for r in unplaced if r[1] == ab]
        per_round = Counter(r[0] for r in rs)
        ts = [r[5] for r in rs if r[5] is not None]
        timing.append(dict(ability=ab, agent=ranked(Counter(r[2] for r in rs), 1)[0][0],
                           rate=Rate.of(len(per_round), n),
                           per_round=round(sum(per_round.values()) / len(per_round), 1),
                           median_t=round(float(np.median(ts)), 1) if ts else None))
    res.value["timing"] = sorted(timing, key=lambda d: (-d["rate"].k, d["ability"]))

    by = {}
    for it in items:
        by.setdefault((it[1], it[7]), []).append(it)
    rows = []
    for (ab, callout), rs in by.items():
        rounds = sorted({r[0] for r in rs})
        ts = [r[4] for r in rs if r[4] is not None]
        mode = rs[0][8]["mode"]
        extra = {}
        if mode == "landing":
            extra = dict(from_callouts=[dict(callout=c, k=k) for c, k in
                                        ranked(Counter(r[8]["from_callout"] for r in rs if r[8]["from_callout"]), 2)],
                         hits=sum(r[8]["hits"] for r in rs))
        elif mode == "direction":
            extra = dict(toward=[dict(callout=c, k=k) for c, k in
                                 ranked(Counter(r[8]["toward"] for r in rs if r[8]["toward"]), 2)])
        rows.append(dict(
            bucket=f"{ab}@{callout}", ability=ab, mode=mode, agent=ranked(Counter(r[2] for r in rs), 1)[0][0],
            callout=callout, rate=Rate.of(len(rounds), n),
            players=[dict(name=nm, k=k) for nm, k in ranked(Counter(r[3] for r in rs if r[3]), 2)],
            median_t=round(float(np.median(ts)), 1) if ts else None,
            buy_phase=sum(1 for r in rs if r[8].get("buy")), casts=len(rs),
            round_keys=rounds, **extra,
        ))
    rows.sort(key=lambda b: (-b["rate"].k, b["bucket"]))
    if agent:   # keep the top spots of every ability in the kit, so no ability is crowded out
        keep, per = [], Counter()
        for b in rows:
            if per[b["ability"]] < 4:
                keep.append(b); per[b["ability"]] += 1
        res.breakdown = keep
    else:
        res.breakdown = rows[:TOP]
    by_ability = Counter({ab: len({it[0] for it in items if it[1] == ab}) for ab in {it[1] for it in items}})
    res.value.update(group=None if agent else group, agent=agent, rounds=n,
                     abilities=[dict(ability=a, mode=mode_of(a), rate=Rate.of(k, n)) for a, k in ranked(by_ability)])
    if res.breakdown:
        top = res.breakdown[0]
        res.rate = top["rate"]
        res.supporting = top["round_keys"]
        res.contrary = sorted(set(scope) - set(top["round_keys"]))
    res.maps = len({it[0].split(":")[0] for it in items})
    return res
