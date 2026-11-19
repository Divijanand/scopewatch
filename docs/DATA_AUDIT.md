# Data audit (step 2)

Run 2026-11-19 with `python -m scripts.data_audit` on the full store. Aggregates only. What happens, how often, and where the data is too thin for a model to learn.

## 1. Corpus and ingest health

- 856 series, 2,078 games, 42,490 rounds.
- Reversals undone during ingest: 15,622 (non-LIFO 0, unmatched 0).
- Kills still without a weapon after the backfill: 123.

## 2. Game states the win-probability model sees (T1)

323,903 training states (after each kill and plant) in 856 series, 91 distinct (attackers alive, defenders alive, planted) states.

| State | States | Attackers win |
|---|---|---|
| 4v5 (first kill to defense) | 21,473 | 30.8% |
| 5v4 (first kill to attack) | 18,068 | 74.1% |
| 1v1, no plant | 1,844 | 42.5% |
| 1v1, planted | 5,316 | 63.3% |
| 2v1, planted | 7,027 | 90.1% |
| 1v2, planted | 5,158 | 26.5% |
| 1v3, planted (attacker clutch) | 3,608 | 8.6% |
| 4v1, no plant | 2,055 | 99.6% |
| 1v4, no plant | 5,617 | 1.0% |
| 1v5, planted | 536 | 1.3% |

**Thin states** (fewer than 200 training states): 22 of 91, covering 396 states (0.1% of all). These are where model ranges must be widest, and where synthetic stress tests are useful.

| Attackers | Defenders | Planted | States | Attackers win |
|---|---|---|---|---|
| -1 | 0 | yes | 1 | 0.0% |
| 0 | -1 | yes | 1 | 100.0% |
| 4 | -1 | no | 2 | 100.0% |
| 1 | -1 | no | 3 | 100.0% |
| 2 | -1 | no | 3 | 100.0% |
| -1 | 5 | no | 4 | 0.0% |
| 5 | -1 | yes | 4 | 100.0% |
| 3 | -1 | no | 5 | 100.0% |
| -1 | 4 | yes | 6 | 0.0% |
| -1 | 1 | no | 10 | 0.0% |
| 4 | -1 | yes | 12 | 100.0% |
| -1 | 4 | no | 13 | 0.0% |

States with a negative alive count (more deaths than players, a data error): 303.

## 3. Economy matchups (T4 and every model's prior)

| Attack | Defense | Rounds | Attackers win |
|---|---|---|---|
| full | full | 25,059 | 50.0% |
| full | half | 5,055 | 78.2% |
| half | full | 4,100 | 25.2% |
| eco | eco | 3,830 | 50.8% |
| full | eco | 2,227 | 88.9% |
| eco | full | 1,724 | 12.2% |
| half | eco | 339 | 61.1% |
| eco | half | 132 | 35.6% |
| half | half | 24 | 50.0% |

Eco-vs-full rounds are rare and lopsided: the model learns them from few examples.

## 4. Drift by patch

| Patch | Rounds | Attackers win | Planted | Full buys with an Operator |
|---|---|---|---|---|
| 10.00 | 563 | 55.6% | 68.9% | 27.3% |
| 10.01 | 1,281 | 51.4% | 70.4% | 25.9% |
| 10.03 | 380 | 44.2% | 67.4% | 22.0% |
| 10.04 | 1,782 | 50.5% | 66.9% | 22.4% |
| 10.05 | 2,183 | 52.2% | 64.9% | 21.6% |
| 10.06 | 805 | 53.0% | 72.9% | 26.2% |
| 10.07 | 2,694 | 50.1% | 66.2% | 24.6% |
| 10.08 | 667 | 49.5% | 67.0% | 28.5% |
| 10.09 | 1,257 | 53.0% | 67.1% | 33.9% |
| 10.10 | 1,275 | 52.7% | 65.5% | 21.8% |
| 10.11 | 3,671 | 52.4% | 69.4% | 23.4% |
| 11.00 | 6,173 | 50.6% | 66.9% | 23.2% |
| 11.04 | 1,424 | 53.9% | 68.1% | 28.2% |
| 11.06 | 664 | 52.6% | 69.9% | 35.1% |
| 11.07 | 1,592 | 51.8% | 70.9% | 34.6% |
| 11.09 | 966 | 50.1% | 65.1% | 33.3% |
| 12.01 | 1,077 | 50.6% | 67.3% | 41.8% |
| 12.02 | 1,514 | 54.3% | 71.2% | 40.8% |
| 12.03 | 301 | 53.5% | 74.8% | 26.7% |
| 12.04 | 1,198 | 52.4% | 71.2% | 28.0% |
| 12.05 | 568 | 53.5% | 70.2% | 24.1% |
| 12.06 | 624 | 45.0% | 62.5% | 33.5% |
| 12.07 | 3,170 | 54.7% | 70.3% | 34.4% |
| 12.08 | 2,191 | 50.0% | 68.7% | 31.5% |
| 12.09 | 2,156 | 49.7% | 68.1% | 33.9% |
| 12.10 | 369 | 42.0% | 64.5% | 37.2% |
| 12.11 | 1,025 | 52.3% | 70.0% | 30.0% |
| 13.00 | 560 | 51.4% | 67.0% | 37.3% |
| 13.01 | 47 | 72.3% | 87.2% | 32.8% |
| 13.02 | 208 | 53.8% | 69.7% | 30.7% |
| 13.04 | 43 | 58.1% | 65.1% | 39.1% |
| 13.05 | 62 | 37.1% | 67.7% | 30.4% |

