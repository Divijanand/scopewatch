"""The Operator as a gamble: what it earns before it's lost, whether the holder gets away after a
shot, and what it takes for the enemy to kill it."""
from __future__ import annotations

from collections import Counter

from ..abilities import FLASH, MOVEMENT, SMOKE, STUN, ULTS, WEAPON_ULTS, sql_list
from .core import Filters, MetricDef, MetricResult, Rate, metric, ranked
from .operator import OP, OP_ITEMS

FIGHT = "('pre_plant', 'post_plant')"
ESCAPE_BEFORE_MS, ESCAPE_AFTER_MS = 1000, 4000   # movement cast this close to the kill counts as the escape
PUNISHED_MS = 5000                              # shooter dies within 5 s of the kill
UTIL_BEFORE_MS = 4000                           # enemy utility cast in the 4 s before the holder's death
UTIL_RADIUS_CM = 3500                           # ... by a caster within 35 m of the holder
SWARM_MS = 3000                                 # 2+ enemies hit the holder in the 3 s before death
ULT_BEFORE_MS = 10000                           # an enemy ult used in the 10 s before the death


def _rounds_of(rows, idx=0):
    return sorted({r[idx] for r in rows})


# ------------------------------------------------------------------ the gamble
GAMBLE = MetricDef(
    id="op.gamble", version=2, title="What the Operator buys them",
    question="In rounds a player holds the Operator/Outlaw, does it earn kills before it's lost, and does the enemy end up with it?",
    population="Player rounds in scope where the player holds an Operator/Outlaw at buy-phase end",
    numerator="Rounds where the holder died without an Operator kill (lost it for nothing)",
    unit="Operator rounds",
    caveats=("Kept = the holder was alive at the end of the round, so the rifle carries over.",
             "Picked up by the enemy = an enemy fired an Operator/Outlaw later in the round without holding one at "
             "buy-phase end. The feed has no weapon pickup events, so a pickup that never fired isn't seen.",
             "Deaths after the round result count: dying in the post-round still loses the rifle."),
)


def _gamble_rows(con, w, p):
    return con.execute(f"""
        WITH h AS (SELECT p.round_key, p.player_id, p.player_name, p.agent, p.team_id
                   FROM player_rounds p WHERE {w} AND p.has_op),
             d AS (SELECT e.round_key, e.vic_id pid, min(e.ts_ms) died_ms FROM engagements e
                   WHERE e.kind = 'kill' AND e.round_key IN (SELECT round_key FROM h) GROUP BY 1, 2),
             k AS (SELECT e.round_key, e.att_id pid, e.ts_ms FROM engagements e
                   WHERE e.kind = 'kill' AND e.weapon IN {OP} AND e.phase IN {FIGHT}
                     AND e.round_key IN (SELECT round_key FROM h)),
             s AS (SELECT e.round_key, e.att_team, min(e.ts_ms) ts FROM engagements e
                   LEFT JOIN player_rounds q ON q.round_key = e.round_key AND q.player_id = e.att_id
                   WHERE e.weapon IN {OP_ITEMS} AND NOT coalesce(q.has_op, FALSE)
                     AND e.round_key IN (SELECT round_key FROM h) GROUP BY 1, 2)
        SELECT h.round_key, h.player_id, h.player_name, h.agent, d.died_ms,
               (SELECT count(*) FROM k WHERE k.round_key = h.round_key AND k.pid = h.player_id
                  AND (d.died_ms IS NULL OR k.ts_ms <= d.died_ms)) op_kills,
               EXISTS (SELECT 1 FROM s WHERE s.round_key = h.round_key AND s.att_team <> h.team_id
                         AND d.died_ms IS NOT NULL AND s.ts > d.died_ms) stolen,
               t.won
        FROM h LEFT JOIN d ON d.round_key = h.round_key AND d.pid = h.player_id
        LEFT JOIN team_rounds t ON t.round_key = h.round_key AND t.team_id = h.team_id""", p).fetchall()


