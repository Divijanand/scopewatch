"""Build the analytical DuckDB (cache/v2/scopewatch.duckdb) from canonical parquet + GRID meta.

Only games listed in meta/games.csv are kept (drops abandoned map attempts). Within-game
reversals were already undone at ingest.

Round key everywhere: game_id || ':' || round_no.

Usage: python -m engine.store
"""
from __future__ import annotations

import duckdb

from .config import DATA_DIR, DB_PATH, MANIFEST_PATH, RAW_DIR

RAW = RAW_DIR.as_posix()
META = (DATA_DIR / "meta").as_posix()
SERIES = (DATA_DIR / "val" / "series.csv").as_posix()


def raw(t):
    return f"read_parquet('{RAW}/{t}/*.parquet', union_by_name=true)"


SQL = f"""
CREATE OR REPLACE TABLE games AS
SELECT g.series_id, g.game_id, g.game_number::INT AS game_number, g.map, g.patch,
       g.started_at::TIMESTAMP AS started_at, g.winner_team_id,
       g.team1_id, g.team1_name, g.team2_id, g.team2_name, s.event, s.stage,
       (s.event ILIKE 'Game Changers%') AS game_changers
FROM read_csv_auto('{META}/games.csv', all_varchar=true) g
JOIN read_csv_auto('{SERIES}', all_varchar=true) s ON s.series_id = g.series_id
WHERE g.title = 'val';

CREATE OR REPLACE TABLE teams AS
SELECT team_id, name, other_names, series_count::INT AS series_count, first_seen, last_seen
FROM read_csv_auto('{META}/teams.csv', all_varchar=true) WHERE title = 'val';

CREATE OR REPLACE TABLE players AS
SELECT player_id, name, other_names, latest_team_id, latest_team_name
FROM read_csv_auto('{META}/players.csv', all_varchar=true) WHERE title = 'val';

CREATE OR REPLACE TABLE manifest AS SELECT * FROM read_parquet('{MANIFEST_PATH.as_posix()}');

-- player state at buy-phase end (possession at the cutoff)
CREATE OR REPLACE TABLE player_rounds AS
SELECT p.*, p.game_id || ':' || p.round_no AS round_key,
       (p.items LIKE '%operator%' OR p.items LIKE '%outlaw%') AS has_op,
       CASE WHEN p.items LIKE '%operator%' THEN 'operator' WHEN p.items LIKE '%outlaw%' THEN 'outlaw' END AS op_weapon,
       CASE WHEN p.team_loadout IS NULL THEN NULL
            WHEN p.team_loadout < 5000 THEN 'eco' WHEN p.team_loadout < 15000 THEN 'half' ELSE 'full' END AS economy,
       g.patch, g.event, g.started_at
FROM {raw('player_rounds')} p JOIN games g USING (game_id);

CREATE OR REPLACE TABLE objectives AS
SELECT o.*, o.game_id || ':' || o.round_no AS round_key FROM {raw('objectives')} o JOIN games g USING (game_id);

-- rounds with derived facts
CREATE OR REPLACE TABLE rounds AS
WITH obj AS (
  SELECT round_key, bool_or(kind = 'plant') planted, bool_or(kind = 'defuse') defused,
         bool_or(kind = 'detonate') detonated, min(t_round) FILTER (WHERE kind = 'plant') plant_t
  FROM objectives GROUP BY round_key)
SELECT r.series_id, r.game_id, r.map, r.round_no, r.game_id || ':' || r.round_no AS round_key,
       r.winner_team_id, r.winner_side, r.freeze_end_ms, r.plant_ms, r.end_ms,
       (r.end_ms - r.freeze_end_ms) / 1000.0 AS duration_s,
       coalesce(obj.planted, false) AS planted, obj.plant_t,
       CASE WHEN obj.defused THEN 'defuse' WHEN obj.detonated THEN 'detonation'
            ELSE 'elimination_or_time' END AS win_type,
       g.patch, g.event, g.started_at, g.team1_id, g.team2_id
FROM {raw('rounds')} r JOIN games g USING (game_id) LEFT JOIN obj ON obj.round_key = r.game_id || ':' || r.round_no;

-- one row per round x team. inventory_known=false when no buy-phase-end snapshot exists for that team.
CREATE OR REPLACE TABLE team_rounds AS
WITH teams_in_round AS (
  SELECT r.*, unnest([r.team1_id, r.team2_id]) AS team_id FROM rounds r),
inv AS (
  SELECT round_key, team_id, any_value(team_name) team_name, any_value(side) side,
         any_value(economy) economy, any_value(team_loadout) team_loadout, count(*) n_players,
         count(*) FILTER (WHERE has_op) n_op,
         list(player_id ORDER BY player_id) FILTER (WHERE has_op) op_player_ids,
         list(player_name ORDER BY player_id) FILTER (WHERE has_op) op_players,
         list(agent ORDER BY player_id) FILTER (WHERE has_op) op_agents
  FROM player_rounds GROUP BY round_key, team_id)
SELECT t.round_key, t.series_id, t.game_id, t.map, t.round_no, t.team_id,
       coalesce(i.team_name, tm.name) AS team_name,
       coalesce(i.side, CASE WHEN t.winner_team_id = t.team_id THEN t.winner_side
                             WHEN t.winner_side = 'attacker' THEN 'defender' ELSE 'attacker' END) AS side,
       i.economy, i.team_loadout, (i.round_key IS NOT NULL) AS inventory_known,
       coalesce(i.n_op, 0) AS n_op, i.op_player_ids, i.op_players, i.op_agents,
       (t.winner_team_id = t.team_id) AS won, t.win_type, t.planted, t.patch, t.event, t.started_at
FROM teams_in_round t
LEFT JOIN inv i ON i.round_key = t.round_key AND i.team_id = t.team_id
LEFT JOIN teams tm ON tm.team_id = t.team_id;

-- engagements with attacker context and opening-kill flag
CREATE OR REPLACE TABLE engagements AS
WITH e AS (
  SELECT e.*, e.game_id || ':' || e.round_no AS round_key FROM {raw('engagements')} e JOIN games g USING (game_id)),
k AS (
  SELECT event_id, row_number() OVER (PARTITION BY round_key ORDER BY seq) AS kill_order
  FROM e WHERE kind = 'kill' AND phase IN ('pre_plant', 'post_plant'))
SELECT e.*, k.kill_order, (k.kill_order = 1) AS opening_kill,
       p.agent AS att_agent, p.has_op AS att_had_op, p.economy AS att_economy,
       g.patch, g.event, g.started_at
FROM e JOIN games g USING (game_id)
LEFT JOIN k USING (event_id)
LEFT JOIN player_rounds p ON p.round_key = e.round_key AND p.player_id = e.att_id;

CREATE OR REPLACE TABLE casts AS
SELECT c.*, c.game_id || ':' || c.round_no AS round_key, g.patch, g.event, g.started_at
FROM {raw('casts')} c JOIN games g USING (game_id);

CREATE OR REPLACE TABLE inventory_events AS
SELECT i.*, i.game_id || ':' || i.round_no AS round_key FROM {raw('inventory_events')} i JOIN games g USING (game_id);

-- spawn per map & side: median buy-phase-start position (docs/DECISIONS.md D-005)
CREATE OR REPLACE TABLE spawns AS
SELECT s.map, s.side, median(s.x) x, median(s.y) y, count(*) n
FROM {raw('spawns')} s JOIN games g USING (game_id)
WHERE s.side IS NOT NULL GROUP BY s.map, s.side;

-- provenance comes from what was actually ingested (the manifest), not from the current config
CREATE OR REPLACE TABLE build_info AS
SELECT string_agg(DISTINCT dataset_revision, ',') AS dataset_revision,
       string_agg(DISTINCT parser_version, ',') AS parser_version,
       now() AS built_at
FROM manifest WHERE status = 'ok';
"""


def main():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(DB_PATH.as_posix())
    con.execute(SQL)
    for t in ("games", "rounds", "team_rounds", "player_rounds", "engagements", "casts", "objectives",
              "inventory_events", "spawns", "manifest"):
        print(f"{t:17s} {con.execute(f'SELECT count(*) FROM {t}').fetchone()[0]:>10,}")
    con.close()


if __name__ == "__main__":
    main()
