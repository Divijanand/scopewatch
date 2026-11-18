"""What the selected filters can support: sample, dates, patches, data quality, exclusions."""
from __future__ import annotations

import json

from .metrics.core import Filters


def coverage(con, f: Filters) -> dict:
    w, p = f.where("t")
    r = con.execute(f"""
        SELECT count(*), count(*) FILTER (WHERE inventory_known), count(DISTINCT game_id), count(DISTINCT series_id),
               min(started_at)::DATE::VARCHAR, max(started_at)::DATE::VARCHAR,
               list(DISTINCT patch ORDER BY patch), list(DISTINCT event ORDER BY event)
        FROM team_rounds t WHERE {w}""", p).fetchone()
    ew, ep = f.where("e", team_col="att_team", side_col="att_side")
    e = con.execute(f"""
        SELECT count(*), count(*) FILTER (WHERE att_x IS NULL), count(*) FILTER (WHERE att_pos_repeat)
        FROM engagements e WHERE {ew} AND phase IN ('pre_plant','post_plant')""", ep).fetchone()
    cw, cp = f.where("c")
    c = con.execute(f"""
        SELECT count(*), count(*) FILTER (WHERE spatial_ok), count(*) FILTER (WHERE low_rate)
        FROM casts c WHERE {cw}""", cp).fetchone()
    # reversals undone at ingest for the series in scope
    sids = [s for (s,) in con.execute(f"SELECT DISTINCT series_id FROM team_rounds t WHERE {w}", p).fetchall()]
    voided = 0
    if sids:
        for (cj,) in con.execute("SELECT counts_json FROM manifest WHERE series_id IN (SELECT unnest(?))",
                                 [sids]).fetchall():
            cnt = json.loads(cj)
            voided += sum(v for k, v in cnt.items() if k.startswith("rows_voided."))
    warnings = []
    if r[0] and len(r[6] or []) > 3:
        warnings.append(f"Spans {len(r[6])} patches. Narrow the date range if the meta changed.")
    if r[2] and r[2] < 3:
        warnings.append("Fewer than 3 maps: treat every pattern as a hint.")
    return dict(
        rounds=r[0], rounds_inventory_known=r[1], rounds_inventory_unknown=r[0] - r[1],
        maps=r[2], series=r[3], first_date=r[4], last_date=r[5], patches=r[6] or [], events=r[7] or [],
        engagements=e[0], engagements_no_position=e[1], engagements_position_repeat=e[2],
        casts=c[0], casts_spatial_ok=c[1], casts_low_rate=c[2],
        rows_voided_by_reversals=voided, warnings=warnings,
    )
