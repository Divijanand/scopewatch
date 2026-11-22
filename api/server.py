"""Scopewatch API (engine v2). Every analytical response is an envelope:

    {data, coverage?, warnings, definition_versions, dataset_revision, parser_version, filter_hash}

Run from the repo root:  uvicorn api.server:app --port 8000
"""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from functools import lru_cache
from dataclasses import asdict

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import duckdb

from api import auth
from engine import vod
from engine.callouts import load as load_callouts
from engine.config import DB_PATH, MAPS_DIR
from engine.coverage import coverage
from engine.metrics import REGISTRY, Filters
from engine.metrics.operator import ENG_COLS, _op_engagements, spawns as _spawns
from engine.metrics.utility import agent_kit, layer_items
from engine import matchup
from engine import report

app = FastAPI(title="Scopewatch", version="2",
              # the hosted demo has no public API docs: everything is behind the judges' password
              docs_url=None if os.environ.get("SCOPEWATCH_REQUIRE_AUTH") == "1" else "/docs", redoc_url=None)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_methods=["GET", "PUT", "DELETE"])
AUTH_ON = auth.install(app)   # password protection for the hosted demo (api/auth.py)
_local = threading.local()

SIDE = Query(None, pattern="^(attacker|defender)$")
DATE = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$")
OP_METRICS = ["op.wpa", "op.possession_full_buy", "op.holder_share", "op.kill_timing", "op.opening",
              "op.win_association", "op.forwardness", "op.setups", "op.deaths",
              "op.gamble", "op.escapes", "op.how_it_dies", "att.executes", "util.recon_timing",
              "fights.dry_duels", "team.retakes", "team.post_plant", "team.economy", "team.openings",
              "team.closing",
              "team.predictability"]


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
    return _tendencies(team_id, map, side, since, until, player_id)


@lru_cache(maxsize=512)
def _tendencies(team_id, map, side, since, until, player_id):
    """The data is read-only while the server runs, so a report for the same filters is computed once.
    Restart the API after rebuilding the store or the WPA files."""
    f = filters(team_id, map, side, since, until, player_id)
    results, defs, warns = {}, [], []
    for mid in OP_METRICS:
        d, fn = REGISTRY[mid]
        r = fn(con(), f)
        results[mid] = r.to_dict(evidence_limit=0)
        defs.append(f"{d.id}@v{d.version}")
        warns += r.warnings
    summary, note = report.summarize(results, side)
    results["summary"] = summary
    results["summary_note"] = note
    cov = coverage(con(), f)
    return envelope(results, f, warnings=warns + cov["warnings"], definitions=defs, cov=cov)


@lru_cache(maxsize=128)
def _matchup(team_a, team_b, map, since, until):
    if team_a == team_b:
        raise HTTPException(422, "team_a and team_b must differ")

    filters(team_a, map, None, since, until)
    filters(team_b, map, None, since, until)

    a_name_row = con().execute("SELECT name FROM teams WHERE team_id = ?", [team_a]).fetchone()
    b_name_row = con().execute("SELECT name FROM teams WHERE team_id = ?", [team_b]).fetchone()
    a_name = a_name_row[0] if a_name_row else team_a
    b_name = b_name_row[0] if b_name_row else team_b

    a_att = _tendencies(team_a, map, "attacker", since, until, None)["data"]
    a_def = _tendencies(team_a, map, "defender", since, until, None)["data"]
    b_att = _tendencies(team_b, map, "attacker", since, until, None)["data"]
    b_def = _tendencies(team_b, map, "defender", since, until, None)["data"]

    h2h = matchup.head_to_head(con(), team_a, team_b, since=since, until=until, limit=10)
    return dict(
        team_a=dict(id=team_a, name=a_name),
        team_b=dict(id=team_b, name=b_name),
        map=map,
        pairs=matchup.facing_pairs(team_a, a_name, team_b, b_name, a_att, a_def, b_att, b_def),
        top=dict(a=matchup.top_lines(a_att, a_def), b=matchup.top_lines(b_att, b_def)),
        head_to_head=h2h,
        note="They haven't met in this data." if not h2h else None,
    )


@app.get("/api/matchup")
def api_matchup(team_a: str, team_b: str, map: str,
                since: str | None = DATE, until: str | None = DATE):
    return envelope(_matchup(team_a, team_b, map, since, until))


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


@app.get("/api/utility")
def utility_layer(team_id: str, map: str, side: str = Query("defender", pattern="^(attacker|defender)$"),
                  group: str = Query("setup", pattern="^(setup|damage|smoke|flash|recon|ultimate)$"),
                  agent: str | None = Query(None, max_length=40),
                  since: str | None = DATE, until: str | None = DATE, player_id: str | None = None,
                  limit: int = Query(4000, le=8000)):
    """Utility metric plus the map layer, for one layer (group) or one agent's whole kit (agent).
    Each point carries its ability's mode (engine/abilities.MODE), which says what its position means:
    placed/self/thrown = where the player stood; landing = where it hurt an enemy (fx/fy = the throw);
    direction = start of a wall or cone along the aim. Unplaced abilities are timing only."""
    f = filters(team_id, map, side, since, until, player_id)
    d, fn = REGISTRY["util.placements"]
    kit = agent_kit(con(), agent) if agent else None
    res = fn(con(), f, group=None if agent else group, agent=agent)
    items, _, _ = layer_items(con(), f, group=None if agent else group, agent_kit=kit)
    kind_of_mode = {"landing": "landing", "direction": "wall"}
    pts = [dict(round_key=it[0], ability=it[1], agent=it[2], player=it[3], t_round=it[4], x=it[5], y=it[6],
                callout=it[7], mode=it[8]["mode"], kind=kind_of_mode.get(it[8]["mode"], "cast"),
                low_rate=it[8].get("low_rate", False),
                vx=it[8].get("vx"), vy=it[8].get("vy"), fx=it[8].get("fx"), fy=it[8].get("fy"),
                from_callout=it[8].get("from_callout"), toward=it[8].get("toward"))
           for it in items]
    warns = res.warnings + ([f"Showing {limit} of {len(pts)} uses."] if len(pts) > limit else [])
    defs = [f"{d.id}@v{d.version}"]
    ults = None
    if group == "ultimate" and not agent:   # when each ult is used and what the 10 s after are worth
        ud, ufn = REGISTRY["ult.usage"]
        ur = ufn(con(), f)
        ults = ur.to_dict(evidence_limit=0)
        warns += ur.warnings
        defs.append(f"{ud.id}@v{ud.version}")
    return envelope(dict(layer="utility_by_ability_mode", group=None if agent else group, agent=agent, ults=ults,
                         result=res.to_dict(evidence_limit=0),
                         casts=pts[:limit], spawns={k: dict(x=v[0], y=v[1]) for k, v in _spawns(con(), map).items()}),
                    f, warnings=warns, definitions=defs)


