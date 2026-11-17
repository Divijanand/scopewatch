"""Scopewatch API: serves team lists, map outlines and Operator profiles.

Run: uvicorn api.server:app --port 8000   (from the repo root)
"""
from __future__ import annotations

import json
import threading

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from pipeline.config import CACHE_DIR
from pipeline.profile import Filters, connect, team_profile

app = FastAPI(title="Scopewatch")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_methods=["GET"])

MAPS_DIR = CACHE_DIR / "maps"
_local = threading.local()


def con():
    # DuckDB connections aren't thread-safe; FastAPI runs sync endpoints in a pool
    if not hasattr(_local, "con"):
        _local.con = connect(read_only=True)
    return _local.con


@app.get("/api/teams")
def teams():
    rows = con().execute(
        """SELECT o.team_id, any_value(t.name) AS name, count(*) AS rounds,
                  count(DISTINCT o.game_id) AS maps, count(*) FILTER (WHERE n_op > 0) AS op_rounds,
                  max(o.started_at)::DATE::VARCHAR AS last_played,
                  list(DISTINCT o.event) AS events
           FROM op_rounds o LEFT JOIN teams t USING (team_id)
           GROUP BY o.team_id HAVING count(DISTINCT o.game_id) >= 3
           ORDER BY (any_value(t.name) ILIKE 'cloud9%') DESC, maps DESC""").fetchall()
    out = []
    for tid, name, rounds, maps, op_rounds, last, events in rows:
        league = "Game Changers" if any("Game Changers" in e for e in events) else "VCT"
        out.append(dict(team_id=tid, name=name, rounds=rounds, maps=maps, op_rounds=op_rounds,
                        last_played=last, league=league))
    return out


@app.get("/api/teams/{team_id}/maps")
def team_maps(team_id: str):
    rows = con().execute(
        """SELECT map, count(DISTINCT game_id) maps, count(*) rounds,
                  count(*) FILTER (WHERE n_op > 0) op_rounds
           FROM op_rounds WHERE team_id = ? GROUP BY map ORDER BY maps DESC""", [team_id]).fetchall()
    return [dict(map=m, maps=n, rounds=r, op_rounds=k) for m, n, r, k in rows]


@app.get("/api/maps")
def maps():
    return json.loads((MAPS_DIR / "maps.json").read_text())


@app.get("/api/maps/{name}.png")
def map_png(name: str):
    path = (MAPS_DIR / f"{name}.png").resolve()
    if path.parent != MAPS_DIR.resolve() or not path.exists():
        raise HTTPException(404, "No outline for that map")
    return FileResponse(path, media_type="image/png")


@app.get("/api/spawns/{map_name}")
def spawns(map_name: str):
    from pipeline.profile import spawns as _sp
    return {k: dict(x=v[0], y=v[1]) for k, v in _sp(con(), map_name).items()}


@app.get("/api/profile")
def profile(team_id: str, map: str | None = None, side: str | None = Query(None, pattern="^(attacker|defender)$"),
            since: str | None = None, player_id: str | None = None):
    return team_profile(Filters(team_id=team_id, map=map, side=side, since=since, player_id=player_id), con())