@metric(GAMBLE)
def gamble(con, f: Filters) -> MetricResult:
    w, p = f.where("p")
    if f.player_id:
        w += " AND p.player_id = ?"; p.append(f.player_id)
    rows = _gamble_rows(con, w, p)
    n = len(rows)
    groups = {
        "kept": [r for r in rows if r[4] is None],
        "traded": [r for r in rows if r[4] is not None and r[5] > 0],
        "lost": [r for r in rows if r[4] is not None and r[5] == 0],
    }
    labels = {"kept": "Survived with it", "traded": "Got a kill, then died", "lost": "Died without an Operator kill"}
    res = MetricResult(GAMBLE, f, rate=Rate.of(len(groups["lost"]), n))
    for key, rs in groups.items():
        res.breakdown.append(dict(bucket=key, label=labels[key], rate=Rate.of(len(rs), n),
                                  won=Rate.of(sum(1 for r in rs if r[7]), len(rs)),
                                  round_keys=_rounds_of(rs)))
    stolen = [r for r in rows if r[6]]
    res.breakdown.append(dict(bucket="stolen", label="Enemy fired it after", rate=Rate.of(len(stolen), n),
                              won=Rate.of(sum(1 for r in stolen if r[7]), len(stolen)),
                              round_keys=_rounds_of(stolen)))
    kills = [r[5] for r in rows]
    league = None
    if f.map and f.side:
        lw, lp = ["p.map = ?", "p.side = ?"], [f.map, f.side]
        if f.since:
            lw.append("p.started_at >= ?::TIMESTAMP"); lp.append(f.since)
        if f.until:
            lw.append("p.started_at < ?::TIMESTAMP"); lp.append(f.until)
        lr = _gamble_rows(con, " AND ".join(lw), lp)
        league = Rate.of(sum(1 for r in lr if r[4] is not None and r[5] == 0), len(lr))
    res.value = dict(league_lost=league,kills_per_round=round(sum(kills) / n, 2) if n else None,
                     multi_kill=Rate.of(sum(1 for k in kills if k >= 2), n),
                     by_player=[dict(name=nm, rounds=c) for nm, c in ranked(Counter(r[2] for r in rows), 3)])
    res.supporting = groups["lost"] and _rounds_of(groups["lost"]) or []
    res.contrary = sorted(set(_rounds_of(rows)) - set(res.supporting))
    res.maps = len({r[0].split(":")[0] for r in rows})
    return res


# ------------------------------------------------------------------ escapes after the shot
ESCAPES = MetricDef(
    id="op.escapes", version=2, title="Getting away with it",
    question="After an Operator kill, does the shooter use a movement ability, and do they survive the next 5 seconds?",
    population="Operator/Outlaw kills by the team in scope, between buy-phase end and the round result",
    numerator="Kills where the shooter died within 5 s (punished)",
    unit="Operator kills",
    caveats=("Movement = dash, teleport or speed ability (Jett, Chamber, Yoru, Veto, Raze, Neon, Omen, Waylay) "
             "cast from 1 s before to 4 s after the kill.",
             "A cast is recorded; whether it actually moved the player to safety isn't.",
             "Survival is association, not cause: holders who escape may also have picked safer angles."),
)


