# Fresh-candidate test of budget-conditioned XGBoost

Predictions, source-bound JSON ensembles and every control were committed before the six candidate attempts. **Scope: new candidates from consumed SHA256 source/input. This is not unseen-workload generalization.** The primary endpoint is best verified feasible speedup at three attempts, +64 LUT4 and12MHz. Five seeds repeat bootstrap/tie choices; they are not five independent workloads.

## Actual processor measurements

Baseline:26,135,630cycles,1,653LUT4. Correctness covers the recorded original full SHA input. Resources and Fmax are integrated synthesis/routing results, not board measurements.

| Candidate | Cycles | Speedup | Added LUT4 | Minimum Fmax MHz | Correctness | Charged seconds |
| --- | --- | --- | --- | --- | --- | --- |
| candidate_01 | 24798030 | 1.053939769 | 68 | 66.243 | Verified for recorded input | 67.968 |
| candidate_12 | 25257830 | 1.034753579 | 68 | 66.458 | Verified for recorded input | 69.423 |
| candidate_23 | 25466830 | 1.026261612 | 43 | 62.992 | Verified for recorded input | 63.840 |
| candidate_32 | 25816430 | 1.012364219 | 60 | 66.840 | Verified for recorded input | 66.389 |
| candidate_43 | 26029230 | 1.004087712 | 56 | 70.522 | Verified for recorded input | 65.009 |
| candidate_56 | 26134205 | 1.000054526 | 105 | 70.442 | Verified for recorded input | 64.125 |

## Equal-budget selection at +64 LUT4

| Policy | Query1 speedup | Query2 | Query3 | Query3 gap | Seconds at3 | Reference hits /5 |
| --- | --- | --- | --- | --- | --- | --- |
| Frequency | 1.015756967 | 1.026261612 | 1.026261612 | 0.000000000 | 198.197 | 5 |
| Merit | 1.000000000 | 1.000000000 | 1.026261612 | 0.000000000 | 201.231 | 5 |
| Calibrated latency | 1.000000000 | 1.000000000 | 1.026261612 | 0.000000000 | 201.231 | 5 |
| Latency + cost heuristic | 1.026261612 | 1.026261612 | 1.026261612 | 0.000000000 | 195.238 | 5 |
| Random | 1.013795031 | 1.023482133 | 1.023482133 | 0.002779478 | 197.200 | 4 |
| Original XGBoost | 1.000000000 | 1.000000000 | 1.019047353 | 0.007214258 | 201.975 | 3 |
| Pairwise XGBoost | 1.000000000 | 1.000000000 | 1.017923176 | 0.008338435 | 202.760 | 2 |
| Normalized XGBoost | 1.000000000 | 1.000000000 | 1.026261612 | 0.000000000 | 201.231 | 5 |
| Hybrid GP: zero shot | 1.000000000 | 1.000000000 | 1.026261612 | 0.000000000 | 201.231 | 5 |
| Hybrid GP: paid adaptation | 1.000000000 | 1.026261612 | 1.026261612 | 0.000000000 | 201.231 | 5 |
| Feasible-benefit XGBoost | 1.000000000 | 1.026261612 | 1.026261612 | 0.000000000 | 201.231 | 5 |

All table entries average the same five dependent seeds. Full caps32/64/128 and budgets1/2/3 are in endpoints.csv. A baseline-only reference is already available at query0/time0; retaining it is not discovery of an improved design. Measured outcomes reach each policy only through its charged replay queries. The exhaustive reference is separate; the complete physical pool was collected serially, so these are prospective predictions followed by cooperative replay, not live adaptive native search.

Pool diversity: six new literal formulas cover4 families, and all6 candidates have a family already seen in the consumed SHA pool. 0 reproduce an old SHA31-feature vector exactly. Related families are excluded from fitting, but model development already consumed the old target families. New literal/feature values do not establish independent-family transfer.

| Added LUT4 cap | Best verified speedup | Complete declared pool |
| --- | --- | --- |
| 32 | 1.000000000 | True |
| 64 | 1.026261612 | True |
| 128 | 1.053939769 | True |

## What the learned output means

One fixed XGBoost ensemble predicts signed saved cycles per executed replacement when measured hardware is feasible under the cap/clock, and zero decision utility when it is not. A cap-relative historical area proxy is its one new context feature. Utility times public replacements divided by baseline cycles ranks feasible program savings. This output is distinct from measured speedup, calibrated feasibility probability and confidence. Candidate-level bootstrap cap replicas retain one candidate of weight, and related families are excluded identically across learned policies. The original speedup/ranking models remain unchanged. Negative outcomes and heuristic wins remain valid.

| Added LUT4 cap | Known candidates | Mean utility coverage of90% bootstrap range | Calibrated confidence |
| --- | --- | --- | --- |
| 32 | 6 | 0.200000000 | False |
| 64 | 6 | 0.166666667 | False |
| 128 | 6 | 0.333333333 | False |

Coverage is for the signed feasible-utility target, averaged over dependent model seeds; it is not coverage of whole-program speedup and is not directly comparable with the old speedup intervals. Unknown failures are excluded from this diagnostic rather than assigned zero utility.

## Costs and limits

Training availability:27 successful non-SHA labels plus3 failed historical attempts, 1698.153 recorded candidate seconds; 21 rows fit after family exclusions. All36 previously consumed development attempts cost2100.614seconds, including six old SHA labels excluded from fitting. Neither excluded labels nor model development are free.

The new native pool used6 charged attempts and396.754ledger seconds. Baseline ledger time:39.347seconds. The native command timer overlaps these scopes. Utility fit plus all-cap prediction time by seed:0.052545s, 0.053798s, 0.053245s, 0.052941s, 0.052822s. It is reported separately, not imputed as zero from a missing inference field. Replay host time is not native search lifetime. Old/new duration scopes and shared-history costs preclude an unqualified end-to-end time claim.

Hardware cost is context dependent. Bootstrap intervals are uncalibrated; this experiment does not repair calibration or demonstrate broad ML superiority. Single-instruction results do not add across a selected set. Joint lowering/execution/area/timing must be measured together.
