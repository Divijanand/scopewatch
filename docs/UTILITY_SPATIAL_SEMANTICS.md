# Spatial semantics

Each map layer means exactly one thing and has one label. Layers never share a legend.

| Layer | What it is | UI label | Status |
|---|---|---|---|
| Observed position | A player's position reported on a GRID event (2D) | "Where each shot was recorded" | In use (Operator sightlines) |
| Ability cast origin | Caster position at the moment of the cast (supplement, 3D) | "Ability cast origin" | Ingested; UI planned |
| Cast aim direction | Unit view vector at the cast | "Cast aim direction" | Ingested; UI planned |
| Interpolated origin | Position between two movement frames (`pos_source = interpolated`) | "Interpolated position" | Recorded per cast |
| Verified annotation | Analyst-entered endpoint with evidence | "Verified annotation" | Not built |
| Estimated endpoint | Output of an ability-specific, validated model | "Estimated endpoint" | Not built; no model planned without validation data |
| Event density | Aggregated event positions | "Event density" | Map outline only |
| Round occurrence | Whether a behaviour happened in an eligible round | "Rounds with …" | In use (all metrics) |

## Rules

- **An origin is never an endpoint.** No feed records where an ability lands (S5). A projected aim ray is an illustration and is never labelled as a landing.
- **Missing geometry stays missing.** `missing_both` casts keep `x = null`. They count toward timing and frequency, never toward maps.
- **Every cast records how its position was chosen.** `pos_source` (interpolated / frame_before / frame_after / missing_after / missing_before), `pos_dt_ms` (distance to the nearest real frame), `low_rate` (about 1 Hz sampling, VCT Americas 2025) and `spatial_ok` (within 500 ms, or 1,200 ms for low-rate series).
- **Low-rate series never look as precise as 5 Hz ones.** The coverage report counts them (`casts_low_rate`). A strict spatial view should exclude or mark them.
- **Use precise words.** Say observed, estimated, annotated, associated with, supported by. Never say "the exact landing", "always", "caused" or "tracks every tick".

Tests: `tests/test_ability_quality.py` (every quality state), `tests/test_map_transform.py`.