@metric(ESCAPES)
def escapes(con, f: Filters) -> MetricResult:
    w, p = f.where("e", team_col="att_team", side_col="att_side")
    if f.player_id:
        w += " AND e.att_id = ?"; p.append(f.player_id)
    rows = con.execute(f"""
        WITH k AS (SELECT e.round_key, e.event_id, e.att_id, e.att_name, e.att_agent, e.ts_ms, e.t_round
                   FROM engagements e
                   WHERE {w} AND e.kind = 'kill' AND e.weapon IN {OP} AND e.phase IN {FIGHT})
        SELECT k.round_key, k.att_name, k.att_agent, k.t_round,
               (SELECT any_value(c.ability) FROM casts c
                 WHERE c.round_key = k.round_key AND c.player_id = k.att_id AND c.ability IN {sql_list(MOVEMENT)}
                   AND c.ts_ms BETWEEN k.ts_ms - {ESCAPE_BEFORE_MS} AND k.ts_ms + {ESCAPE_AFTER_MS}) moved,
               EXISTS (SELECT 1 FROM engagements d
                        WHERE d.round_key = k.round_key AND d.kind = 'kill' AND d.vic_id = k.att_id
                          AND d.ts_ms > k.ts_ms AND d.ts_ms <= k.ts_ms + {PUNISHED_MS}) punished
        FROM k ORDER BY k.ts_ms""", p).fetchall()
    n = len(rows)
    punished = [r for r in rows if r[5]]
    moved = [r for r in rows if r[4]]
    still = [r for r in rows if not r[4]]
    res = MetricResult(ESCAPES, f, rate=Rate.of(len(punished), n))
    res.breakdown = [
        dict(bucket="moved", label="Used a movement ability", rate=Rate.of(len(moved), n),
             punished=Rate.of(sum(1 for r in moved if r[5]), len(moved)),
             abilities=[dict(ability=a, k=c) for a, c in ranked(Counter(r[4] for r in moved), 3)],
             round_keys=_rounds_of(moved)),
        dict(bucket="stayed", label="No movement ability", rate=Rate.of(len(still), n),
             punished=Rate.of(sum(1 for r in still if r[5]), len(still)), abilities=[],
             round_keys=_rounds_of(still)),
        dict(bucket="punished", label="Died within 5 s", rate=Rate.of(len(punished), n),
             round_keys=_rounds_of(punished)),
    ]
    by_agent = {}
    for r in rows:
        by_agent.setdefault(r[2] or "unknown", []).append(r)
    res.value = dict(by_agent=[dict(agent=a, kills=len(rs), punished=Rate.of(sum(1 for r in rs if r[5]), len(rs)),
                                    moved=Rate.of(sum(1 for r in rs if r[4]), len(rs)))
                               for a, rs in sorted(by_agent.items(), key=lambda kv: (-len(kv[1]), str(kv[0])))])
    res.supporting = _rounds_of(punished)
    res.contrary = sorted(set(_rounds_of(rows)) - set(res.supporting))
    res.maps = len({r[0].split(":")[0] for r in rows})
    return res


# ------------------------------------------------------------------ what it takes to kill it
BROKEN = MetricDef(
    id="op.how_it_dies", version=2, title="How it gets broken",
    question="When the team's Operator holder dies, was it after enemy flashes or stuns, smokes, or several enemies at once?",
    population="Deaths of a player who held an Operator/Outlaw at buy-phase end, between buy-phase end and the round result",
    numerator="Deaths with an enemy flash or stun cast nearby in the 4 s before",
    unit="deaths",
    caveats=("'Nearby' = cast by an enemy standing within 35 m of where the holder died. The feed records where "
             "utility was thrown from, not where it landed or who it blinded.",
             "Casts without a reliable position (ability-supplement quality) aren't counted, so utility is undercounted.",
             "Swarmed = two or more different enemies hit the holder in the 3 s before the death.",
             "Enemy ult = an enemy used an ultimate in the 10 s before the death, anywhere on the map (ults like "
             "Nightfall or Hunter's Fury reach far). Blade Storm, Overdrive and Tour de Force count only once they "
             "have hit someone."),
)


