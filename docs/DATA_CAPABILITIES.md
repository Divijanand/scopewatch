# Data capabilities

What the GRID VALORANT feeds and the ability supplement actually contain, as checked against records rather than documentation alone.

**States:** `supported` = field present and semantics checked on real records, with coverage measured. `partial` = present but limited. `unsupported` = not in the data. `not_inspected` = not yet checked.

**Evidence base:**
- **Probe:** series 2972936 (3 maps, 62 rounds).
- **Stratified sample audit:** 40 series covering every event, from `scripts/audit_sample.py` (output in git-ignored `cache/audit/`).
- **Full extraction:** 857 series.

## Round structure

| Capability | State | Evidence and notes |
|---|---|---|
| Map / game boundaries | supported | `series-started-game` … `series-ended-game`; abandoned attempts rolled back with `series-!started-game` (8 in the sample). Played games come from `meta/games.csv`. |
| Round boundaries | supported | `game-started-round`, `team-won-round`, `game-ended-round`. Rounds themselves can be rolled back: 22 `game-!started-round` and 15 `team-!won-round` in the sample. |
| Buy phase start / end | supported | `round-started-freezetime` / `round-ended-freezetime`, also reversible (`round-!…`). Timeouts appear as `freezetime-started-timeout`. |
| Round winner and side | supported | `team-won-round` actor state has team id and side. |
| Win type | partial | Target of `team-won-round` is the round, not a win condition; win type must be derived (elimination / spike / defuse / time) from events in the round. |
| Spike plant time and position | supported | 1,340 plants in the sample, all with planter position. |
| Defuse time | supported | `player-completed-defuseBomb`, plus begin/stop/checkpoint events. |

## Reversals ("!" events)

| Capability | State | Evidence and notes |
|---|---|---|
| Reversal matching | supported | Every reversal in the sample (548/548) matched an earlier event with the same type (minus `!`), actor id and target id. Reversed types include damage (160), kills (49), ability uses (166), pickups and drops, round start/end, freeze time and game start. |
| Current pipeline v1 | **gap** | v1 ignores reversals: reversed kills, hits and rounds are still counted. Engine v2 must undo them (LIFO per type/actor/target). The size of the effect on each metric still needs measuring once v2 exists. |

## Inventory and weapons

| Capability | State | Evidence and notes |
|---|---|---|
| Inventory at buy-phase end | supported | Full `inventory.items` per player on `round-ended-freezetime` (full-state event). This is *possession at the cutoff*, not purchase. |
| Purchase events | **unsupported** | No `player-purchased-item` events occur in the sample. Who *bought* a weapon cannot be told apart from who was *given* or *picked up* one before the cutoff. |
| Pickups / drops | partial | `player-pickedUp-item` / `player-dropped-item` exist; item id in target. The first examples are the spike; weapon pickups still need confirming (v2 audit). |
| Weapon used in a hit or kill | supported | Damage: actor round `damageDealtSources[].source.name`. Kill: actor round `weaponKills` keys. This is the weapon *used*, observed per event. |
| Equipped weapon at a moment | not_inspected | Inventory items carry `equipped`/`stashed` counts, not "weapon in hand". |
| Weapon instance identity | unsupported | No per-instance ids; analysis is at player/team level. |

## Positions

| Capability | State | Evidence and notes |
|---|---|---|
| Positions on events | supported | Actor and target `state.game.position` (2D) on damage, kill and other player events. |
| Continuous tracking | unsupported | Positions exist only at events. |
| Position freshness | partial | 31.4% of player-actor events repeat that player's previous xy exactly: genuinely stationary, or stale. A freshness flag is required before any time-occupancy analysis; event-anchored views ("where they fight from") are fine. |
| Spawn location | supported | Buy-phase-start positions are tight (spread about 2–3 m) and give spawn points; see DECISIONS D-005. |
| Height (z) | partial | Only in the ability supplement (3D). GRID feed positions are 2D. |
| Sample rate | partial | VCT Americas 2025 movement in the supplement is 1 Hz; elsewhere 5 Hz (S5). |

## Ability casts (supplement)

| Capability | State | Evidence and notes |
|---|---|---|
| Cast origin (3D) and aim | supported | 1.51M casts joined to played games. Probe series quality: 2,141 `ok`, 10 `gap_exceeded`. |
| Join to GRID events | supported | `grid_event_id` = GRID event id; 175/2,151 probe casts are supplement-only (`in_grid=false`, mostly buy-phase signatures). |
| Ability endpoint / landing | unsupported | Not in any feed (S5). A projected aim ray is an illustration, never a "landing". |
| Ability use reversals | supported | `player-!used-ability` occurs; v2 must drop reversed casts from the GRID side. |

## Identity

| Capability | State | Evidence and notes |
|---|---|---|
| Stable team / player ids | supported | String ids in feeds; `meta/teams.csv` holds earlier names. Two different teams can share a display name (S4), so ids are used everywhere. |
| Agent per player per round | supported | `character.id` in the full state at buy-phase end. |

## Not yet inspected

Assists, revives (`player-revived-player` exists), the semantics of `grid-invalidated-series` / `grid-validated-series` (13 and 11 in the sample), and pause/timeout effects on the round clock.
