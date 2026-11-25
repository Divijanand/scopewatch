# Are the findings real?

Run 2026-11-24T18:34:03. League-level only. Method: D-024, `engine/significance.py`.

## 1. Rounds in a series aren't independent

Pearson dispersion across series within one team, map and side: 1 means independent rounds. Ranges and tests that treat rounds as independent are too confident wherever it's above 1.

| Measure | Dispersion | In the code | Team-map-sides |
|---|---|---|---|
| `util.recon_timing.before` | 2.37 | 2.37 | 584 |
| `team.retakes.plants_faced` | 1.69 | 1.69 | 296 |
| `team.post_plant.plant_share` | 1.66 | 1.66 | 296 |
| `team.post_plant.win` | 1.45 | 1.45 | 293 |
| `team.retakes.retake` | 1.44 | 1.44 | 290 |
| `team.openings.after_first_blood` | 1.38 | 1.38 | 584 |
| `team.openings.after_first_death` | 1.38 | 1.38 | 575 |
| `util.recon_timing.late` | 1.36 | 1.36 | 486 |
| `team.economy.full_vs_full` | 1.36 | 1.36 | 580 |
| `team.openings.first_blood` | 1.26 | 1.26 | 592 |
| `team.economy.scrappy_vs_full` | 1.18 | 1.18 | 403 |
| `team.economy.full_vs_anti` | 1.13 | 1.13 | 420 |
| `team.post_plant.pre_plant_losses` | 1.12 | 1.12 | 282 |
| `att.executes` | 1.06 | 1.06 | 713 |

## 2. How many findings chance alone gives

The 20 biggest team-maps on both sides (40 reports, 842 checks), against the same reports with every real difference removed (20 draws each): rates redrawn at the league's rate with the measured clustering, dry-duel results sign-flipped per series. Predictability is left out (its null isn't simulated). Old rule = the range excludes the league. New rule = also survives Benjamini-Hochberg at q = 0.10 over the whole report. Counts are before the limit of five.

| | Old rule | New rule |
|---|---|---|
| Findings in the real data | 93 | 25 |
| Findings with no real differences | 65.0 | 6.1 |
| Real reports with at least one finding | 38 of 40 | 15 of 40 |
| No-difference reports with at least one finding | 82% | 12% |

| Metric | Old: real | Old: chance | New: real | New: chance |
|---|---|---|---|---|
| `att.executes` | 10 | 3.5 | 4 | 0.4 |
| `util.recon_timing` | 20 | 7.8 | 7 | 0.5 |
| `team.retakes` | 2 | 3.5 | 0 | 0.2 |
| `team.post_plant` | 0 | 2.4 | 0 | 0.1 |
| `team.economy` | 7 | 5.7 | 3 | 1.6 |
| `team.openings` | 17 | 5.2 | 8 | 0.5 |
| `op.wpa` | 3 | 3.7 | 0 | 0.3 |
| `fights.dry_duels` | 30 | 24.8 | 3 | 1.8 |
| `team.closing` | 4 | 8.5 | 0 | 0.7 |

## 3. Do findings hold in later games?

Checks on each team-map-side's games before 2025-08-17 and after it (28 with at least 60 rounds each side). A finding holds when the later games differ from the league in the same direction. Rosters, agents and patches change in between, so this asks for more than statistical significance. A pure coin flip would be 50%.

| Checks on the earlier games | Same direction later | Later gap as a share of the earlier gap (rates) |
|---|---|---|
| Every check | 56% (220 of 390; likely 51%–61%) | 47% |
| Old rule only (now dropped) | 68% (23 of 34; likely 51%–81%) | 40% |
| New rule (shown) | 87% (13 of 15; likely 62%–96%) | 36% |

| Metric (new rule) | Same direction later |
|---|---|
| `team.openings` | 7 of 7 |
| `att.executes` | 2 of 3 |
| `util.recon_timing` | 2 of 2 |
| `team.retakes` | 1 of 1 |
| `op.wpa` | 1 of 1 |
| `team.post_plant` | 0 of 1 |

## How to read this

- **Chance** is the number with no real differences anywhere, so it's a worst case for the real reports: where some differences are real, false-discovery control aims for about one false finding in ten.
- **Direction, not size.** The gaps that get picked are larger than the ones that follow (selection, plus real change between the halves). Read a finding as 'more than most' or 'less than most', not as a forecast of its number.
- **Replication samples are small**, and checks on one team overlap (attack and defence, first blood and what follows it), so the ranges in section 3 are too narrow. It can't show that the new rule beats the old one.
- The dispersion numbers come from the same games as the reports. They're league-wide, with no team tuned.
- The ranges printed on cards are still per-round Wilson ranges; only the choice of findings allows for clustering.
