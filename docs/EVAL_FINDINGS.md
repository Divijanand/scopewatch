# Are the findings real?

Run 2026-11-25T10:23:52. League-level only. Method: D-024, `engine/significance.py`.

## 1. How many findings chance alone gives

The 20 biggest team-maps on both sides (40 reports, 842 checks), against the same reports with every real difference removed (20 draws each): rates redrawn at the league's rate with the measured clustering, dry-duel results sign-flipped per series. Predictability is left out (its null isn't simulated). Old rule = the range excludes the league. New rule = also survives Benjamini-Hochberg at q = 0.10 over the whole report. Counts are before the limit of five.

| | Old rule | New rule |
|---|---|---|
| Findings in the real data | 80 | 28 |
| Findings with no real differences | 45.3 | 6.1 |
| Real reports with at least one finding | 36 of 40 | 16 of 40 |
| No-difference reports with at least one finding | 68% | 12% |

| Metric | Old: real | Old: chance | New: real | New: chance |
|---|---|---|---|---|
| `att.executes` | 10 | 2.6 | 4 | 0.5 |
| `util.recon_timing` | 12 | 1.9 | 7 | 0.3 |
| `team.retakes` | 1 | 1.5 | 0 | 0.3 |
| `team.post_plant` | 0 | 1.0 | 0 | 0.2 |
| `team.economy` | 7 | 5.3 | 3 | 1.8 |
| `team.openings` | 14 | 2.9 | 9 | 0.5 |
| `op.wpa` | 3 | 3.8 | 0 | 0.4 |
| `fights.dry_duels` | 30 | 23.8 | 3 | 1.4 |
| `team.closing` | 3 | 2.5 | 2 | 0.8 |

## 2. Do findings hold in later games?

Checks on each team-map-side's games before 2025-08-17 and after it (28 with at least 60 rounds each side). A finding holds when the later games differ from the league in the same direction. Rosters, agents and patches change in between, so this asks for more than statistical significance. A pure coin flip would be 50%.

| Checks on the earlier games | Same direction later | Later gap as a share of the earlier gap (rates) |
|---|---|---|
| Every check | 56% (220 of 390; likely 51%–61%) | 47% |
| Old rule only (now dropped) | 78% (14 of 18; likely 55%–91%) | 55% |
| New rule (shown) | 79% (15 of 19; likely 57%–91%) | 33% |

| Metric (new rule) | Same direction later |
|---|---|
| `team.openings` | 7 of 7 |
| `team.closing` | 2 of 3 |
| `att.executes` | 2 of 3 |
| `util.recon_timing` | 2 of 2 |
| `team.retakes` | 1 of 1 |
| `op.wpa` | 1 of 1 |
| `fights.dry_duels` | 0 of 1 |
| `team.post_plant` | 0 of 1 |

## How to read this

- **Chance** is the number with no real differences anywhere, so it's a worst case for the real reports: where some differences are real, false-discovery control aims for about one false finding in ten.
- **Direction, not size.** The gaps that get picked are larger than the ones that follow (selection, plus real change between the halves). Read a finding as 'more than most' or 'less than most', not as a forecast of its number.
- **Replication samples are small**, and checks on one team overlap (attack and defence, first blood and what follows it), so the ranges in section 2 are too narrow. It can't show that the new rule beats the old one.
- The correlations come from the same games as the reports. They're league-wide, with no team tuned (EVAL_RANGES.md).
- **Old rule** here uses the D-025 ranges, which are wider than the ones the first version printed. With those, the old rule gave 93 findings against 65 by chance.
