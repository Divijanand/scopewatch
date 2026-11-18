"""Operator / Outlaw tendency metrics. Possession = item in inventory at buy-phase end."""
from __future__ import annotations

from collections import Counter

import numpy as np

from .core import Filters, MetricDef, MetricResult, Rate, Unknown, metric, ranked

# weapons a player buys and holds
OP_ITEMS = "('operator', 'outlaw')"
# sniper kills: those plus Chamber's ultimate, Tour de Force (its kills get their weapon in engine/weapons.py)
OP = "('operator', 'outlaw', 'tour-de-force')"
BUCKETS = [("0-20s", 0, 20), ("20-40s", 20, 40), ("40-60s", 40, 60), ("60s+", 60, 10_000)]


def _scope(con, f: Filters, extra=""):
    w, p = f.where("t")
    row = con.execute(f"SELECT count(DISTINCT game_id), count(DISTINCT series_id) FROM team_rounds t "
                      f"WHERE {w} {extra}", p).fetchone()
    return row[0], row[1]


# ------------------------------------------------------------------ possession
POSSESSION = MetricDef(
    id="op.possession_full_buy", version=1, title="Operator on full buys",
    question="How often does the team have an Operator or Outlaw when it full-buys?",
    population="Team rounds in scope with a buy-phase-end inventory snapshot and team loadout >= 15,000",
    numerator="Those rounds where at least one player holds an Operator or Outlaw at buy-phase end",
    unit="rounds",
    caveats=("Possession at buy-phase end, not purchase: the feed has no purchase events.",
             "Rounds without an inventory snapshot are reported as unknown, never as 'no Operator'."),
)


@metric(POSSESSION)
def possession_full_buy(con, f: Filters) -> MetricResult:
    w, p = f.where("t")
    rows = con.execute(f"""SELECT round_key, inventory_known, economy, n_op FROM team_rounds t WHERE {w}""", p).fetchall()
    unknown = [r for r in rows if not r[1]]
    elig = [r for r in rows if r[1] and r[2] == "full"]
    sup = [r[0] for r in elig if r[3] > 0]
    con_ = [r[0] for r in elig if r[3] == 0]
    maps, series = _scope(con, f)
    res = MetricResult(POSSESSION, f, rate=Rate.of(len(sup), len(elig)), maps=maps, series=series,
                       supporting=sup, contrary=con_)
    if unknown:
        res.unknown.append(Unknown(len(unknown), "no buy-phase-end inventory snapshot"))
    by_econ = {}
    for e in ("full", "half", "eco"):
        rr = [r for r in rows if r[1] and r[2] == e]
        by_econ[e] = Rate.of(sum(1 for r in rr if r[3] > 0), len(rr))
    res.breakdown = [dict(economy=e, rate=r) for e, r in by_econ.items()]
    return res


# ------------------------------------------------------------------ holders
HOLDERS = MetricDef(
    id="op.holder_share", version=1, title="Who carries it",
    question="Which player has the Operator/Outlaw in the team's Operator rounds?",
    population="Team rounds in scope where at least one player holds an Operator/Outlaw at buy-phase end",
    numerator="Rounds where this player holds it (a round with two holders counts for both)",
    unit="rounds",
    caveats=("Shares can sum above 100% when two players hold one in the same round.",),
)


@metric(HOLDERS)
def holder_share(con, f: Filters) -> MetricResult:
    w, p = f.where("t")
    op_rounds = con.execute(f"SELECT round_key FROM team_rounds t WHERE {w} AND n_op > 0", p).fetchall()
    n = len(op_rounds)
    pw, pp = f.where("p")
    holders = con.execute(f"""
        SELECT player_id, any_value(player_name), count(*) k, list(agent), list(DISTINCT agent ORDER BY agent),
               list(round_key)
        FROM player_rounds p WHERE {pw} AND has_op GROUP BY player_id ORDER BY k DESC, player_id""", pp).fetchall()
    maps, series = _scope(con, f, "AND n_op > 0")
    res = MetricResult(HOLDERS, f, maps=maps, series=series)
    res.breakdown = [dict(player_id=pid, name=name, agent=ranked(Counter(agent_list), 1)[0][0], agents=agents,
                          rate=Rate.of(k, n))
                     for pid, name, k, agent_list, agents, _ in holders]
    if holders:
        res.rate = Rate.of(holders[0][2], n)
        res.supporting = list(holders[0][5])
        res.contrary = sorted({r[0] for r in op_rounds} - set(holders[0][5]))
    # possession shift: rounds where the holder isn't that map's main holder
    shift = con.execute(f"""
        WITH r AS (SELECT game_id, round_key, unnest(op_player_ids) pid FROM team_rounds t WHERE {w} AND n_op > 0),
             c AS (SELECT game_id, pid, count(*) n FROM r GROUP BY 1, 2),
             m AS (SELECT game_id, pid AS main FROM (SELECT *, row_number() OVER (PARTITION BY game_id ORDER BY n DESC, pid) rn FROM c) WHERE rn = 1)
        SELECT count(*) FILTER (WHERE pid <> main), count(*) FROM r JOIN m USING (game_id)""", p).fetchone()
    res.value["possession_shift"] = Rate.of(shift[0], shift[1])
    return res


