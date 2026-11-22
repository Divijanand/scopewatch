from __future__ import annotations

import duckdb
import numpy as np
import pandas as pd

from engine.abilities import FLASH, INFO, SMOKE, STUN, ULTS
from engine.config import DB_PATH, V2_DIR
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
    """Fights with pre-fight utility features. See `fight_core` and `add_utility`."""
    own_con = con is None
    if own_con:
        con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        out = add_utility(fight_core(con), con, window_s=window_s, radius=radius)
        cols = {r[1] for r in con.execute("PRAGMA table_info('player_rounds')").fetchall()}
        if "agent" in cols:
            players = con.execute("SELECT round_key, player_id, agent FROM player_rounds").df()
            players["player_id"] = players["player_id"].astype(str)
            out["opener_id"] = out["opener_id"].astype(str)
            out["other_id"] = out["other_id"].astype(str)
            opener_agents = players.rename(columns={"player_id": "opener_id", "agent": "opener_agent"})
            other_agents = players.rename(columns={"player_id": "other_id", "agent": "other_agent"})
            out = out.merge(opener_agents[["round_key", "opener_id", "opener_agent"]], on=["round_key", "opener_id"], how="left")
            out = out.merge(other_agents[["round_key", "other_id", "other_agent"]], on=["round_key", "other_id"], how="left")
        return out
    finally:
        if own_con:
            con.close()


