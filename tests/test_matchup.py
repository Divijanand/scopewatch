import duckdb
import pytest

from engine.matchup import stance, read, facing_pairs, head_to_head


def _rate(p, lo, hi, n=400, small_sample=False):
    return {"p": p, "lo": lo, "hi": hi, "n": n, "small_sample": small_sample}


def test_stance_cases():
    assert stance(_rate(0.55, 0.50, 0.60), {"p": 0.57}) == 0
    assert stance(_rate(0.65, 0.61, 0.70), {"p": 0.50}) == 1
    assert stance(_rate(0.20, 0.15, 0.25), {"p": 0.35}, higher_is_better=False) == 1
    assert stance(_rate(0.65, 0.61, 0.70), {"p": 0.50}, higher_is_better=False) == -1
    assert stance(_rate(0.65, 0.61, 0.70, n=19), {"p": 0.50}) is None


def test_read_cases():
    assert read(+1, 0) == "attacker"
    assert read(0, -1) == "attacker"
    assert read(+1, +1) == "even"
    assert read(None, +1) == "too_few"


def test_pairs_mirroring_and_plant_reach_direction():
    a_att = {
        "team.post_plant": {"value": {
            "plant_share": _rate(0.62, 0.57, 0.67),
            "league_plant_share": {"p": 0.50},
            "post_plant_win": _rate(0.72, 0.66, 0.78),
            "league_post_plant_win": {"p": 0.60},
        }},
        "team.openings": {"value": {"first_blood": _rate(0.56, 0.52, 0.60), "league_first_blood": {"p": 0.50}}},
        "fights.dry_duels": {"value": {"diff": 0.06, "lo": 0.02, "hi": 0.10, "n": 55, "beyond_noise": True, "p_value": 0.001}},
        "team.economy": {"breakdown": [
            {"bucket": "scrappy_vs_full", "rate": _rate(0.30, 0.24, 0.36), "league": {"p": 0.22}}
        ]},
        "summary": [{"id": "a1", "score": 2.0}],
    }
    a_def = {
        "team.retakes": {"value": {
            "plants_faced": _rate(0.38, 0.32, 0.44),
            "league_plants_faced": {"p": 0.50},
            "retake": _rate(0.48, 0.41, 0.55),
            "league_retake": {"p": 0.50},
        }},
        "team.openings": {"value": {"first_blood": _rate(0.44, 0.40, 0.48), "league_first_blood": {"p": 0.50}}},
        "fights.dry_duels": {"value": {"diff": -0.01, "lo": -0.05, "hi": 0.03, "n": 40, "beyond_noise": False, "p_value": 0.5}},
        "team.economy": {"breakdown": [{"bucket": "full_vs_anti", "rate": _rate(0.70, 0.64, 0.76), "league": {"p": 0.66}}]},
        "summary": [{"id": "a2", "score": 1.0}],
    }
    b_att = {
        "team.post_plant": {"value": {
            "plant_share": _rate(0.48, 0.42, 0.54),
            "league_plant_share": {"p": 0.50},
            "post_plant_win": _rate(0.52, 0.46, 0.58),
            "league_post_plant_win": {"p": 0.60},
        }},
        "team.openings": {"value": {"first_blood": _rate(0.50, 0.45, 0.55), "league_first_blood": {"p": 0.50}}},
        "fights.dry_duels": {"value": {"diff": 0.00, "lo": -0.03, "hi": 0.03, "n": 44, "beyond_noise": False, "p_value": 0.5}},
        "team.economy": {"breakdown": [{"bucket": "scrappy_vs_full", "rate": _rate(0.21, 0.17, 0.25), "league": {"p": 0.22}}]},
        "summary": [{"id": "b1", "score": 1.5}],
    }
    b_def = {
        "team.retakes": {"value": {
            "plants_faced": _rate(0.50, 0.45, 0.55),
            "league_plants_faced": {"p": 0.50},
            "retake": _rate(0.50, 0.45, 0.55),
            "league_retake": {"p": 0.50},
        }},
        "team.openings": {"value": {"first_blood": _rate(0.50, 0.45, 0.55), "league_first_blood": {"p": 0.50}}},
        "fights.dry_duels": {"value": {"diff": 0.00, "lo": -0.03, "hi": 0.03, "n": 44, "beyond_noise": False, "p_value": 0.5}},
        "team.economy": {"breakdown": [{"bucket": "full_vs_anti", "rate": _rate(0.66, 0.61, 0.71), "league": {"p": 0.66}}]},
        "summary": [{"id": "b2", "score": 1.2}],
    }

    pairs = facing_pairs("A", "Alpha", "B", "Bravo", a_att, a_def, b_att, b_def)
    assert len(pairs) == 10

    post = [p for p in pairs if p["id"] == "post_plant" and p["attacker"] == "A" and p["defender"] == "B"][0]
    assert post["read"] == "attacker"
    assert post["edge"] == "A"

    mirrored = [p for p in pairs if p["id"] == "post_plant" and p["attacker"] == "B" and p["defender"] == "A"][0]
    assert mirrored["attacker"] == "B"

    plant = [p for p in pairs if p["id"] == "plant_reach" and p["attacker"] == "B" and p["defender"] == "A"][0]
    assert plant["dfn"]["stance"] == 1


