"""Team fundamentals cards: retakes, post-plant, economy, openings, and closing rounds."""
from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

from engine.config import V2_DIR
from engine.model.winprob import AliveTracker, load_revives
from .core import Filters, MetricDef, MetricResult, Rate, metric, ranked
from .executes import MIN_LEAGUE

EVENT_WP_PARQUET = V2_DIR / "models" / "event_wp.parquet"

PLANT_BUCKETS = ("ahead", "even", "behind")
ECO_BUCKETS = (
    ("full_vs_full", "full", ("full",)),
    ("full_vs_anti", "full", ("eco", "half")),
    ("scrappy_vs_full", "eco_half", ("full",)),
)   # half against half is too rare to rate (24 rounds league-wide); pistols have their own line

RETAKES = MetricDef(
    id="team.retakes",
    version=1,
    title="Retakes after facing a plant",
    question="When this team defends and faces a plant, how often does it retake?",
    population="Defender rounds where the team faced a plant on one map and side/date filter.",
    numerator="Those rounds the defenders won.",
    unit="plants faced",
    caveats=(
        "Numbers at the plant use alive counts at or before plant t_round, including revives.",
        "Buckets are from the attackers' view: ahead/even/behind.",
        "Association, not cause.",
    ),
)

POST_PLANT = MetricDef(
    id="team.post_plant",
    version=1,
    title="Attack plants and post-plant outcomes",
    question="How often does this team reach a plant on attack, and how often does it win after planting?",
    population="Attack rounds for one team on one map and side/date filter.",
    numerator="Rounds with a plant, and planted rounds won.",
    unit="attack rounds",
    caveats=(
        "Numbers at the plant use alive counts at or before plant t_round, including revives.",
        "Buckets are from the attackers' view: ahead/even/behind.",
        "Pre-plant attack losses are losses in rounds with no plant.",
        "Association, not cause.",
    ),
)

ECONOMY = MetricDef(
    id="team.economy",
    version=1,
    title="Economy outcomes",
    question="Which economy matchups and pistol/bonus spots does this team convert?",
    population="Team rounds with known economy labels for both teams.",
    numerator="Rounds won in each matchup or special round type.",
    unit="rounds",
    caveats=(
        "Pistol rounds are rounds 1 and 13 only (12-round halves). Overtime rounds are never pistols.",
        "Bonus rounds are rounds 2 and 14 only, and only when the same team won the prior pistol.",
        "'Scrappy' combines eco and half buys. Buy matchups leave out pistol rounds, which have their own line.",
        "Association, not cause.",
    ),
)

OPENINGS = MetricDef(
    id="team.openings",
    version=1,
    title="Opening fights",
    question="How often does this team get first blood, and what follows from it?",
    population="Team rounds with a first kill in pre-plant or post-plant phases.",
    numerator="Rounds with first blood for the team, and wins in each opening state.",
    unit="rounds",
    caveats=(
        "First blood is the first kill by (ts_ms, seq) in pre-plant/post-plant phases.",
        "A trade kill is still the second kill.",
        "Player breakdown is descriptive; not blame.",
        "Association, not cause.",
    ),
)

CLOSING = MetricDef(
    id="team.closing",
    version=1,
    title="Closing rounds from win-probability swings",
    question="How often does this team complete comebacks and avoid throws?",
    population="Team rounds that reached the comeback/throw win-probability thresholds.",
    numerator="Comebacks won after <=0.20 and throws lost after >=0.80.",
    unit="rounds",
    caveats=(
        "Win probability is from event_wp.parquet and is from the attackers' view; defender view is flipped.",
        "A round is in a denominator only if it reached the threshold at least once.",
        "Association, not cause.",
    ),
)


def _time_clause(since: str | None, until: str | None):
    w, p = [], []
    if since:
        w.append("t.started_at >= ?::TIMESTAMP")
        p.append(since)
    if until:
        w.append("t.started_at < ?::TIMESTAMP")
        p.append(until)
    return w, p


def _bucket(att_alive: int, def_alive: int) -> str:
    if att_alive > def_alive:
        return "ahead"
    if att_alive < def_alive:
        return "behind"
    return "even"