Across patches with at least 500 rounds, the attacker win rate ranges from 45.0% to 55.6%. A model trained on all patches averages over that; the patch-forward check (ML_TAXONOMY.md section 5) measures what drift costs.

## 5. Agents and roles

| Agent | Role | Player rounds | Share in first patch → last patch with data |
|---|---|---|---|
| omen | controller | 54,239 | 10.3% → 13.4% |
| sova | initiator | 37,655 | 5.9% → 13.5% |
| viper | controller | 32,910 | 5.7% → 6.5% |
| neon | duelist | 27,624 | 0.8% → 6.6% |
| cypher | sentinel | 25,662 | 6.0% → 8.8% |
| fade | initiator | 25,620 | 4.6% → 6.5% |
| breach | initiator | 22,806 | 9.4% → 1.1% |
| raze | duelist | 21,290 | 10.2% → 3.2% |
| jett | duelist | 20,501 | 6.6% → 6.8% |
| yoru | duelist | 20,089 | 2.7% → 10.0% |
| vyse | sentinel | 18,774 | 4.2% → 6.6% |
| tejo | initiator | 15,794 | 7.6% → 1.7% |
| killjoy | sentinel | 15,423 | 2.3% → 3.4% |
| astra | controller | 14,988 | 6.7% → 3.4% |
| chamber | sentinel | 9,307 | 0.8% → 5.6% |
| kay/o | initiator | 9,146 | 3.8% → 0.8% |
| skye | initiator | 8,765 | 2.2% → 1.2% |
| brimstone | controller | 8,684 | 4.0% → 4.9% |
| waylay | duelist | 7,827 | 0.8% → 3.4% |
| phoenix | duelist | 5,397 | 0.4% → 3.4% |
| deadlock | sentinel | 4,748 | 1.5% → 5.6% |
| iso | duelist | 4,346 | 0.3% → 1.9% |
| clove | controller | 3,425 | 1.6% → 6.6% |
| sage | sentinel | 3,285 | 1.0% → 3.4% |
| gekko | initiator | 2,466 | 1.6% → 0.4% |
| harbor | controller | 2,463 | 0.2% → 3.4% |
| reyna | duelist | 1,317 | 0.1% → 4.9% |
|  | ? | 1,228 | 0.6% → 0.8% |
| veto | sentinel | 475 | 1.6% → 0.2% |
| miks | controller | 259 | 0.6% → 0.1% |

873 distinct team comps across 4,156 team-games: most comps are seen once or twice, so a model should use roles and agent embeddings, not one comp = one category.

## 6. Utility data quality

- 1,509,064 casts; 99.9% have a usable position; 12.6% come from about 1 Hz position sampling.
- Events where more than 20% of casts are low-rate:
  - VCT Americas - Stage 1 2025: 86,075 casts, 100% low-rate
  - VCT Americas - Kickoff 2025: 47,331 casts, 100% low-rate
  - VCT Americas - Stage 2 2025: 80,369 casts, 68% low-rate

A position-based utility feature must carry the low-rate flag, or be dropped for those events.

## 7. What this means for each task

- **T1 win probability:** 323,903 states is plenty for gradient boosting and a small sequence model. The risk is the 22 thin states, not the total.
- **T2 next-round site:** 28,978 plants, but per team and map the data is small: 461 of 1,109 (team, map) pairs have fewer than 24 attack rounds (two halves). Team habits must be pooled toward the league (shrinkage), and the baseline to beat is "always their most common site".
- **T3 Operator buy:** depends on economy and on who's on the team. A roster change resets a team's habits, so recent rounds should count for more.
- **All tasks:** split by series; check patch-forward; report thin-state performance separately.

