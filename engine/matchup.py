"""Step 5e: two teams on one map. Pairs one team's attack measures with the other's defence measures,
each against the league, and says where an edge is beyond noise. Built only from existing metric results.

A matchup runs up to 20 checks, so a stance counts only if it survives false-discovery control over all of them
(D-024). An edge compares the two stances; it isn't a test of one team against the other."""
from __future__ import annotations

from engine.report import _signed, pct
from engine.significance import benjamini_hochberg, dispersion, rate_p


MIN_N = 20


def stance(r, league, higher_is_better=True):
    """+1 beyond noise in this team's favour, -1 beyond noise against it, 0 within noise, None if too few rounds."""
    if not r or r.get("p") is None or (r.get("n") or 0) < MIN_N or r.get("small_sample"):
        return None
    if not league or league.get("p") is None:
        return None
    if r["lo"] <= league["p"] <= r["hi"]:
        return 0
    return 1 if (r["p"] > league["p"]) == higher_is_better else -1


def duel_stance(v):
    if not v or v.get("diff") is None or (v.get("n") or 0) < MIN_N:
        return None
    if not v.get("beyond_noise"):
        return 0
    return 1 if v["diff"] > 0 else -1


def read(s_att, s_def):
    if s_att is None or s_def is None:
        return "too_few"
    if s_att > s_def:
        return "attacker"
    if s_def > s_att:
        return "defender"
    return "even"


def _missing_rate():
    return dict(p=None, lo=None, hi=None, n=None, league=None, stance=None, p_value=None)


def _num(v):
    return "too few rounds" if v is None else pct(v)


def _dry(v):
    return "too few rounds" if v is None else _signed(round(v * 100, 1))   # no "−0.0"


def _metric(data: dict, key: str):
    return data.get(key) if isinstance(data, dict) else None


def _economy_bucket(data: dict, bucket: str):
    m = _metric(data, "team.economy") or {}
    for b in m.get("breakdown", []):
        if b.get("bucket") == bucket:
            return b
    return None


def _rate_side(test_id, rate, league_rate, higher_is_better=True):
    if not rate or not league_rate:
        return _missing_rate()
    st = stance(rate, league_rate, higher_is_better=higher_is_better)
    return dict(p=rate.get("p"), lo=rate.get("lo"), hi=rate.get("hi"), n=rate.get("n"), league=league_rate.get("p"),
                stance=st, p_value=None if st is None else rate_p(rate, league_rate.get("p"), dispersion(test_id)))


def _dry_side(value):
    if not value:
        return _missing_rate()
    st = duel_stance(value) if value.get("p_value") is not None else None    # one series: no range
    return dict(p=value.get("diff"), lo=value.get("lo"), hi=value.get("hi"), n=value.get("n"), league=0.0,
                stance=st, p_value=None if st is None else value["p_value"])


def _sentence(pair_id: str, x_name: str, y_name: str, att: dict, dfn: dict) -> str:
    x = _num(att["p"])
    lx = _num(att["league"])
    y = _num(dfn["p"])
    ly = _num(dfn["league"])
    if pair_id == "plant_reach":
        return f"{x_name} plant in {x} of attack rounds (league {lx}); attackers plant in {y} of {y_name}'s defence rounds (league {ly})."
    if pair_id == "post_plant":
        return f"{x_name} win {x} after planting (league {lx}); {y_name} retake {y} of plants (league {ly})."
    if pair_id == "first_blood":
        return f"{x_name} get first blood in {x} of attack rounds (league {lx}); {y_name} get it in {y} of defence rounds (league {ly})."
    if pair_id == "dry_duels":
        return f"In dry duels {x_name} on attack are {_dry(att['p'])} points against expected; {y_name} on defence are {_dry(dfn['p'])}."
    return f"{x_name}'s ecos against a full buy win {x} (league {lx}); {y_name}'s full buys against an eco win {y} (league {ly})."


