from __future__ import annotations

from dataclasses import dataclass

import duckdb
import pandas as pd

from engine.abilities import PLACEABLE, ULTS, WEAPON_ULTS, kind_of
from engine.config import DB_PATH
from engine.model.winprob import AliveTracker, REVIVES
from engine.roles import ROLE

ROLE_ORDER = ("duelist", "initiator", "controller", "sentinel")
UTIL_KINDS = ("smoke", "flash", "stun", "info", "movement")
ULT_SET = set(ULTS) - set(WEAPON_ULTS)


@dataclass
class PlayerState:
    side: str
    role: str
    loadout: int
    alive: bool = True


class RoundTracker:
    """Tracks role/loadout features; revive target is assumed as the most recently dead teammate.

    GRID casts do not identify the revived player. For role and alive-loadout feature families we therefore
    approximate by reviving the latest dead player on that side.
    """
    def __init__(self, players: dict[str, PlayerState]):
        self.players = players
        self.dead_by_side = {"attacker": [], "defender": []}
        self.role_alive = {"attacker": {r: 0 for r in ROLE_ORDER}, "defender": {r: 0 for r in ROLE_ORDER}}
        self.alive_loadout = {"attacker": 0, "defender": 0}
        self.ops_alive = {"attacker": set(), "defender": set()}
        for pid, p in players.items():
            if p.side in self.role_alive:
                self.role_alive[p.side][p.role] += 1
                self.alive_loadout[p.side] += p.loadout

    def set_ops(self, ops_rows: pd.DataFrame):
        for r in ops_rows.itertuples(index=False):
            if r.side in self.ops_alive and r.player_id in self.players and self.players[r.player_id].alive:
                self.ops_alive[r.side].add(r.player_id)

    def kill(self, victim_id: str):
        p = self.players.get(victim_id)
        if p is None or not p.alive or p.side not in self.role_alive:
            return
        p.alive = False
        self.dead_by_side[p.side].append(victim_id)
        self.role_alive[p.side][p.role] = max(0, self.role_alive[p.side][p.role] - 1)
        self.alive_loadout[p.side] -= p.loadout
        self.ops_alive[p.side].discard(victim_id)

    def revive(self, side: str):
        if side not in self.dead_by_side:
            return
        while self.dead_by_side[side]:
            pid = self.dead_by_side[side].pop()
            p = self.players.get(pid)
            if p is None:
                continue
            if not p.alive:
                p.alive = True
                self.role_alive[side][p.role] += 1
                self.alive_loadout[side] += p.loadout
                return

    def alive_count(self, side: str) -> int:
        return sum(1 for p in self.players.values() if p.side == side and p.alive)


def _patch_index_map(con) -> dict[str, int]:
    rows = con.execute("""
        SELECT patch, min(started_at) AS started
        FROM games
        WHERE patch IS NOT NULL
        GROUP BY patch
        ORDER BY started, patch
    """).fetchall()
    return {patch: i for i, (patch, _) in enumerate(rows)}


def _scores_before_round(rounds: pd.DataFrame) -> dict[str, tuple[int, int]]:
    scores = {}
    by_game = rounds.sort_values(["game_id", "round_no", "round_key"]).groupby("game_id", sort=False)
    for _, g in by_game:
        wins = {}
        for r in g.itertuples(index=False):
            att_score = wins.get(r.attacker_team_id, 0)
            def_score = wins.get(r.defender_team_id, 0)
            scores[r.round_key] = (att_score, def_score)
            if r.winner_team_id is not None:
                wins[r.winner_team_id] = wins.get(r.winner_team_id, 0) + 1
    return scores