@app.get("/api/evidence")
def evidence(metric: str, team_id: str, map: str | None = None, side: str | None = SIDE,
             since: str | None = DATE, until: str | None = DATE, player_id: str | None = None,
             which: str = Query("supporting", pattern="^(supporting|contrary)$"),
             bucket: str | None = None, group: str | None = Query(None, pattern="^(setup|damage|smoke|flash|recon|ultimate)$"),
             agent: str | None = Query(None, max_length=40),
             page: int = Query(0, ge=0), page_size: int = Query(25, le=100)):
    """The rounds behind a metric result, newest first, paginated."""
    if metric not in REGISTRY:
        raise HTTPException(404, "Unknown metric")
    f = filters(team_id, map, side, since, until, player_id)
    d, fn = REGISTRY[metric]
    if metric == "util.placements" and (group or agent):
        res = fn(con(), f, group=None if agent else group, agent=agent)
    else:
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
    page_rows = [dict(zip(cols, r)) for r in rows[page * page_size:(page + 1) * page_size]]
    for r in page_rows:
        r["game_id"] = r["round_key"].rsplit(":", 1)[0]
        r["vod"] = _vod_round(r["game_id"], r["round_no"])
    return envelope(dict(total=len(rows), which=which, rounds=page_rows), f,
                    definitions=[f"{d.id}@v{d.version}"])


# ------------------------------------------------------------------ VOD links (analyst notes, separate SQLite)
def _buy_ends(game_id: str) -> dict[int, int]:
    return dict(con().execute("SELECT round_no, freeze_end_ms FROM rounds WHERE game_id = ?", [game_id]).fetchall())


def _vod_game(game_id: str):
    url, syncs = vod.get(game_id)
    return url, syncs, vod.round_times(_buy_ends(game_id), syncs) if url else {}


def _vod_round(game_id: str, round_no: int):
    url, syncs, times = _vod_game(game_id)
    if not url:
        return None
    t = times.get(round_no)
    return dict(url=url, buy_end_s=t["buy_end_s"] if t else None, synced_at_round=t["synced_at_round"] if t else None)


class VodIn(BaseModel):
    url: str | None = None
    round_no: int | None = None
    vod_s: float | None = None


@app.get("/api/vod/{game_id}")
def vod_get(game_id: str):
    url, syncs, times = _vod_game(game_id)
    return envelope(dict(game_id=game_id, url=url, syncs=[dict(round_no=r, vod_s=s) for r, s in syncs],
                         rounds={str(k): v for k, v in times.items()}))


@app.put("/api/vod/{game_id}")
def vod_put(game_id: str, body: VodIn):
    if not _buy_ends(game_id):
        raise HTTPException(404, "Unknown game")
    try:
        vod.save(game_id, url=body.url, round_no=body.round_no, vod_s=body.vod_s)
    except ValueError as e:
        raise HTTPException(422, str(e))
    return vod_get(game_id)


@app.delete("/api/vod/{game_id}")
def vod_delete(game_id: str):
    vod.clear(game_id)
    return vod_get(game_id)


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
    game_id, round_no = round_key.rsplit(":", 1)
    return envelope(dict(
        round=info, game_id=game_id, vod=_vod_round(game_id, int(round_no)),
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


# ------------------------------------------------------------------ warm-up (hosted demo)
def _warm():
    """Precompute the reports judges are most likely to open first (Cloud9, every map they played, both
    sides), so the first click is fast on a small shared CPU. Runs in the background; failures are ignored."""
    try:
        teams = con().execute("""SELECT DISTINCT t.team_id, t.map FROM team_rounds t
                                 WHERE t.team_name ILIKE 'cloud9%' AND t.map IS NOT NULL""").fetchall()
        for team_id, map_name in teams:
            for side in ("defender", "attacker"):
                _tendencies(team_id, map_name, side, None, None, None)
    except Exception as e:  # noqa: BLE001 - warm-up must never take the server down
        print(f"warm-up stopped: {e}")


@app.on_event("startup")
def _start_warmup():
    if os.environ.get("SCOPEWATCH_WARM") == "1":
        threading.Thread(target=_warm, name="warmup", daemon=True).start()


# ------------------------------------------------------------------ the built web app (hosted demo)
# One service: the API above, and the built React app for every other path. Registered last, so /api wins.
WEB_DIST = Path(__file__).resolve().parent.parent / "web" / "dist"


@app.get("/robots.txt", include_in_schema=False)
def robots():
    return PlainTextResponse("User-agent: *\nDisallow: /\n")


if WEB_DIST.exists():
    app.mount("/", StaticFiles(directory=WEB_DIST, html=True), name="web")
