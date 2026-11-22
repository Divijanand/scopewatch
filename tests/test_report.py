from engine.report import summarize, NO_FINDINGS_NOTE, pct


def _rate(p, lo, hi, n=100, small=False):
    return {"k": int(round(p * n)), "n": n, "p": p, "lo": lo, "hi": hi, "small_sample": small}


def test_noise_gate_and_note():
    results = {
        "att.executes": {"breakdown": [{"site": "A", "rate": _rate(0.50, 0.45, 0.55), "league": _rate(0.52, 0.48, 0.56)}]}
    }
    out, note = summarize(results, "attacker")
    assert out == []
    assert note == NO_FINDINGS_NOTE


def test_outside_noise_produces_finding_and_headline_has_team_and_league():
    results = {
        "att.executes": {"breakdown": [{"site": "A", "rate": _rate(0.70, 0.62, 0.78), "league": _rate(0.50, 0.45, 0.55)}]}
    }
    out, note = summarize(results, "attacker")
    assert note is None
    assert len(out) == 1
    assert "70%" in out[0]["headline"]
    assert "50%" in out[0]["headline"]


def test_caps_and_ordering():
    results = {
        "att.executes": {"breakdown": [
            {"site": "A", "rate": _rate(0.70, 0.62, 0.78), "league": _rate(0.45, 0.40, 0.50)},
            {"site": "B", "rate": _rate(0.68, 0.61, 0.75), "league": _rate(0.40, 0.36, 0.44)},
            {"site": "C", "rate": _rate(0.65, 0.58, 0.72), "league": _rate(0.35, 0.31, 0.39)},
        ]},
        "util.recon_timing": {"value": {
            "before_league_median": _rate(0.70, 0.62, 0.78),
            "late": _rate(0.30, 0.23, 0.38),
            "on_time": _rate(0.58, 0.51, 0.65),
        }},
        "team.predictability": {"breakdown": [
            {"habit": "h", "label": "Early A", "choice": "A", "percentile": 85, "small_sample": False,
             "rate": _rate(0.72, 0.64, 0.80), "league_median": 0.50}
        ]},
    }
    out, _ = summarize(results, "attacker")
    assert len(out) == 5
    assert sum(1 for x in out if x["metric"] == "att.executes") == 2


def test_language_bans_absent_in_templates():
    results = {
        "att.executes": {"breakdown": [{"site": "A", "rate": _rate(0.70, 0.62, 0.78), "league": _rate(0.50, 0.45, 0.55)}]},
        "util.recon_timing": {"value": {"before_league_median": _rate(0.70, 0.62, 0.78)}},
        "fights.dry_duels": {"value": {"n": 200, "diff": 0.08, "lo": 0.02, "hi": 0.14, "beyond_noise": True}},
        "team.predictability": {"breakdown": [{"habit": "h", "label": "Early A", "choice": "A", "percentile": 85,
                                                   "small_sample": False, "rate": _rate(0.72, 0.64, 0.80), "league_median": 0.50}]},
    }
    out, _ = summarize(results, "attacker")
    bad = ("caused", "always", "exact", "fault")
    for f in out:
        low = (f["headline"] + " " + f["prepare"]).lower()
        assert all(w not in low for w in bad)


HI, LG = _rate(0.70, 0.62, 0.78), _rate(0.50, 0.45, 0.55)      # beyond noise, team above the league
LO = _rate(0.30, 0.22, 0.38)                                     # beyond noise, team below the league


def _pair(**keys):
    v = {}
    for k, r in keys.items():
        v[k], v[f"league_{k}"] = r, LG
    return {"value": v, "breakdown": []}


ALL = {
    "att.executes": {"value": {}, "breakdown": [{"site": "A", "rate": HI, "league": LG}]},
    "util.recon_timing": {"value": {"before_league_median": HI, "late": _rate(0.30, 0.23, 0.38),
                                    "on_time": _rate(0.58, 0.51, 0.65)}},
    "fights.dry_duels": {"value": {"n": 200, "diff": 0.08, "lo": 0.02, "hi": 0.14, "beyond_noise": True},
                         "breakdown": [{"bucket": "agent", "agent": "jett", "n": 90, "diff": -0.1, "lo": -0.18,
                                        "hi": -0.02, "beyond_noise": True}]},
    "team.predictability": {"value": {}, "breakdown": [{"habit": "h", "label": "Early A", "choice": "A", "percentile": 85,
                                                        "small_sample": False, "rate": HI, "league_median": 0.50}]},
    "op.wpa": {"value": {"n": 80, "mean": 6.0, "lo": 2.0, "hi": 10.0, "league_mean": 0.5}},
    "team.retakes": _pair(retake=LO, plants_faced=HI),
    "team.post_plant": _pair(post_plant_win=LO, pre_plant_losses=HI),
    "team.economy": {"value": {"pistol": HI, "league_pistol": LG, "bonus": LO, "league_bonus": LG},
                     "breakdown": [{"bucket": "scrappy_vs_full", "rate": HI, "league": LG},
                                   {"bucket": "full_vs_anti", "rate": LO, "league": LG}]},
    "team.openings": _pair(first_blood=HI, win_after_first_blood=LO, win_after_first_death=HI),
    "team.closing": _pair(comebacks=HI, throws=HI),
}


