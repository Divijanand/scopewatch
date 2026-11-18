"""Metric contracts on hand-built tables: n/N, unknowns and evidence must reconcile exactly."""
import duckdb
import pandas as pd
import pytest

from engine.metrics import REGISTRY, Filters, Rate

TS = pd.Timestamp("2030-01-01")


def tr(rk, team="T1", side="defender", economy="full", known=True, n_op=0, won=False, ops=None, game="G1"):
    return dict(round_key=rk, series_id="S1", game_id=game, map="testmap", round_no=int(rk.split(":")[1]),
                team_id=team, team_name="Alpha", side=side, economy=economy if known else None,
                team_loadout=20000, inventory_known=known, n_op=n_op, op_player_ids=ops or [],
                op_players=ops or [], op_agents=["a"] * len(ops or []), won=won, win_type="elimination_or_time",
                planted=False, patch="1.0", event="Test", started_at=TS)


@pytest.fixture
def con():
    c = duckdb.connect()
    team_rounds = pd.DataFrame([
        tr("G1:1", n_op=1, won=True, ops=["p1"]),
        tr("G1:2", n_op=1, won=False, ops=["p1"]),
        tr("G1:3", n_op=0, won=True),
        tr("G1:4", n_op=1, won=True, ops=["p2"]),
        tr("G1:5", economy="eco"),
        tr("G1:6", known=False),                  # no snapshot: unknown, not "no Operator"
        tr("G1:7", side="attacker", n_op=1, ops=["p1"]),
    ])
    c.execute("CREATE TABLE team_rounds AS SELECT * FROM team_rounds")
    pr = []
    for r in team_rounds.itertuples():
        if not r.inventory_known:
            continue
        for pid in ("p1", "p2"):
            pr.append(dict(round_key=r.round_key, game_id=r.game_id, map=r.map, team_id=r.team_id, side=r.side,
                           player_id=pid, player_name=pid.upper(), agent="a", has_op=pid in r.op_player_ids,
                           started_at=TS))
    player_rounds = pd.DataFrame(pr)
    c.execute("CREATE TABLE player_rounds AS SELECT * FROM player_rounds")
    eng = pd.DataFrame([
        # Operator kills by T1: t=5 (opening), t=25, t=70 post-plant; one vandal kill ignored; one buy-phase ignored
        dict(round_key="G1:1", event_id="k1", kind="kill", weapon="operator", t_round=5.0, t_plant=None,
             phase="pre_plant", opening_kill=True, att_id="p1", att_team="T1", att_side="defender"),
        dict(round_key="G1:2", event_id="k2", kind="kill", weapon="operator", t_round=25.0, t_plant=None,
             phase="pre_plant", opening_kill=False, att_id="p1", att_team="T1", att_side="defender"),
        dict(round_key="G1:4", event_id="k3", kind="kill", weapon="outlaw", t_round=70.0, t_plant=10.0,
             phase="post_plant", opening_kill=False, att_id="p2", att_team="T1", att_side="defender"),
        dict(round_key="G1:3", event_id="k4", kind="kill", weapon="vandal", t_round=8.0, t_plant=None,
             phase="pre_plant", opening_kill=True, att_id="p2", att_team="T1", att_side="defender"),
        dict(round_key="G1:1", event_id="k5", kind="kill", weapon="operator", t_round=-3.0, t_plant=None,
             phase="buy", opening_kill=None, att_id="p1", att_team="T1", att_side="defender"),
        # opponent opens round 2 by killing our holder p1
        dict(round_key="G1:2", event_id="k6", kind="kill", weapon="vandal", t_round=3.0, t_plant=None,
             phase="pre_plant", opening_kill=True, att_id="x9", att_team="T2", att_side="attacker", vic="p1"),
    ])
    eng["vic_id"] = eng.pop("vic").fillna("x1")
    for col in ("att_name", "att_agent", "vic_name", "map"):
        eng[col] = "testmap" if col == "map" else "n"
    eng["att_x"] = 0.0; eng["att_y"] = 0.0; eng["vic_x"] = 1.0; eng["vic_y"] = 1.0
    eng["att_pos_repeat"] = False; eng["round_no"] = eng.round_key.str.split(":").str[1].astype(int)
    eng["ts_ms"] = range(len(eng)); eng["started_at"] = TS
    c.execute("CREATE TABLE engagements AS SELECT * FROM eng")
    rounds = team_rounds[["round_key"]].assign(winner_team_id=team_rounds.won.map({True: "T1", False: "T2"}))
    c.execute("CREATE TABLE rounds AS SELECT * FROM rounds")
    return c


def run(con, mid, **kw):
    return REGISTRY[mid][1](con, Filters(team_id="T1", **kw))


def test_possession_full_buy_excludes_unknown_and_non_full(con):
    r = run(con, "op.possession_full_buy", side="defender")
    # full-buy known defender rounds: 1,2,3,4 -> with Operator: 1,2,4
    assert (r.rate.k, r.rate.n) == (3, 4)
    assert sorted(r.supporting) == ["G1:1", "G1:2", "G1:4"] and r.contrary == ["G1:3"]
    assert r.unknown[0].count == 1 and "snapshot" in r.unknown[0].reason
    eco = next(b for b in r.breakdown if b["economy"] == "eco")["rate"]
    assert (eco.k, eco.n) == (0, 1)


def test_holder_share_and_shift(con):
    r = run(con, "op.holder_share", side="defender")
    top = r.breakdown[0]
    assert top["player_id"] == "p1" and (top["rate"].k, top["rate"].n) == (2, 3)
    assert r.contrary == ["G1:4"]
    assert (r.value["possession_shift"].k, r.value["possession_shift"].n) == (1, 3)


def test_kill_timing_ignores_buy_phase_and_other_weapons(con):
    r = run(con, "op.kill_timing", side="defender")
    counts = {b["bucket"]: b["rate"].k for b in r.breakdown}
    assert counts == {"0-20s": 1, "20-40s": 1, "40-60s": 0, "60s+": 1}
    assert r.breakdown[0]["rate"].n == 3
    assert (r.value["post_plant"].k, r.value["post_plant"].n) == (1, 3)


def test_opening_duels(con):
    r = run(con, "op.opening", side="defender")
    # Operator rounds with a recorded first kill: G1:1 (holder opened with Operator), G1:2 (holder died first)
    assert (r.rate.k, r.rate.n) == (1, 2)
    assert (r.value["holder_died_first"].k, r.value["holder_died_first"].n) == (1, 2)


def test_win_association(con):
    r = run(con, "op.win_association", side="defender")
    assert (r.rate.k, r.rate.n) == (2, 3)               # rounds 1, 4 won of 1, 2, 4
    assert (r.value["without"].k, r.value["without"].n) == (1, 1)


def test_wilson_interval_bounds():
    r = Rate.of(0, 5)
    assert r.lo == 0 and 0 < r.hi < 0.6 and r.small_sample
    assert Rate.of(0, 0).p is None


def test_ranking_breaks_ties_by_name_not_by_arrival_order():
    from collections import Counter
    from engine.metrics.core import ranked
    a = Counter(["neon", "raze", "raze", "neon", "jett"])
    b = Counter(["jett", "neon", "raze", "raze", "neon"])   # same counts, different order of arrival
    assert ranked(a) == ranked(b) == [("neon", 2), ("raze", 2), ("jett", 1)]
    assert ranked(a, 1) == [("neon", 2)]
