"""Synthetic GRID-shaped feeds for tests.

Everything here is invented: team names, player names, ids and coordinates are made up, and the
shapes follow the documented GRID envelope format (S4). Nothing is copied from the licensed corpus.
"""
from __future__ import annotations

import itertools
from datetime import datetime, timedelta, timezone

T0 = datetime(2030, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
_ids = itertools.count(1)


def iso(sec: float) -> str:
    return (T0 + timedelta(seconds=sec)).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def player(pid, name, team, side, x=0.0, y=0.0, agent="sentinel-a", items=("classic",)):
    return dict(id=pid, name=name, teamId=team, side=side, character={"id": agent, "name": agent},
                position={"x": x, "y": y}, inventory={"items": [{"id": i} for i in items]},
                money=800, loadoutValue=1000)


class Feed:
    """Builds a list of envelopes. Times are seconds after T0."""

    def __init__(self, series_id="S1", game_id="G1", map_name="testmap"):
        self.sid, self.gid, self.map = series_id, game_id, map_name
        self.envs = []
        self.seq = 0
        self.teams = {
            "TA": dict(id="TA", name="Alpha", side="attacker", players=[]),
            "TD": dict(id="TD", name="Delta", side="defender", players=[]),
        }

    # -------------------------------------------------------------- low level
    def ev(self, sec, type_, actor, target, full=False, actor_delta=None):
        self.seq += 1
        e = dict(id=f"e{next(_ids)}", type=type_, actor=actor, target=target,
                 action=type_.split("-")[1], includesFullState=full)
        if actor_delta:
            e["actor"] = dict(actor, stateDelta=actor_delta)
        if full:
            e["seriesState"] = self.series_state()
        self.envs.append(dict(id=f"env{self.seq}", occurredAt=iso(sec), seriesId=self.sid,
                              sequenceNumber=self.seq, events=[e]))
        return e

    def series_state(self):
        teams = []
        for t in self.teams.values():
            teams.append(dict(id=t["id"], name=t["name"], side=t["side"], money=4000, loadoutValue=20000,
                              players=[dict(id=p["id"], name=p["name"], character=p["character"],
                                            position=p["position"], inventory=p["inventory"], money=p["money"],
                                            loadoutValue=p["loadoutValue"]) for p in t["players"]]))
        game = dict(id=self.gid, started=True, finished=False,
                    map=dict(name=self.map, bounds={"min": {"x": -1000, "y": -1000}, "max": {"x": 1000, "y": 1000}}),
                    teams=teams)
        return dict(id=self.sid, games=[game])

    def add_player(self, team, pid, name, **kw):
        p = player(pid, name, team, self.teams[team]["side"], **kw)
        self.teams[team]["players"].append(p)
        return p

    def swap_sides(self):
        for t in self.teams.values():
            t["side"] = "defender" if t["side"] == "attacker" else "attacker"
            for p in t["players"]:
                p["side"] = t["side"]

    def reverse(self, sec, original):
        """Emit the GRID reversal of an earlier event (same actor/target, action prefixed with '!')."""
        a, act, *rest = original["type"].split("-")
        t = "-".join([a, "!" + act, *rest])
        return self.ev(sec, t, {k: v for k, v in original["actor"].items() if k != "stateDelta"},
                       original["target"])

    # -------------------------------------------------------------- game flow
    def start_game(self, sec):
        return self.ev(sec, "series-started-game", {"type": "series", "id": self.sid},
                       {"type": "game", "id": self.gid}, full=True)

    def start_round(self, sec, n):
        return self.ev(sec, "game-started-round", {"type": "game", "id": self.gid},
                       {"type": "round", "id": f"round-{n}", "state": {"sequenceNumber": n}}, full=True)

    def start_buy(self, sec, n):
        return self.ev(sec, "round-started-freezetime", {"type": "round", "id": f"round-{n}",
                                                         "state": {"sequenceNumber": n}},
                       {"type": "freezetime", "id": "freezetime-1"}, full=True)

    def end_buy(self, sec, n):
        return self.ev(sec, "round-ended-freezetime", {"type": "round", "id": f"round-{n}",
                                                       "state": {"sequenceNumber": n}},
                       {"type": "freezetime", "id": "freezetime-1"}, full=True)

    def win_round(self, sec, n, team):
        t = self.teams[team]
        return self.ev(sec, "team-won-round", {"type": "team", "id": team, "state": {"id": team, "side": t["side"]}},
                       {"type": "round", "id": f"round-{n}"})

    def _pstate(self, p, x, y):
        return {"type": "player", "id": p["id"],
                "state": {"id": p["id"], "name": p["name"], "teamId": p["teamId"], "side": p["side"],
                          "game": {"position": {"x": x, "y": y}}}}

    def kill(self, sec, att, vic, weapon="vandal", att_xy=(0, 0), vic_xy=(100, 0)):
        return self.ev(sec, "player-killed-player", self._pstate(att, *att_xy), self._pstate(vic, *vic_xy),
                       actor_delta={"round": {"weaponKills": {weapon: 1}}})

    def damage(self, sec, att, vic, weapon="vandal", amount=50, att_xy=(0, 0), vic_xy=(100, 0)):
        return self.ev(sec, "player-damaged-player", self._pstate(att, *att_xy), self._pstate(vic, *vic_xy),
                       actor_delta={"round": {"damageDealt": amount,
                                              "damageDealtSources": [{"source": {"name": weapon}}],
                                              "damageDealtTargets": [{"target": {"name": "body"}}]}})

    def plant(self, sec, p, xy=(500, 500)):
        return self.ev(sec, "player-completed-plantBomb", self._pstate(p, *xy), {"type": "bomb", "id": "spike"})

    def use_ability(self, sec, p, ability="trip"):
        return self.ev(sec, "player-used-ability", self._pstate(p, 0, 0), {"type": "ability", "id": ability})


def cast(series_id, game_id, sec, player_id, grid_event_id=None, quality="ok", x=1.0, y=2.0,
         offsets=(-100, 100), ability="trip"):
    fb = dict(offset_ms=offsets[0], position=dict(x=x, y=y, z=0.0), view=dict(x=1.0, y=0.0, z=0.0),
              velocity=dict(x=0.0, y=0.0, z=0.0)) if offsets[0] is not None else None
    fa = dict(offset_ms=offsets[1], position=dict(x=x + 10, y=y, z=0.0), view=dict(x=1.0, y=0.0, z=0.0),
              velocity=dict(x=0.0, y=0.0, z=0.0)) if offsets[1] is not None else None
    interp = None if quality == "missing_both" else dict(position=dict(x=x, y=y, z=0.0),
                                                         view=dict(x=1.0, y=0.0, z=0.0),
                                                         velocity=dict(x=0.0, y=0.0, z=0.0), weight=0.5)
    return dict(series_id=series_id, game_id=game_id, grid_event_id=grid_event_id, in_grid=grid_event_id is not None,
                occurred_at=iso(sec), player_id=player_id, ability=ability, slot="ABILITY_1",
                charges_consumed=1, frame_before=fb, frame_after=fa, interpolated=interp, quality=quality)