_ROUNDS_SQL = """
    SELECT t.round_key, t.series_id, t.map, t.round_no, t.side, t.won, t.team_id, t.economy,
           t.started_at, p.round_key IS NOT NULL AS planted, p.plant_t, 'plant' AS plant_result,
           opp.team_id AS opp_team_id, opp.economy AS opp_economy
    FROM team_rounds t
    LEFT JOIN (SELECT round_key, min(t_round) AS plant_t FROM objectives WHERE kind = 'plant' GROUP BY 1) p
           ON p.round_key = t.round_key
    JOIN team_rounds opp ON opp.round_key = t.round_key AND opp.team_id <> t.team_id
    WHERE {where}
    ORDER BY t.round_key
"""

# League numbers are the same for every team on a map and side: computed once, kept here.
# Keyed by (what, map, side, since, until); the store is read-only while the server runs. Tests clear it.
_LEAGUE: dict[tuple, object] = {}


def _cached(key: tuple, build):
    if key not in _LEAGUE:
        _LEAGUE[key] = build()
    return _LEAGUE[key]


def _team_rounds(con, f: Filters):
    w, p = f.where("t")
    return con.execute(_ROUNDS_SQL.format(where=w), p).fetchall()


def _game(round_key: str) -> str:
    return round_key.rsplit(":", 1)[0]


def _kills_by_round(con, round_keys: list[str]):
    if not round_keys:
        return {}
    rows = con.execute("""
        SELECT round_key, t_round, ts_ms, seq, vic_side, vic_id
        FROM engagements
        WHERE round_key IN (SELECT unnest(?)) AND kind = 'kill' AND phase IN ('pre_plant', 'post_plant')
        ORDER BY round_key, t_round, ts_ms, seq
    """, [round_keys]).fetchall()
    out = defaultdict(list)
    for rk, t, ts, seq, side, vic in rows:
        out[rk].append((float(t), int(ts), int(seq), side, vic))
    return out


def _plant_alive(con, rounds):
    keys = [r[0] for r in rounds if r[9] and r[10] is not None]
    revives = load_revives(con)
    kills = _kills_by_round(con, keys)
    out = {}
    for r in rounds:
        rk, _, _, _, _, _, _, _, _, planted, plant_t, *_ = r
        if not planted or plant_t is None:
            continue
        alive = AliveTracker()
        events = []
        for t, ts, seq, side, vic in kills.get(rk, []):
            if t <= float(plant_t):
                events.append((t, 0, ts, seq, side, vic))
        for t, side in revives.get(rk, []):
            if float(t) <= float(plant_t):
                events.append((float(t), 1, 0, 0, side, None))
        events.sort(key=lambda x: (x[0], x[1], x[2], x[3]))
        for _, kind, _, _, side, vic in events:
            if kind == 0:
                alive.kill(side, vic)
            else:
                alive.revive(side)
        a, d = alive.alive("attacker"), alive.alive("defender")
        out[rk] = dict(att_alive=a, def_alive=d, bucket=_bucket(a, d))
    return out


def _first_blood(con, round_keys: list[str]):
    if not round_keys:
        return {}
    rows = con.execute("""
        SELECT round_key, att_team, vic_team, att_id, att_name, vic_id, vic_name
        FROM (
            SELECT *, row_number() OVER (PARTITION BY round_key ORDER BY ts_ms, seq) AS rn
            FROM engagements
            WHERE kind = 'kill' AND phase IN ('pre_plant', 'post_plant') AND round_key IN (SELECT unnest(?))
        )
        WHERE rn = 1
    """, [round_keys]).fetchall()
    return {rk: dict(att_team=att_t, vic_team=vic_t, att_id=att_id, att_name=att_name, vic_id=vic_id, vic_name=vic_name)
            for rk, att_t, vic_t, att_id, att_name, vic_id, vic_name in rows}


def _league_rounds(con, f: Filters):
    def build():
        w, p = [], []
        if f.map:
            w.append("t.map = ?"); p.append(f.map)
        if f.side:
            w.append("t.side = ?"); p.append(f.side)
        tw, tp = _time_clause(f.since, f.until)
        return con.execute(_ROUNDS_SQL.format(where=" AND ".join(w + tw) or "1=1"), p + tp).fetchall()
    return _cached(("rounds", f.map, f.side, f.since, f.until), build)


def _league_plant_alive(con, f: Filters, lplants):
    return _cached(("plant_alive", f.map, f.side, f.since, f.until), lambda: _plant_alive(con, lplants))


def _league_first_blood(con, f: Filters, lrows):
    return _cached(("first_blood", f.map, f.side, f.since, f.until), lambda: _first_blood(con, [r[0] for r in lrows]))


