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
