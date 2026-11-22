# Junie brief: step 5f, guns and ultimates (Arsenal, eco buys, shotgun spots, spike stalls, retake ults, buffs)

**Model:** GPT-5.3-codex. **Branch:** `deep-learning` (`git pull` first; start only once step 5e is committed). Follow `AGENTS.md`: never commit data or model files, fixtures synthetic only, no per-team numbers in `docs/`. Read `engine/metrics/ultimates.py` (`ult.usage`, extend rather than duplicate), `engine/abilities.py` (`ULTS`, `WEAPON_ULTS`, `DAMAGE_THROWN`, `SMOKE`), `engine/weapons.py` (`GUNS`), `engine/metrics/fundamentals.py` (numbers at the plant, the league cache pattern) and `engine/report.py` (step 5d) first.

## Why
Our cards grew out of the Operator. Pro play is mostly rifles, and rounds swing on ultimates. The data has what we need:
- every hit: its weapon, damage and location (`engagements.hit`: head, body or leg; `general` is ability damage, so leave it out of headshot rates);
- every kill and its weapon;
- each player's guns at the end of the buy (`player_rounds.items`, for example `melee|vandal`);
- every ability and ultimate cast with time, phase and caster position;
- every plant position (`objectives.x`, `y`).

Everything here follows our pattern: a team against the league, Wilson ranges, n shown, "Show the rounds", association not cause.

## 1. Arsenal (`engine/metrics/guns.py`, metric `guns.profile`)
- **Rifle mix:** among the team's player-rounds on a full buy (`player_rounds.economy = 'full'`), the share holding a Vandal, Phantom, Operator, Outlaw, Odin or other primary, from `items`. Compare with the league on the map and side. Per player, their usual primary.
- **One-tap discipline:**
  - the headshot share of hits, as head / (head + body + leg), for the Vandal, the Phantom, and pistols together;
  - the single-hit kill share: kills where the killer's damage to that victim in the previous 3 s was a single hit.

  Both for the team and the league, with a per-player breakdown (at least 50 hits).
- **Weapon ultimate kills:** kills with `tour-de-force`, `blade-storm`, `overdrive`, `showstopper`, `hunter's-fury` and `orbital-strike`, as a share of the team's kills, with the three most common nearest callouts. Use the `ult.usage` caveat that weapon ults are seen only when they hit.
- **Smoke comps and the Phantom (league study, `scripts/guns_and_smokes.py` writes `docs/GUNS_AND_SMOKES.md`):** does a team that throws more smokes buy more Phantoms?
  - Per team-map-game: smokes cast per round (`SMOKE`), and the Phantom share of Vandal plus Phantom on full buys.
  - Report the league relationship: the Phantom share in thirds by smokes per round, with series-bootstrap ranges (`bootstrap_mean`, D-020).
  - It's league-level only. Say plainly if there's no relationship.

## 2. Eco and pistol rounds (`guns.eco`)
- On the team's `eco` and `half` rounds (pistol rounds 1 and 13 separately):
  - what they hold (the most common sidearm or primary, from `items`);
  - their round win rate against the league's in the same buy matchup (reuse `fundamentals.OWN` and the matchups; no new definitions);
  - kills by weapon in those rounds.
- One sentence on the card. Example (format only, invented numbers): "On ecos they buy Sheriffs and Judges and win 22% (league 17%)."

## 3. Close-range danger (`guns.close_range`)
- Kills with shotguns (`judge`, `bucky`, `shorty`) by the team's nearest callout (`att_callout`), against the league's share at that callout on the map and side.
- On the card: the top three callouts with n, and "Expect a shotgun at A Main" only when the team's share there is beyond noise above the league's.

## 4. Ultimates and utility after the plant (`util.post_plant`)
- **Attack (spike stall):** in rounds the team planted, any cast after the plant by the attackers within 1,500 units of the plant position (caster position, `spatial_ok`), split into:
  - a stall ult: `viper's-pit`, `hunter's-fury`, `orbital-strike`, `steel-garden`, `annihilation`, `rolling-thunder`;
  - damaging utility: `DAMAGE_THROWN`, for example `snake-bite`, `nanoswarm` and mollies.

  Report the post-plant win rate with and without each, **within the same numbers-at-the-plant bucket** (reuse `fundamentals._plant_alive`), against the league's.
- **Defence (retake ults):** rounds where the team faced a plant, with and without a retake ult cast after the plant (`nightfall`, `null-cmd`, `rolling-thunder`, `thrash`, `reckoning`, `lockdown`, `hunter's-fury`). Report the retake rate with and without, within the same bucket, against the league's.
- Caveats on the card:
  - a stall or retake ult is thrown when it looks useful, so the comparison is association;
  - caster position isn't where the ult landed (Viper's Pit is centred on the caster, Sova's ult isn't).
- Evidence: the rounds with the stall or ult, split by won and lost.

## 5. Buffs in fights (`engine/model/fights.py` and `scripts/eval_fight_buffs.py`)
- In `add_utility`, add `buff_opener` and `buff_other`: a `stim-beacon` or `null-cmd` cast by that side within the same window and radius. Reyna's Empress isn't recorded as a cast in the feed; say so in the docstring.
- `scripts/eval_fight_buffs.py` writes `docs/EVAL_FIGHT_BUFFS.md`. It follows `eval_fights.compare`: full model against full plus buff columns, at 4 s and 2,500 units, with the step 1 rule, plus the count of fights with a buff on each side. Say plainly if there are too few buffed fights to tell.

## 6. UI and the summary
- A **Guns** section on the Report tab (step 5d) with the Arsenal, Eco and Close-range cards. The post-plant card goes in Attack (stall) and Defence (retake ults).
- One finding template per new metric in `engine/report.py`, beyond-noise only, with a `prepare` line. Example (format only): "Expect a Viper ult on the spike: they use one in 41% of post-plants (league 12%)."

## Tests (`tests/test_guns.py`, `tests/test_post_plant_util.py`, synthetic)
- `general` hits don't count toward headshot rates. A single-hit kill needs exactly one hit from the killer on that victim within 3 s.
- The rifle mix reads `items`, and a round with no primary isn't counted as a rifle.
- Pistol rounds are separate from eco rounds.
- A shotgun callout finding needs the team's range to exclude the league share.
- Stall: a cast before the plant, by the defenders, or more than 1,500 units from the plant doesn't count. The with and without comparison stays within one numbers-at-the-plant bucket.
- Retake ults: only casts after the plant by the defending team.
- Buff flags: a buff cast after `t0`, or by the other side, doesn't set the flag.
- League numbers come from the connection passed in (`fundamentals` pattern, cache cleared in tests). No test writes outside `tmp_path`.

## Don't run the long jobs
Run `python -m pytest tests -q`, `cd web && npx tsc -b` and the web build only. The reviewer runs `scripts.guns_and_smokes`, `scripts.eval_fight_buffs` and rebuilds the fights file. You may call each new metric once for one team, map and side and report the timing (not the numbers).

## Done when
- All tests pass, the web app builds, `git status` shows no data or model files, and nothing is committed.
- PyCharm run configurations "Guns and smokes" and "Evaluate fight buffs".
- `docs/ROADMAP_ML.md` has a step 5f section, `AI_SHOWCASE.md` a log row naming the model, `docs/IMPLEMENTATION_STATUS.md` a line per metric (no team numbers), and `docs/METRICS.md` regenerated.
- Your report lists every ability you put in or left out of the stall, retake and buff lists, and why.
