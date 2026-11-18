# Decisions

Consequential choices and the evidence behind them. Newest last.

## D-001: First scouting branch is Operator tendencies (2026-11-17)

**Decision:** Build the Operator profiler first; utility origins second, reusing the same data layer.

**Evidence:** The probe of series 2972936 (Cloud9 GC vs HIMMERS) showed full inventory at buy-phase end on every round (28/62 rounds with an Operator or Outlaw) and shooter + victim positions on every damage and kill event. The full corpus extraction produced 29,419 Operator/Outlaw engagements across 857 series. The ability supplement is also strong (1.5M casts, mostly `ok` quality), so utility is a viable second branch, not a fallback.

## D-002: Draw maps from data instead of using map art (2026-11-17)

**Decision:** Generate each map's floor plan from the density of observed positions (50 cm bins, smoothed, thresholded, walls kept as holes).

**Why:** No permitted, provenance-clear minimap source is bundled with the corpus. And because outlines come from the *same coordinate system* as the events, calibration is identity by construction: no affine fit, no axis-swap risk. What still needs checking is that the outline is complete and that known landmarks land where they should (see `VALIDATION.md`).

**Limit:** Elevated or overlapping areas collapse into one 2D projection.

## D-003: Judged demo sits behind a login, not on an open website (2026-11-17)

**Decision:** No public, open hosting of anything served from the data. The hosted demo for judges (if any) requires credentials given in the submission's testing instructions.

**Evidence:** Data license §3(a) forbids making the Data "or any part or derivative of it available to any third party … including … website", and §4(b) permits showing project outputs to judges and organizers. Official rules allow login credentials for private projects. The open-source repo contains code only; the corpus loads from the official repository (§4(b)).

## D-004: Round clock starts when the buy phase ends (2026-11-17)

**Decision:** `t_round = event time − round-ended-freezetime time`. Events during the buy phase get negative values.

**Why:** Freeze-end is the moment both teams can act, so "a 15 s peek" means the same thing in every round. Round-start-based clocks would shift with buy-phase length, and overtime or timeout buy phases differ.

## D-005: Spawns come from buy-phase start, not end (2026-11-17)

**Decision:** A spawn point is the median of everyone's position at `round-started-freezetime`.

**Evidence:** Series 2972936: at buy-phase start, the attacker spread is about 210 × 110 cm and the defender spread about 280 × 160 cm. At buy-phase end, defenders spread about 3.8 × 1.3 m because they walk onto sites during buy. The first implementation used buy-phase-end positions and put both spawns mid-map; that's fixed.

## D-006: Economy buckets from team loadout value (2026-11-17)

**Decision:** At buy-phase end, team loadout < 5,000 = eco, < 15,000 = half, otherwise full.

**Evidence:** Corpus team-loadout quantiles (10/25/50/75/90%) = 4,250 / 14,300 / 23,700 / 27,800 / 29,150. Operator rate by bucket: eco 0.2%, half 3.8%, full 28.5%. These are transparent loadout categories, not claims about intent (spec §10.4); "force buy" is not labelled.

## D-007: In-game reversals undone with an undo stack; feed markers stay off it (2026-11-17)

**Decision:** Every applied event is pushed with a state snapshot. A `!` event pops the latest event with the same type, actor id and target id, voids its rows, and restores state when it was the top of the stack. `grid-*` events (`grid-invalidated-series`, `grid-validated-series`, …) are counted but never pushed.

**Evidence:** In series 2787782 a map restart unwinds `team-won-round` → clock → buy end → buy start → round start → game start in exact reverse order. In the first full v2 run, 6,086 of 15,712 reversals looked non-LIFO. In every case inspected (series 2938651, 1,263 of 1,263), exactly one event sat above the match: the `grid-invalidated-series` marker GRID emits just before unwinding. With markers off the stack, that series unwinds 1,263 of 1,263 LIFO. The corpus has 0 unmatched reversals. Regression test: `test_invalidation_marker_does_not_break_lifo_unwind`.

## D-008: Map density stored per series (2026-11-17)

**Decision:** Each series writes its own density grid (`cache/v2/raw/density/{series}.npz`); `engine.maps` sums them.

**Why:** The first version merged grids across runs, so an incremental re-ingest double-counted positions. Per-series files make re-ingest replace, never add. Only casts that pass the quality policy add points.

## D-009: Real minimaps with the community calibration replace the drawn outlines (2026-11-18)

**Decision:** The map view uses the in-game minimaps and world→minimap numbers from valorant-api.com (`engine/minimaps.py`), recoloured to our palette. The data-drawn outline (D-002) stays as a fallback for any map without a minimap.

**Why:** A coach who knows the maps couldn't read the drawn outline. It was blobby, and it was rotated 90° from the in-game minimap, because the minimap puts game y on the horizontal axis and the outline put game x there. Every fight looked wrong even when the data was right.

