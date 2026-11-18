"""Reducer behaviour on synthetic feeds with hand-computed expected results."""
import pytest

from engine.ingest.reducer import SeriesReducer
from tests.synth import Feed, cast


def run(feed, casts=()):
    r = SeriesReducer(feed.sid)
    for env in feed.envs:
        r.feed(env)
    r.add_casts(list(casts))
    return r, r.finish()


@pytest.fixture
def basic():
    f = Feed()
    a = f.add_player("TA", "pA", "atk1", x=-900, y=0, items=("classic", "operator"))
    d = f.add_player("TD", "pD", "def1", x=900, y=0)
    f.start_game(0)
    f.start_round(1, 1)
    f.start_buy(1, 1)
    f.end_buy(31, 1)          # buy phase ends at t=31s -> round clock zero
    return f, a, d


def test_round_clock_starts_at_buy_phase_end(basic):
    f, a, d = basic
    f.damage(36, a, d)        # 5s after buy end
    f.kill(41.5, a, d, weapon="operator")
    f.win_round(42, 1, "TA")
    _, out = run(f)
    e = sorted(out["engagements"], key=lambda r: r["ts_ms"])
    assert [r["t_round"] for r in e] == [5.0, 10.5]
    assert e[1]["weapon"] == "operator" and e[1]["kind"] == "kill"
    assert all(r["phase"] == "pre_plant" for r in e)
    assert out["rounds"][0]["winner_team_id"] == "TA"


def test_reversed_kill_is_voided_and_counted(basic):
    f, a, d = basic
    k = f.kill(40, a, d)
    f.reverse(40.1, k)
    f.kill(45, a, d, weapon="sheriff")
    r, out = run(f)
    kills = [x for x in out["engagements"] if x["kind"] == "kill"]
    assert [x["weapon"] for x in kills] == ["sheriff"]
    assert r.counts["reversals_lifo"] == 1
    assert r.counts["rows_voided.engagements"] == 1


def test_round_rollback_restores_state_and_drops_round(basic):
    """GRID unwinds a restarted round in reverse order; nothing from the first attempt survives."""
    f, a, d = basic
    w = f.win_round(40, 1, "TA")
    eb2 = None
    f.reverse(50, w)
    # unwind round 1 completely, then replay it
    f.reverse(50, f.envs[3]["events"][0])   # round-ended-freezetime
    f.reverse(50, f.envs[2]["events"][0])   # round-started-freezetime
    f.reverse(50, f.envs[1]["events"][0])   # game-started-round
    f.start_round(60, 1)
    f.start_buy(60, 1)
    eb2 = f.end_buy(90, 1)
    f.kill(95, a, d)
    f.win_round(96, 1, "TD")
    r, out = run(f)
    assert len(out["rounds"]) == 1 and out["rounds"][0]["winner_team_id"] == "TD"
    assert len(out["round_clock"]) == 1
    assert len(out["player_rounds"]) == 2           # one attempt x two players
    kill = out["engagements"][0]
    assert kill["t_round"] == 5.0                    # measured from the replayed buy-phase end
    assert r.counts["reversals_lifo"] == 4 and r.counts.get("reversals_non_lifo", 0) == 0


def test_invalidation_marker_does_not_break_lifo_unwind(basic):
    """GRID emits grid-invalidated-series right before unwinding; the unwind must still restore state."""
    f, a, d = basic
    w = f.win_round(40, 1, "TA")
    f.ev(50, "grid-invalidated-series", {"type": "grid", "id": "g"}, {"type": "series", "id": "S1"})
    f.reverse(50, w)
    f.reverse(50, f.envs[3]["events"][0])   # round-ended-freezetime
    r, _ = run(f)
    assert r.counts["reversals_lifo"] == 2 and r.counts.get("reversals_non_lifo", 0) == 0
    assert r.state.freeze_end_ms is None    # restored to before the buy-phase end


def test_reversed_marker_is_not_an_unmatched_reversal(basic):
    f, a, d = basic
    m = f.ev(50, "grid-validated-series", {"type": "grid", "id": "g"}, {"type": "series", "id": "S1"})
    f.reverse(51, m)
    r, _ = run(f)
    assert r.counts.get("reversals_unmatched", 0) == 0
    assert r.counts["markers_reversed.grid-!validated-series"] == 1


def test_unmatched_reversal_is_counted_not_guessed(basic):
    f, a, d = basic
    f.ev(40, "player-!killed-player", {"type": "player", "id": "ghost"}, {"type": "player", "id": "pD"})
    r, _ = run(f)
    assert r.counts["reversals_unmatched"] == 1


