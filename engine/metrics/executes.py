"""How a team takes sites on attack: which site, how fast, where first contact happens, and what
utility goes in before the plant."""
from __future__ import annotations

from collections import Counter
from functools import lru_cache

import numpy as np

from ..abilities import kind_of
from ..callouts import Labeller, load as load_callouts
from .core import Filters, MetricDef, MetricResult, Rate, metric

EXEC_WINDOW_MS = 25_000          # utility thrown in the 25 s before the plant counts as the execute
PACE = [("fast", 0, 35), ("default", 35, 70), ("late", 70, 10_000)]
MIN_LEAGUE = 20

EXECUTES = MetricDef(
    id="att.executes", version=1, title="How they hit sites",
    question="On attack, which site does the team plant on, how fast, where does first contact happen, "
             "and what utility goes in before the plant?",
    population="The team's attack rounds on one map (buy-phase end to round result)",
    numerator="Rounds with a spike plant on this site",
    unit="attack rounds",
    caveats=("The site is the nearest site callout to the plant position.",
             "Rounds without a plant are counted in the total but have no site: retakes and eco saves "
             "are mixed in there.",
             "Execute utility = abilities cast by the attackers in the 25 s before the plant. The feed records "
             "the cast, not where it landed.",
             "Against an Operator = rounds where a defender held an Operator/Outlaw at buy-phase end; "
             "'lost it without a kill' means that holder died before the round result with no Operator kill.",
             "Site entry = the first hit or kill before the plant where the attacker involved stood in that "
             "site's callouts (for example A Main or A Rubble for an A plant). Rounds won without a fight there "
             "have no entry."),
)


@lru_cache(maxsize=32)
def _site_labeller(map_name: str):
    sites = [a for a in load_callouts().get(map_name, []) if a["name"].endswith("Site")]
    return Labeller(map_name, sites) if sites else None


def plant_sites(map_name: str, xs, ys):
    lab = _site_labeller(map_name)
    if lab is None:
        return [None] * len(xs)
    names, _ = lab.label(np.asarray(xs, float), np.asarray(ys, float))
    return [n.split()[0] if n else None for n in names]


def _rounds(con, where, params):
    """(round_key, team_id, won, plant_ts, plant_t, plant_x, plant_y, contact_t, contact_callout)"""
    return con.execute(f"""
        WITH r AS (SELECT t.round_key, t.team_id, t.won FROM team_rounds t WHERE {where}),
             p AS (SELECT o.round_key, min(o.ts_ms) ts, arg_min(o.t_round, o.ts_ms) t,
                          arg_min(o.x, o.ts_ms) x, arg_min(o.y, o.ts_ms) y
                   FROM objectives o WHERE o.kind = 'plant' AND o.round_key IN (SELECT round_key FROM r) GROUP BY 1),
             c AS (SELECT r.round_key, r.team_id,
                          arg_min(e.t_round, e.ts_ms) t,
                          arg_min(CASE WHEN e.att_team = r.team_id THEN e.att_callout ELSE e.vic_callout END, e.ts_ms) callout
                   FROM r JOIN engagements e ON e.round_key = r.round_key
                   WHERE e.phase = 'pre_plant' AND e.kind IN ('kill', 'damage')
                     AND (e.att_team = r.team_id OR e.vic_team = r.team_id)
                   GROUP BY 1, 2)
        SELECT r.round_key, r.team_id, r.won, p.ts, p.t, p.x, p.y, c.t, c.callout
        FROM r LEFT JOIN p USING (round_key) LEFT JOIN c ON c.round_key = r.round_key AND c.team_id = r.team_id
        """, params).fetchall()


