"""Scopewatch API (engine v2). Every analytical response is an envelope:

    {data, coverage?, warnings, definition_versions, dataset_revision, parser_version, filter_hash}

Run from the repo root:  uvicorn api.server:app --port 8000
"""
from __future__ import annotations

import json
import threading
from dataclasses import asdict

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

import duckdb

from engine.callouts import load as load_callouts
from engine.config import DB_PATH, MAPS_DIR
from engine.coverage import coverage
from engine.metrics import REGISTRY, Filters
from engine.metrics.operator import ENG_COLS, _op_engagements, spawns as _spawns

app = FastAPI(title="Scopewatch", version="2")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_methods=["GET"])
_local = threading.local()

SIDE = Query(None, pattern="^(attacker|defender)$")
DATE = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$")
OP_METRICS = ["op.possession_full_buy", "op.holder_share", "op.kill_timing", "op.opening",
              "op.win_association", "op.forwardness", "op.setups", "op.deaths"]


def con():
    if not hasattr(_local, "con"):  # DuckDB connections aren't thread-safe; one per worker thread
        _local.con = duckdb.connect(DB_PATH.as_posix(), read_only=True)
    return _local.con


def build_info():
    if not hasattr(_local, "info"):
        r = con().execute("SELECT dataset_revision, parser_version FROM build_info").fetchone()
        _local.info = dict(dataset_revision=r[0], parser_version=r[1])
    return _local.info


def envelope(data, f: Filters | None = None, warnings=(), definitions=(), cov=None):
    out = dict(data=data, warnings=list(warnings), definition_versions=list(definitions), **build_info())
    if f is not None:
        out["filter_hash"] = f.hash()
    if cov is not None:
        out["coverage"] = cov
    return out


def filters(team_id, map, side, since, until, player_id=None) -> Filters:
    if not con().execute("SELECT 1 FROM team_rounds WHERE team_id = ? LIMIT 1", [team_id]).fetchone():
        raise HTTPException(404, f"No rounds for team {team_id}")
    return Filters(team_id=team_id, map=map, side=side, since=since, until=until, player_id=player_id)


@app.get("/health")
def health():
    return dict(status="ok", **build_info())


@app.get("/api/catalog")
def catalog():
    teams = con().execute("""
        SELECT t.team_id, any_value(t.team_name), count(*) rounds, count(DISTINCT t.game_id) maps,
               count(*) FILTER (WHERE n_op > 0) op_rounds, max(t.started_at)::DATE::VARCHAR last_played,
               bool_or(g.game_changers) gc
        FROM team_rounds t JOIN games g USING (game_id)
        GROUP BY t.team_id HAVING count(DISTINCT t.game_id) >= 3
        ORDER BY (any_value(t.team_name) ILIKE 'cloud9%') DESC, maps DESC""").fetchall()
    maps = json.loads((MAPS_DIR / "maps.json").read_text())
    for name, anchors in load_callouts().items():   # community callout anchors, native coordinates
        if name in maps:
            maps[name]["callouts"] = anchors
    metrics = [asdict(d) for d, _ in REGISTRY.values()]
    return envelope(dict(
        teams=[dict(team_id=a, name=b, rounds=c, maps=d, op_rounds=e, last_played=f_,
                    league="Game Changers" if g else "VCT") for a, b, c, d, e, f_, g in teams],
        maps=maps, metrics=metrics))


@app.get("/api/teams/{team_id}/maps")
def team_maps(team_id: str):
    rows = con().execute("""SELECT map, count(DISTINCT game_id), count(*), count(*) FILTER (WHERE n_op > 0)
                            FROM team_rounds WHERE team_id = ? GROUP BY map ORDER BY 2 DESC""", [team_id]).fetchall()
    return envelope([dict(map=m, maps=n, rounds=r, op_rounds=k) for m, n, r, k in rows])


@app.get("/api/coverage")
def get_coverage(team_id: str, map: str | None = None, side: str | None = SIDE,
                 since: str | None = DATE, until: str | None = DATE):
    f = filters(team_id, map, side, since, until)
    cov = coverage(con(), f)
    return envelope(cov, f, warnings=cov["warnings"])


@app.get("/api/weapons/tendencies")
def weapon_tendencies(team_id: str, map: str | None = None, side: str | None = SIDE,
                      since: str | None = DATE, until: str | None = DATE, player_id: str | None = None):
    f = filters(team_id, map, side, since, until, player_id)
    results, defs, warns = {}, [], []
    for mid in OP_METRICS:
        d, fn = REGISTRY[mid]
        r = fn(con(), f)
        results[mid] = r.to_dict(evidence_limit=0)
        defs.append(f"{d.id}@v{d.version}")
        warns += r.warnings
    cov = coverage(con(), f)
    return envelope(results, f, warnings=warns + cov["warnings"], definitions=defs, cov=cov)