def fight_core(con) -> pd.DataFrame:
    """One row per fight with a winner: everything except the utility window features.

    A fight is one pair of opposite-side players. It starts at the first gun damage between them,
    ends at a kill between them (winner = killer) or after 3.0 s with no damage (no winner).
    """
    revives_by_round = load_revives(con)
    rounds = con.execute("""
        SELECT r.round_key, r.series_id, r.map,
               tr_a.team_loadout AS att_loadout_value,
               tr_d.team_loadout AS def_loadout_value
        FROM rounds r
        JOIN team_rounds tr_a ON tr_a.round_key = r.round_key AND tr_a.side = 'attacker'
        JOIN team_rounds tr_d ON tr_d.round_key = r.round_key AND tr_d.side = 'defender'
    """).df()
    plants = con.execute("SELECT round_key, min(t_round) AS t FROM objectives WHERE kind = 'plant' GROUP BY 1").df()
    ops = con.execute("SELECT round_key, player_id FROM player_rounds WHERE has_op").df()
    eng_cols = {r[1] for r in con.execute("PRAGMA table_info('engagements')").fetchall()}
    team_cols = "att_team, vic_team" if {"att_team", "vic_team"} <= eng_cols else "NULL AS att_team, NULL AS vic_team"
    # Same-millisecond events: the feed's own order (seq) keeps a killing shot's damage before the kill.
    order = "round_key, ts_ms, seq" if "seq" in eng_cols else "round_key, ts_ms, (kind = 'kill')"
    engages = con.execute(f"""
        SELECT round_key, t_round, ts_ms, kind, phase, weapon,
               att_id, att_side, vic_id, vic_side, damage,
               att_x, att_y, vic_x, vic_y, att_callout, {team_cols}
        FROM engagements
        WHERE phase IN ('pre_plant', 'post_plant')
          AND kind IN ('damage', 'kill')
          AND att_id IS NOT NULL
          AND vic_id IS NOT NULL
        ORDER BY {order}
    """).df()

    plant_t = dict(zip(plants["round_key"], plants["t"]))
    ops_by_round: dict[str, set] = {}
    for rk, pid in zip(ops["round_key"], ops["player_id"].astype(str)):
        ops_by_round.setdefault(rk, set()).add(pid)
    rounds_by_key = {r.round_key: r for r in rounds.itertuples(index=False)}

    rows = []
    no_winner = 0
    for round_key, ev in engages.groupby("round_key", sort=False):
        r = rounds_by_key.get(round_key)
        if r is None:
            continue
        evs = list(ev.itertuples(index=False))
        # alive state: kills and revives in time order, kill before revive at equal times (as winprob does)
        kills = [(float(e.t_round), 0, str(e.vic_side), str(e.vic_id)) for e in evs if e.kind == "kill"]
        revs = [(float(t), 1, side, None) for t, side in revives_by_round.get(round_key, [])]
        state_events = sorted(kills + revs, key=lambda x: (x[0], x[1]))
        gun_damage_by_player: dict[str, list] = {}

        open_fights: dict = {}
        finished = []
        for e in evs:
            t = float(e.t_round)
            for k in [k for k, st in open_fights.items() if t - st["last_damage_t"] > 3.0]:
                finished.append(open_fights.pop(k))
            if e.att_side == e.vic_side:
                continue
            key = _fight_key(str(e.att_id), str(e.vic_id))
            weapon = _weapon_norm(e.weapon)
            if e.kind == "damage" and weapon in GUNS:
                st = open_fights.get(key)
                if st is None:
                    prior = gun_damage_by_player.get(str(e.vic_id))
                    open_fights[key] = dict(
                        t0=t, opener_id=str(e.att_id), other_id=str(e.vic_id),
                        opener_side=str(e.att_side), other_side=str(e.vic_side),
                        opener_team=e.att_team, other_team=e.vic_team,
                        phase=str(e.phase), opener_weapon=weapon,
                        other_weapon=prior[-1] if prior else "unknown",
                        att_callout=e.att_callout,
                        p1x=e.att_x, p1y=e.att_y, p2x=e.vic_x, p2y=e.vic_y,
                        winner_id=None, last_damage_t=t,
                    )
                else:
                    st["last_damage_t"] = t
                gun_damage_by_player.setdefault(str(e.att_id), []).append(weapon)
            elif e.kind == "kill":
                st = open_fights.get(key)
                if st is not None and t - st["last_damage_t"] <= 3.0:
                    st["winner_id"] = str(e.att_id)
                    finished.append(open_fights.pop(key))
        finished.extend(open_fights.values())

        for st in finished:
            if st["winner_id"] is None:
                no_winner += 1
                continue
            t0 = st["t0"]
            alive = AliveTracker()
            for t, kind, side, vic in state_events:
                if t > t0:
                    break
                if kind == 0:
                    alive.kill(side, vic)
                else:
                    alive.revive(side)
            pt = plant_t.get(round_key)
            ops_here = ops_by_round.get(round_key, set())
            att = st["opener_side"] == "attacker"
            callout = st["att_callout"]
            rows.append({
                "series_id": r.series_id,
                "round_key": round_key,
                "t0": t0,
                "opener_id": st["opener_id"],
                "other_id": st["other_id"],
                "opener_team": st["opener_team"],
                "other_team": st["other_team"],
                "opener_side": st["opener_side"],
                "other_side": st["other_side"],
                "label": 1 if st["winner_id"] == st["opener_id"] else 0,
                "phase": st["phase"],
                "planted": bool(pt is not None and float(pt) <= t0),
                "seconds_since_buy_phase_end": t0,
                "opener_side_alive": alive.alive(st["opener_side"]),
                "other_side_alive": alive.alive(st["other_side"]),
                "opener_side_econ": r.att_loadout_value if att else r.def_loadout_value,
                "other_side_econ": r.def_loadout_value if att else r.att_loadout_value,
                "opener_weapon": st["opener_weapon"],
                "other_weapon": st["other_weapon"],
                "opener_has_op": st["opener_id"] in ops_here,
                "other_has_op": st["other_id"] in ops_here,
                "map": r.map,
                "callout": callout if isinstance(callout, str) and callout else "unknown",
                "p1x": st["p1x"], "p1y": st["p1y"], "p2x": st["p2x"], "p2y": st["p2y"],
            })

    out = pd.DataFrame(rows)
    out.attrs["no_winner_count"] = int(no_winner)
    total = len(rows) + no_winner
    out.attrs["no_winner_share"] = float(no_winner / total) if total else 0.0
    return out


