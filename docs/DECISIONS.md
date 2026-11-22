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

## D-014: Utility setups from cast positions, named by callout (2026-11-18)

**Decision:** The Utility view shows where a team uses each ability on one map and side (`util.placements`, `/api/utility`). There are four layers: setups (Cypher, Killjoy, Chamber, Vyse, Deadlock and Sage placeables), smokes, flashes and stuns, and recon. Each cast is drawn at the caster's position with an aim tick, and named with the nearest reachable callout. Findings count **rounds**, not casts: "Cyber Cage at C Site in 27 of 62 defense rounds".

**Why:** It's the brief's first blueprint for this category (placeables first), and it produces exactly the kind of claim the brief asks for.

**Evidence:** Setups are where cast position is most meaningful. 83% of trapwires, 85% of Chamber trademarks and 87% of Vyse Shears are placed in the buy phase, and 100% of placeable casts pass the position-quality policy.

**Limits:** Thrown utility (Omen and Brimstone smokes, flashes, recon) lands somewhere else, and the feed doesn't record where. Those layers say "used from", and the UI says so. Casts after the round result are left out. Lower-rate (1 Hz) positions are drawn dashed.

## D-015: Each utility layer shows the position that means something (2026-11-18)

**Decision:** `util.placements` v2 replaces "everything at the caster's feet" (D-014) with a position per layer:
- **Setups:** caster position, which is next to the setup.
- **Mollies and damaging utility:** where the utility **hurt an enemy**, as the median of the hit players' positions from GRID's damage records. Each use is linked to its throw with an as-of join, so the throw position is shown too.
- **Walls** (Viper, Harbor, Neon, Phoenix): a line from the caster along the aim, named by where it starts and the callout it runs toward. Length isn't measured.
- **Map-placed smokes** (Omen, Brimstone, Clove, Astra, Harbor Cove, Viper orb): **no position**. Shown as how often and when only.
- **Flashes and recon:** caster position, labelled "used from".

**Why:** An analyst flagged that smokes looked random, and that a KJ molly "at C Link" made no sense. Both came from drawing every ability where the caster stood. A Brimstone smoke placed from spawn, or a molly thrown 20 m, says nothing about where the utility went.

**Evidence:** 99.9% of Snake Bite damage links to its throw. Median throw-to-hit distance is 20 m for Snake Bite and 11 m for Nanoswarm, so the caster's position was the wrong spot for these.

**Limits:** The damage layer only sees uses that hurt someone. A molly used to deny space that hit nobody is invisible, which is survivorship again, and it's stated on the layer.

## D-016: Every agent's whole kit, and Tour de Force counted as a sniper kill (2026-11-18)

**Decision:** All 111 abilities in the corpus (29 agents) are classified in `engine/abilities.MODE` by what their position means:
- **placed** (19): where the player stood, next to the setup.
- **landing** (17): where it hurt an enemy.
- **direction** (13): a line along the aim.
- **thrown** (32): where it was used from.
- **self** (20): the player's own position.
- **unplaced** (10): timing only.

The Utility view can show one agent's whole kit, each ability drawn by its mode. Denominators are the rounds where the team fielded that agent. Unknown future abilities default to "thrown", so they're never drawn as placed or landed.

**Weaponless kills:** GRID sends 10,976 kills with no weapon. Each takes the weapon of the damage event from the same attacker on the same victim within 50 ms (`engine/weapons.py`, flagged `weapon_inferred`). That fills 10,853 of them: Tour de Force 2,205, Neon's Overdrive 1,490, Jett's Blade Storm 1,355, Showstopper 1,349, Hunter's Fury 1,264, and so on. 123 stay unknown. Headhunter has no damage records under its own name, so it can't be recovered.

**Tour de Force:** counts as a sniper kill in every kill-based Operator metric (timing, opening, forwardness, setups, escapes, gamble kills, executes against an Operator). It is not an item, so an enemy Tour de Force is never a "stolen Operator". Affected metrics moved to version 2.

## D-017: Ultimates, judged by the 10 seconds after, against the league (2026-11-18)

**Decision:** `ult.usage` lists every ultimate a team uses on one map and side. For each ult it gives:
- **Usage:** rounds used out of the rounds they fielded that agent, the median time, and how many came after a plant.
- **The 10 s window after each use:** kills, deaths and the change in round-win chance, using the WPA scores from the win-probability model.
- **Comparison:** the same window for every team on the map and side, plus a series-bootstrap range from 10 uses.

**Other changes:**
- `op.how_it_dies` v2 adds deaths **during an enemy ult** (any enemy ult in the 10 s before).
- An **Ultimates** layer joins the Utility view.

**Why:** An analyst pointed out that ults (Fade, Breach, Sova, KJ, Tejo and others) break Operator setups and swing rounds. The ultimates were in the data but unused.

**Evidence:**
- On Lotus attack, Cloud9's Fade ult window is −16.3 points (likely −27.8 to −4.7), with 7 kills and 14 deaths. The league is 0.0.
- Their Raze ult window is +8.3 (+3.0 to +12.6), against +0.4 for the league.
- Across all maps, 12 of 107 Cloud9 Operator-holder deaths came during an enemy ult.

**Limits:**
- **Association, not cause.** Teams ult when they're about to fight anyway, so the comparison is with the league, never with zero.
- **Weapon ults are seen only when they hit someone.** Blade Storm, Overdrive and Tour de Force have no reliable cast record, so their use is their first hit.
- **Buy-phase ult casts are left out.** About half of all Viper's Pit casts are recorded in the buy phase and no other ult is, which looks like a recording artefact.

**Performance:** The series bootstrap is now vectorised (the same resamples, about 100× faster). The league baseline is cached per map and side.

## D-018: Predictability as "how often the best guess is right", against other teams (2026-11-18)

