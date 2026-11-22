# Step 5: stress tests for T1

Run 2026-11-21T22:15:00.

| Check | Pass | Details |
|---|---|---|
| More attackers alive never worse | yes | violations=0 |
| More defenders alive never better for attackers | yes | violations=0 |
| Post-plant clock monotonic (1v1) | yes | p5=0.507, p40=0.938 |
| Extreme 5v0 > 0.95 | yes | p=1.000 |
| Extreme 0v5 no plant < 0.05 | yes | p=0.001 |

## Rare state (no pass or fail)

- 1 attacker against 5 defenders, spike down, 3 s to detonation (42 s after the plant): predicted attacker win = 0.466.
- Training states within one alive player of it (0-2 attackers, 4-5 defenders, planted): 5,524; of those, 24 are 37-45 s after the plant, and the attackers won 75.0% of them.
- Defenders this far behind on time must defuse within 3 s, which takes 7 s, so the round is the attackers' unless the defuse started earlier (a half defuse). The state features don't know about a defuse in progress.