@metric(RETAKES)
def retakes(con, f: Filters) -> MetricResult:
    res = MetricResult(RETAKES, f)
    if f.side == "attacker":
        return res
    fd = Filters(team_id=f.team_id, map=f.map, side="defender", since=f.since, until=f.until)
    rows = _team_rounds(con, fd)
    plants = [r for r in rows if r[9]]
    n = len(plants)
    if n == 0:
        return res
    alive = _plant_alive(con, plants)
    won = [r for r in plants if r[5]]
    res.rate = Rate.of(len(won), n)
    res.supporting = sorted(r[0] for r in plants if not r[5])
    res.contrary = sorted(r[0] for r in won)
    lrows = _league_rounds(con, fd)
    lplants = [r for r in lrows if r[9]]
    lalive = _league_plant_alive(con, fd, lplants)
    by = {b: [r for r in plants if alive.get(r[0], {}).get("bucket") == b] for b in PLANT_BUCKETS}
    lby = {b: [r for r in lplants if lalive.get(r[0], {}).get("bucket") == b] for b in PLANT_BUCKETS}
    res.value = dict(
        n=n,
        retake=Rate.of(len(won), n),
        league_retake=Rate.of(sum(1 for r in lplants if r[5]), len(lplants)) if len(lplants) >= MIN_LEAGUE else None,
        plants_faced=Rate.of(n, len(rows)),
        league_plants_faced=Rate.of(len(lplants), len(lrows)) if len(lrows) >= MIN_LEAGUE else None,
    )
    for b in PLANT_BUCKETS:
        rs = by[b]
        ls = lby[b]
        res.breakdown.append(dict(
            bucket=b,
            label=f"{b} at plant",
            rate=Rate.of(sum(1 for r in rs if r[5]), len(rs)),
            league=Rate.of(sum(1 for r in ls if r[5]), len(ls)) if len(ls) >= MIN_LEAGUE else None,
        ))
    res.series = len({r[1] for r in plants})
    res.maps = len({r[2] for r in plants})
    return res


@metric(POST_PLANT)
def post_plant(con, f: Filters) -> MetricResult:
    res = MetricResult(POST_PLANT, f)
    if f.side == "defender":
        return res
    fa = Filters(team_id=f.team_id, map=f.map, side="attacker", since=f.since, until=f.until)
    rows = _team_rounds(con, fa)
    n = len(rows)
    if n == 0:
        return res
    planted = [r for r in rows if r[9]]
    losses = [r for r in rows if not r[5]]
    pre_losses = [r for r in losses if not r[9]]
    alive = _plant_alive(con, planted)
    by = {b: [r for r in planted if alive.get(r[0], {}).get("bucket") == b] for b in PLANT_BUCKETS}
    lrows = _league_rounds(con, fa)
    lplanted = [r for r in lrows if r[9]]
    llosses = [r for r in lrows if not r[5]]
    lpre_losses = [r for r in llosses if not r[9]]
    lalive = _league_plant_alive(con, fa, lplanted)
    lby = {b: [r for r in lplanted if lalive.get(r[0], {}).get("bucket") == b] for b in PLANT_BUCKETS}
    res.value = dict(
        n=n,
        plant_share=Rate.of(len(planted), n),
        league_plant_share=Rate.of(len(lplanted), len(lrows)) if len(lrows) >= MIN_LEAGUE else None,
        post_plant_win=Rate.of(sum(1 for r in planted if r[5]), len(planted)),
        league_post_plant_win=Rate.of(sum(1 for r in lplanted if r[5]), len(lplanted)) if len(lplanted) >= MIN_LEAGUE else None,
        pre_plant_losses=Rate.of(len(pre_losses), len(losses)),
        league_pre_plant_losses=Rate.of(len(lpre_losses), len(llosses)) if len(llosses) >= MIN_LEAGUE else None,
    )
    for b in PLANT_BUCKETS:
        rs = by[b]
        ls = lby[b]
        res.breakdown.append(dict(
            bucket=b,
            label=f"{b} at plant",
            rate=Rate.of(sum(1 for r in rs if r[5]), len(rs)),
            league=Rate.of(sum(1 for r in ls if r[5]), len(ls)) if len(ls) >= MIN_LEAGUE else None,
        ))
    res.supporting = sorted(r[0] for r in pre_losses)
    res.contrary = sorted(r[0] for r in losses if r[9])
    res.series = len({r[1] for r in rows})
    res.maps = len({r[2] for r in rows})
    return res