# ------------------------------------------------------------------ timing
TIMING = MetricDef(
    id="op.kill_timing", version=2, title="When it fires",
    question="When in the round do the team's Operator/Outlaw kills happen?",
    population="Kills by the team with an Operator or Outlaw, after buy-phase end and before the round result",
    numerator="Kills in each window of time since buy-phase end",
    unit="kills",
    caveats=("A kill is when the duel ended, not when the hold started.",
             "Sniper kills include Chamber's ultimate (Tour de Force).",
             "Windows are an analytical choice (0-20, 20-40, 40-60, 60+ s); short rounds can't reach late windows."),
)


def _op_engagements(con, f: Filters, kinds=("kill",)):
    w, p = f.where("e", team_col="att_team", side_col="att_side")
    if f.player_id:
        w += " AND e.att_id = ?"; p.append(f.player_id)
    k = ",".join(f"'{x}'" for x in kinds)
    return con.execute(f"""
        SELECT e.round_key, e.event_id, e.kind, e.weapon, e.t_round, e.t_plant, e.phase, e.opening_kill,
               e.att_id, e.att_name, e.att_agent, e.att_side, e.att_x, e.att_y, e.att_pos_repeat,
               e.vic_name, e.vic_x, e.vic_y, e.map, e.round_no,
               (r.winner_team_id = e.att_team) AS won
        FROM engagements e LEFT JOIN rounds r USING (round_key)
        WHERE {w} AND e.weapon IN {OP} AND e.kind IN ({k}) AND e.phase IN ('pre_plant', 'post_plant')
        ORDER BY e.ts_ms""", p).fetchall()


ENG_COLS = ["round_key", "event_id", "kind", "weapon", "t_round", "t_plant", "phase", "opening_kill", "att_id",
            "att_name", "agent", "side", "x", "y", "pos_repeat", "vic_name", "vx", "vy", "map", "round_no", "won"]


@metric(TIMING)
def kill_timing(con, f: Filters) -> MetricResult:
    kills = _op_engagements(con, f)
    n = len(kills)
    res = MetricResult(TIMING, f)
    for name, lo, hi in BUCKETS:
        kb = [k for k in kills if lo <= k[4] < hi]
        res.breakdown.append(dict(bucket=name, rate=Rate.of(len(kb), n), round_keys=sorted({k[0] for k in kb})))
    post = [k for k in kills if k[6] == "post_plant"]
    res.value = dict(median_t=float(np.median([k[4] for k in kills])) if kills else None,
                     post_plant=Rate.of(len(post), n))
    top = max(res.breakdown, key=lambda b: b["rate"].k) if n else None
    if top:
        res.rate = top["rate"]
        res.value["top_bucket"] = top["bucket"]
        res.supporting = top["round_keys"]
        res.contrary = sorted({k[0] for k in kills} - set(top["round_keys"]))
    res.maps = len({k[0].split(":")[0] for k in kills})
    return res


# ------------------------------------------------------------------ opening duels
OPENING = MetricDef(
    id="op.opening", version=2, title="Opening duels",
    question="In rounds where they have an Operator, how often does it take or lose the round's first kill?",
    population="Team rounds in scope with an Operator/Outlaw holder and a recorded first kill",
    numerator="Rounds whose first kill is by the holder with the rifle (won) / of the holder (lost)",
    unit="rounds",
    caveats=("First recorded kill of the round; duels that ended in damage only are not counted.",),
)


