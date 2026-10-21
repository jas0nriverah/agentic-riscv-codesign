# Held-out BEEBS DCT: factorized selection test

The complete models, public features and predictions were pushed at `a2004f9540a2355c7b2fec31cacfa8fe8f153bb4` before six serial one-attempt measurements. This source had no earlier candidate outcomes. The original full input and all64 coefficient checks are unchanged. It is BEEBS, not Embench. The fixed primary endpoint is best verified feasible speedup at three attempts, +64LUT4 and12MHz.

## Actual processor outcomes

Baseline:117,522 cycles,1,653 LUT4, minimum routed Fmax68.493149MHz. PicoRV32 RV32I/ILP32, original8KiB synchronous RAM, checked3072-byte program limit,128-byte guard and4992-byte stack reservation. All area/Fmax results are integrated synthesis and three routing seeds, not physical-board measurements.

| Candidate | Cycles | Speedup | Added LUT4 | Minimum Fmax MHz | Correctness | Ledger s | Outer operation s |
| --- | --- | --- | --- | --- | --- | --- | --- |
| candidate_00 | 116946 | 1.004925350 | 61 | 70.911926270 | Verified for recorded input | 37.533 | 39.599 |
| candidate_06 | 117394 | 1.001090345 | 72 | 65.036415100 | Verified for recorded input | 42.881 | 44.856 |
| candidate_11 | 117474 | 1.000408601 | 33 | 60.390121460 | Verified for recorded input | 36.170 | 38.219 |
| candidate_17 | 117474 | 1.000408601 | 15 | 69.348129272 | Verified for recorded input | 38.586 | 40.577 |
| candidate_22 | 117450 | 1.000613027 | 62 | 65.475021362 | Verified for recorded input | 45.633 | 47.631 |
| candidate_28 | 117482 | 1.000340478 | 36 | 67.805801392 | Verified for recorded input | 49.970 | 52.104 |

Measured cycles remain distinct from public analytic estimates. The candidates.csv file contains both and their residuals. The fixed pool contains six rank-stratified candidates from29 eligible formulas; its oracle does not cover every legal formula.

## Equal-budget primary comparison

| Policy | Query1 speedup | Query2 | Query3 | Gap at3 | Ledger s at3 | Outer s at3 | Optimum hits /5 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Frequency | 1.004925350 | 1.004925350 | 1.004925350 | 0.000000000 | 113.148 | 119.251 | 5 |
| Merit | 1.004925350 | 1.004925350 | 1.004925350 | 0.000000000 | 118.959 | 125.028 | 5 |
| Calibrated latency | 1.004925350 | 1.004925350 | 1.004925350 | 0.000000000 | 126.047 | 132.086 | 5 |
| Latency + cost heuristic | 1.000408601 | 1.000408601 | 1.000408601 | 0.004516749 | 124.726 | 130.901 | 0 |
| Random | 1.001352836 | 1.001352836 | 1.001393721 | 0.003531629 | 122.705 | 128.793 | 1 |
| Original XGBoost | 1.004925350 | 1.004925350 | 1.004925350 | 0.000000000 | 120.386 | 126.516 | 5 |
| Pairwise XGBoost | 1.004925350 | 1.004925350 | 1.004925350 | 0.000000000 | 117.067 | 123.145 | 5 |
| Normalized XGBoost | 1.004925350 | 1.004925350 | 1.004925350 | 0.000000000 | 126.047 | 132.086 | 5 |
| Hybrid GP: zero shot | 1.004925350 | 1.004925350 | 1.004925350 | 0.000000000 | 126.047 | 132.086 | 5 |
| Hybrid GP: paid adaptation | 1.004925350 | 1.004925350 | 1.004925350 | 0.000000000 | 126.047 | 132.086 | 5 |
| Feasible-benefit XGBoost | 1.004925350 | 1.004925350 | 1.004925350 | 0.000000000 | 114.490 | 120.578 | 5 |
| Factorized feasibility XGBoost | 1.004925350 | 1.004925350 | 1.004925350 | 0.000000000 | 116.208 | 122.290 | 5 |

All policies see the same historical information and candidate pool, and pay for every attempted query before receiving its outcome. Five seeds repeat bootstrap/tie choices; they are dependent, not five independent workloads. The complete physical pool is collected for a separate oracle and cooperative paid replay. This is not a live adaptive hardware search. Three-query policies still spend all three attempts after finding the optimum. A baseline-only reference is available at query0/time0, not an improved-design discovery. Full caps32/64/128 and all budgets are in endpoints.csv.

| Added LUT4 cap | Best verified speedup | Complete declared-pool reference |
| --- | --- | --- |
| 32 | 1.000408601 | True |
| 64 | 1.004925350 | True |
| 128 | 1.004925350 | True |

## What changed in the model

39 historical labels are available; 38 candidates from 6 sources remain after identical family exclusions. One fixed20-member XGBoost binary ensemble predicts hardware feasibility conditional on verified successful execution. Its score multiplies nonnegative public calibrated cycle savings divided by baseline cycles. It does not relearn the already exact historical cycle deltas, predict correctness, or replace paid acceptance checks. Features, cap replicas,80trees/depth2 and seeds remain fixed; the changed objective/target is the declared experiment. No setting was chosen using these new outcomes.

This follows the separation of objective and constraints in [Gardner et al.,2014,§3.1–3.2](https://proceedings.mlr.press/v32/gardner14.pdf). It is not a reproduction of constrained expected improvement: there is no GP objective posterior or expected-improvement acquisition in the new static policy.

| Cap | New feasibility Brier | Existing GP Brier | Known candidates |
| --- | --- | --- | --- |
| 32 | 0.130626320 | 0.147464716 | 6 |
| 64 | 0.213193995 | 0.211783258 | 6 |
| 128 | 0.012270206 | 0.000638860 | 6 |

Brier error measures hardware feasibility only on successfully verified candidates. Unknown failures are excluded from that denominator and remain charged. Bootstrap spread is estimator disagreement; scores are uncalibrated. Comparing binary labels to score quantiles would not establish90% predictive coverage. Cap-monotonicity violations and training-range flags are diagnostics, with no abstention threshold or post-label reranking.

## Cost accounting and limits

Historical cost:42 attempts / 2497.368 recorded candidate seconds, including two recorded invalid executions and one infrastructure-censored unknown. All three remain outside fitting. New pool:6 attempts / 250.772ledger seconds; 262.987outer-operation seconds. Baseline ledger:27.570s. 133 native commands:266.639s. These scopes overlap and must not be summed. Outer-operation time includes evaluator creation, discovery authentication, hardware work and lock close, excluding interpreter startup; the raw collection-driver records also retain complete subprocess wall time. All policy times are sums of observed paid operations, not a measured adaptive-search lifetime.

New model fitting / all-cap prediction seconds by seed: 0.050706/0.005108, 0.053122/0.004931, 0.050604/0.004970, 0.051143/0.004956, 0.050629/0.005119. Eleven-control fitting, setup/calibration, failed qualification and report/replay host time remain separate. Previous duration scopes and shared-history costs preclude an unqualified end-to-end time claim.

One additional source is a useful transfer test, not evidence of broad ML superiority. The short DCT workload and restricted candidate shapes limit absolute improvements and architectural diversity. Preserve heuristic wins, ties, regressions and poor calibration. No further variant is selected from these now-consumed labels. Joint instruction sets and an independent-source reliability test remain future work.