OWN = {"full": ("full",), "eco_half": ("eco", "half"), "half": ("half",)}


def _is_pistol(round_no: int) -> bool:
    return round_no in (1, 13)


@metric(ECONOMY)
def economy(con, f: Filters) -> MetricResult:
    res = MetricResult(ECONOMY, f)
    rows = _team_rounds(con, f)
    rows = [r for r in rows if r[7] is not None and r[13] is not None]
    if not rows:
        return res
    lrows = [r for r in _league_rounds(con, f) if r[7] is not None and r[13] is not None]
    pwin = {(_game(r[0]), r[3], r[6]): r[5] for r in rows if _is_pistol(r[3])}
    lpwin = {(_game(r[0]), r[3], r[6]): r[5] for r in lrows if _is_pistol(r[3])}

    def filt(xs, own, opp):
        out = []
        for r in xs:
            if r[7] in OWN[own] and r[13] in opp and not _is_pistol(r[3]):
                out.append(r)
        return out

    res.value = {"n": len(rows)}
    for key, own, opp in ECO_BUCKETS:
        rs = filt(rows, own, opp)
        ls = filt(lrows, own, opp)
        res.breakdown.append(dict(
            bucket=key,
            label=key.replace("_", " "),
            rate=Rate.of(sum(1 for r in rs if r[5]), len(rs)),
            league=Rate.of(sum(1 for r in ls if r[5]), len(ls)) if len(ls) >= MIN_LEAGUE else None,
        ))
    pistols = [r for r in rows if _is_pistol(r[3])]
    lpistols = [r for r in lrows if _is_pistol(r[3])]
    bonus = [r for r in rows if r[3] in (2, 14) and pwin.get((_game(r[0]), r[3] - 1, r[6]))]
    lbonus = [r for r in lrows if r[3] in (2, 14) and lpwin.get((_game(r[0]), r[3] - 1, r[6]))]
    res.value.update(dict(
        pistol=Rate.of(sum(1 for r in pistols if r[5]), len(pistols)),
        league_pistol=Rate.of(sum(1 for r in lpistols if r[5]), len(lpistols)) if len(lpistols) >= MIN_LEAGUE else None,
        bonus=Rate.of(sum(1 for r in bonus if r[5]), len(bonus)),
        league_bonus=Rate.of(sum(1 for r in lbonus if r[5]), len(lbonus)) if len(lbonus) >= MIN_LEAGUE else None,
    ))
    res.series = len({r[1] for r in rows})
    res.maps = len({r[2] for r in rows})
    return res


@metric(OPENINGS)
def openings(con, f: Filters) -> MetricResult:
    res = MetricResult(OPENINGS, f)
    rows = _team_rounds(con, f)
    if not rows:
        return res
    rks = [r[0] for r in rows]
    fb = _first_blood(con, rks)
    used = [r for r in rows if r[0] in fb]
    if not used:
        return res
    lrows = _league_rounds(con, f)
    lfb = _league_first_blood(con, f, lrows)
    lused = [r for r in lrows if r[0] in lfb]

    got = [r for r in used if fb[r[0]]["att_team"] == r[6]]
    gave = [r for r in used if fb[r[0]]["vic_team"] == r[6]]
    lgot = [r for r in lused if lfb[r[0]]["att_team"] == r[6]]
    lgave = [r for r in lused if lfb[r[0]]["vic_team"] == r[6]]

    fk, fd = Counter(), Counter()
    fd_lost = Counter()
    for r in used:
        e = fb[r[0]]
        if e["att_team"] == r[6]:
            fk[(e["att_id"], e["att_name"])]+=1
        if e["vic_team"] == r[6]:
            fd[(e["vic_id"], e["vic_name"])]+=1
            if not r[5]:
                fd_lost[(e["vic_id"], e["vic_name"])]+=1
    for (pid, name), n in ranked(fk):
        res.breakdown.append(dict(bucket="player", player_id=pid, player_name=name, first_kills=n,
                                  first_deaths=fd.get((pid, name), 0), first_deaths_in_losses=fd_lost.get((pid, name), 0)))
    for (pid, name), n in ranked(fd):
        if (pid, name) not in fk:
            res.breakdown.append(dict(bucket="player", player_id=pid, player_name=name, first_kills=0,
                                      first_deaths=n, first_deaths_in_losses=fd_lost.get((pid, name), 0)))

    res.value = dict(
        n=len(used),
        first_blood=Rate.of(len(got), len(used)),
        league_first_blood=Rate.of(len(lgot), len(lused)) if len(lused) >= MIN_LEAGUE else None,
        win_after_first_blood=Rate.of(sum(1 for r in got if r[5]), len(got)),
        league_win_after_first_blood=Rate.of(sum(1 for r in lgot if r[5]), len(lgot)) if len(lgot) >= MIN_LEAGUE else None,
        win_after_first_death=Rate.of(sum(1 for r in gave if r[5]), len(gave)),
        league_win_after_first_death=Rate.of(sum(1 for r in lgave if r[5]), len(lgave)) if len(lgave) >= MIN_LEAGUE else None,
    )
    res.supporting = sorted(r[0] for r in gave if not r[5])
    res.contrary = sorted(r[0] for r in got if r[5])
    res.series = len({r[1] for r in used})
    res.maps = len({r[2] for r in used})
    return res


