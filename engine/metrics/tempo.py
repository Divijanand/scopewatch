"""Recon timing and commit timing around first information utility."""
from __future__ import annotations

from collections import Counter

import numpy as np

from engine.abilities import INFO, sql_list
from engine.weapons import GUNS
from .core import Filters, MetricDef, MetricResult, Rate, metric, ranked
from .executes import MIN_LEAGUE

RECON_TIMING = MetricDef(
    id="util.recon_timing",
    version=1,
    title="Recon timing and commit after recon",
    question="When does this team use its first recon, and how soon after does it commit?",
    population="Team rounds on one map and side from buy-phase end until round end (pre/post-plant casts only).",
    numerator="Rounds with at least one recon cast.",
    unit="rounds",
    caveats=(
        "Recon = recon-bolt, owl-drone, haunt, prowler, stealth-drone, seekers, wingman and Skye's trailblazer.",
        "Commit after recon: time from the first recon to the plant (rounds with a plant) or to the team's first "
        "gun damage dealt or taken, only when the recon came first.",
        "Late = first recon after the league's 75th percentile for this map and side, or no recon at all.",
        "Association, not cause.",
        "Late recon can be a choice (for example a slow default), not always a denial.",
        "The feed records casts, not recons destroyed before value.",
    ),
)


def _q(values: list[float], q: float) -> float | None:
    if not values:
        return None
    return float(np.quantile(np.asarray(values, dtype=float), q))


def _med_iqr(values: list[float]) -> dict | None:
    if not values:
        return None
    arr = np.asarray(values, dtype=float)
    return dict(
        median=round(float(np.median(arr)), 1),
        q1=round(float(np.quantile(arr, 0.25)), 1),
        q3=round(float(np.quantile(arr, 0.75)), 1),
    )


def _team_rounds(con, f: Filters):
    """One row per team round: won, first recon (time and agent, this team's casts only), plant, first contact."""
    w, p = f.where("t")
    return con.execute(f"""
        WITH t AS (SELECT * FROM team_rounds t WHERE {w}),
        c AS (
            SELECT c.round_key, c.team_id, min(c.t_round) AS first_recon_t, arg_min(c.agent, c.t_round) AS first_recon_agent
            FROM casts c JOIN t ON t.round_key = c.round_key AND t.team_id = c.team_id
            WHERE c.phase IN ('pre_plant', 'post_plant') AND c.ability IN {sql_list(INFO)}
            GROUP BY 1, 2
        ),
        p AS (SELECT round_key, min(t_round) AS plant_t FROM objectives WHERE kind = 'plant' GROUP BY 1),
        e AS (
            SELECT e.round_key, t.team_id, min(e.t_round) AS first_contact_t
            FROM engagements e JOIN t ON t.round_key = e.round_key AND (e.att_team = t.team_id OR e.vic_team = t.team_id)
            WHERE e.kind = 'damage' AND e.phase IN ('pre_plant', 'post_plant') AND lower(e.weapon) IN {sql_list(GUNS)}
            GROUP BY 1, 2
        )
        SELECT t.round_key, t.side, t.won, c.first_recon_t, c.first_recon_agent, p.plant_t, e.first_contact_t, t.series_id
        FROM t
        LEFT JOIN c ON c.round_key = t.round_key AND c.team_id = t.team_id
        LEFT JOIN p ON p.round_key = t.round_key
        LEFT JOIN e ON e.round_key = t.round_key AND e.team_id = t.team_id
        ORDER BY t.round_key
    """, p).fetchall()


_LEAGUE_CACHE: dict[tuple[str, str, str | None, str | None], dict] = {}


def _league_baseline(con, map_name: str, side: str, since: str | None, until: str | None):
    key = (map_name, side, since, until)
    if key in _LEAGUE_CACHE:
        return _LEAGUE_CACHE[key]
    w = ["t.map = ?", "t.side = ?"]
    p = [map_name, side]
    if since:
        w.append("t.started_at >= ?::TIMESTAMP")
        p.append(since)
    if until:
        w.append("t.started_at < ?::TIMESTAMP")
        p.append(until)
    rows = con.execute(f"""
        WITH t AS (SELECT round_key, team_id FROM team_rounds t WHERE {' AND '.join(w)})
        SELECT t.round_key, min(c.t_round)
        FROM t LEFT JOIN casts c ON c.round_key = t.round_key AND c.team_id = t.team_id
             AND c.phase IN ('pre_plant', 'post_plant') AND c.ability IN {sql_list(INFO)}
        GROUP BY t.round_key, t.team_id
    """, p).fetchall()
    xs = [float(r[1]) for r in rows if r[1] is not None]
    out = dict(
        median=_med_iqr(xs),
        p75=_q(xs, 0.75),
        n=len(rows),
    )
    _LEAGUE_CACHE[key] = out
    return out


@metric(RECON_TIMING)
def recon_timing(con, f: Filters) -> MetricResult:
    res = MetricResult(RECON_TIMING, f)
    if not f.map:
        res.warnings.append("Pick one map to compare recon timing with the league.")
        return res
    if not f.side:
        res.warnings.append("Pick one side to compare recon timing with the league.")
        return res
    rows = _team_rounds(con, f)
    n = len(rows)
    if n == 0:
        return res
    first_recon = [float(r[3]) for r in rows if r[3] is not None]
    by_agent = Counter(str(r[4]) for r in rows if r[4])

    # commit after recon: only when the recon came first (a recon after the plant or after first contact isn't
    # the read that set up the commit)
    recon_to_plant = [float(r[5]) - float(r[3]) for r in rows
                      if r[3] is not None and r[5] is not None and r[1] == "attacker" and r[5] >= r[3]]
    recon_to_contact = [float(r[6]) - float(r[3]) for r in rows
                        if r[3] is not None and r[6] is not None and r[1] == "attacker" and r[6] >= r[3]]

    league = _league_baseline(con, f.map, f.side, f.since, f.until)
    split_at = league["p75"]
    on_time = [r for r in rows if split_at is not None and r[3] is not None and float(r[3]) <= split_at]
    late = [r for r in rows if split_at is not None and (r[3] is None or float(r[3]) > split_at)]

    res.value = dict(
        n=n,
        first_recon=_med_iqr(first_recon),
        no_recon=Rate.of(sum(1 for r in rows if r[3] is None), n),
        first_recon_agent=[dict(agent=a, n=k) for a, k in ranked(by_agent)],
        recon_to_plant=_med_iqr(recon_to_plant) if f.side == "attacker" else None,
        recon_to_contact=_med_iqr(recon_to_contact) if f.side == "attacker" else None,
        league_first_recon=league["median"],
        vs_league=(round(float(np.median(first_recon)) - league["median"]["median"], 1)
                   if first_recon and league["median"] else None),
        league_n=league["n"],
        split_at=round(float(split_at), 1) if split_at is not None else None,
        on_time=Rate.of(sum(1 for r in on_time if r[2]), len(on_time)) if split_at is not None else None,
        late=Rate.of(sum(1 for r in late if r[2]), len(late)) if split_at is not None else None,
        min_league=MIN_LEAGUE,
    )
    res.supporting = sorted(r[0] for r in late if not r[2])
    res.contrary = sorted(r[0] for r in late if r[2])
    res.series = len({r[7] for r in rows})
    res.maps = len({f.map})
    return res