def build_states(db_path=DB_PATH) -> pd.DataFrame:
    con = duckdb.connect(str(db_path), read_only=True)
    patch_index = _patch_index_map(con)

    rounds = con.execute("""
        SELECT r.round_key, r.series_id, r.game_id, r.round_no, r.map, r.patch,
               r.winner_side, r.winner_team_id,
               att.team_id AS attacker_team_id, def.team_id AS defender_team_id,
               att.team_loadout AS att_loadout, def.team_loadout AS def_loadout
        FROM rounds r
        JOIN team_rounds att ON att.round_key = r.round_key AND att.side = 'attacker'
        JOIN team_rounds def ON def.round_key = r.round_key AND def.side = 'defender'
        ORDER BY r.round_key
    """).df()

    players = con.execute("""
        SELECT round_key, player_id, side, agent, loadout_value
        FROM player_rounds
        WHERE side IN ('attacker', 'defender')
    """).df()
    player_ops = con.execute("""
        SELECT round_key, player_id, side
        FROM player_rounds
        WHERE has_op = true AND side IN ('attacker', 'defender')
    """).df()
    kills = con.execute("""
        SELECT round_key, t_round, vic_side, vic_id
        FROM engagements
        WHERE kind = 'kill' AND phase IN ('pre_plant', 'post_plant')
        ORDER BY round_key, t_round
    """).df()
    plants = con.execute("""
        SELECT round_key, t_round
        FROM objectives
        WHERE kind = 'plant'
        ORDER BY round_key, t_round
    """).df()
    casts = con.execute("""
        SELECT round_key, t_round, side, ability, phase
        FROM casts
        WHERE side IN ('attacker', 'defender') AND phase != 'post_round'
        ORDER BY round_key, t_round
    """).df()
    revives = con.execute(f"""
        SELECT round_key, t_round, side
        FROM casts
        WHERE ability IN {REVIVES} AND phase IN ('pre_plant', 'post_plant') AND side IS NOT NULL
        ORDER BY round_key, t_round
    """).df()
    con.close()

    players_by_round = {k: g for k, g in players.groupby("round_key")}
    ops_by_round = {k: g for k, g in player_ops.groupby("round_key")}
    kills_by_round = {k: g for k, g in kills.groupby("round_key")}
    plants_by_round = {k: g for k, g in plants.groupby("round_key")}
    casts_by_round = {k: g for k, g in casts.groupby("round_key")}
    revives_by_round = {k: g for k, g in revives.groupby("round_key")}
    score_before = _scores_before_round(rounds)

    rows = []
    for r in rounds.itertuples(index=False):
        pr = players_by_round.get(r.round_key, pd.DataFrame(columns=["player_id", "side", "agent", "loadout_value"]))
        roster = {}
        for p in pr.itertuples(index=False):
            role = ROLE.get(p.agent, "sentinel")
            roster[p.player_id] = PlayerState(side=p.side, role=role if role in ROLE_ORDER else "sentinel",
                                              loadout=int(p.loadout_value or 0))
        tracker = RoundTracker(roster)
        tracker.set_ops(ops_by_round.get(r.round_key, pd.DataFrame(columns=["player_id", "side"])))
        alive = AliveTracker()
        att_ops = set(tracker.ops_alive["attacker"])
        def_ops = set(tracker.ops_alive["defender"])

        util_counts = {"attacker": {f"util_{k}": 0 for k in UTIL_KINDS} | {"util_placeable": 0},
                       "defender": {f"util_{k}": 0 for k in UTIL_KINDS} | {"util_placeable": 0}}
        ult_counts = {"attacker": 0, "defender": 0}

        events = []
        for k in kills_by_round.get(r.round_key, pd.DataFrame(columns=["t_round", "vic_side", "vic_id"])).itertuples(index=False):
            events.append(("kill", float(k.t_round), k))
        for p in plants_by_round.get(r.round_key, pd.DataFrame(columns=["t_round"])).itertuples(index=False):
            events.append(("plant", float(p.t_round), p))
        for c in casts_by_round.get(r.round_key, pd.DataFrame(columns=["t_round", "side", "ability", "phase"])).itertuples(index=False):
            events.append(("cast", float(c.t_round), c))
        for rv in revives_by_round.get(r.round_key, pd.DataFrame(columns=["t_round", "side"])).itertuples(index=False):
            events.append(("revive", float(rv.t_round), rv))
        order = {"cast": 0, "kill": 1, "revive": 2, "plant": 3}
        events.sort(key=lambda x: (x[1], order[x[0]]))

        planted = False
        plant_t = None
        score_att, score_def = score_before.get(r.round_key, (0, 0))

        for etype, t, e in events:
            if etype == "cast":
                side = e.side
                if side not in ("attacker", "defender"):
                    continue
                k = kind_of(e.ability)
                if k in UTIL_KINDS:
                    util_counts[side][f"util_{k}"] += 1
                if e.ability in PLACEABLE:
                    util_counts[side]["util_placeable"] += 1
                if e.ability in ULT_SET and e.phase in ("pre_plant", "post_plant"):
                    ult_counts[side] += 1
                continue
            if etype == "revive":
                alive.revive(e.side)
                tracker.revive(e.side)
                continue
            if etype == "kill":
                alive.kill(e.vic_side, e.vic_id)
                if e.vic_side == "attacker":
                    att_ops.discard(e.vic_id)
                elif e.vic_side == "defender":
                    def_ops.discard(e.vic_id)
                tracker.kill(e.vic_id)
            elif etype == "plant":
                planted = True
                plant_t = t

            row = {
                "series_id": r.series_id,
                "round_key": r.round_key,
                "seconds_since_buy_phase_end": t,
                "planted": planted,
                "seconds_since_plant": (t - plant_t) if planted and plant_t is not None else 0,
                "attackers_alive": alive.alive("attacker"),
                "defenders_alive": alive.alive("defender"),
                "att_loadout_value": int(r.att_loadout or 0),
                "def_loadout_value": int(r.def_loadout or 0),
                "att_has_op": len(att_ops) > 0,
                "def_has_op": len(def_ops) > 0,
                "label": 1 if r.winner_side == "attacker" else 0,
                "score_round_no": int(r.round_no or 0),
                "score_att_before": int(score_att),
                "score_def_before": int(score_def),
                "score_overtime": bool((r.round_no or 0) > 24),
                "map": r.map,
                "patch_index": patch_index.get(r.patch, -1),
                "ult_att_used": ult_counts["attacker"],
                "ult_def_used": ult_counts["defender"],
                "aliveload_att": tracker.alive_loadout["attacker"],
                "aliveload_def": tracker.alive_loadout["defender"],
            }
            for role in ROLE_ORDER:
                row[f"role_att_{role}"] = tracker.role_alive["attacker"][role]
                row[f"role_def_{role}"] = tracker.role_alive["defender"][role]
            for side, prefix in (("attacker", "att"), ("defender", "def")):
                for kind in UTIL_KINDS:
                    row[f"util_{prefix}_{kind}"] = util_counts[side][f"util_{kind}"]
                row[f"util_{prefix}_placeable"] = util_counts[side]["util_placeable"]
            rows.append(row)

    df = pd.DataFrame(rows)
    if not df.empty:
        df["map"] = df["map"].astype("category")
    return df