def add_utility(core: pd.DataFrame, con, window_s: float = 4.0, radius: float = 2500.0) -> pd.DataFrame:
    """Utility in [t0 - window_s, t0]: casts by each team within `radius` of either fighter
    (caster position, `spatial_ok` only), and ability damage each team dealt to the other fighter."""
    out = core.copy()
    out.attrs.update(core.attrs)
    for side in ("opener", "other"):
        for c in _UTILITY_COLS:
            out[f"util_{side}_{c}"] = 0
        out[f"dmg_util_{side}"] = 0.0
    if out.empty:
        return out
    f = out[["round_key", "t0", "opener_side", "other_side", "opener_id", "other_id", "p1x", "p1y", "p2x", "p2y"]].copy()
    f["fight_id"] = np.arange(len(f))
    con.register("_fights", f)
    try:
        casts = con.execute("""
            SELECT f.fight_id, (c.side = f.opener_side) AS mine, c.ability
            FROM _fights f
            JOIN casts c ON c.round_key = f.round_key AND c.t_round BETWEEN f.t0 - ? AND f.t0
            WHERE c.phase IN ('pre_plant', 'post_plant') AND c.side IN (f.opener_side, f.other_side)
              AND coalesce(c.spatial_ok, false) AND c.x IS NOT NULL AND c.y IS NOT NULL
              AND least(sqrt((c.x - f.p1x) ** 2 + (c.y - f.p1y) ** 2),
                        sqrt((c.x - f.p2x) ** 2 + (c.y - f.p2y) ** 2)) <= ?
        """, [window_s, radius]).df()
        guns = "(" + ",".join(f"'{g}'" for g in sorted(GUNS)) + ")"
        dmg = con.execute(f"""
            SELECT f.fight_id,
                   sum(CASE WHEN e.att_side = f.opener_side AND e.vic_id = f.other_id
                            THEN coalesce(e.damage, 0) ELSE 0 END) AS dmg_util_opener,
                   sum(CASE WHEN e.att_side = f.other_side AND e.vic_id = f.opener_id
                            THEN coalesce(e.damage, 0) ELSE 0 END) AS dmg_util_other
            FROM _fights f
            JOIN engagements e ON e.round_key = f.round_key AND e.t_round BETWEEN f.t0 - ? AND f.t0
            WHERE e.kind = 'damage' AND e.phase IN ('pre_plant', 'post_plant')
              AND e.att_id IS NOT NULL AND e.vic_id IS NOT NULL
              AND lower(coalesce(e.weapon, 'unknown')) NOT IN {guns}
            GROUP BY 1
        """, [window_s]).df()
    finally:
        con.unregister("_fights")
    if not casts.empty:
        casts["bucket"] = casts["ability"].map(_ability_bucket)
        casts = casts.dropna(subset=["bucket"])
        casts["col"] = "util_" + np.where(casts["mine"], "opener", "other") + "_" + casts["bucket"]
        counts = casts.groupby(["fight_id", "col"]).size().unstack(fill_value=0)
        for col in counts.columns:
            out.loc[counts.index.to_numpy(), col] = counts[col].to_numpy()
    if not dmg.empty:
        idx = dmg["fight_id"].to_numpy()
        out.loc[idx, "dmg_util_opener"] = dmg["dmg_util_opener"].to_numpy()
        out.loc[idx, "dmg_util_other"] = dmg["dmg_util_other"].to_numpy()
    return out


def main():
    out = build_fights(window_s=4.0, radius=2500.0)
    target = V2_DIR / "models" / "fights.parquet"
    target.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(target, index=False)
    print(f"Wrote {len(out)} fights to {target}")


if __name__ == "__main__":
    main()
