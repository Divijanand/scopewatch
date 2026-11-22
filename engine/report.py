"""Step 5d: the "Prepare for these" summary. Turns metric results into at most five findings that are
beyond noise against the league, each with a headline (team number, range, league number) and a prepare line."""
from __future__ import annotations

NO_FINDINGS_NOTE = "Nothing stands out beyond noise on this map and side: they play close to the league average."
ORDER = ["att.executes", "util.recon_timing", "team.retakes", "team.post_plant", "team.economy", "team.openings", "op.wpa", "fights.dry_duels", "team.predictability", "team.closing"]


def pct(x: float) -> str:
    return f"{round(x * 100)}%"


def _signed(x: float) -> str:
    """+6.0 / −3.2 with a real minus sign, as the cards print points."""
    return f"{'+' if x > 0 else '−' if x < 0 else ''}{abs(x):.1f}"


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
                score=score, unit="rate", evidence={"metric": metric, "label": "Show the rounds"})


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
            f"They plant on {site} in {pct(tm['p'])} of attack rounds (likely {pct(tm['lo'])}–{pct(tm['hi'])}), league {pct(lg['p'])}.", prep, tm, lg, s
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
            f"Their first recon comes before the league's median time in {pct(early['p'])} of rounds (likely {pct(early['lo'])}–{pct(early['hi'])}), against half for the league.",
            prep, early, {"p": 0.5}, s,
        ))
    late, on = v.get("late"), v.get("on_time")
    if (late and on and late.get("p") is not None and on.get("p") is not None
            and not late.get("small_sample") and not on.get("small_sample")):
        if late["lo"] > on["hi"] or late["hi"] < on["lo"]:
            hw = max((((late["hi"] - late["lo"]) / 2) + ((on["hi"] - on["lo"]) / 2)) / 2, 1e-6)
            sc = abs(late["p"] - on["p"]) / hw
            out.append(_finding(
                "util.recon_timing.late", "util.recon_timing", "When recon comes late",
                f"When their first recon comes late they win {pct(late['p'])} (likely {pct(late['lo'])}–{pct(late['hi'])}), against {pct(on['p'])} on time.",
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
            headline=f"With no utility around they win {abs(v['diff']) * 100:.1f} points {'more' if more else 'fewer'} fights than the opener advantage predicts (likely {_signed(v['lo'] * 100)} to {_signed(v['hi'] * 100)} points).",
            prepare="Don't take even dry duels: use utility first." if more else "Their players lose dry duels: take the fight without utility.",
            team=v["diff"], league=0.0, n=v["n"], lo=v["lo"], hi=v["hi"], score=sc, unit="diff", evidence={"metric": "fights.dry_duels", "label": "Show the rounds"}
        ))
    for b in r.get("breakdown", []):
        if b.get("bucket") == "agent" and b.get("beyond_noise"):
            half = max((b["hi"] - b["lo"]) / 2, 1e-6)
            sc = abs(b["diff"]) / half
            more = b["diff"] > 0
            out.append(dict(
                id=f"fights.dry_duels.{b['agent']}", metric="fights.dry_duels", title=f"Duels on {b['agent'].capitalize()}",
                headline=f"With no utility around they win {abs(b['diff']) * 100:.1f} points {'more' if more else 'fewer'} fights than the opener advantage predicts (likely {_signed(b['lo'] * 100)} to {_signed(b['hi'] * 100)} points).",
                prepare="Don't take even dry duels: use utility first." if more else "Their players lose dry duels: take the fight without utility.",
                team=b["diff"], league=0.0, n=b["n"], lo=b["lo"], hi=b["hi"], score=sc, unit="diff", evidence={"metric": "fights.dry_duels", "label": "Show the rounds"}
            ))
    return out


def findings_predictability(r):
    out = []
    for b in r.get("breakdown", []):
        if (b.get("percentile") or 0) < 80 or b.get("small_sample"):   # None when the league has too few teams
            continue
        rt = b.get("rate")
        lg = {"p": b.get("league_median")}
        s = vs_league(rt, lg)
        if s is None:
            continue
        out.append(_finding(
            f"team.predictability.{b['habit']}", "team.predictability", f"Predictable: {b['label']}",
            f"{b['label']}: they pick {b['choice']} in {pct(rt['p'])} of rounds (likely {pct(rt['lo'])}–{pct(rt['hi'])}), more predictable than {b['percentile']}% of teams.",
            f"Prepare for {b['choice']}.", rt, lg, s
        ))
    return out


def _compare(fid, metric, title, tm, lg, headline, higher, lower):
    """One team-vs-league rate finding. `headline(X, lo, hi, Y)` gets formatted percentages; `higher` and
    `lower` are the prepare lines for each direction (None = no finding in that direction)."""
    s = vs_league(tm, lg)
    if s is None:
        return []
    prep = higher if tm["p"] > lg["p"] else lower
    if not prep:
        return []
    return [_finding(fid, metric, title, headline(pct(tm["p"]), pct(tm["lo"]), pct(tm["hi"]), pct(lg["p"])),
                     prep, tm, lg, s)]


def findings_wpa(r):
    v = r.get("value") or {}
    if v.get("mean") is None or v.get("league_mean") is None or v.get("lo") is None or v.get("hi") is None:
        return []
    lm = v["league_mean"]
    if v["lo"] <= lm <= v["hi"]:
        return []
    sc = abs(v["mean"] - lm) / max((v["hi"] - v["lo"]) / 2, 1e-6)
    higher = v["mean"] > lm
    return [dict(
        id="op.wpa", metric="op.wpa", title="Operator value",
        headline=f"An Operator round is worth {_signed(v['mean'])} points of round-win chance to them "
                 f"(likely {_signed(v['lo'])} to {_signed(v['hi'])}), league {_signed(lm)}.",
        prepare=("Their Operator is a real threat: plan to trade it or deny it." if higher
                 else "Their Operator costs them more than most: bait it."),
        team=v["mean"], league=lm, n=v.get("n"), lo=v["lo"], hi=v["hi"], score=sc, unit="points",
        evidence={"metric": "op.wpa", "label": "Show the rounds"})]


