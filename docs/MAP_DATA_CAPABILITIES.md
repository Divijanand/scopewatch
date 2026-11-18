# Map data capabilities

States: `supported`, `partial`, `unsupported`, `not_inspected`. General data capabilities are in DATA_CAPABILITIES.md.

| Capability | State | Evidence and notes |
|---|---|---|
| Native player positions (2D) | supported | On damage, kill and other player events; 1.44M engagements, 0 without attacker position in the Lotus/Sentinels coverage check |
| Native cast positions (3D) + aim | supported | Supplement, 1.51M casts; quality policy in UTILITY_SPATIAL_SEMANTICS.md |
| Continuous movement | unsupported | Positions only at events; supplement frames only around casts |
| Uniform sampling | unsupported | 1 Hz for VCT Americas 2025 casts, 5 Hz elsewhere |
| Map bounds | supported | `map.bounds` in GRID game state, per map |
| Ready-to-use minimap images | unsupported | None in the corpus. We draw our own (MAP_ASSET_POLICY.md) |
| World→pixel transform | supported | Exact by construction for our outlines; versioned in `config/maps/` |
| Outline calibration | supported (12 maps) / partial (Summit) | Independent landmark check; MAP_CALIBRATION.md |
| Ability landing locations | unsupported | Not in any feed (S5) |
| Official callout polygons | unsupported | Not in the corpus; none used |
| Elevation (z) in GRID events | unsupported | Supplement only |
| Spawn locations | supported | Buy-phase-start positions (D-005) |
| Spike plant locations | supported | Planter position on every plant in the 40-series audit (1,340 of 1,340); used as calibration landmarks |
| Map version per game | partial | `patch` per game is known; outlines pool versions that share bounds |
