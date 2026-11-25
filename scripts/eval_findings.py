"""Are the "Prepare for these" findings real? (D-024). League-level only: no team names or numbers, safe for docs/.

    python -m scripts.eval_findings

1. Chance: the same reports with every real difference removed. Anything found there is false by construction.
2. Replication: findings from a team's games before a cut date, checked against its games after it.
"""
from __future__ import annotations

import collections
import copy
import logging
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

import duckdb
import numpy as np

from engine import report
from engine.config import DB_PATH, ROOT
from engine.metrics import REGISTRY, Filters
from engine.metrics import duels as D
from engine.metrics.core import Rate
from engine.significance import Q

N_TEAM_MAPS = 20        # the biggest team-maps, both sides
CHANCE_REPS = 20
CUT_MIN_ROUNDS = 60     # rounds needed on each side of the cut date
SKIP = ("team.predictability",)   # its choice can differ between halves, and its null isn't simulated


def run_metrics(con, team, mp, side, since=None, until=None, skip=()):
    f = Filters(team_id=team, map=mp, side=side, since=since, until=until)
    return {mid: REGISTRY[mid][1](con, f).to_dict(evidence_limit=0) for mid in report.TEMPLATES if mid not in skip}


def duel_result(g, rng=None):
    """The dry-duel metric's value and agent breakdown for these fights; with rng, signs flipped per series (null)."""
    if rng is not None and len(g):
        s = g["series_id"].astype(str)
        sign = s.map(dict(zip(s.unique(), rng.choice([-1, 1], s.nunique()))))
        g = g.assign(actual=g["expected"] + sign * (g["actual"] - g["expected"]))
    br = [dict(bucket="agent", agent=a, **D.section(x)) for a, x in g.groupby("team_agent")
          if isinstance(a, str) and a and len(x) >= D.MIN_AGENT_FIGHTS]
    return dict(value=dict(total=len(g), **D.section(g)), breakdown=br)


def null_results(res, rng):
    """Every rate redrawn at the league's rate, with the measured clustering; every mean recentred on the league's."""
    def draw(r, p):
        if not r or not r.get("n") or p is None:
            return r
        n, deff = r["n"], r["deff"]
        eff = max(1, round(n / deff))
        return asdict(Rate.of(int(round(rng.binomial(eff, p) / eff * n)), n, deff))

    out = {}
    for mid, r in res.items():
        if mid in SKIP or mid == "fights.dry_duels":
            continue
        v, br = copy.deepcopy(r.get("value") or {}), copy.deepcopy(r.get("breakdown") or [])
        for k in list(v):
            lg = v.get("league_" + k)
            if isinstance(v[k], dict) and isinstance(lg, dict):
                v[k] = draw(v[k], lg.get("p"))
        if isinstance(v.get("before_league_median"), dict):
            v["before_league_median"] = draw(v["before_league_median"], 0.5)
        if isinstance(v.get("late"), dict) and isinstance(v.get("on_time"), dict) and v["late"]["n"] + v["on_time"]["n"]:
            p = (v["late"]["k"] + v["on_time"]["k"]) / (v["late"]["n"] + v["on_time"]["n"])
            v["late"], v["on_time"] = (draw(v[x], p) for x in ("late", "on_time"))
        if mid == "op.wpa" and v.get("p_value") is not None:
            # redraw the mean around the league's, keeping the range's width; p from a uniform draw is exact under the null
            u = float(rng.uniform())
            half = (v["hi"] - v["lo"]) / 2
            v["p_value"], beyond = u, u < 0.10
            c = v["league_mean"] + (half * 1.01 if beyond else half * 0.5) * (1 if rng.uniform() < 0.5 else -1)
            v["mean"], v["lo"], v["hi"] = c, c - half, c + half
        for b in br:
            if isinstance(b.get("rate"), dict) and isinstance(b.get("league"), dict):
                b["rate"] = draw(b["rate"], b["league"].get("p"))
        out[mid] = dict(value=v, breakdown=br)
    return out