@metric(OPENING)
def opening(con, f: Filters) -> MetricResult:
    w, p = f.where("t")
    rows = con.execute(f"""
        WITH op AS (SELECT round_key, team_id, op_player_ids FROM team_rounds t WHERE {w} AND n_op > 0),
             fk AS (SELECT round_key, att_id, vic_id, weapon FROM engagements WHERE opening_kill)
        SELECT op.round_key, fk.att_id, fk.vic_id, fk.weapon, list_contains(op.op_player_ids, fk.att_id) att_holder,
               list_contains(op.op_player_ids, fk.vic_id) vic_holder
        FROM op JOIN fk USING (round_key)""", p).fetchall()
    n = len(rows)
    won = [r[0] for r in rows if r[4] and r[3] in ("operator", "outlaw", "tour-de-force")]
    lost = [r[0] for r in rows if r[5]]
    res = MetricResult(OPENING, f, rate=Rate.of(len(won), n), supporting=won,
                       contrary=[r[0] for r in rows if r[0] not in set(won)])
    res.value = dict(holder_died_first=Rate.of(len(lost), n))
    res.maps = len({r[0].split(":")[0] for r in rows})
    return res


# ------------------------------------------------------------------ association with winning
WIN = MetricDef(
    id="op.win_association", version=1, title="Rounds won with it",
    question="How often does the team win full-buy rounds with an Operator vs without?",
    population="Team full-buy rounds in scope with a known inventory",
    numerator="Rounds won",
    unit="rounds",
    caveats=("Association, not cause: economy, opponent and map choice also differ between these rounds.",),
)


@metric(WIN)
def win_association(con, f: Filters) -> MetricResult:
    w, p = f.where("t")
    rows = con.execute(f"""SELECT round_key, n_op > 0, won FROM team_rounds t
                           WHERE {w} AND inventory_known AND economy = 'full' AND won IS NOT NULL""", p).fetchall()
    with_ = [r for r in rows if r[1]]
    without = [r for r in rows if not r[1]]
    res = MetricResult(WIN, f, rate=Rate.of(sum(r[2] for r in with_), len(with_)),
                       supporting=[r[0] for r in with_ if r[2]], contrary=[r[0] for r in with_ if not r[2]])
    res.value = dict(without=Rate.of(sum(r[2] for r in without), len(without)))
    res.maps, res.series = _scope(con, f, "AND inventory_known AND economy = 'full'")
    return res


# ------------------------------------------------------------------ forwardness
FORWARD = MetricDef(
    id="op.forwardness", version=2, title="How far forward",
    question="How far toward the enemy spawn are their Operator fights, compared with every team on this map?",
    population="Operator/Outlaw kills and hits by the team on one map and side, with a shooter position",
    numerator="Median of d(own spawn) / (d(own spawn) + d(enemy spawn)) at the shooter's position",
    unit="engagements",
    caveats=("Needs a single map and side.", "Positions come from the event, not continuous tracking."),
)


def spawns(con, map_name):
    return {s: (x, y) for s, x, y in con.execute("SELECT side, x, y FROM spawns WHERE map = ?", [map_name]).fetchall()}


def fwd(side, x, y, sp):
    own, enemy = (sp["defender"], sp["attacker"]) if side == "defender" else (sp["attacker"], sp["defender"])
    d_own = np.hypot(np.asarray(x) - own[0], np.asarray(y) - own[1])
    d_en = np.hypot(np.asarray(x) - enemy[0], np.asarray(y) - enemy[1])
    return d_own / (d_own + d_en)


@metric(FORWARD)
def forwardness(con, f: Filters) -> MetricResult:
    res = MetricResult(FORWARD, f)
    if not (f.map and f.side):
        res.warnings.append("Pick one map and one side to compare positioning.")
        return res
    sp = spawns(con, f.map)
    if {"attacker", "defender"} - sp.keys():
        res.warnings.append("No spawn reference for this map.")
        return res
    eng = [e for e in _op_engagements(con, f, kinds=("kill", "damage")) if e[12] is not None]
    if not eng:
        return res
    vals = fwd(f.side, [e[12] for e in eng], [e[13] for e in eng], sp)
    league = con.execute(f"""SELECT list(att_x), list(att_y) FROM engagements
                             WHERE map = ? AND att_side = ? AND weapon IN {OP} AND att_x IS NOT NULL
                               AND phase IN ('pre_plant','post_plant')""", [f.map, f.side]).fetchone()
    lv = fwd(f.side, np.array(league[0]), np.array(league[1]), sp)
    res.value = dict(team_median=round(float(np.median(vals)), 3), league_median=round(float(np.median(lv)), 3),
                     league_n=int(len(lv)), n=len(vals),
                     team_q=[round(float(q), 3) for q in np.quantile(vals, [0.25, 0.75])])
    res.maps = len({e[0].split(":")[0] for e in eng})
    return res