def findings_retakes(r):
    v = r.get("value") or {}
    m = "team.retakes"
    return (_compare("team.retakes.retake", m, "Retakes", v.get("retake"), v.get("league_retake"),
                     lambda x, a, b, y: f"They retake {x} of plants they face (likely {a}–{b}), league {y}.",
                     "Plant safely: they retake well.", "Get the plant down: they rarely retake.")
            + _compare("team.retakes.plants_faced", m, "Plants against them", v.get("plants_faced"),
                       v.get("league_plants_faced"),
                       lambda x, a, b, y: f"Attackers plant in {x} of their defence rounds (likely {a}–{b}), league {y}.",
                       "Their site holds break: the plant goes down.", None))


def findings_post_plant(r):
    v = r.get("value") or {}
    m = "team.post_plant"
    return (_compare("team.post_plant.win", m, "Post-plant", v.get("post_plant_win"), v.get("league_post_plant_win"),
                     lambda x, a, b, y: f"They win {x} after planting (likely {a}–{b}), league {y}.",
                     None, "Retake them: their post-plant is weak.")
            + _compare("team.post_plant.pre_plant_losses", m, "Where their attack fails", v.get("pre_plant_losses"),
                       v.get("league_pre_plant_losses"),
                       lambda x, a, b, y: f"{x} of their attack losses come with no plant (likely {a}–{b}), league {y}.",
                       "Hold the site entrance: their attack fails before the plant.", None))


ECO_LINES = {   # bucket: (headline words, prepare if higher, prepare if lower)
    "full_vs_full": ("full buys against full buys", None, None),
    "full_vs_anti": ("full buys against an eco or half", None,
                     "They drop anti-eco rounds more than most: a force buy can pay off."),
    "scrappy_vs_full": ("ecos and half buys against a full buy",
                        "Their ecos are dangerous: don't over-peek on anti-ecos.", None),
}


def findings_economy(r):
    v = r.get("value") or {}
    m = "team.economy"
    out = (_compare("team.economy.pistol", m, "Pistols", v.get("pistol"), v.get("league_pistol"),
                    lambda x, a, b, y: f"They win {x} of pistol rounds (likely {a}–{b}), league {y}.",
                    "Their pistol rounds are strong: have a plan for the bonus.", None)
           + _compare("team.economy.bonus", m, "Bonus rounds", v.get("bonus"), v.get("league_bonus"),
                      lambda x, a, b, y: f"After a pistol win they win {x} of bonus rounds (likely {a}–{b}), league {y}.",
                      None, "Their bonus rounds are weak: force buy after losing the pistol."))
    for b in r.get("breakdown") or []:
        words, hi, lo = ECO_LINES.get(b.get("bucket"), (None, None, None))
        if words:
            out += _compare(f"team.economy.{b['bucket']}", m, "Buy rounds", b.get("rate"), b.get("league"),
                            lambda x, a, c, y, w=words: f"On {w} they win {x} (likely {a}–{c}), league {y}.", hi, lo)
    return out


def findings_openings(r):
    v = r.get("value") or {}
    m = "team.openings"
    return (_compare("team.openings.first_blood", m, "First blood", v.get("first_blood"), v.get("league_first_blood"),
                     lambda x, a, b, y: f"They get first blood in {x} of rounds (likely {a}–{b}), league {y}.",
                     "Expect early aggression: they take first contact.", None)
            + _compare("team.openings.after_first_blood", m, "After first blood", v.get("win_after_first_blood"),
                       v.get("league_win_after_first_blood"),
                       lambda x, a, b, y: f"After getting first blood they win {x} of rounds (likely {a}–{b}), league {y}.",
                       None, "They don't convert first blood: stay calm after an early loss.")
            + _compare("team.openings.after_first_death", m, "After a first death", v.get("win_after_first_death"),
                       v.get("league_win_after_first_death"),
                       lambda x, a, b, y: f"After losing the first player they still win {x} of rounds (likely {a}–{b}), league {y}.",
                       "They come back from first deaths: don't relax after first blood.", None))


def findings_closing(r):
    v = r.get("value") or {}
    m = "team.closing"
    return (_compare("team.closing.comebacks", m, "Comebacks", v.get("comebacks"), v.get("league_comebacks"),
                     lambda x, a, b, y: f"From a win chance of 20% or lower they come back in {x} (likely {a}–{b}), league {y}.",
                     "Close rounds out: they come back.", None)
            + _compare("team.closing.throws", m, "Closing rounds", v.get("throws"), v.get("league_throws"),
                       lambda x, a, b, y: f"From 80% or higher they lose {x} (likely {a}–{b}), league {y}.",
                       "Keep pressure on: they let rounds slip.", None))


TEMPLATES = {
    "att.executes": findings_att_executes,
    "util.recon_timing": findings_recon,
    "team.retakes": findings_retakes,
    "team.post_plant": findings_post_plant,
    "team.economy": findings_economy,
    "team.openings": findings_openings,
    "op.wpa": findings_wpa,
    "fights.dry_duels": findings_dry_duels,
    "team.predictability": findings_predictability,
    "team.closing": findings_closing,
}


def summarize(results: dict, side: str | None, k: int = 5) -> tuple[list[dict], str | None]:
    items = []
    for mid, fn in TEMPLATES.items():
        r = results.get(mid)
        if r:
            items += fn(r)
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