**Evidence:** GRID positions are native game units, so the community transform applies unchanged. Spike plants land on the minimap floor 98.5–100% of the time on every map, and buy-phase spawns 99.2–100%. With the axes not swapped, plants land on the floor 0–72%. Summit, which failed with the drawn outline, now validates. Kill lines with a clear path on the minimap (≤2 of 60 samples on transparent pixels): 85% of all kills on Lotus, 88% on Ascent and Haven. The rest are mostly boxes and objects that are transparent on the minimap, plus wallbangs.

**Trade-off:** It's Riot artwork via an unofficial host. The images are fetched into git-ignored `cache/` and never committed. Every map is checked against independent landmarks on each build.

## D-010: Findings in callout language: nearest reachable community callout (2026-11-18)

**Decision:** Every engagement position gets the name of its nearest community callout anchor (valorant-api.com `callouts`, 17–28 per map) that it can reach in a straight line on the minimap floor, within 25 m (`engine/callouts.py`). Two metrics use this. `op.setups` gives the callout of each round's first Operator shot, with a league share. `op.deaths` gives where the Operator holder dies, and from where.

**Why:** A coach reads "first Operator shot from A Stairs into A Main, 4 of 24 rounds", not a cloud of lines. The map becomes the evidence for a sentence, not the product.

**Evidence:** 98.9–99.99% of distinct positions per map get a name, with a median 6.6–11.4 m to the anchor. The reachability rule stops a player behind a wall being named after the room on the other side (`test_wall_sends_the_name_to_the_reachable_anchor`).

**Limits:** Anchors are points, not areas, so names near the boundary between two callouts are approximate. The UI says "nearest community callout". The first shot is where the rifle fought, which isn't always where it set up.

## D-011: VOD links from one analyst sync per map (2026-11-18)

**Decision:** The analyst pastes a VOD link for a map and types the VOD time at which one round's buy phase ends. Every round and every kill in that map then gets a "watch at" link, opening 5 s early (`engine/vod.py`). Edited VODs drift, so the analyst can re-time at any round, and each round uses the nearest earlier sync.

**Why:** Finding the rounds is the slowest part of prep. Each claim already lists its rounds, so this turns the list into a watch list.

**How:** GRID event times are wall clock, so `vod_time = sync + (buy_end[round] − buy_end[sync round])`, and `event = round buy end + t_round`. A live broadcast VOD runs in real time, so one sync holds for the whole map. YouTube and Twitch links open at the second; other hosts show the time to skip to.

**Storage:** Links live in `cache/v2/user.sqlite` (git-ignored), separate from the analytical store: they're the analyst's notes, not GRID data. Only http(s) links are accepted.

## D-012: The Operator as a gamble: payoff, escapes, how it's broken (2026-11-18)

**Decision:** Three metrics (`engine/metrics/gamble.py`):
- `op.gamble`: per holder round, kept / got a kill then died / died without an Operator kill, with round win rate per outcome and a league share. "Enemy fired it after" means an enemy who had no Operator at buy end fired one after the holder's death.
- `op.escapes`: after each Operator kill, whether the shooter cast a movement ability from 1 s before to 4 s after, and whether they died within 5 s. Shown per agent.
- `op.how_it_dies`: holder deaths preceded by an enemy flash or stun, or a smoke, cast within 35 m in the 4 s before; deaths where two or more enemies hit the holder in 3 s; or none of these (a straight duel).

**Why:** An analyst's framing: the Operator is a glass cannon. It pays off only if it earns kills and survives. Mobile agents carry it so they can shoot and leave. It gets broken by utility and coordinated takes.

**Limits:** The feed records casts (who, when, from where, aim), never landings or who was blinded, so utility is "associated with", not "caused". The feed has no weapon pickups, so a stolen Operator is seen only when the enemy fires it. Ability classes are in `engine/abilities.py`.

## D-013: Site executes on attack, and how defending Operators fare against them (2026-11-18)

**Decision:** `att.executes` describes how a team takes each site on one map (`engine/metrics/executes.py`):
- **Site:** the nearest site callout to the plant position.
- **Share:** how often they plant there, against the league share.
- **Pace:** by plant time.
- **Site entry:** when and where the first fight in that site's own callouts happens. An early pick elsewhere is excluded.
- **Utility:** abilities the attackers cast in the 25 s before the plant, per round and by ability.
- **Against an Operator:** in rounds where a defender held an Operator, whether it got a kill or died without one.

**Why:** It answers an analyst's question: how do you set up an Operator against this team's A execute? You get when and where they arrive, what utility they bring, and how Operators have fared against it.

**Evidence:** Every plant in the corpus gets a site. On Lotus, plants split A 2,004 / C 1,965 / B 986.

**Limits:** Rounds without a plant have no site (35 of 155 for Cloud9 on Lotus attack). Utility is the cast, not the landing. "Against an Operator" is small per team and site, so it's labelled with its count.
