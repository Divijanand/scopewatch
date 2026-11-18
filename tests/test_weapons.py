"""Weaponless kills get their weapon from the matching damage event; Tour de Force counts as a sniper kill
but never as a picked-up Operator; every ability in the game has a display mode."""
import duckdb
import pandas as pd

from engine import weapons
from engine.abilities import MODE, mode_of
from engine.metrics.operator import OP, OP_ITEMS


def e(eid, kind, ts, weapon, att="c1", vic="v1"):
    return dict(event_id=eid, round_key="G:1", kind=kind, ts_ms=ts, weapon=weapon, att_id=att, vic_id=vic)


def test_backfill_takes_the_weapon_of_the_matching_hit():
    con = duckdb.connect()
    eng = pd.DataFrame([
        e("d1", "damage", 1000, "tour-de-force"), e("k1", "kill", 1010, None),           # Chamber ult kill
        e("d2", "damage", 5000, "vandal", vic="v2"), e("k2", "kill", 5200, None, vic="v2"),  # 200 ms apart: no match
        e("k3", "kill", 9000, "phantom", vic="v3"),                                       # already known: untouched
        e("d4", "damage", 7000, "vandal", att="other", vic="v4"), e("k4", "kill", 7000, None, vic="v4"),  # other attacker
    ])
    con.execute("CREATE TABLE engagements AS SELECT * FROM eng")
    out = weapons.backfill(con)
    got = dict(con.execute("SELECT event_id, weapon FROM engagements WHERE kind = 'kill'").fetchall())
    assert got == {"k1": "tour-de-force", "k2": None, "k3": "phantom", "k4": None}
    assert out["filled"] == 1 and out["null_after"] == 2
    inferred = dict(con.execute("SELECT event_id, weapon_inferred FROM engagements WHERE kind = 'kill'").fetchall())
    assert inferred["k1"] is True and inferred["k3"] is False


def test_backfill_is_idempotent():
    con = duckdb.connect()
    eng = pd.DataFrame([e("d1", "damage", 1000, "tour-de-force"), e("k1", "kill", 1010, None)])
    con.execute("CREATE TABLE engagements AS SELECT * FROM eng")
    weapons.backfill(con)
    assert weapons.backfill(con)["filled"] == 0


def test_tour_de_force_is_a_sniper_kill_but_not_an_item():
    assert "tour-de-force" in OP and "tour-de-force" not in OP_ITEMS


def test_every_mode_is_known():
    assert set(MODE.values()) <= {"placed", "landing", "direction", "thrown", "self", "unplaced"}
    assert mode_of("toxic-screen") == "direction" and mode_of("dark-cover") == "unplaced"
    assert mode_of("nanoswarm") == "landing" and mode_of("trapwire") == "placed"
    assert mode_of("some-new-ability") == "thrown"      # unknown abilities are never drawn as placed or landed