@metric(EXECUTES)
def executes(con, f: Filters) -> MetricResult:
    res = MetricResult(EXECUTES, f)
    if not f.map:
        res.warnings.append("Pick one map to see how they hit sites.")
        return res
    if f.side == "defender":      # an attacking pattern: nothing to report on defense, and no warning noise
        return res
    fa = Filters(team_id=f.team_id, map=f.map, side="attacker", since=f.since, until=f.until)
    w, p = fa.where("t")
    rows = _rounds(con, w, p)
    n = len(rows)
    sites = plant_sites(f.map, [r[5] if r[5] is not None else np.nan for r in rows],
                       [r[6] if r[6] is not None else np.nan for r in rows])

    planted = [(r, s) for r, s in zip(rows, sites) if r[3] is not None and s]
    keys = [r[0] for r, _ in planted]
    casts = con.execute("""
        SELECT c.round_key, c.ability, c.ts_ms FROM casts c
        WHERE c.team_id = ? AND c.round_key IN (SELECT unnest(?))""", [f.team_id, keys]).fetchall() if keys else []
    # site entry: the first fight in that site's own callouts ("A Main", "A Rubble", ...) before the plant
    fights = con.execute("""
        SELECT e.round_key, e.t_round,
               CASE WHEN e.att_team = ? THEN e.att_callout ELSE e.vic_callout END AS callout
        FROM engagements e
        WHERE e.round_key IN (SELECT unnest(?)) AND e.phase = 'pre_plant' AND e.kind IN ('kill', 'damage')
          AND (e.att_team = ? OR e.vic_team = ?)
        ORDER BY e.ts_ms""", [f.team_id, keys, f.team_id, f.team_id]).fetchall() if keys else []
    site_of = {r[0]: s for r, s in planted}
    entry = {}
    for rk, t, callout in fights:
        if rk not in entry and callout and callout.split()[0] == site_of[rk]:
            entry[rk] = (t, callout)
    # the defenders' Operator in these rounds: did it get a kill before it died?
    vs_op = {rk: (bool(died), kills) for rk, died, kills in con.execute("""
        WITH h AS (SELECT p.round_key, p.player_id FROM player_rounds p
                   WHERE p.round_key IN (SELECT unnest(?)) AND p.team_id <> ? AND p.has_op)
        SELECT h.round_key,
               bool_or(EXISTS (SELECT 1 FROM engagements d WHERE d.round_key = h.round_key AND d.kind = 'kill'
                               AND d.vic_id = h.player_id AND d.phase IN ('pre_plant', 'post_plant'))),
               sum((SELECT count(*) FROM engagements k WHERE k.round_key = h.round_key AND k.kind = 'kill'
                    AND k.att_id = h.player_id AND k.weapon IN ('operator', 'outlaw')
                    AND k.phase IN ('pre_plant', 'post_plant')))
        FROM h GROUP BY 1""", [keys, f.team_id]).fetchall()} if keys else {}
    by_round = {}
    plant_ts = {r[0]: r[3] for r, _ in planted}
    for rk, ab, ts in casts:
        if plant_ts[rk] - EXEC_WINDOW_MS <= ts <= plant_ts[rk]:
            by_round.setdefault(rk, []).append(ab)

    lw, lp = ["t.map = ?", "t.side = 'attacker'"], [f.map]
    if f.since:
        lw.append("t.started_at >= ?::TIMESTAMP"); lp.append(f.since)
    if f.until:
        lw.append("t.started_at < ?::TIMESTAMP"); lp.append(f.until)
    league_rows = con.execute(f"""
        SELECT o.x, o.y FROM team_rounds t JOIN objectives o ON o.round_key = t.round_key AND o.kind = 'plant'
        WHERE {' AND '.join(lw)} AND o.x IS NOT NULL
          AND o.team_id = t.team_id""", lp).fetchall()
    league_n = con.execute(f"SELECT count(*) FROM team_rounds t WHERE {' AND '.join(lw)}", lp).fetchone()[0]
    league_sites = Counter(plant_sites(f.map, [x for x, _ in league_rows], [y for _, y in league_rows]))

    by_site = {}
    for r, s in planted:
        by_site.setdefault(s, []).append(r)
    for site, rs in sorted(by_site.items(), key=lambda kv: -len(kv[1])):
        k = len(rs)
        util = [by_round.get(r[0], []) for r in rs]
        kinds = [Counter(kind_of(a) for a in u) for u in util]
        per_round = {kd: round(sum(c[kd] for c in kinds) / k, 1) for kd in ("smoke", "flash", "stun", "info", "other")}
        ab_rounds = Counter(a for u in util for a in set(u))
        ent = [entry[r[0]] for r in rs if r[0] in entry]
        res.breakdown.append(dict(
            bucket=site, label=f"{site} site", site=site, rate=Rate.of(k, n),
            won=Rate.of(sum(1 for r in rs if r[2]), k),
            plant_t=round(float(np.median([r[4] for r in rs])), 1),
            entry_t=round(float(np.median([t for t, _ in ent])), 1) if ent else None,
            entry=Rate.of(len(ent), k),
            entry_callouts=[dict(callout=c, k=v) for c, v in Counter(c for _, c in ent).most_common(3)],
            pace=[dict(pace=nm, k=sum(1 for r in rs if lo <= r[4] < hi)) for nm, lo, hi in PACE],
            utility_per_round=per_round,
            abilities=[dict(ability=a, rounds=v) for a, v in ab_rounds.most_common(5)],
            league=Rate.of(league_sites.get(site, 0), league_n) if league_n >= MIN_LEAGUE else None,
            vs_op=dict(rounds=sum(1 for r in rs if r[0] in vs_op),
                       op_kill=Rate.of(sum(1 for r in rs if r[0] in vs_op and vs_op[r[0]][1] > 0),
                                       sum(1 for r in rs if r[0] in vs_op)),
                       lost_no_kill=Rate.of(sum(1 for r in rs if r[0] in vs_op and vs_op[r[0]][0] and not vs_op[r[0]][1]),
                                            sum(1 for r in rs if r[0] in vs_op))),
            round_keys=sorted(r[0] for r in rs),
        ))
    no_plant = [r for r in rows if r[3] is None]
    res.value = dict(no_plant=Rate.of(len(no_plant), n),
                     no_plant_won=Rate.of(sum(1 for r in no_plant if r[2]), len(no_plant)))
    if res.breakdown:
        top = res.breakdown[0]
        res.rate = top["rate"]
        res.supporting = top["round_keys"]
        res.contrary = sorted({r[0] for r, _ in planted} - set(top["round_keys"]))
    res.maps = len({r[0].split(":")[0] for r in rows})
    return res
