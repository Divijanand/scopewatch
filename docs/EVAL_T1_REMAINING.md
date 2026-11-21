# T1 utility remaining ablation (step 4b)

Run 2026-11-20T19:15:41 on held-out **test series** only (129 series, 48,584 states).

## Overall

| Variant | Log loss | Brier | AUC | Calibration error (ECE) | Δ log loss vs baseline | 90% range |
|---|---:|---:|---:|---:|---:|---:|
| baseline | 0.3773 | 0.1234 | 0.9079 | 0.0053 | +0.0000 | [+0.0000, +0.0000] |
| baseline+remain_strict | 0.3772 | 0.1234 | 0.9079 | 0.0048 | -0.0001 | [-0.0007, +0.0005] |
| baseline+remain_all | 0.3777 | 0.1235 | 0.9077 | 0.0052 | +0.0004 | [-0.0002, +0.0010] |
| baseline+remain_strict+step4 | 0.3783 | 0.1237 | 0.9075 | 0.0063 | +0.0010 | [-0.0008, +0.0027] |

## Post-plant only

| Variant | Log loss | Brier | AUC | Calibration error (ECE) | Δ log loss vs baseline | 90% range |
|---|---:|---:|---:|---:|---:|---:|
| baseline | 0.3269 | 0.1065 | 0.9218 | 0.0074 | +0.0000 | [+0.0000, +0.0000] |
| baseline+remain_strict | 0.3268 | 0.1064 | 0.9219 | 0.0074 | -0.0002 | [-0.0010, +0.0007] |
| baseline+remain_all | 0.3268 | 0.1064 | 0.9218 | 0.0076 | -0.0001 | [-0.0010, +0.0008] |
| baseline+remain_strict+step4 | 0.3288 | 0.1070 | 0.9211 | 0.0132 | +0.0018 | [-0.0003, +0.0038] |

## Verdict

A variant helps only if its 90% log-loss difference range is entirely below 0 and its calibration error is at most the baseline's + 0.002.

- Overall: no variant helps beyond noise.
- Post-plant: no variant helps beyond noise.
- The coach-facing check (defender win rate with a smoke left vs none) runs only if post-plant helps.