@app.get("/api/spatial/operator")
def spatial_operator(team_id: str, map: str, side: str | None = SIDE, since: str | None = DATE,
                     until: str | None = DATE, player_id: str | None = None,
                     limit: int = Query(1500, le=5000)):
    """Map layer: Operator/Outlaw kills and hits as shooter -> victim lines (observed event positions)."""
    f = filters(team_id, map, side, since, until, player_id)
    rows = _op_engagements(con(), f, kinds=("kill", "damage"))
    data = [dict(zip(ENG_COLS, r)) for r in rows[:limit]]
    warns = [f"Showing {limit} of {len(rows)} engagements."] if len(rows) > limit else []
    sp = _spawns(con(), map)
    return envelope(dict(layer="observed_engagement_positions", engagements=data,
                         spawns={k: dict(x=v[0], y=v[1]) for k, v in sp.items()}), f, warnings=warns)


@app.get("/api/evidence")
def evidence(metric: str, team_id: str, map: str | None = None, side: str | None = SIDE,
             since: str | None = DATE, until: str | None = DATE, player_id: str | None = None,
             which: str = Query("supporting", pattern="^(supporting|contrary)$"),
             bucket: str | None = None, page: int = Query(0, ge=0), page_size: int = Query(25, le=100)):
    """The rounds behind a metric result, newest first, paginated."""
    if metric not in REGISTRY:
        raise HTTPException(404, "Unknown metric")
    f = filters(team_id, map, side, since, until, player_id)
    d, fn = REGISTRY[metric]
    res = fn(con(), f)
    keys = res.supporting if which == "supporting" else res.contrary
    if bucket and any("round_keys" in b for b in res.breakdown):  # one bar / callout of a breakdown
        in_bucket = next((b["round_keys"] for b in res.breakdown if b["bucket"] == bucket), [])
        all_rounds = sorted({k for b in res.breakdown for k in b["round_keys"]})
        keys = in_bucket if which == "supporting" else sorted(set(all_rounds) - set(in_bucket))
    if not keys:
        return envelope(dict(total=0, rounds=[]), f, definitions=[f"{d.id}@v{d.version}"])
    rows = con().execute("""
        SELECT t.round_key, t.map, t.round_no, t.side, t.economy, t.won, t.win_type, t.op_players, t.op_agents,
               t.started_at::DATE::VARCHAR, t.event,
               CASE WHEN g.team1_id = t.team_id THEN g.team2_name ELSE g.team1_name END AS opponent
        FROM team_rounds t JOIN games g USING (game_id)
        WHERE t.team_id = ? AND t.round_key IN (SELECT unnest(?))
        ORDER BY t.started_at DESC, t.round_no""", [team_id, keys]).fetchall()
    cols = ["round_key", "map", "round_no", "side", "economy", "won", "win_type", "op_players", "op_agents",
            "date", "event", "opponent"]
    page_rows = rows[page * page_size:(page + 1) * page_size]
    return envelope(dict(total=len(rows), which=which, rounds=[dict(zip(cols, r)) for r in page_rows]), f,
                    definitions=[f"{d.id}@v{d.version}"])


@app.get("/api/rounds/{round_key}")
def round_context(round_key: str):
    """Everything recorded in one round: result, loadouts, engagements, objectives."""
    r = con().execute("""SELECT round_key, map, round_no, winner_team_id, winner_side, win_type, duration_s,
                                planted, plant_t, event, started_at::DATE::VARCHAR, patch
                         FROM rounds WHERE round_key = ?""", [round_key]).fetchone()
    if not r:
        raise HTTPException(404, "Round not found")
    info = dict(zip(["round_key", "map", "round_no", "winner_team_id", "winner_side", "win_type", "duration_s",
                     "planted", "plant_t", "event", "date", "patch"], r))
    players = con().execute("""SELECT team_id, team_name, side, player_id, player_name, agent, items, economy
                               FROM player_rounds WHERE round_key = ? ORDER BY side, player_name""",
                            [round_key]).fetchall()
    events = con().execute("""SELECT kind, t_round, phase, weapon, att_name, att_side, vic_name, opening_kill
                              FROM engagements WHERE round_key = ? AND kind = 'kill' ORDER BY seq""",
                           [round_key]).fetchall()
    obj = con().execute("SELECT kind, t_round, player_id FROM objectives WHERE round_key = ? ORDER BY ts_ms",
                        [round_key]).fetchall()
    return envelope(dict(
        round=info,
        players=[dict(zip(["team_id", "team_name", "side", "player_id", "name", "agent", "items", "economy"], p))
                 for p in players],
        kills=[dict(zip(["kind", "t_round", "phase", "weapon", "attacker", "attacker_side", "victim", "opening"], e))
               for e in events],
        objectives=[dict(zip(["kind", "t_round", "player_id"], o)) for o in obj]))


@app.get("/api/maps/{name}.png")
def map_png(name: str, v: str | None = None):
    """The map image. `v` is the transform version the client is drawing with: if the map was
    rebuilt since, refuse rather than pair a new image with an old transform."""
    path = (MAPS_DIR / f"{name}.png").resolve()
    if path.parent != MAPS_DIR.resolve() or not path.exists():
        raise HTTPException(404, "No image for that map")
    if v is not None:
        cur = json.loads((MAPS_DIR / "maps.json").read_text()).get(name, {})
        if v != cur.get("transform_version"):
            raise HTTPException(409, "Map rebuilt since this page loaded")
    return FileResponse(path, media_type="image/png", headers={"Cache-Control": "no-cache"})