**Decision:** `team.predictability` looks at four habits per map and side:
- where the team's first fight happens;
- when it happens (15 s windows);
- which site they plant (attack only);
- where the first Operator shot is taken.

For each habit, the team's most common choice is the opponent's best guess, and its share of rounds is how often that guess would be right. The comparison is with every other team on the same map and side that has at least 12 rounds for that habit, giving the share of teams that are less predictable. The score averages that over the habits with enough rounds.

**Why:** It's the self-scout question an analyst asks ("how easy are we to anti-strat?"), in a form a coach can read without statistics: "Best guess A site, right 55 of 120, typical team 47%".

**Limits:**
- Small samples make anyone look predictable, so habits under 12 rounds are flagged and kept out of the score, and teams under 12 rounds aren't used as comparisons.
- Ties count as not less predictable, which is conservative.
- Predictable isn't bad on its own; the UI says so.

## D-019: The judged build is a password-protected container (2026-11-18; password removed by D-022)

**Decision:** The hosted demo is one container: FastAPI serves both the API and the built web app. HTTP Basic auth covers every path except `/health` (`api/auth.py`). The image sets `SCOPEWATCH_REQUIRE_AUTH=1`, so it refuses to start without `SCOPEWATCH_PASSWORD`. The data bundle (`scripts/bundle_demo.py`, git-ignored `cache/demo/`) holds only what the app reads: the store, the two WPA score files, the map images and index, and the callout list. Fly.io builds the image remotely into its private registry. Steps are in DEPLOY.md.

**Why:** It resolves D-003. On 2026-11-18 the organisers confirmed on the Cloud9 Discord that a password-protected demo visible only to judges is allowed and encouraged. Basic auth needs no user database and works in every browser.

**Evidence:** Run locally from the bundle with the password required:
- Pages, API calls and map images return 401 without the password or with a wrong one.
- `/health` returns 200; the API docs page returns 404.
- With the password: the page, scripts, report and map images return 200, with `X-Robots-Tag: noindex`.
- Without a password, the server refuses to start.

**Also found:** The production build's typecheck (`tsc -b`) caught errors the command we'd been using (`tsc --noEmit -p .`) never checked. One was a real bug: selecting a callout in "Where they play it" or "Where it dies" never registered, because a metric id was compared with a metric object. Fixed. AGENTS.md and Junie's guidelines now use `tsc -b`.

## D-020: Every range uses a t interval on the series bootstrap (2026-11-19)

**Decision:** `core.bootstrap_mean` now returns mean ± t(0.95, G−1) × bootstrap standard error × √(G/(G−1)), where G is the number of series. Before, it returned the 5th–95th percentile of the resampled means, which is still available as `method="percentile"`. With a single series it returns no range. This affects every range shown in Scopewatch: Operator value per team and player, and the ultimate windows.

**Why:** Step 3 of the ML roadmap checked whether our "likely" ranges are honest, on simulated data with a known truth and the same series structure as ours. The percentile interval covered only 79% at 6 series and 75% at 4 when it claimed 90%.

**Evidence:** With 600 simulations per row (EVAL_BOOTSTRAP.md), the t interval covered 88% at 60 series, 91% at 15, 89% at 6 and 90% at 4. The percentile interval covered 87%, 88%, 79% and 75%. Resampling rounds as if independent covered about 70% at every size.

**Effect:** Ranges are slightly wider for small samples, which is the honest direction. Centre values are unchanged.

## D-021: Phantom roster entries are dropped from player_rounds (2026-11-19)

**Decision:** `engine/store.py` drops `player_rounds` entries with no agent.

**Why:** Reviewing Junie's step 4 work showed 1,181 side-rounds listing 6 or 7 players. The extras are phantom entries: listed in the feed's state with an empty agent, a $0 loadout, and no kills, damage or casts. They're probably substitutes or coaches. There are 1,228 of them, in 64 games. They made a roster-based alive count disagree with the production model, inflated the comp count, and made an earlier availability check ("agents known 100%") wrong, because it tested for null rather than empty text.

**Evidence:** All 1,228 had an empty agent, $0 loadout, 0 events and 0 casts. After the rebuild, 85,048 side-rounds have 5 players. The 8 side-rounds that still have 6 come from one broken game start (rounds 1–3) where nobody has any events. Player-rounds 426,516 → 425,288; distinct team comps 873 → 831.

**Effect:** No metric that counts real activity changes, because phantoms never held an Operator, spent credits or appeared in events. Counts of agents and comps are now correct.

## D-022: The hosted demo is open, with no password (2026-11-21)

**Decision:** The live demo at https://scopewatch-c9.fly.dev no longer asks for a login. This supersedes the password part of D-019; the container and the data bundle are unchanged.

**Why:** On 2026-11-21 the organisers confirmed on the Cloud9 Discord that apps may serve statistics, insights and per-event data derived from the real GRID files for the hackathon, and that an app which can't be used without an extra step is poor for judges. The password only existed because we read the licence as forbidding derived data on an open site. Without it, judges open the demo with one click.

**How:** Fly secrets override the image's environment: `SCOPEWATCH_PASSWORD` and `SCOPEWATCH_USER` were unset and `SCOPEWATCH_REQUIRE_AUTH=0` set, so the machine restarted on the same image. `api/auth.py` is unchanged and a password can be put back with one command (DEPLOY.md).

**Still true:** the repo holds code only; the data bundle goes only to Fly's private registry; `robots.txt` disallows all crawling; per-team numbers stay out of `docs/`.

**Evidence:** Checked live on 2026-11-21: the page, `/api/catalog`, `/docs` and `/health` return 200 with no login, the app loads Cloud9's report in the browser, and `robots.txt` returns `Disallow: /`.
