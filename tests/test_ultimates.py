"""Ultimates on hand-built rounds: uses, the 10 s window, win-chance swing, weapon ults seen on first hit."""
import duckdb
import pandas as pd
import pytest

from engine.metrics import REGISTRY, Filters
from engine.metrics import ultimates as ul

TS = pd.Timestamp("2030-01-01")


def kill(eid, rk, ts, att_team, vic_team, weapon="vandal", kind="kill", agent="fade", att="a1"):
    side = {"T1": "attacker", "T2": "defender"}
    return dict(event_id=eid, round_key=rk, series_id="S1", ts_ms=ts, t_round=ts / 1000, kind=kind, weapon=weapon,
                phase="pre_plant", att_id=att, att_team=att_team, att_side=side[att_team], att_agent=agent,
                att_x=0.0, att_y=0.0, vic_team=vic_team, map="testmap", started_at=TS)


@pytest.fixture
def con(tmp_path, monkeypatch):
    c = duckdb.connect()
    casts = pd.DataFrame([dict(round_key="G:1", series_id="S1", team_id="T1", side="attacker", ability="nightfall",
                               agent="fade", player_id="a1", ts_ms=10_000, t_round=10.0, phase="pre_plant",
                               spatial_ok=True, x=0.0, y=0.0, map="testmap", started_at=TS)])
    c.execute("CREATE TABLE casts AS SELECT * FROM casts")
    eng = pd.DataFrame([
        kill("k1", "G:1", 12_000, "T1", "T2"),                      # in the window: a kill for
        kill("k2", "G:1", 15_000, "T2", "T1", agent="sova"),        # in the window: a death
        kill("k3", "G:1", 25_000, "T1", "T2"),                      # after the window: ignored
        kill("d4", "G:2", 30_000, "T1", "T2", weapon="blade-storm", kind="damage", agent="jett", att="a2"),
    ])
    c.execute("CREATE TABLE engagements AS SELECT * FROM eng")
    c.execute("CREATE TABLE rounds AS SELECT * FROM (VALUES ('G:1', 'T2'), ('G:2', 'T1')) t(round_key, winner_team_id)")
    pr = pd.DataFrame([dict(round_key=rk, player_id=pid, player_name=pid.upper(), team_id="T1", map="testmap",
                            side="attacker", agent=ag, started_at=TS)
                       for rk, pid, ag in [("G:1", "a1", "fade"), ("G:2", "a1", "fade"), ("G:2", "a2", "jett")]])
    c.execute("CREATE TABLE player_rounds AS SELECT * FROM pr")
    wp = tmp_path / "event_wp.parquet"
    pd.DataFrame([dict(event_id="k1", wp_before=0.5, wp_after=0.6), dict(event_id="k2", wp_before=0.6, wp_after=0.4),
                  dict(event_id="k3", wp_before=0.4, wp_after=0.5)]).to_parquet(wp)
    monkeypatch.setattr(ul, "EVENT_WP", wp)
    ul._LEAGUE_CACHE.clear()
    return c


F = Filters(team_id="T1", map="testmap", side="attacker")


def test_ult_window_and_swing(con):
    d, fn = REGISTRY["ult.usage"]
    r = fn(con, F)
    by = {b["ability"]: b for b in r.breakdown}
    nf = by["nightfall"]
    assert (nf["rate"].k, nf["rate"].n) == (1, 2)          # used in 1 of the 2 rounds they played Fade
    assert (nf["kills"], nf["deaths"]) == (1, 1)           # the kill at 25 s is outside the 10 s window
    assert nf["swing"] == pytest.approx(-10.0)             # +10 for the kill, -20 for the death, attacker side
    assert nf["league_swing"] == pytest.approx(-10.0)
    assert nf["won"].k == 0
    assert nf["swing_lo"] is None                          # fewer than 10 uses: no range


def test_weapon_ults_are_seen_on_their_first_hit(con):
    d, fn = REGISTRY["ult.usage"]
    bs = {b["ability"]: b for b in fn(con, F).breakdown}["blade-storm"]
    assert bs["seen_only_on_hit"] and (bs["rate"].k, bs["rate"].n) == (1, 1) and bs["agent"] == "jett"


def test_needs_map_and_side(con):
    d, fn = REGISTRY["ult.usage"]
    assert fn(con, Filters(team_id="T1")).warnings
