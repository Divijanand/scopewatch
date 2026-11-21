from __future__ import annotations

import duckdb
import numpy as np
import pandas as pd

from engine.abilities import FLASH, INFO, SMOKE, STUN, ULTS
from engine.config import DB_PATH
from engine.model.winprob import AliveTracker, load_revives
from engine.weapons import GUNS

_UTILITY_COLS = ["flash_stun", "smoke", "recon", "ult"]


def _weapon_norm(weapon: str | None) -> str:
    if weapon is None:
        return "unknown"
    w = str(weapon).strip().lower()
    return w if w else "unknown"


def _ability_bucket(ability: str | None) -> str | None:
    if ability in FLASH or ability in STUN:
        return "flash_stun"
    if ability in SMOKE:
        return "smoke"
    if ability in INFO:
        return "recon"
    if ability in ULTS:
        return "ult"
    return None


def _dist_ok(cx, cy, p1x, p1y, p2x, p2y, r: float) -> bool:
    if pd.isna(cx) or pd.isna(cy):
        return False
    d1 = np.hypot(float(cx) - float(p1x), float(cy) - float(p1y))
    d2 = np.hypot(float(cx) - float(p2x), float(cy) - float(p2y))
    return min(d1, d2) <= r


def _fight_key(a: str, b: str) -> tuple[str, str]:
    return (a, b) if a < b else (b, a)


