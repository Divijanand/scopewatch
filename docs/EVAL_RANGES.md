# Are the ranges wide enough?

Run 2026-11-25T10:25:25. League-level only. Method: D-025, `engine/clustering.py`.

Rounds of one game repeat each other (same plan, same opponent, same day), so a range that treats them as independent is too narrow. Each team's games were split into two random halves: the halves estimate the same rate, so they should differ beyond the 95% allowance in 5% of cases.

| Cards | Comparisons | Old ranges | New ranges |
|---|---|---|---|
| One map, one side (correlation from other teams) | 105,016 | 19.1% | 7.0% |
| The same, leaving out the utility spots (most of the comparisons) | 28,469 | 10.2% | 4.8% |
| One map, both sides (correlation from the one-side cards) | 18,150 | 10.4% | 4.0% |

## Per measure

Correlation: 0 means rounds of a game are independent. Wider: how much wider the typical one-side range is now. Disagreement: how often two halves differ beyond 95%, with the correlation taken from other teams (5% is right); measures with fewer than 200 comparisons are left out of it.

| Measure | Correlation measured | In the code | Rates | Wider | Old disagreement | New disagreement |
|---|---|---|---|---|---|---|
| `op.holder` | 0.946 | 0.946 | 400 | 105% | 44.0% | 3.5% |
| `util.placements.ability` | 0.546 | 0.546 | 7457 | 156% | 42.8% | 6.6% |
| `util.placements.unplaced` | 0.491 | 0.491 | 966 | 145% | 43.7% | 7.6% |
| `op.possession` | 0.184 | 0.184 | 478 | 9% | 20.8% | 5.0% |
| `util.recon_timing.before` | 0.167 | 0.167 | 579 | 59% | 19.6% | 5.7% |
| `util.recon_timing.none` | 0.140 | 0.140 | 361 | 56% | 24.5% | 7.2% |
| `op.kill_timing.post_plant` | 0.140 | 0.140 | 158 | 19% | – | – |
| `util.placements.spot` | 0.117 | 0.117 | 19990 | 48% | 22.0% | 9.3% |
| `util.recon_timing.won` | 0.103 | 0.103 | 1000 | 28% | 13.6% | 5.1% |
| `team.economy.scrappy_vs_full` | 0.097 | 0.097 | 77 | 7% | – | – |
| `team.openings.after_first_death` | 0.088 | 0.088 | 524 | 20% | 8.0% | 3.0% |
| `att.executes.won` | 0.084 | 0.084 | 469 | 12% | 12.0% | 7.9% |
| `team.openings.after_first_blood` | 0.083 | 0.083 | 536 | 20% | 10.7% | 5.6% |
| `op.escapes.punished` | 0.080 | 0.080 | 177 | 6% | – | – |
| `team.retakes.by_numbers` | 0.075 | 0.075 | 248 | 7% | – | – |
| `team.retakes.retake` | 0.075 | 0.075 | 284 | 24% | 10.3% | 4.0% |
| `team.retakes.plants_faced` | 0.075 | 0.075 | 296 | 33% | 13.9% | 5.8% |
| `team.post_plant.by_numbers` | 0.073 | 0.073 | 234 | 7% | – | – |
| `op.gamble.won` | 0.073 | 0.073 | 112 | 2% | – | – |
| `op.win.without` | 0.072 | 0.072 | 538 | 19% | 9.3% | 4.0% |
| `att.executes.no_plant` | 0.071 | 0.071 | 295 | 31% | 12.5% | 5.9% |
| `team.post_plant.plant_share` | 0.071 | 0.071 | 295 | 31% | 14.2% | 6.2% |
| `team.post_plant.win` | 0.070 | 0.070 | 289 | 23% | 9.1% | 4.3% |
| `team.economy.full_vs_full` | 0.066 | 0.066 | 580 | 18% | 8.9% | 4.9% |
| `util.ults.won` | 0.054 | 0.054 | 316 | 1% | – | – |
| `op.kill_timing` | 0.052 | 0.052 | 641 | 8% | 7.9% | 4.2% |
| `op.win.with` | 0.049 | 0.049 | 270 | 7% | 8.8% | 6.4% |
| `team.economy.full_vs_anti` | 0.044 | 0.044 | 72 | 3% | – | – |
| `team.closing.comebacks` | 0.030 | 0.030 | 346 | 8% | – | – |
| `att.executes.entry` | 0.028 | 0.028 | 254 | 4% | – | – |
| `util.kit.unplaced` | 0.028 | 0.028 | 447 | 14% | 11.1% | 6.8% |
| `team.closing.throws` | 0.027 | 0.027 | 326 | 8% | – | – |
| `team.openings.first_blood` | 0.027 | 0.027 | 592 | 13% | 7.8% | 4.0% |
| `util.kit.spot` | 0.026 | 0.026 | 15739 | 13% | 11.3% | 7.6% |
| `team.post_plant.pre_plant_losses` | 0.026 | 0.026 | 278 | 6% | 7.2% | 6.3% |
| `op.broken.how` | 0.025 | 0.025 | 313 | 2% | – | – |
| `team.predictability.contact_when` | 0.019 | 0.019 | 591 | 9% | 7.6% | 5.3% |
| `op.escapes.moved` | 0.005 | 0.005 | 259 | 0% | 7.9% | 7.5% |
| `att.executes.site` | 0.004 | 0.004 | 699 | 2% | 4.9% | 4.5% |
| `team.predictability.contact_where` | 0.002 | 0.002 | 590 | 1% | 5.4% | 4.9% |
| `util.kit.ability` | -0.002 | 0.000 | 4186 | 0% | 7.6% | 7.5% |
| `op.gamble.outcome` | -0.003 | 0.000 | 762 | 0% | 4.9% | 4.6% |
| `op.opening.lost` | -0.003 | 0.000 | 54 | 0% | – | – |
| `op.setups.callout` | -0.004 | 0.000 | 246 | 0% | – | – |
| `team.predictability.sniper_spot` | -0.011 | 0.000 | 120 | 0% | – | – |
| `team.predictability.site` | -0.013 | 0.000 | 293 | 0% | 5.3% | 5.3% |
| `op.deaths.callout` | -0.016 | 0.000 | 156 | 0% | – | – |
| `op.gamble.multi_kill` | -0.018 | 0.000 | 145 | 0% | – | – |
| `op.opening.won` | -0.020 | 0.000 | 190 | 0% | – | – |
| `op.possession_shift` | -0.027 | 0.000 | 56 | 0% | – | – |
| `op.deaths.first` | -0.031 | 0.000 | 54 | 0% | – | – |
| `att.executes.op_kill` | -0.064 | 0.000 | 91 | 0% | – | – |
| `util.ults.used` | -0.074 | 0.000 | 1691 | 0% | 0.4% | 0.4% |
| `att.executes.lost_no_kill` | -0.081 | 0.000 | 95 | 0% | – | – |
| `team.economy.pistol` | -0.501 | 0.000 | 81 | 0% | – | – |
| `att.executes.no_plant_won` | too few | 0.078 | 296 | 12% | – | – |
| `team.economy.bonus` | too few | 0.078 | 582 | 0% | – | – |
| `op.gamble.stolen` | too few | 0.078 | 571 | 11% | – | – |

Measures without enough rates use the 75th percentile, 0.078. Negative correlations count as 0.