def _round_extremes(con) -> pd.DataFrame:
    """Per round and side: the lowest and highest win chance that side had after any event, and whether it won.
    Built once per event_wp file version (event_wp is from the attackers' view; flipped for defenders)."""
    path = Path(EVENT_WP_PARQUET)

    def build():
        wp = con.execute(f"""
            SELECT round_key, min(wp_after) AS lo, max(wp_after) AS hi
            FROM read_parquet('{path.as_posix()}') GROUP BY 1
        """).df()
        tr = con.execute("SELECT round_key, series_id, map, side, team_id, won, started_at FROM team_rounds").df()
        m = tr.merge(wp, on="round_key", how="inner")
        att = m["side"] == "attacker"
        m["min_wp"] = np.where(att, m["lo"], 1.0 - m["hi"])
        m["max_wp"] = np.where(att, m["hi"], 1.0 - m["lo"])
        m["team_id"] = m["team_id"].astype(str)
        m["started_at"] = pd.to_datetime(m["started_at"])
        return m.drop(columns=["lo", "hi"])
    return _cached(("closing", path.as_posix(), path.stat().st_mtime), build)


def _filter_rounds(m: pd.DataFrame, f: Filters, team: bool) -> pd.DataFrame:
    keep = np.ones(len(m), dtype=bool)
    if team:
        keep &= (m["team_id"] == str(f.team_id)).to_numpy()
    if f.map:
        keep &= (m["map"] == f.map).to_numpy()
    if f.side:
        keep &= (m["side"] == f.side).to_numpy()
    if f.since:
        keep &= (m["started_at"] >= pd.Timestamp(f.since)).to_numpy()
    if f.until:
        keep &= (m["started_at"] < pd.Timestamp(f.until)).to_numpy()
    return m[keep]


@metric(CLOSING)
def closing(con, f: Filters) -> MetricResult:
    res = MetricResult(CLOSING, f)
    if not Path(EVENT_WP_PARQUET).exists():
        res.warnings.append("Run python -m engine.model.wpa first")
        return res
    m = _round_extremes(con)
    g = _filter_rounds(m, f, team=True)
    if g.empty:
        return res
    lg = _filter_rounds(m, f, team=False)     # one row per round and side, so "both sides" counts each side once

    def rates(d):
        cb_den, th_den = d[d["min_wp"] <= 0.2], d[d["max_wp"] >= 0.8]
        return cb_den, cb_den[cb_den["won"]], th_den, th_den[~th_den["won"]]

    cb_den, cb, th_den, th = rates(g)
    lcb_den, lcb, lth_den, lth = rates(lg)
    res.value = dict(
        n=int(len(g)),
        comebacks=Rate.of(len(cb), len(cb_den)),
        league_comebacks=Rate.of(len(lcb), len(lcb_den)) if len(lcb_den) >= MIN_LEAGUE else None,
        throws=Rate.of(len(th), len(th_den)),
        league_throws=Rate.of(len(lth), len(lth_den)) if len(lth_den) >= MIN_LEAGUE else None,
    )
    res.supporting = sorted(th["round_key"].tolist())
    res.contrary = sorted(cb["round_key"].tolist())
    res.series = int(g["series_id"].nunique())
    res.maps = int(g["map"].nunique())
    return res
