# T1 fix: late post-plant states (step 5 stress finding)

Run 2026-11-21T22:28:39 on held-out test series (129 series, 48,584 states; 1,028 are 35 s or more after the plant).

The production model put 1 attacker against 5 defenders, 3 s before detonation, at about 0.47, though a full defuse takes 7 s. Variants: **monotonic** adds constraints a coach would sign (more attackers alive never hurts the attackers, more defenders never helps them, more time since the plant never hurts them); **defuse_left** also adds the seconds a defender would have left after a full 7 s defuse started now.

| Variant | Log loss | Brier | ECE | Δ log loss vs production | 90% range | Δ on late post-plant | 90% range | Not worse overall |
|---|---:|---:|---:|---:|---:|---:|---:|:---:|
| production | 0.3773 | 0.1234 | 0.0053 | +0.0000 | [+0.0000, +0.0000] | +0.0000 | [+0.0000, +0.0000] | yes |
| monotonic | 0.3779 | 0.1235 | 0.0100 | +0.0005 | [-0.0003, +0.0012] | -0.0018 | [-0.0066, +0.0026] | no |
| defuse_left | 0.3777 | 0.1234 | 0.0093 | +0.0003 | [-0.0005, +0.0011] | -0.0021 | [-0.0069, +0.0027] | no |

## Stress checks

| Variant | Alive-count violations > 0.02 | 1v1 after plant, 5 s → 40 s | 5v0 / 0v5 | 1v5 at 30, 36, 38.5, 40, 42, 44 s after plant |
|---|---:|---|---|---|
| production | 0 | 0.507 → 0.938 | 1.000 / 0.001 | 0.02, 0.17, 0.36, 0.41, 0.47, 0.47 |
| monotonic | 0 | 0.550 → 0.927 | 1.000 / 0.000 | 0.04, 0.16, 0.31, 0.40, 0.56, 0.56 |
| defuse_left | 0 | 0.550 → 0.924 | 1.000 / 0.000 | 0.05, 0.16, 0.32, 0.40, 0.53, 0.53 |

Not worse overall = the 90% log-loss range's upper end is at most +0.0005 and calibration error is at most production's + 0.002. A fix ships only if it is not worse overall and fixes the late 1v5 state.

## Reality check (all series, descriptive)

- 8,277 defuses; 10.7% finish 40 s or more after the plant and 5.3% 42 s or more, so defenders often have a defuse under way late. The feed has no defuse-start event, so the model can't know one is in progress.

| Late post-plant, attackers alive | After the plant | States | Attackers won | Production model |
|---|---|---:|---:|---:|
| defenders up 3 or more | 35-38 s | 24 | 37.5% | 33.1% |
| defenders up 3 or more | 38-40 s | 11 | 63.6% | 47.4% |
| defenders up 3 or more | 40-42 s | 2 | 100.0% | 84.7% |
| defenders up 3 or more | 42-45 s | 2 | 100.0% | 67.2% |
| everything else | 35-38 s | 2,927 | 92.4% | 92.1% |
| everything else | 38-40 s | 1,374 | 96.0% | 95.6% |
| everything else | 40-42 s | 983 | 98.3% | 97.3% |
| everything else | 42-45 s | 699 | 98.7% | 98.3% |

## Verdict

- Variants that are not worse overall and fix the late 1v5 state: **none**.
- The 1v5-like states barely exist in the data (see the table), and where late post-plant data exists the production model is well calibrated. The stress expectation ("defenders can't finish a 7 s defuse") ignored defuses already in progress.
- **Production stays.**