def _every_finding():
    from engine.report import TEMPLATES
    return [f for mid, fn in TEMPLATES.items() for f in fn(ALL[mid])]


def test_every_template_fires_once_per_direction_with_a_prepare_line():
    ids = {f["id"] for f in _every_finding()}
    assert ids == {
        "att.executes.A", "util.recon_timing.before", "util.recon_timing.late", "fights.dry_duels.overall",
        "fights.dry_duels.jett", "team.predictability.h", "op.wpa", "team.retakes.retake",
        "team.retakes.plants_faced", "team.post_plant.win", "team.post_plant.pre_plant_losses",
        "team.economy.pistol", "team.economy.bonus", "team.economy.scrappy_vs_full", "team.economy.full_vs_anti",
        "team.openings.first_blood", "team.openings.after_first_blood", "team.openings.after_first_death",
        "team.closing.comebacks", "team.closing.throws",
    }


def test_every_template_avoids_banned_words_and_shows_both_numbers():
    for f in _every_finding():
        text = (f["headline"] + " " + f["prepare"]).lower()
        assert f["prepare"]
        assert not any(w in text for w in ("caused", "always", "exact", "fault")), f["id"]
        assert "likely" in text, f["id"]
        if f["metric"] == "op.wpa":
            assert "+6.0" in f["headline"] and "+0.5" in f["headline"]
        elif f["id"] == "util.recon_timing.before":
            assert "70%" in f["headline"] and "half for the league" in f["headline"]
        elif f["id"] == "util.recon_timing.late":
            assert "30%" in f["headline"] and "58%" in f["headline"]
        elif f["metric"] not in ("fights.dry_duels", "team.predictability"):
            assert pct(f["team"]) in f["headline"] and pct(f["league"]) in f["headline"], f["id"]


def test_direction_without_a_prepare_line_gives_nothing():
    out, note = summarize({"team.post_plant": _pair(post_plant_win=HI, pre_plant_losses=LO)}, "attacker")
    assert out == [] and note == NO_FINDINGS_NOTE


def test_wpa_inside_range_is_noise():
    out, _ = summarize({"op.wpa": {"value": {"n": 80, "mean": 2.0, "lo": -1.0, "hi": 5.0, "league_mean": 0.5}}}, "attacker")
    assert out == []


def test_ties_break_by_metric_order():
    same = {"team.closing": _pair(comebacks=HI), "att.executes": ALL["att.executes"],
            "team.openings": _pair(first_blood=HI)}
    out, _ = summarize(same, "attacker")
    assert [f["metric"] for f in out] == ["att.executes", "team.openings", "team.closing"]


def test_at_most_five_and_two_per_metric_over_everything():
    out, _ = summarize(ALL, "attacker")
    assert len(out) == 5
    assert max(sum(1 for f in out if f["metric"] == m) for m in {f["metric"] for f in out}) <= 2
    assert [f["score"] for f in out] == sorted((f["score"] for f in out), reverse=True)


def test_habit_without_a_league_percentile_is_skipped_not_a_crash():
    r = {"team.predictability": {"value": {}, "breakdown": [{"habit": "h", "label": "x", "choice": "A", "percentile": None,
                                                             "small_sample": False, "rate": HI, "league_median": None}]}}
    assert summarize(r, "attacker") == ([], NO_FINDINGS_NOTE)


def test_every_finding_says_its_unit():
    units = {f["id"]: f["unit"] for f in _every_finding()}
    assert units["op.wpa"] == "points"
    assert units["fights.dry_duels.overall"] == units["fights.dry_duels.jett"] == "diff"
    assert {u for i, u in units.items() if not i.startswith(("op.", "fights."))} == {"rate"}