def chance(con, df, rates):
    rng = np.random.default_rng(7)
    combos = con.execute("SELECT team_id, map FROM team_rounds GROUP BY 1, 2 HAVING count(*) >= 150 "
                         "ORDER BY count(*) DESC, 1, 2 LIMIT ?", [N_TEAM_MAPS]).fetchall()
    obs = collections.Counter()
    null = collections.Counter()
    by_metric = {k: collections.Counter() for k in ("old", "new", "null_old", "null_new")}
    for team, mp in combos:
        tv = D.team_view(df, rates, str(team))
        tv = tv[tv["map"] == mp]
        for side in ("attacker", "defender"):
            res = run_metrics(con, team, mp, side)
            items = [f for f in report.checks(res) if f["metric"] not in SKIP]
            old, new = [f for f in items if f["stands_out"]], report.select(items)
            obs.update(reports=1, checks=len(items), old=len(old), new=len(new), any_old=bool(old), any_new=bool(new))
            for key, fs in (("old", old), ("new", new)):
                by_metric[key].update(f["metric"] for f in fs)
            fights = tv[tv["team_side"] == side]
            for _ in range(CHANCE_REPS):
                nr = null_results(res, rng)
                nr["fights.dry_duels"] = duel_result(fights, rng)
                ni = report.checks(nr)
                no, nn = [f for f in ni if f["stands_out"]], report.select(ni)
                null.update(reports=1, old=len(no), new=len(nn), any_old=bool(no), any_new=bool(nn))
                for key, fs in (("null_old", no), ("null_new", nn)):
                    by_metric[key].update(f["metric"] for f in fs)
    return obs, null, by_metric


def replication(con, df, rates):
    cut = con.execute("SELECT median(d)::DATE::VARCHAR FROM (SELECT series_id, min(started_at) d FROM team_rounds GROUP BY 1)").fetchone()[0]
    starts = dict(con.execute("SELECT series_id, min(started_at)::VARCHAR FROM team_rounds GROUP BY 1").fetchall())
    combos = con.execute("""SELECT team_id, map, side FROM team_rounds GROUP BY ALL
                            HAVING count(*) FILTER (WHERE started_at < ?::TIMESTAMP) >= ?
                               AND count(*) FILTER (WHERE started_at >= ?::TIMESTAMP) >= ? ORDER BY ALL""",
                         [cut, CUT_MIN_ROUNDS, cut, CUT_MIN_ROUNDS]).fetchall()
    out = {k: collections.Counter() for k in ("all", "old_only", "new")}
    per = collections.defaultdict(lambda: [0, 0])
    for team, mp, side in combos:
        tv = D.team_view(df, rates, str(team))
        tv = tv[(tv["map"] == mp) & (tv["team_side"] == side)]
        early_series = tv["series_id"].astype(str).map(lambda s: starts.get(s, "9999") < cut)
        early = run_metrics(con, team, mp, side, until=cut, skip=SKIP + ("fights.dry_duels",))
        late = run_metrics(con, team, mp, side, since=cut, skip=SKIP + ("fights.dry_duels",))
        early["fights.dry_duels"], late["fights.dry_duels"] = duel_result(tv[early_series]), duel_result(tv[~early_series])
        items = report.checks(early)
        later = {f["id"]: f for f in report.checks(late)}
        chosen = {f["id"] for f in report.select(items)}
        for f in items:
            g = later.get(f["id"])
            if g is None or g["team"] == g["league"] or f["team"] == f["league"]:
                continue
            same = (f["team"] > f["league"]) == (g["team"] > g["league"])
            ratio = (g["team"] - g["league"]) / (f["team"] - f["league"])
            kinds = ["all"] + (["new"] if f["id"] in chosen else ["old_only"] if f["stands_out"] else [])
            for k in kinds:
                out[k].update(n=1, same=int(same))
                out[k]["ratio"] += ratio if f["unit"] == "rate" else 0
                out[k]["ratio_n"] += f["unit"] == "rate"
            if f["id"] in chosen:
                per[f["metric"]][0] += same
                per[f["metric"]][1] += 1
    return cut, len(combos), out, per