def build_fights(con=None, window_s: float = 4.0, radius: float = 2500.0) -> pd.DataFrame:
    own_con = con is None
    if own_con:
        con = duckdb.connect(str(DB_PATH), read_only=True)

    try:
        revives_by_round = load_revives(con)
        rounds = con.execute("""
            SELECT r.round_key, r.series_id, r.map,
                   tr_a.team_loadout AS att_loadout_value,
                   tr_d.team_loadout AS def_loadout_value
            FROM rounds r
            JOIN team_rounds tr_a ON tr_a.round_key = r.round_key AND tr_a.side = 'attacker'
            JOIN team_rounds tr_d ON tr_d.round_key = r.round_key AND tr_d.side = 'defender'
        """).df()
        plants = con.execute("SELECT round_key, t_round FROM objectives WHERE kind = 'plant'").df()
        ops = con.execute("SELECT round_key, player_id, has_op FROM player_rounds WHERE has_op").df()
        engages = con.execute("""
            SELECT round_key, t_round, ts_ms, kind, phase, weapon,
                   att_id, att_side, vic_id, vic_side, damage,
                   att_x, att_y, vic_x, vic_y, att_callout
            FROM engagements
            WHERE phase IN ('pre_plant', 'post_plant')
              AND kind IN ('damage', 'kill')
              AND att_id IS NOT NULL
              AND vic_id IS NOT NULL
            ORDER BY round_key, ts_ms
        """).df()
        casts = con.execute("""
            SELECT round_key, t_round, side, ability, x, y, spatial_ok
            FROM casts
            WHERE phase IN ('pre_plant', 'post_plant')
              AND side IS NOT NULL
            ORDER BY round_key, ts_ms
        """).df()

        plants_by_round = {k: g["t_round"].min() for k, g in plants.groupby("round_key")}
        ops_by_round = {k: set(g["player_id"].astype(str)) for k, g in ops.groupby("round_key")}
        casts_by_round = {k: g.reset_index(drop=True) for k, g in casts.groupby("round_key")}
        rounds_by_key = {r.round_key: r for r in rounds.itertuples(index=False)}

        rows = []
        no_winner = 0

        for round_key, ev in engages.groupby("round_key", sort=False):
            if round_key not in rounds_by_key:
                continue
            r = rounds_by_key[round_key]
            ev = ev.reset_index(drop=True)

            open_fights = {}
            finished = []
            for e in ev.itertuples(index=False):
                t = float(e.t_round)
                stale = [k for k, st in open_fights.items() if t - st["last_damage_t"] > 3.0]
                for k in stale:
                    finished.append(open_fights.pop(k))

                key = _fight_key(str(e.att_id), str(e.vic_id))
                if e.kind == "damage" and _weapon_norm(e.weapon) in GUNS:
                    st = open_fights.get(key)
                    if st is None:
                        open_fights[key] = dict(
                            t0=t,
                            ts_ms=int(e.ts_ms),
                            opener_id=str(e.att_id),
                            other_id=str(e.vic_id),
                            opener_side=str(e.att_side),
                            other_side=str(e.vic_side),
                            phase=str(e.phase),
                            opener_weapon=_weapon_norm(e.weapon),
                            att_callout=getattr(e, "att_callout", None),
                            p1x=float(e.att_x) if not pd.isna(e.att_x) else np.nan,
                            p1y=float(e.att_y) if not pd.isna(e.att_y) else np.nan,
                            p2x=float(e.vic_x) if not pd.isna(e.vic_x) else np.nan,
                            p2y=float(e.vic_y) if not pd.isna(e.vic_y) else np.nan,
                            winner_id=None,
                        )
                    else:
                        st["last_damage_t"] = t
                    open_fights[key]["last_damage_t"] = t
                elif e.kind == "kill":
                    st = open_fights.get(key)
                    if st is None:
                        continue
                    if t >= st["t0"] and t - st["last_damage_t"] <= 3.0:
                        st["winner_id"] = str(e.att_id)
                        finished.append(st)
                        open_fights.pop(key, None)

            finished.extend(open_fights.values())

            for st in finished:
                if st["winner_id"] is None:
                    no_winner += 1
                    continue

                t0 = st["t0"]
                alive = AliveTracker()
                kill_ev = ev[(ev["kind"] == "kill") & (ev["t_round"] <= t0)].sort_values(["t_round", "ts_ms"])
                rev = revives_by_round.get(round_key, [])
                rev_i = 0
                for k in kill_ev.itertuples(index=False):
                    while rev_i < len(rev) and rev[rev_i][0] <= float(k.t_round):
                        alive.revive(rev[rev_i][1])
                        rev_i += 1
                    alive.kill(str(k.vic_side), str(k.vic_id))
                while rev_i < len(rev) and rev[rev_i][0] <= t0:
                    alive.revive(rev[rev_i][1])
                    rev_i += 1

                plant_t = plants_by_round.get(round_key)
                planted = plant_t is not None and float(plant_t) <= t0

                prior_other = ev[
                    (ev["kind"] == "damage")
                    & (ev["att_id"] == st["other_id"])
                    & (ev["t_round"] < t0)
                ]
                other_weapon = "unknown"
                if not prior_other.empty:
                    other_weapon = _weapon_norm(prior_other.iloc[-1]["weapon"])

                cast_rows = casts_by_round.get(round_key)
                util = {f"util_opener_{c}": 0 for c in _UTILITY_COLS}
                util.update({f"util_other_{c}": 0 for c in _UTILITY_COLS})
                dmg_util_opener = 0.0
                dmg_util_other = 0.0
                if cast_rows is not None:
                    win = cast_rows[(cast_rows["t_round"] >= t0 - window_s) & (cast_rows["t_round"] <= t0)]
                    for c in win.itertuples(index=False):
                        if not bool(c.spatial_ok):
                            continue
                        if not _dist_ok(c.x, c.y, st["p1x"], st["p1y"], st["p2x"], st["p2y"], radius):
                            continue
                        bucket = _ability_bucket(c.ability)
                        if bucket is None:
                            continue
                        if c.side == st["opener_side"]:
                            util[f"util_opener_{bucket}"] += 1
                        elif c.side == st["other_side"]:
                            util[f"util_other_{bucket}"] += 1

                dmg = ev[
                    (ev["kind"] == "damage")
                    & (ev["t_round"] >= t0 - window_s)
                    & (ev["t_round"] <= t0)
                    & (~ev["weapon"].fillna("unknown").str.lower().isin(GUNS))
                ]
                for d in dmg.itertuples(index=False):
                    if d.att_side == st["opener_side"] and d.vic_id == st["other_id"]:
                        dmg_util_opener += float(d.damage or 0.0)
                    elif d.att_side == st["other_side"] and d.vic_id == st["opener_id"]:
                        dmg_util_other += float(d.damage or 0.0)

                rows.append({
                    "series_id": r.series_id,
                    "round_key": round_key,
                    "t0": t0,
                    "opener_id": st["opener_id"],
                    "other_id": st["other_id"],
                    "opener_side": st["opener_side"],
                    "label": 1 if st["winner_id"] == st["opener_id"] else 0,
                    "phase": st["phase"],
                    "planted": bool(planted),
                    "seconds_since_buy_phase_end": t0,
                    "opener_side_alive": alive.alive(st["opener_side"]),
                    "other_side_alive": alive.alive(st["other_side"]),
                    "opener_side_econ": r.att_loadout_value if st["opener_side"] == "attacker" else r.def_loadout_value,
                    "other_side_econ": r.def_loadout_value if st["opener_side"] == "attacker" else r.att_loadout_value,
                    "opener_weapon": st["opener_weapon"],
                    "other_weapon": other_weapon,
                    "opener_has_op": st["opener_id"] in ops_by_round.get(round_key, set()),
                    "other_has_op": st["other_id"] in ops_by_round.get(round_key, set()),
                    "map": r.map,
                    "callout": st["att_callout"] if st["att_callout"] else "unknown",
                    "dmg_util_opener": dmg_util_opener,
                    "dmg_util_other": dmg_util_other,
                    **util,
                })

        out = pd.DataFrame(rows)
        out.attrs["no_winner_count"] = int(no_winner)
        out.attrs["no_winner_share"] = float(no_winner / (len(rows) + no_winner)) if (len(rows) + no_winner) else 0.0
        return out
    finally:
        if own_con:
            con.close()
