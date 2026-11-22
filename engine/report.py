from __future__ import annotations

NO_FINDINGS_NOTE = "Nothing stands out beyond noise on this map and side: they play close to the league average."
ORDER = ["att.executes", "util.recon_timing", "team.retakes", "team.post_plant", "team.economy", "team.openings", "op.wpa", "fights.dry_duels", "team.predictability", "team.closing"]


def pct(x: float) -> str:
    return f"{round(x * 100)}%"


def vs_league(r, league):
    """Beyond noise when the league rate is outside the team's range. Score = gap in half-range widths."""
    if not r or not league or r.get("p") is None or league.get("p") is None or r.get("small_sample"):
        return None
    if r["lo"] <= league["p"] <= r["hi"]:
        return None
    half = max((r["hi"] - r["lo"]) / 2, 1e-6)
    return abs(r["p"] - league["p"]) / half


def _finding(fid, metric, title, headline, prepare, team, league, score):
    return dict(id=fid, metric=metric, title=title, headline=headline, prepare=prepare,
                team=team["p"], league=league["p"], n=team["n"], lo=team["lo"], hi=team["hi"],
                score=score, evidence={"metric": metric, "label": "Show the rounds"})


def findings_att_executes(r):
    out = []
    for b in r.get("breakdown", []):
        tm, lg = b.get("rate"), b.get("league")
        s = vs_league(tm, lg)
        if s is None:
            continue
        site = b.get("site", "site")
        prep = (f"Expect {site}: they go there more than most teams." if tm["p"] > lg["p"]
                else f"{site} is rare for them: they mostly go elsewhere.")
        out.append(_finding(
            f"att.executes.{site}", "att.executes", "Site choice",
            f"They plant on {site} in {pct(tm['p'])} of attack rounds (likely {pct(tm['lo'])}-{pct(tm['hi'])}), league {pct(lg['p'])}.", prep, tm, lg, s
        ))
    return out


def findings_recon(r):
    out = []
    v = r.get("value", {})
    early = v.get("before_league_median")
    s = vs_league(early, {"p": 0.5})
    if s is not None:
        prep = ("Plan for an early dart: their timing is built on it."
                if early["p"] > 0.5 else "Their first recon comes late: early pressure meets them before their info.")
        out.append(_finding(
            "util.recon_timing.before", "util.recon_timing", "Recon timing",
            f"Their first recon comes before the league's median time in {pct(early['p'])} of rounds (likely {pct(early['lo'])}-{pct(early['hi'])}), against half for the league.",
            prep, early, {"p": 0.5}, s,
        ))
    late, on = v.get("late"), v.get("on_time")
    if late and on and late.get("p") is not None and on.get("p") is not None and late.get("hi") is not None and on.get("lo") is not None:
        if late["lo"] > on["hi"] or late["hi"] < on["lo"]:
            hw = max((((late["hi"] - late["lo"]) / 2) + ((on["hi"] - on["lo"]) / 2)) / 2, 1e-6)
            sc = abs(late["p"] - on["p"]) / hw
            out.append(_finding(
                "util.recon_timing.late", "util.recon_timing", "When recon comes late",
                f"When their first recon comes late they win {pct(late['p'])} (likely {pct(late['lo'])}-{pct(late['hi'])}), against {pct(on['p'])} on time.",
                "Deny or delay their first recon." if late["p"] < on["p"] else "", late, on, sc,
            ))
    return [f for f in out if f["prepare"]]


def findings_dry_duels(r):
    out = []
    v = r.get("value", {})
    if v.get("beyond_noise") and v.get("diff") is not None:
        half = max((v["hi"] - v["lo"]) / 2, 1e-6)
        sc = abs(v["diff"]) / half
        more = v["diff"] > 0
        out.append(dict(
            id="fights.dry_duels.overall", metric="fights.dry_duels", title="Dry duels",
            headline=f"With no utility around they win {abs(v['diff']) * 100:.1f} points {'more' if more else 'fewer'} fights than the opener advantage predicts (likely {v['lo'] * 100:.1f} to {v['hi'] * 100:.1f}).",
            prepare="Don't take even dry duels: use utility first." if more else "Their players lose dry duels: take the fight without utility.",
            team=v["diff"], league=0.0, n=v["n"], lo=v["lo"], hi=v["hi"], score=sc, evidence={"metric": "fights.dry_duels", "label": "Show the rounds"}
        ))
    for b in r.get("breakdown", []):
        if b.get("bucket") == "agent" and b.get("beyond_noise"):
            half = max((b["hi"] - b["lo"]) / 2, 1e-6)
            sc = abs(b["diff"]) / half
            more = b["diff"] > 0
            out.append(dict(
                id=f"fights.dry_duels.{b['agent']}", metric="fights.dry_duels", title=f"Duels on {b['agent'].capitalize()}",
                headline=f"With no utility around they win {abs(b['diff']) * 100:.1f} points {'more' if more else 'fewer'} fights than the opener advantage predicts (likely {b['lo'] * 100:.1f} to {b['hi'] * 100:.1f}).",
                prepare="Don't take even dry duels: use utility first." if more else "Their players lose dry duels: take the fight without utility.",
                team=b["diff"], league=0.0, n=b["n"], lo=b["lo"], hi=b["hi"], score=sc, evidence={"metric": "fights.dry_duels", "label": "Show the rounds"}
            ))
    return out


def findings_predictability(r):
    out = []
    for b in r.get("breakdown", []):
        if b.get("percentile", 0) < 80 or b.get("small_sample"):
            continue
        rt = b.get("rate")
        lg = {"p": b.get("league_median")}
        s = vs_league(rt, lg)
        if s is None:
            continue
        out.append(_finding(
            f"team.predictability.{b['habit']}", "team.predictability", f"Predictable: {b['label']}",
            f"{b['label']}: they pick {b['choice']} in {pct(rt['p'])} of rounds (likely {pct(rt['lo'])}-{pct(rt['hi'])}), more predictable than {b['percentile']}% of teams.",
            f"Prepare for {b['choice']}.", rt, lg, s
        ))
    return out


def summarize(results: dict, side: str | None, k: int = 5) -> tuple[list[dict], str | None]:
    items = []
    if "att.executes" in results:
        items += findings_att_executes(results["att.executes"])
    if "util.recon_timing" in results:
        items += findings_recon(results["util.recon_timing"])
    if "fights.dry_duels" in results:
        items += findings_dry_duels(results["fights.dry_duels"])
    if "team.predictability" in results:
        items += findings_predictability(results["team.predictability"])
    if not items:
        return [], NO_FINDINGS_NOTE
    rank = {m: i for i, m in enumerate(ORDER)}
    items.sort(key=lambda x: (-x["score"], rank.get(x["metric"], 99), x["id"]))
    picked, seen = [], {}
    for it in items:
        if len(picked) >= k:
            break
        if seen.get(it["metric"], 0) >= 2:
            continue
        picked.append(it)
        seen[it["metric"]] = seen.get(it["metric"], 0) + 1
    return picked, None