def main():
    logging.disable(logging.WARNING)
    con = duckdb.connect(str(DB_PATH), read_only=True)
    path = Path(D.FIGHTS_PARQUET)
    df, rates = D._load(str(path), path.stat().st_mtime)
    obs, null, bm = chance(con, df, rates)
    cut, n_combos, rep, per = replication(con, df, rates)
    con.close()
    k = null["reports"] / obs["reports"]

    def r(x):
        w = Rate.of(x["same"], x["n"])
        return f"{w.p:.0%} ({w.k} of {w.n}; likely {w.lo:.0%}–{w.hi:.0%})" if x["n"] else "–"

    lines = [
        "# Are the findings real?", "",
        f"Run {datetime.now().isoformat(timespec='seconds')}. League-level only. Method: D-024, `engine/significance.py`.", "",
        "## 1. How many findings chance alone gives", "",
        f"The {N_TEAM_MAPS} biggest team-maps on both sides ({obs['reports']} reports, {obs['checks']} checks), against the "
        f"same reports with every real difference removed ({CHANCE_REPS} draws each): rates redrawn at the league's rate with "
        "the measured clustering, dry-duel results sign-flipped per series. Predictability is left out (its null isn't "
        "simulated). Old rule = the range excludes the league. New rule = also survives Benjamini-Hochberg at "
        f"q = {Q:.2f} over the whole report. Counts are before the limit of five.", "",
        "| | Old rule | New rule |", "|---|---|---|",
        f"| Findings in the real data | {obs['old']} | {obs['new']} |",
        f"| Findings with no real differences | {null['old'] / k:.1f} | {null['new'] / k:.1f} |",
        f"| Real reports with at least one finding | {obs['any_old']} of {obs['reports']} | {obs['any_new']} of {obs['reports']} |",
        f"| No-difference reports with at least one finding | {null['any_old'] / null['reports']:.0%} | {null['any_new'] / null['reports']:.0%} |", "",
        "| Metric | Old: real | Old: chance | New: real | New: chance |", "|---|---|---|---|---|",
        *[f"| `{m}` | {bm['old'][m]} | {bm['null_old'][m] / k:.1f} | {bm['new'][m]} | {bm['null_new'][m] / k:.1f} |"
          for m in report.TEMPLATES if m not in SKIP], "",
        "## 2. Do findings hold in later games?", "",
        f"Checks on each team-map-side's games before {cut} and after it ({n_combos} with at least {CUT_MIN_ROUNDS} rounds "
        "each side). A finding holds when the later games differ from the league in the same direction. Rosters, agents and "
        "patches change in between, so this asks for more than statistical significance. A pure coin flip would be 50%.", "",
        "| Checks on the earlier games | Same direction later | Later gap as a share of the earlier gap (rates) |", "|---|---|---|",
        *[f"| {label} | {r(rep[key])} | {rep[key]['ratio'] / rep[key]['ratio_n']:.0%} |" if rep[key]["ratio_n"] else f"| {label} | {r(rep[key])} | – |"
          for key, label in (("all", "Every check"), ("old_only", "Old rule only (now dropped)"), ("new", "New rule (shown)"))], "",
        "| Metric (new rule) | Same direction later |", "|---|---|",
        *[f"| `{m}` | {a} of {b} |" for m, (a, b) in sorted(per.items(), key=lambda kv: -kv[1][1])],
    ]
    lines += ["", "## How to read this", "",
        "- **Chance** is the number with no real differences anywhere, so it's a worst case for the real reports: where "
        "some differences are real, false-discovery control aims for about one false finding in ten.",
        "- **Direction, not size.** The gaps that get picked are larger than the ones that follow (selection, plus real "
        "change between the halves). Read a finding as 'more than most' or 'less than most', not as a forecast of its number.",
        "- **Replication samples are small**, and checks on one team overlap (attack and defence, first blood and what "
        "follows it), so the ranges in section 2 are too narrow. It can't show that the new rule beats the old one.",
        "- The correlations come from the same games as the reports. They're league-wide, with no team tuned (EVAL_RANGES.md).",
        "- **Old rule** here uses the D-025 ranges, which are wider than the ones the first version printed. With those, the old rule gave 93 findings against 65 by chance."]
    out = ROOT / "docs" / "EVAL_FINDINGS.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[lines.index("## 1. How many findings chance alone gives"):]))


if __name__ == "__main__":
    main()