def test_missing_metric_yields_too_few_and_no_crash():
    pairs = facing_pairs("A", "Alpha", "B", "Bravo", {}, {}, {}, {})
    item = [p for p in pairs if p["id"] == "post_plant" and p["attacker"] == "A"][0]
    assert item["read"] == "too_few"
    assert item["att"]["p"] is None
    assert item["dfn"]["p"] is None


def test_head_to_head_newest_first_with_round_counts():
    con = duckdb.connect(":memory:")
    con.execute("""
        CREATE TABLE games (
            series_id VARCHAR, game_id VARCHAR, map VARCHAR, started_at TIMESTAMP,
            event VARCHAR, stage VARCHAR, winner_team_id VARCHAR, team1_id VARCHAR, team2_id VARCHAR
        )
    """)
    con.execute("CREATE TABLE team_rounds (game_id VARCHAR, team_id VARCHAR, won BOOLEAN)")

    con.execute("""
        INSERT INTO games VALUES
        ('s1','g1','ascent','2026-01-01 10:00:00','E1','S1','A','A','B'),
        ('s2','g2','haven','2026-02-01 10:00:00','E2','S2','B','B','A'),
        ('s3','g3','split','2026-03-01 10:00:00','E3','S3','C','A','C')
    """)
    con.execute("INSERT INTO team_rounds VALUES ('g1','A',true), ('g1','A',true), ('g1','B',true)")
    con.execute("INSERT INTO team_rounds VALUES ('g2','A',true), ('g2','B',true), ('g2','B',true)")

    out = head_to_head(con, "A", "B")
    assert [r["game_id"] for r in out] == ["g2", "g1"]
    assert out[0]["a_rounds"] == 1 and out[0]["b_rounds"] == 2
    assert out[1]["a_rounds"] == 2 and out[1]["b_rounds"] == 1


def test_endpoint_validation(monkeypatch):
    pytest.importorskip("httpx")   # TestClient needs it
    from fastapi.testclient import TestClient

    server = pytest.importorskip("api.server")
    client = TestClient(server.app)

    r = client.get("/api/matchup", params={"team_a": "A", "team_b": "A", "map": "ascent"})
    assert r.status_code == 422

    def fake_filters(team_id, map, side, since, until, player_id=None):
        if team_id == "missing":
            from fastapi import HTTPException
            raise HTTPException(404, "No rounds")
        return object()

    monkeypatch.setattr(server, "filters", fake_filters)
    r2 = client.get("/api/matchup", params={"team_a": "missing", "team_b": "B", "map": "ascent"})
    assert r2.status_code == 404


