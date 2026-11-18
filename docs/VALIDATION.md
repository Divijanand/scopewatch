# Validation

Checks that were actually run and what they showed. Dataset commit `496fa7f`, parser 2.0.1, run on 2026-11-17.

## Automated tests (70 passing)

`python -m pytest tests`. The fixtures are synthetic: invented teams, players and coordinates in GRID's documented shape, never extracts of the corpus.

| Area | Tests |
|---|---|
| Round clock | Measured from buy-phase end; buy-phase events have no clock and `phase=buy` |
| Reversals | A reversed kill is voided; a full round rollback restores state and drops every row from the first attempt; an invalidation marker doesn't break LIFO unwinding; a reversed marker isn't "unmatched"; a truly unmatched reversal is counted, not guessed |
| Phases | Plant splits pre/post-plant and sets the plant clock; kills after the round result are `post_round` |
| Identity | Side swap read from state each round; two teams with the same display name stay separate by id |
| Inventory | Possession is the inventory at the cutoff |
| Positions | Repeat flag set only when a player's xy equals their previous one |
| Casts | Joined to rounds by round start (buy-phase casts get negative clocks); reversed-in-GRID casts excluded; `gap_exceeded` uses the closer real frame; no-geometry casts kept for counts but never mapped |
| Ingest IO | Malformed lines are quarantined, not fatal |
| Map transform | Corners and y-flip; round trip preserves native coordinates; missing geometry stays null; out-of-bounds detected; affine fit recovers a rotated image with zero holdout error; collinear landmarks rejected; minimap calibration swaps axes |
| Ability quality | Every supplement quality state gets an explicit decision; `missing_both` never becomes 0,0; 1 Hz series detected |
| Weapon backfill | A weaponless kill takes the weapon of the same attacker's hit on the same victim within 50 ms; 200 ms apart or another attacker doesn't match; known weapons untouched; idempotent |
| Tour de Force | Counts as a sniper kill, never as a picked-up Operator |
| Agent kits | One agent's kit is shown by mode; unplaced abilities never drawn; denominator is rounds with that agent |
| Rankings | Ties broken by name, independent of the order rows arrive |
| Operator value (Junie) | WPA logic on a stub model; registry includes every report metric; bootstrap determinism; metric on hand-built holder rounds |
| Utility setups | Rounds counted per ability and callout (two traps in one round count once); unplaced casts reported as unknown; post-round casts and other teams ignored; smokes kept apart from setups; needs a map and side |
| Win-probability model (Junie) | Feature building on a synthetic round; series split has no overlap; a 5v1 ranks above a 1v5 |
| Site executes | Plant → site; site entry ignores an early pick elsewhere and uses the attacker's own callout; only attacker utility in the 25 s before the plant counts; a defending Operator that died without a kill is counted; the defense view is empty and adds no warning |
| VOD timing | One sync places every round (before and after it); the nearest earlier sync wins for edited VODs; no sync means no times; only http(s) links; negative times rejected; re-time replaces |
| Operator gamble | Kept / traded / lost and stolen on hand-built rounds; a movement cast near the kill and death within 5 s; a nearby flash plus two shooters counts as blinded and swarmed, a flash 90 m away doesn't |
| Callouts | Names read like comms; nearest anchor; a wall sends the name to the reachable anchor; far or missing positions stay unnamed; setups count the first Operator shot per round (hit then kill within 1 s counts as a kill), report unnamed rounds as unknown, and need a map and side; holder deaths |
| Metrics | n/N, unknowns and evidence reconcile exactly on hand-built tables for possession, holders and possession shift, kill timing, opening duels and win association; Wilson bounds |

## Full-corpus ingest reconciliation

`python -m scripts.reconcile_v1_v2`

| Check | Result |
|---|---|
| Series ingested | 857 ok / 0 failed |
| Events read | 3,494,416 |
| Malformed lines quarantined | 0 feed, 0 supplement |
| Data reversals | 15,622, all LIFO; 0 non-LIFO; 0 unmatched |
| Marker retractions (`grid-!…`) | 90, in 6 series; counted separately |
| Rows voided by reversals | engagements 5,629; player-rounds 3,096; spawns 4,431; inventory events 962; round clocks 309; rounds 253; objectives 138 |
| Casts excluded (reversed in GRID) | 5,244 of 1,516,833 |
| Casts without a round | 251 (before a game's first round) |
| Effect against v1 | rounds −253 (−0.59%), kills −1,179 (−0.40%), Operator/Outlaw kills −43 (−0.31%) |

**History:** the first v2 run reported 6,086 non-LIFO reversals. Inspection showed a `grid-invalidated-series` marker sitting above each match (D-007). Taking markers off the stack made every reversal LIFO, and voided-row counts didn't change.

## Spatial checks

| Check | Result |
|---|---|
| Map transform | In-game minimaps with the community calibration (D-009). The axis-swapped transform puts 98.5–100% of plants on the floor; unswapped, 0–72% |
| Spawns | Buy-phase-start positions are tight (spread about 1–3 m in the probe series) and sit at opposite ends of each map. Visual check: Lotus attacker spawn at the left map edge |
| Outline shape | Haven shows its three lanes, courtyard and walls (visual check) |
| Landmark calibration | 13 of 13 maps validated on the minimaps (plants 98.46–100%, spawns 99.2–100%). Details: MAP_CALIBRATION.md |
| Position freshness | A player's position changes between events more than 5 s apart in 99.96% of cases; events in the same millisecond (damage then kill) share a position |
| Kill lines | On the minimap, 85–88% of kills (Lotus, Ascent, Haven) have a clear path; the rest mostly cross boxes that are transparent on the minimap, or are wallbangs |

## Manual trace: finding → rounds → source

Cloud9, Lotus, defense:
- **UI:** "OXY has it in 80% of their Operator rounds (12 of 15)".
- **Evidence drawer:** lists exactly 12 rounds for OXY and 3 for "someone else".
- **Round 30 vs FURIA (2025-04-12, VCT Americas Stage 1):** OXY on Neon takes the round's first kill with the Operator at 24.2 s and another at 86.0 s, and defense wins after 91 s.

The timeline and inventory come straight from `player_rounds` and `engagements` for that round key.

## Performance (2026-11-17, laptop, 12 logical cores, other apps open, no ingest running)

| Call | Time |
|---|---|
| `/api/weapons/tendencies` (6 metrics + coverage), three teams, cold and warm | 0.36–0.48 s |
| `/api/spatial/operator` | 0.24 s |
| `/api/evidence` | 0.26 s |
| Full ingest, 10 workers | 1,118 s (18.6 min) |

## Known open items

- 123 kills still have no weapon (no matching damage event); Headhunter kills can't be told apart.
- No Playwright journey test yet.
- No usability check with a coach. None is claimed.