def test_plant_splits_phases_and_plant_clock(basic):
    f, a, d = basic
    f.damage(40, a, d)
    f.plant(50, a)
    f.kill(62, d, a)
    _, out = run(f)
    e = sorted(out["engagements"], key=lambda r: r["ts_ms"])
    assert [x["phase"] for x in e] == ["pre_plant", "post_plant"]
    assert e[1]["t_plant"] == 12.0 and e[0]["t_plant"] is None
    assert out["objectives"][0]["kind"] == "plant" and out["objectives"][0]["t_round"] == 19.0


def test_kill_after_round_result_is_post_round(basic):
    f, a, d = basic
    f.win_round(40, 1, "TA")
    f.kill(42, a, d)
    _, out = run(f)
    assert out["engagements"][0]["phase"] == "post_round"


def test_event_during_buy_phase_has_negative_clock_and_buy_phase():
    f = Feed()
    a = f.add_player("TA", "pA", "atk1")
    d = f.add_player("TD", "pD", "def1")
    f.start_game(0)
    f.start_round(1, 1)
    f.start_buy(1, 1)
    f.damage(10, a, d)   # before any buy-phase end
    _, out = run(f)
    assert out["engagements"][0]["t_round"] is None and out["engagements"][0]["phase"] == "buy"


def test_side_swap_is_read_from_state_each_round(basic):
    f, a, d = basic
    f.win_round(40, 1, "TA")
    f.swap_sides()
    f.start_round(50, 13)
    f.start_buy(50, 13)
    f.end_buy(80, 13)
    _, out = run(f)
    sides = {(r["round_no"], r["player_id"]): r["side"] for r in out["player_rounds"]}
    assert sides[(1, "pA")] == "attacker" and sides[(13, "pA")] == "defender"


def test_possession_is_inventory_at_cutoff(basic):
    f, a, d = basic
    _, out = run(f)
    items = {r["player_id"]: r["items"].split("|") for r in out["player_rounds"]}
    assert "operator" in items["pA"] and "operator" not in items["pD"]


def test_position_repeat_flag():
    f = Feed()
    a = f.add_player("TA", "pA", "atk1")
    d = f.add_player("TD", "pD", "def1")
    f.start_game(0); f.start_round(1, 1); f.start_buy(1, 1); f.end_buy(31, 1)
    f.damage(35, a, d, att_xy=(10, 10), vic_xy=(500, 0))
    f.damage(36, a, d, att_xy=(10, 10), vic_xy=(510, 0))
    _, out = run(f)
    e = sorted(out["engagements"], key=lambda r: r["ts_ms"])
    assert e[0]["att_pos_repeat"] is False and e[1]["att_pos_repeat"] is True
    assert e[1]["vic_pos_repeat"] is False


def test_casts_join_rounds_and_apply_quality_policy(basic):
    f, a, d = basic
    used = f.use_ability(36, a)
    rev = f.use_ability(37, a)
    f.reverse(37.5, rev)
    f.win_round(40, 1, "TA")
    casts = [
        cast("S1", "G1", 36, "pA", grid_event_id=used["id"]),                                 # ok
        cast("S1", "G1", 37, "pA", grid_event_id=rev["id"]),                                  # reversed in GRID
        cast("S1", "G1", 38, "pA", quality="gap_exceeded", offsets=(-50, 900)),               # use closer frame
        cast("S1", "G1", 38.5, "pA", quality="missing_both", offsets=(None, None)),           # no geometry
        cast("S1", "G1", 20, "pA"),                                                           # buy phase
    ]
    r, out = run(f, casts)
    c = sorted(out["casts"], key=lambda r: r["ts_ms"])
    assert len(c) == 4 and r.counts["casts_excluded.reversed_in_grid"] == 1
    buy, ok, gap, none = c
    assert buy["phase"] == "buy" and buy["t_round"] == -11.0
    assert ok["spatial_ok"] and ok["pos_source"] == "interpolated" and ok["t_round"] == 5.0
    assert ok["agent"] == "sentinel-a" and ok["side"] == "attacker"
    assert gap["pos_source"] == "frame_before" and gap["pos_dt_ms"] == 50 and gap["spatial_ok"]
    assert none["x"] is None and not none["spatial_ok"]          # kept for counts, not for maps
    assert r.counts["casts_no_geometry"] == 1


def test_same_display_name_different_team_ids_stay_separate():
    f = Feed()
    f.teams["TD"]["name"] = "Alpha"   # two teams both called Alpha
    a = f.add_player("TA", "pA", "x")
    d = f.add_player("TD", "pD", "y")
    f.start_game(0); f.start_round(1, 1); f.start_buy(1, 1); f.end_buy(31, 1)
    _, out = run(f)
    assert {r["team_id"] for r in out["player_rounds"]} == {"TA", "TD"}