def test_sentences_avoid_banned_words():
    pairs = facing_pairs("A", "Alpha", "B", "Bravo", {}, {}, {}, {})
    bad = ("caused", "always", "exact", "fault")
    for p in pairs:
        s = p["sentence"].lower()
        assert not any(w in s for w in bad)


def test_head_to_head_date_filter_applies_to_both_orders():
    con = duckdb.connect(":memory:")
    con.execute("""CREATE TABLE games (series_id VARCHAR, game_id VARCHAR, map VARCHAR, started_at TIMESTAMP,
                   event VARCHAR, stage VARCHAR, winner_team_id VARCHAR, team1_id VARCHAR, team2_id VARCHAR)""")
    con.execute("CREATE TABLE team_rounds (game_id VARCHAR, team_id VARCHAR, won BOOLEAN)")
    con.execute("""INSERT INTO games VALUES
        ('s1','g1','ascent','2026-01-01','E','S','A','A','B'),
        ('s2','g2','haven','2026-01-02','E','S','B','B','A'),
        ('s3','g3','split','2026-03-01','E','S','A','A','B')""")
    out = head_to_head(con, "A", "B", since="2026-02-01")
    assert [r["game_id"] for r in out] == ["g3"]       # g1 (A first) and g2 (B first) are both before the date


def test_duel_sentence_uses_real_minus_and_no_negative_zero():
    d = {"fights.dry_duels": {"value": {"diff": -0.0004, "lo": -0.03, "hi": 0.03, "n": 40, "beyond_noise": False, "p_value": 0.5}}}
    a = {"fights.dry_duels": {"value": {"diff": -0.013, "lo": -0.05, "hi": 0.02, "n": 40, "beyond_noise": False, "p_value": 0.5}}}
    s = [p for p in facing_pairs("A", "Alpha", "B", "Bravo", a, {}, {}, d) if p["id"] == "dry_duels"][0]["sentence"]
    assert "−1.3" in s and "are 0.0" in s and "-" not in s


def test_a_stance_must_survive_every_check_in_the_matchup():
    # one measure with p of about 0.04 clears a 95% range alone, but not among 8 checks
    def side(p):
        return {"team.post_plant": {"value": {"plant_share": _rate(p, 0.51, 0.59), "league_plant_share": {"p": 0.5},
                                              "post_plant_win": _rate(0.5, 0.45, 0.55), "league_post_plant_win": {"p": 0.5}}},
                "team.openings": {"value": {"first_blood": _rate(0.5, 0.45, 0.55), "league_first_blood": {"p": 0.5}}}}
    dfn = {"team.retakes": {"value": {"plants_faced": _rate(0.5, 0.45, 0.55), "league_plants_faced": {"p": 0.5},
                                      "retake": _rate(0.5, 0.45, 0.55), "league_retake": {"p": 0.5}}}}
    weak = facing_pairs("A", "Alpha", "B", "Bravo", side(0.553), {}, {}, dfn)[0]
    strong = facing_pairs("A", "Alpha", "B", "Bravo", side(0.65), {}, {}, dfn)[0]
    assert stance(_rate(0.553, 0.51, 0.59), {"p": 0.5}) == 1
    assert weak["read"] == "even" and weak["att"]["stance"] == 0
    assert strong["read"] == "attacker" and strong["edge"] == "A"


def test_head_to_head_end_date_is_exclusive():
    con = duckdb.connect(":memory:")
    con.execute("""CREATE TABLE games (series_id VARCHAR, game_id VARCHAR, map VARCHAR, started_at TIMESTAMP,
                   event VARCHAR, stage VARCHAR, winner_team_id VARCHAR, team1_id VARCHAR, team2_id VARCHAR)""")
    con.execute("CREATE TABLE team_rounds (game_id VARCHAR, team_id VARCHAR, won BOOLEAN)")
    con.execute("INSERT INTO games VALUES ('s1','g1','ascent','2026-01-01','E','S','A','A','B'), "
                "('s2','g2','haven','2026-01-02','E','S','B','B','A')")
    assert [r["game_id"] for r in head_to_head(con, "A", "B", until="2026-01-02")] == ["g1"]