@metric(BROKEN)
def how_it_dies(con, f: Filters) -> MetricResult:
    w, p = f.where("e", team_col="vic_team", side_col="vic_side")
    if f.player_id:
        w += " AND e.vic_id = ?"; p.append(f.player_id)
    rows = con.execute(f"""
        WITH d AS (SELECT e.round_key, e.vic_id, e.vic_name, e.vic_team, e.ts_ms, e.vic_x, e.vic_y, e.weapon
                   FROM engagements e
                   JOIN player_rounds pr ON pr.round_key = e.round_key AND pr.player_id = e.vic_id AND pr.has_op
                   WHERE {w} AND e.kind = 'kill' AND e.phase IN {FIGHT})
        SELECT d.round_key, d.vic_name, d.weapon,
               (SELECT list(DISTINCT c.ability) FROM casts c
                 WHERE c.round_key = d.round_key AND c.team_id <> d.vic_team AND c.spatial_ok
                   AND c.ts_ms BETWEEN d.ts_ms - {UTIL_BEFORE_MS} AND d.ts_ms
                   AND d.vic_x IS NOT NULL
                   AND sqrt((c.x - d.vic_x) ^ 2 + (c.y - d.vic_y) ^ 2) <= {UTIL_RADIUS_CM}) util,
               (SELECT count(DISTINCT a.att_id) FROM engagements a
                 WHERE a.round_key = d.round_key AND a.vic_id = d.vic_id AND a.att_team <> d.vic_team
                   AND a.ts_ms BETWEEN d.ts_ms - {SWARM_MS} AND d.ts_ms) shooters,
               (SELECT list(DISTINCT u.ability) FROM (
                   SELECT c.ability FROM casts c
                    WHERE c.round_key = d.round_key AND c.team_id <> d.vic_team
                      AND c.ability IN {sql_list(ULTS - WEAPON_ULTS)}
                      AND c.ts_ms BETWEEN d.ts_ms - {ULT_BEFORE_MS} AND d.ts_ms
                   UNION ALL
                   SELECT a.weapon FROM engagements a
                    WHERE a.round_key = d.round_key AND a.att_team <> d.vic_team
                      AND a.weapon IN {sql_list(WEAPON_ULTS)}
                      AND a.ts_ms BETWEEN d.ts_ms - {ULT_BEFORE_MS} AND d.ts_ms) u) ults
        FROM d ORDER BY d.ts_ms""", p).fetchall()
    n = len(rows)

    def has(r, kinds):
        return any(a in kinds for a in (r[3] or []))
    blinded = [r for r in rows if has(r, FLASH | STUN)]
    smoked = [r for r in rows if has(r, SMOKE)]
    swarmed = [r for r in rows if (r[4] or 0) >= 2]
    ulted = [r for r in rows if r[5]]
    duel = [r for r in rows if r not in blinded and r not in smoked and r not in swarmed and r not in ulted]
    util = Counter(a for r in rows for a in (r[3] or []) if a in FLASH | STUN | SMOKE)
    res = MetricResult(BROKEN, f, rate=Rate.of(len(blinded), n))
    res.breakdown = [
        dict(bucket="blinded", label="Flash or stun nearby", rate=Rate.of(len(blinded), n), round_keys=_rounds_of(blinded)),
        dict(bucket="smoked", label="Smoke nearby", rate=Rate.of(len(smoked), n), round_keys=_rounds_of(smoked)),
        dict(bucket="swarmed", label="Two or more enemies at once", rate=Rate.of(len(swarmed), n),
             round_keys=_rounds_of(swarmed)),
        dict(bucket="ulted", label="During an enemy ult", rate=Rate.of(len(ulted), n), round_keys=_rounds_of(ulted)),
        dict(bucket="duel", label="None of these: a straight duel", rate=Rate.of(len(duel), n),
             round_keys=_rounds_of(duel)),
    ]
    res.value = dict(top_utility=[dict(ability=a, k=c) for a, c in ranked(util, 4)],
                     top_ults=[dict(ability=a, k=c) for a, c in ranked(Counter(a for r in ulted for a in r[5]), 4)])
    res.supporting = _rounds_of(blinded)
    res.contrary = sorted(set(_rounds_of(rows)) - set(res.supporting))
    res.maps = len({r[0].split(":")[0] for r in rows})
    return res
