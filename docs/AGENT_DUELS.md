# Dry duels by agent pair (league)

Run 2026-11-21T22:12:08 on all series. 134,519 dry fights between two different agents; 133 pairs with at least 300 fights; 27 differ from expected beyond noise.

Dry = no flash, stun, smoke, recon or ult cast near the fight by either team, and no ability damage to either fighter, in the 4 s before. **Expected** is the league's dry-fight opener win rate for the same map, opener side, alive counts and plant (flipped when the other agent opened), so who shot first is accounted for. **Points** = (won − expected) × 100 for the first agent. Ranges are 90% series-bootstrap t intervals (D-020). Association, not cause: agent choice comes with role, position and player.

- **Weapons aren't separated.** Chamber's Headhunter and Tour de Force, and the Operator (often on Chamber), are part of what an agent row measures.
- **Chance alone.** With 133 pairs and 90% ranges, about 13 pairs would show a range that excludes 0 even if no agent pair differed; 27 do. Read single pairs as hints, and patterns across many pairs (one agent winning against most others) as the stronger signal.

| Agent | Against | Fights | Won | Expected | Points | 90% range | Beyond noise |
|---|---|---:|---:|---:|---:|---:|:---:|
| chamber | vyse | 399 | 53.4% | 47.4% | +6.0 | [+2.3, +9.6] | yes |
| chamber | cypher | 355 | 60.0% | 54.3% | +5.7 | [+2.6, +8.9] | yes |
| chamber | raze | 325 | 55.1% | 50.4% | +4.7 | [+1.5, +7.8] | yes |
| brimstone | cypher | 415 | 52.0% | 47.4% | +4.6 | [+1.1, +8.2] | yes |
| vyse | kay/o | 321 | 55.5% | 51.0% | +4.5 | [+1.1, +7.9] | yes |
| iso | cypher | 411 | 56.9% | 52.6% | +4.3 | [+1.0, +7.6] | yes |
| chamber | viper | 710 | 58.3% | 54.0% | +4.3 | [+2.2, +6.4] | yes |
| cypher | vyse | 630 | 53.8% | 49.8% | +4.0 | [+1.8, +6.3] | yes |
| waylay | fade | 437 | 57.4% | 53.5% | +3.9 | [+1.0, +6.7] | yes |
| jett | tejo | 441 | 61.7% | 58.0% | +3.7 | [+0.6, +6.8] | yes |
| sova | fade | 553 | 53.7% | 50.0% | +3.7 | [+1.1, +6.2] | yes |
| chamber | omen | 885 | 57.7% | 54.2% | +3.6 | [+1.6, +5.5] | yes |
| chamber | yoru | 375 | 54.9% | 51.5% | +3.5 | [+1.1, +5.9] | yes |
| chamber | fade | 616 | 56.8% | 53.5% | +3.4 | [+1.0, +5.7] | yes |
| sova | waylay | 375 | 50.1% | 46.9% | +3.2 | [-0.3, +6.8] |  |
| omen | kay/o | 577 | 55.6% | 52.5% | +3.2 | [+0.4, +5.9] | yes |
| astra | neon | 643 | 49.9% | 46.9% | +3.0 | [+0.7, +5.3] | yes |
| yoru | raze | 618 | 51.6% | 48.7% | +2.9 | [+0.6, +5.3] | yes |
| tejo | vyse | 673 | 49.6% | 46.9% | +2.7 | [+0.3, +5.2] | yes |
| yoru | fade | 805 | 55.7% | 52.9% | +2.7 | [+0.7, +4.8] | yes |
| brimstone | skye | 396 | 49.7% | 47.0% | +2.7 | [-0.3, +5.7] |  |
| tejo | astra | 481 | 47.2% | 44.5% | +2.7 | [-0.2, +5.6] |  |
| clove | omen | 333 | 50.5% | 47.8% | +2.6 | [-0.7, +6.0] |  |
| omen | iso | 481 | 49.9% | 47.3% | +2.6 | [-0.2, +5.3] |  |
| jett | kay/o | 540 | 61.5% | 59.0% | +2.5 | [-0.2, +5.2] |  |
| tejo | breach | 984 | 54.4% | 52.0% | +2.3 | [+0.2, +4.5] | yes |
| viper | tejo | 677 | 54.4% | 52.1% | +2.3 | [+0.1, +4.4] | yes |
| sova | neon | 1,946 | 48.0% | 45.8% | +2.2 | [+0.9, +3.5] | yes |
| chamber | neon | 690 | 51.2% | 49.0% | +2.2 | [+0.2, +4.1] | yes |
| chamber | astra | 376 | 56.9% | 54.8% | +2.1 | [-1.1, +5.4] |  |
| chamber | killjoy | 313 | 54.6% | 52.5% | +2.1 | [-0.8, +5.0] |  |
| viper | brimstone | 669 | 55.8% | 53.7% | +2.1 | [-0.3, +4.5] |  |
| jett | yoru | 733 | 54.7% | 52.7% | +2.0 | [-0.0, +4.1] |  |
| fade | neon | 1,147 | 50.4% | 48.4% | +2.0 | [+0.1, +4.0] | yes |
| vyse | killjoy | 365 | 52.1% | 50.1% | +2.0 | [-1.1, +5.0] |  |
| jett | neon | 647 | 53.6% | 51.7% | +1.9 | [-0.2, +4.0] |  |
| jett | breach | 462 | 58.9% | 57.0% | +1.9 | [-0.6, +4.3] |  |
| omen | deadlock | 458 | 51.3% | 49.5% | +1.8 | [-0.7, +4.4] |  |
| fade | vyse | 1,247 | 50.5% | 48.7% | +1.8 | [+0.2, +3.5] | yes |
| omen | phoenix | 347 | 48.4% | 46.6% | +1.8 | [-1.4, +5.0] |  |
| jett | viper | 1,369 | 55.8% | 54.0% | +1.8 | [+0.2, +3.4] | yes |
| omen | skye | 518 | 51.0% | 49.2% | +1.8 | [-0.9, +4.4] |  |
| yoru | astra | 963 | 53.2% | 51.4% | +1.8 | [-0.3, +3.8] |  |
| viper | breach | 589 | 56.9% | 55.1% | +1.7 | [-0.9, +4.4] |  |
| cypher | tejo | 767 | 53.2% | 51.5% | +1.7 | [-0.6, +4.1] |  |
| sova | tejo | 398 | 54.8% | 53.1% | +1.7 | [-1.7, +5.0] |  |
| viper | omen | 2,805 | 51.5% | 49.9% | +1.6 | [+0.4, +2.8] | yes |
| harbor | sova | 304 | 53.9% | 52.3% | +1.6 | [-2.0, +5.2] |  |
| cypher | kay/o | 308 | 54.9% | 53.4% | +1.5 | [-1.8, +4.7] |  |
| vyse | astra | 525 | 51.0% | 49.7% | +1.3 | [-1.2, +3.8] |  |
| sova | kay/o | 725 | 50.3% | 49.1% | +1.3 | [-1.2, +3.7] |  |
| viper | fade | 1,861 | 52.3% | 51.0% | +1.2 | [-0.1, +2.6] |  |
| cypher | yoru | 848 | 49.8% | 48.5% | +1.2 | [-0.8, +3.2] |  |
| vyse | neon | 742 | 51.3% | 50.2% | +1.2 | [-1.1, +3.4] |  |
| yoru | tejo | 510 | 56.5% | 55.3% | +1.2 | [-1.3, +3.7] |  |
| waylay | viper | 643 | 51.9% | 50.8% | +1.2 | [-1.2, +3.5] |  |
| fade | breach | 471 | 57.7% | 56.6% | +1.2 | [-1.8, +4.1] |  |
| viper | astra | 684 | 51.3% | 50.2% | +1.1 | [-1.4, +3.5] |  |
| yoru | neon | 665 | 50.7% | 49.6% | +1.1 | [-1.3, +3.4] |  |
| killjoy | yoru | 445 | 49.2% | 48.1% | +1.1 | [-1.3, +3.5] |  |
| astra | fade | 676 | 53.7% | 52.6% | +1.1 | [-1.4, +3.5] |  |
| sova | iso | 515 | 48.3% | 47.3% | +1.0 | [-1.5, +3.5] |  |
| brimstone | neon | 350 | 48.0% | 47.0% | +1.0 | [-2.4, +4.4] |  |
| cypher | jett | 1,012 | 44.6% | 43.6% | +1.0 | [-0.9, +2.8] |  |
| kay/o | killjoy | 325 | 45.5% | 44.6% | +0.9 | [-2.4, +4.3] |  |
| breach | yoru | 457 | 46.4% | 45.5% | +0.9 | [-2.1, +3.9] |  |
| omen | neon | 2,679 | 48.8% | 47.9% | +0.9 | [-0.2, +2.0] |  |
| killjoy | fade | 427 | 50.1% | 49.2% | +0.9 | [-2.0, +3.8] |  |
| jett | chamber | 356 | 53.7% | 52.7% | +0.9 | [-1.6, +3.4] |  |
| harbor | viper | 362 | 48.9% | 48.0% | +0.9 | [-2.6, +4.3] |  |
| phoenix | neon | 314 | 47.1% | 46.3% | +0.9 | [-2.4, +4.2] |  |
| viper | yoru | 1,267 | 47.9% | 47.1% | +0.8 | [-0.9, +2.6] |  |
| raze | skye | 665 | 51.7% | 50.9% | +0.8 | [-1.4, +3.1] |  |
| astra | cypher | 403 | 52.1% | 51.3% | +0.8 | [-2.0, +3.6] |  |
| yoru | kay/o | 362 | 56.6% | 55.8% | +0.8 | [-1.7, +3.4] |  |
| cypher | fade | 575 | 50.1% | 49.3% | +0.8 | [-1.9, +3.5] |  |
| neon | viper | 1,671 | 54.1% | 53.3% | +0.8 | [-0.8, +2.4] |  |
| raze | vyse | 875 | 50.5% | 49.7% | +0.8 | [-1.2, +2.8] |  |
| killjoy | cypher | 605 | 52.1% | 51.3% | +0.8 | [-1.4, +3.0] |  |
| jett | vyse | 553 | 54.8% | 54.0% | +0.8 | [-1.6, +3.1] |  |
| neon | raze | 762 | 54.6% | 53.8% | +0.8 | [-1.4, +3.0] |  |
| breach | vyse | 524 | 47.1% | 46.4% | +0.8 | [-1.9, +3.5] |  |
| cypher | omen | 2,814 | 50.4% | 49.6% | +0.8 | [-0.4, +2.0] |  |
| neon | skye | 368 | 52.7% | 52.0% | +0.7 | [-2.4, +3.9] |  |
| omen | fade | 2,063 | 49.9% | 49.3% | +0.7 | [-0.8, +2.1] |  |
| killjoy | viper | 1,214 | 50.3% | 49.7% | +0.7 | [-1.1, +2.4] |  |
| viper | skye | 1,039 | 49.1% | 48.4% | +0.7 | [-1.2, +2.6] |  |
| waylay | yoru | 404 | 50.2% | 49.6% | +0.6 | [-2.0, +3.2] |  |
| omen | tejo | 1,049 | 53.8% | 53.1% | +0.6 | [-1.3, +2.6] |  |
| neon | killjoy | 814 | 54.1% | 53.4% | +0.6 | [-1.5, +2.8] |  |
| sova | killjoy | 1,730 | 48.1% | 47.5% | +0.6 | [-1.0, +2.3] |  |
| omen | vyse | 1,853 | 50.5% | 49.9% | +0.6 | [-0.9, +2.0] |  |
| omen | waylay | 549 | 50.5% | 49.9% | +0.6 | [-1.7, +2.9] |  |
| jett | omen | 1,559 | 54.5% | 53.9% | +0.6 | [-1.0, +2.1] |  |
| astra | killjoy | 509 | 49.3% | 48.8% | +0.6 | [-2.1, +3.2] |  |
| sova | viper | 1,843 | 48.4% | 47.9% | +0.5 | [-0.8, +1.9] |  |
| breach | omen | 1,910 | 48.3% | 47.8% | +0.5 | [-0.9, +1.9] |  |
| breach | brimstone | 401 | 49.6% | 49.1% | +0.5 | [-3.5, +4.5] |  |
| raze | cypher | 683 | 51.0% | 50.4% | +0.5 | [-2.0, +3.0] |  |
| breach | neon | 961 | 45.4% | 44.8% | +0.5 | [-1.7, +2.7] |  |
| vyse | yoru | 726 | 48.2% | 47.7% | +0.5 | [-1.6, +2.6] |  |
| sova | breach | 858 | 51.3% | 50.8% | +0.5 | [-1.8, +2.8] |  |
| sova | cypher | 2,208 | 48.7% | 48.3% | +0.5 | [-0.8, +1.8] |  |
| breach | cypher | 1,496 | 48.5% | 48.0% | +0.5 | [-1.2, +2.1] |  |
| phoenix | sova | 392 | 54.1% | 53.6% | +0.5 | [-2.7, +3.6] |  |
| jett | sova | 2,208 | 55.8% | 55.3% | +0.5 | [-0.9, +1.9] |  |
| raze | breach | 737 | 52.9% | 52.5% | +0.4 | [-1.8, +2.7] |  |
| viper | kay/o | 319 | 51.7% | 51.3% | +0.4 | [-3.0, +3.9] |  |
| astra | kay/o | 384 | 53.6% | 53.2% | +0.4 | [-2.6, +3.5] |  |
| raze | brimstone | 700 | 51.0% | 50.6% | +0.4 | [-1.7, +2.6] |  |
| fade | brimstone | 335 | 51.3% | 50.9% | +0.4 | [-2.6, +3.4] |  |
| raze | fade | 1,234 | 50.6% | 50.2% | +0.4 | [-1.3, +2.1] |  |
| tejo | raze | 725 | 46.2% | 45.8% | +0.4 | [-1.9, +2.6] |  |
| sova | yoru | 1,332 | 47.4% | 47.1% | +0.4 | [-1.3, +2.1] |  |
| tejo | neon | 556 | 46.8% | 46.4% | +0.4 | [-2.1, +2.8] |  |
| tejo | brimstone | 490 | 49.2% | 48.9% | +0.3 | [-2.1, +2.8] |  |
| sova | omen | 3,284 | 49.6% | 49.3% | +0.3 | [-0.7, +1.4] |  |
| omen | raze | 1,642 | 48.7% | 48.3% | +0.3 | [-1.3, +2.0] |  |
| viper | sage | 355 | 48.2% | 47.9% | +0.3 | [-3.2, +3.8] |  |
| astra | sova | 964 | 49.6% | 49.3% | +0.3 | [-1.6, +2.2] |  |
| sova | vyse | 741 | 49.0% | 48.7% | +0.3 | [-2.0, +2.5] |  |
| astra | omen | 527 | 52.2% | 51.9% | +0.2 | [-2.8, +3.3] |  |
| tejo | fade | 434 | 49.8% | 49.5% | +0.2 | [-2.5, +2.9] |  |
| raze | viper | 1,906 | 50.4% | 50.2% | +0.2 | [-1.1, +1.6] |  |
| cypher | viper | 696 | 47.8% | 47.7% | +0.2 | [-2.1, +2.5] |  |
| cypher | neon | 1,583 | 47.6% | 47.4% | +0.2 | [-1.3, +1.7] |  |
| yoru | omen | 1,542 | 54.3% | 54.2% | +0.2 | [-1.3, +1.6] |  |
| omen | killjoy | 1,261 | 48.5% | 48.4% | +0.1 | [-1.7, +1.9] |  |
| sova | chamber | 637 | 45.1% | 44.9% | +0.1 | [-2.2, +2.5] |  |
| fade | skye | 369 | 53.4% | 53.3% | +0.1 | [-3.4, +3.6] |  |
| jett | killjoy | 1,142 | 54.6% | 54.5% | +0.1 | [-1.6, +1.7] |  |
| astra | jett | 745 | 47.5% | 47.5% | +0.0 | [-2.1, +2.2] |  |
| viper | vyse | 1,006 | 49.5% | 49.5% | +0.0 | [-2.0, +2.0] |  |