def _pair(pair_id: str, title: str, attacker_id: str, attacker_name: str, xa: dict, defender_id: str, defender_name: str, yd: dict):
    ap = (_metric(xa, "team.post_plant") or {}).get("value") or {}
    dp = (_metric(yd, "team.retakes") or {}).get("value") or {}
    unit = "rate"
    if pair_id == "plant_reach":
        att = _rate_side("team.post_plant.plant_share", ap.get("plant_share"), ap.get("league_plant_share"))
        dfn = _rate_side("team.retakes.plants_faced", dp.get("plants_faced"), dp.get("league_plants_faced"),
                         higher_is_better=False)
    elif pair_id == "post_plant":
        att = _rate_side("team.post_plant.win", ap.get("post_plant_win"), ap.get("league_post_plant_win"))
        dfn = _rate_side("team.retakes.retake", dp.get("retake"), dp.get("league_retake"))
    elif pair_id == "first_blood":
        ao = (_metric(xa, "team.openings") or {}).get("value") or {}
        do = (_metric(yd, "team.openings") or {}).get("value") or {}
        att = _rate_side("team.openings.first_blood", ao.get("first_blood"), ao.get("league_first_blood"))
        dfn = _rate_side("team.openings.first_blood", do.get("first_blood"), do.get("league_first_blood"))
    elif pair_id == "dry_duels":
        att = _dry_side((_metric(xa, "fights.dry_duels") or {}).get("value"))
        dfn = _dry_side((_metric(yd, "fights.dry_duels") or {}).get("value"))
        unit = "diff"
    else:
        ae = _economy_bucket(xa, "scrappy_vs_full") or {}
        de = _economy_bucket(yd, "full_vs_anti") or {}
        att = _rate_side("team.economy.scrappy_vs_full", ae.get("rate"), ae.get("league"))
        dfn = _rate_side("team.economy.full_vs_anti", de.get("rate"), de.get("league"))
    return dict(id=pair_id, title=title, attacker=attacker_id, defender=defender_id, att=att, dfn=dfn, unit=unit,
                sentence=_sentence(pair_id, attacker_name, defender_name, att, dfn))


def _decide(pairs: list[dict]) -> list[dict]:
    """Drop stances that don't survive false-discovery control over the whole matchup, then read each pair."""
    sides = [x for p in pairs for x in (p["att"], p["dfn"])]
    for x, kept in zip(sides, benjamini_hochberg([x["p_value"] for x in sides])):
        if x["stance"] and not kept:
            x["stance"] = 0
    for p in pairs:
        r = read(p["att"]["stance"], p["dfn"]["stance"])
        p["read"] = r
        p["edge"] = p["attacker"] if r == "attacker" else p["defender"] if r == "defender" else None
    return pairs


def facing_pairs(team_a_id: str, team_a_name: str, team_b_id: str, team_b_name: str,
                 a_att: dict, a_def: dict, b_att: dict, b_def: dict):
    specs = [
        ("plant_reach", "Getting the plant down"),
        ("post_plant", "After the plant"),
        ("first_blood", "First blood"),
        ("dry_duels", "Dry duels"),
        ("ecos", "Ecos against full buys"),
    ]
    out = []
    for pid, title in specs:
        out.append(_pair(pid, title, team_a_id, team_a_name, a_att, team_b_id, team_b_name, b_def))
    for pid, title in specs:
        out.append(_pair(pid, title, team_b_id, team_b_name, b_att, team_a_id, team_a_name, a_def))
    return _decide(out)


def top_lines(att_data, def_data, k=3):
    items = []
    for f in (att_data.get("summary") or []):
        c = dict(f)
        c["side"] = "attacker"
        items.append(c)
    for f in (def_data.get("summary") or []):
        c = dict(f)
        c["side"] = "defender"
        items.append(c)
    items.sort(key=lambda x: x.get("score") if x.get("score") is not None else float("-inf"), reverse=True)
    return items[:k]


def head_to_head(con, a, b, since=None, until=None, limit=10):
    where = ["((g.team1_id = ? AND g.team2_id = ?) OR (g.team1_id = ? AND g.team2_id = ?))"]   # parenthesised: AND binds tighter than OR
    params = [a, b, b, a]
    if since:
        where.append("g.started_at >= ?")
        params.append(since)
    if until:
        where.append("g.started_at < ?")      # exclusive, like every other filter
        params.append(until)
    params.append(limit)

    rows = con.execute(f"""
        WITH h2h AS (
            SELECT g.series_id, g.game_id, g.map, g.started_at, g.event, g.stage, g.winner_team_id
            FROM games g
            WHERE {' AND '.join(where)}
            ORDER BY g.started_at DESC
            LIMIT ?
        ), rr AS (
            SELECT game_id, team_id, count(*) FILTER (WHERE won) AS rounds_won
            FROM team_rounds
            GROUP BY game_id, team_id
        )
        SELECT h.series_id, h.game_id, h.map, h.started_at::DATE::VARCHAR AS d, h.event, h.stage,
               coalesce(ra.rounds_won, 0), coalesce(rb.rounds_won, 0), h.winner_team_id
        FROM h2h h
        LEFT JOIN rr ra ON ra.game_id = h.game_id AND ra.team_id = ?
        LEFT JOIN rr rb ON rb.game_id = h.game_id AND rb.team_id = ?
        ORDER BY h.started_at DESC
    """, params + [a, b]).fetchall()

    return [dict(series_id=sid, game_id=gid, map=m, date=d, event=e, stage=s,
                 a_rounds=ar, b_rounds=br, winner=w)
            for sid, gid, m, d, e, s, ar, br, w in rows]
