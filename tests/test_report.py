from engine.report import summarize, NO_FINDINGS_NOTE


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
