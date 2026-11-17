"""Build cache/scopewatch.duckdb from the extracted parquet tables + GRID meta CSVs.

Only games listed in meta/games.csv are kept: that drops maps GRID rolled back
(restarted after technical issues), so nothing is double-counted.

Tables:
  games        played VALORANT maps with patch, event, date, teams
  teams        team id -> current name
  loadouts     per player per round (buy-phase end), + has_op flag and team economy bucket
  rounds       per round winner
  engagements  damage/kill events, + attacker agent and has_op context
  op_rounds    one row per (round, team): who held an Operator/Outlaw, did the team win
  op_eng       engagements fired with an Operator/Outlaw, with time bucket
  casts        ability casts (precise 3D position + aim)

Usage: python -m pipeline.build
"""
from __future__ import annotations

import duckdb

from .config import DATA_DIR, RAW_DIR, DB_PATH

RAW = RAW_DIR.as_posix()
META = (DATA_DIR / "meta").as_posix()
SERIES = (DATA_DIR / "val" / "series.csv").as_posix()

SQL = f"""
CREATE OR REPLACE TABLE games AS
SELECT g.series_id::VARCHAR AS series_id, g.game_id, g.game_number, g.map, g.patch::VARCHAR AS patch,
       g.started_at::TIMESTAMP AS started_at, g.winner_team_id::VARCHAR AS winner_team_id,
       g.team1_id::VARCHAR AS team1_id, g.team1_name, g.team2_id::VARCHAR AS team2_id, g.team2_name,
       s.event, s.stage
FROM read_csv_auto('{META}/games.csv', all_varchar=true) g
JOIN read_csv_auto('{SERIES}', all_varchar=true) s ON s.series_id = g.series_id
WHERE g.title = 'val';

CREATE OR REPLACE TABLE teams AS
SELECT team_id::VARCHAR AS team_id, name, other_names, series_count::INT AS series_count, last_seen
FROM read_csv_auto('{META}/teams.csv', all_varchar=true) WHERE title = 'val';

CREATE OR REPLACE TABLE players AS
SELECT player_id::VARCHAR AS player_id, name, latest_team_id::VARCHAR AS latest_team_id, latest_team_name
FROM read_csv_auto('{META}/players.csv', all_varchar=true) WHERE title = 'val';

CREATE OR REPLACE TABLE loadouts AS
SELECT l.*,
       (l.items LIKE '%operator%' OR l.items LIKE '%outlaw%') AS has_op,
       CASE WHEN l.items LIKE '%operator%' THEN 'operator'
            WHEN l.items LIKE '%outlaw%' THEN 'outlaw' END AS op_weapon,
       CASE WHEN l.team_loadout < 5000 THEN 'eco'
            WHEN l.team_loadout < 15000 THEN 'half'
            ELSE 'full' END AS economy,
       g.patch, g.event, g.started_at
FROM read_parquet('{RAW}/loadouts/*.parquet', union_by_name=true) l
JOIN games g USING (game_id);

CREATE OR REPLACE TABLE rounds AS
SELECT r.* FROM read_parquet('{RAW}/rounds/*.parquet', union_by_name=true) r
JOIN games g USING (game_id);

CREATE OR REPLACE TABLE engagements AS
SELECT e.*, l.agent AS att_agent, l.has_op AS att_has_op, l.economy AS att_economy,
       g.patch, g.event, g.started_at
FROM read_parquet('{RAW}/engagements/*.parquet', union_by_name=true) e
JOIN games g USING (game_id)
LEFT JOIN loadouts l
  ON l.game_id = e.game_id AND l.round_no = e.round_no AND l.player_id = e.att_id;

CREATE OR REPLACE TABLE casts AS
SELECT c.*, g.patch, g.event, g.started_at
FROM read_parquet('{RAW}/casts/*.parquet', union_by_name=true) c
JOIN games g USING (game_id);

-- one row per (round, team): who (if anyone) carried a long rifle, and the result
CREATE OR REPLACE TABLE op_rounds AS
WITH t AS (
  SELECT series_id, game_id, map, round_no, team_id, any_value(team_name) AS team_name,
         any_value(side) AS side, any_value(economy) AS economy, any_value(team_loadout) AS team_loadout,
         any_value(patch) AS patch, any_value(event) AS event, any_value(started_at) AS started_at,
         count(*) FILTER (WHERE has_op) AS n_op,
         list(player_id) FILTER (WHERE has_op) AS op_player_ids,
         list(player_name) FILTER (WHERE has_op) AS op_players,
         list(agent) FILTER (WHERE has_op) AS op_agents,
         list(op_weapon) FILTER (WHERE has_op) AS op_weapons
  FROM loadouts GROUP BY ALL
)
SELECT t.*, (r.winner_team_id = t.team_id) AS won
FROM t LEFT JOIN rounds r USING (game_id, round_no);

-- engagements fired with an Operator/Outlaw
CREATE OR REPLACE TABLE op_eng AS
SELECT *,
       CASE WHEN t_round < 20 THEN '0-20s'
            WHEN t_round < 40 THEN '20-40s'
            WHEN t_round < 60 THEN '40-60s'
            ELSE '60s+' END AS t_bucket,
       row_number() OVER (PARTITION BY game_id, round_no, att_team ORDER BY ts_ms) AS nth_for_team
FROM engagements
WHERE weapon IN ('operator', 'outlaw');
"""


def main():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(DB_PATH.as_posix())
    con.execute(SQL)
    for t in ("games", "teams", "loadouts", "rounds", "engagements", "casts", "op_rounds", "op_eng"):
        print(f"{t:12s} {con.execute(f'SELECT count(*) FROM {t}').fetchone()[0]:>10,}")
    con.close()


if __name__ == "__main__":
    main()
