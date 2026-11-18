"""Typed schemas for the canonical tables the ingest writes (one parquet per series per table).

Nullable means "not observed", never zero. Every row keeps the GRID event id that produced it
(`event_id`) so any number can be traced back to source observations.
"""
import pyarrow as pa

S, I, F, B, T = pa.string(), pa.int32(), pa.float64(), pa.bool_(), pa.int64()

KEY = [("series_id", S), ("game_id", S), ("map", S), ("round_no", I)]


def _schema(*fields):
    return pa.schema([pa.field(n, t) for n, t in fields])


SCHEMAS = {
    # round clock: one row per round attempt that reached buy-phase end
    "round_clock": _schema(*KEY, ("round_start_ms", T), ("freeze_end_ms", T), ("event_id", S)),
    # round result
    "rounds": _schema(*KEY, ("winner_team_id", S), ("winner_side", S), ("freeze_end_ms", T),
                      ("plant_ms", T), ("end_ms", T), ("event_id", S)),
    # everyone's position when the buy phase starts (spawn)
    "spawns": _schema(*KEY, ("team_id", S), ("side", S), ("player_id", S), ("x", F), ("y", F), ("event_id", S)),
    # player state at buy-phase end: possession at the cutoff, not purchase (no purchase events exist)
    "player_rounds": _schema(*KEY, ("team_id", S), ("team_name", S), ("side", S), ("team_money", T),
                             ("team_loadout", T), ("player_id", S), ("player_name", S), ("agent", S),
                             ("money", T), ("loadout_value", T), ("items", S), ("x", F), ("y", F),
                             ("freeze_end_ms", T), ("event_id", S)),
    # damage and kills; positions are the post-event state reported on that event
    "engagements": _schema(*KEY, ("event_id", S), ("seq", T), ("kind", S), ("ts_ms", T), ("t_round", F),
                           ("t_plant", F), ("phase", S), ("weapon", S), ("damage", F), ("hit", S),
                           ("att_id", S), ("att_name", S), ("att_team", S), ("att_side", S),
                           ("att_x", F), ("att_y", F), ("att_pos_repeat", B),
                           ("vic_id", S), ("vic_name", S), ("vic_team", S), ("vic_side", S),
                           ("vic_x", F), ("vic_y", F), ("vic_pos_repeat", B)),
    # spike plant / defuse / detonation
    "objectives": _schema(*KEY, ("event_id", S), ("kind", S), ("ts_ms", T), ("t_round", F),
                          ("player_id", S), ("team_id", S), ("x", F), ("y", F)),
    # item pickups and drops during play
    "inventory_events": _schema(*KEY, ("event_id", S), ("kind", S), ("ts_ms", T), ("t_round", F),
                                ("player_id", S), ("team_id", S), ("item", S)),
    # ability casts from the supplement, with our quality decision
    "casts": _schema(*KEY, ("grid_event_id", S), ("in_grid", B), ("ts_ms", T), ("t_round", F), ("t_plant", F),
                     ("phase", S), ("player_id", S), ("team_id", S), ("side", S), ("agent", S),
                     ("ability", S), ("slot", S), ("quality", S), ("pos_source", S), ("pos_dt_ms", F),
                     ("low_rate", B), ("spatial_ok", B),
                     ("x", F), ("y", F), ("z", F), ("vx", F), ("vy", F), ("vz", F)),
}

MANIFEST = _schema(
    ("series_id", S), ("feed_sha1", S), ("supp_sha1", S), ("parser_version", S), ("dataset_revision", S),
    ("status", S), ("error", S), ("seconds", F), ("ingested_at", S), ("counts_json", S),
)
