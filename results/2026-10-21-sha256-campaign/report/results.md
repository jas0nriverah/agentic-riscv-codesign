# Guarded instruction selection: embench-nettle-sha256

Scope: **prospective**. Primary endpoint: three charged candidate attempts, +64 LUT4, 12 MHz. One source workload is the independent unit; five seeds are dependent bootstrap/tie repetitions. These results do not establish broad generalization. Values come from checked RTL simulation and integrated FPGA synthesis/routing.

No learned policy exceeds calibrated latency at the primary endpoint; some perform worse.

Retained baseline: 26135630 cycles; 1653 integrated LUT4; minimum routed Fmax: not retained in the selection report.

## Verified references

| Added LUT4 cap | Best verified speedup | Selected candidate | Complete recorded pool |
| --- | --- | --- | --- |
| 32 | 1.000000000 | Baseline | True |
| 64 | 1.021384665 | candidate_22 | True |
| 128 | 1.053939769 | candidate_00 | True |

References cover the declared recorded-input pool, including baseline and known invalid attempts. They do not cover all legal instructions or other inputs.

A reference equal to 1.0 is baseline retention; reference hits in that case are not discoveries of improved designs.

## Candidate outcomes

| Candidate | Verified cycles | Speedup | LUT4 / added | Min Fmax MHz | Correctness | Charged wall seconds |
| --- | --- | --- | --- | --- | --- | --- |
| candidate_00 | 24798030 | 1.053939769 | 1721 / 68 | 68.250 | Verified for recorded input | 67.047 |
| candidate_11 | 25257830 | 1.034753579 | 1721 / 68 | 68.097 | Verified for recorded input | 66.034 |
| candidate_22 | 25588430 | 1.021384665 | 1703 / 50 | 65.994 | Verified for recorded input | 67.471 |
| candidate_33 | 25770830 | 1.014155539 | 1714 / 61 | 68.587 | Verified for recorded input | 67.009 |
| candidate_44 | 25998830 | 1.005261775 | 1700 / 47 | 66.627 | Verified for recorded input | 70.734 |
| candidate_57 | 26134205 | 1.000054526 | 1754 / 101 | 67.609 | Verified for recorded input | 64.165 |

Correctness failures apply to the recorded run, not every possible input. Blank performance/hardware values are unverified. The charged ledger wall time includes the complete attempt; original measurement-record duration is retained separately in candidates.csv. Failed attempts still consume their query and known wall time.

## Analytic cycle check

| Verified candidate | Estimated saved cycles | Measured saved cycles | Residual: measured minus estimated |
| --- | --- | --- | --- |
| candidate_00 | 1337600 | 1337600 | 0 |
| candidate_11 | 877800 | 877800 | 0 |
| candidate_22 | 547200 | 547200 | 0 |
| candidate_33 | 364800 | 364800 | 0 |
| candidate_44 | 136800 | 136800 | 0 |
| candidate_57 | 1425 | 1425 | 0 |

## Frozen regression diagnostics

| Model | Dependent seed repetitions | Mean speedup MAE | Nominal interval coverage (%) |
| --- | --- | --- | --- |
| normalized | 5 | 0.006941309 | 43.3 |
| raw | 5 | 0.016548112 | 16.7 |

These diagnostics cover verified success labels only. Failed and censored attempts have no regression label. Means across dependent model seeds are descriptive; nominal ensemble coverage is not calibrated confidence. Lower prediction error does not by itself establish a selection win.

## Equal-budget policy results

### At most 32 added LUT4

| Policy | Queries | Mean best speedup | Gap to verified reference | Reference hits / 5 | Mean attempt seconds | Mean failed queries |
| --- | --- | --- | --- | --- | --- | --- |
| Frequency | 1 | 1.000000000 | 0.000000000 | 5 | 67.301 | 0.0 |
| Frequency | 2 | 1.000000000 | 0.000000000 | 5 | 134.518 | 0.0 |
| Frequency | 3 | 1.000000000 | 0.000000000 | 5 | 201.528 | 0.0 |
| Merit | 1 | 1.000000000 | 0.000000000 | 5 | 67.047 | 0.0 |
| Merit | 2 | 1.000000000 | 0.000000000 | 5 | 133.081 | 0.0 |
| Merit | 3 | 1.000000000 | 0.000000000 | 5 | 200.552 | 0.0 |
| Calibrated latency | 1 | 1.000000000 | 0.000000000 | 5 | 67.047 | 0.0 |
| Calibrated latency | 2 | 1.000000000 | 0.000000000 | 5 | 133.081 | 0.0 |
| Calibrated latency | 3 | 1.000000000 | 0.000000000 | 5 | 200.552 | 0.0 |
| Latency + cost heuristic | 1 | 1.000000000 | 0.000000000 | 5 | 67.047 | 0.0 |
| Latency + cost heuristic | 2 | 1.000000000 | 0.000000000 | 5 | 134.518 | 0.0 |
| Latency + cost heuristic | 3 | 1.000000000 | 0.000000000 | 5 | 200.552 | 0.0 |
| Random | 1 | 1.000000000 | 0.000000000 | 5 | 67.947 | 0.0 |
| Random | 2 | 1.000000000 | 0.000000000 | 5 | 134.572 | 0.0 |
| Random | 3 | 1.000000000 | 0.000000000 | 5 | 201.367 | 0.0 |
| Original XGBoost | 1 | 1.000000000 | 0.000000000 | 5 | 66.439 | 0.0 |
| Original XGBoost | 2 | 1.000000000 | 0.000000000 | 5 | 133.081 | 0.0 |
| Original XGBoost | 3 | 1.000000000 | 0.000000000 | 5 | 201.112 | 0.0 |
| Pairwise XGBoost | 1 | 1.000000000 | 0.000000000 | 5 | 66.642 | 0.0 |
| Pairwise XGBoost | 2 | 1.000000000 | 0.000000000 | 5 | 133.081 | 0.0 |
| Pairwise XGBoost | 3 | 1.000000000 | 0.000000000 | 5 | 200.275 | 0.0 |
| Normalized XGBoost | 1 | 1.000000000 | 0.000000000 | 5 | 67.047 | 0.0 |
| Normalized XGBoost | 2 | 1.000000000 | 0.000000000 | 5 | 133.081 | 0.0 |
| Normalized XGBoost | 3 | 1.000000000 | 0.000000000 | 5 | 200.552 | 0.0 |
| Hybrid GP: zero shot | 1 | 1.000000000 | 0.000000000 | 5 | 67.047 | 0.0 |
| Hybrid GP: zero shot | 2 | 1.000000000 | 0.000000000 | 5 | 133.081 | 0.0 |
| Hybrid GP: zero shot | 3 | 1.000000000 | 0.000000000 | 5 | 200.552 | 0.0 |
| Hybrid GP: paid adaptation | 1 | 1.000000000 | 0.000000000 | 5 | 67.047 | 0.0 |
| Hybrid GP: paid adaptation | 2 | 1.000000000 | 0.000000000 | 5 | 134.518 | 0.0 |
| Hybrid GP: paid adaptation | 3 | 1.000000000 | 0.000000000 | 5 | 205.252 | 0.0 |

### At most 64 added LUT4

| Policy | Queries | Mean best speedup | Gap to verified reference | Reference hits / 5 | Mean attempt seconds | Mean failed queries |
| --- | --- | --- | --- | --- | --- | --- |
| Frequency | 1 | 1.012830799 | 0.008553866 | 3 | 67.301 | 0.0 |
| Frequency | 2 | 1.021384665 | 0.000000000 | 5 | 134.518 | 0.0 |
| Frequency | 3 | 1.021384665 | 0.000000000 | 5 | 201.528 | 0.0 |
| Merit | 1 | 1.000000000 | 0.021384665 | 0 | 67.047 | 0.0 |
| Merit | 2 | 1.000000000 | 0.021384665 | 0 | 133.081 | 0.0 |
| Merit | 3 | 1.021384665 | 0.000000000 | 5 | 200.552 | 0.0 |
| Calibrated latency | 1 | 1.000000000 | 0.021384665 | 0 | 67.047 | 0.0 |
| Calibrated latency | 2 | 1.000000000 | 0.021384665 | 0 | 133.081 | 0.0 |
| Calibrated latency | 3 | 1.021384665 | 0.000000000 | 5 | 200.552 | 0.0 |
| Latency + cost heuristic | 1 | 1.021384665 | 0.000000000 | 5 | 67.471 | 0.0 |
| Latency + cost heuristic | 2 | 1.021384665 | 0.000000000 | 5 | 134.480 | 0.0 |
| Latency + cost heuristic | 3 | 1.021384665 | 0.000000000 | 5 | 205.215 | 0.0 |
| Random | 1 | 1.012437329 | 0.008947336 | 2 | 67.947 | 0.0 |
| Random | 2 | 1.019938840 | 0.001445825 | 4 | 134.572 | 0.0 |
| Random | 3 | 1.019938840 | 0.001445825 | 4 | 201.367 | 0.0 |
| Original XGBoost | 1 | 1.000000000 | 0.021384665 | 0 | 66.439 | 0.0 |
| Original XGBoost | 2 | 1.000000000 | 0.021384665 | 0 | 133.081 | 0.0 |
| Original XGBoost | 3 | 1.016714262 | 0.004670403 | 3 | 201.112 | 0.0 |
| Pairwise XGBoost | 1 | 1.000000000 | 0.021384665 | 0 | 66.642 | 0.0 |
| Pairwise XGBoost | 2 | 1.000000000 | 0.021384665 | 0 | 133.081 | 0.0 |
| Pairwise XGBoost | 3 | 1.017047190 | 0.004337475 | 2 | 200.275 | 0.0 |
| Normalized XGBoost | 1 | 1.000000000 | 0.021384665 | 0 | 67.047 | 0.0 |
| Normalized XGBoost | 2 | 1.000000000 | 0.021384665 | 0 | 133.081 | 0.0 |
| Normalized XGBoost | 3 | 1.021384665 | 0.000000000 | 5 | 200.552 | 0.0 |
| Hybrid GP: zero shot | 1 | 1.000000000 | 0.021384665 | 0 | 67.047 | 0.0 |
| Hybrid GP: zero shot | 2 | 1.000000000 | 0.021384665 | 0 | 133.081 | 0.0 |
| Hybrid GP: zero shot | 3 | 1.021384665 | 0.000000000 | 5 | 200.552 | 0.0 |
| Hybrid GP: paid adaptation | 1 | 1.000000000 | 0.021384665 | 0 | 67.047 | 0.0 |
| Hybrid GP: paid adaptation | 2 | 1.021384665 | 0.000000000 | 5 | 134.518 | 0.0 |
| Hybrid GP: paid adaptation | 3 | 1.021384665 | 0.000000000 | 5 | 200.552 | 0.0 |

### At most 128 added LUT4

| Policy | Queries | Mean best speedup | Gap to verified reference | Reference hits / 5 | Mean attempt seconds | Mean failed queries |
| --- | --- | --- | --- | --- | --- | --- |
| Frequency | 1 | 1.034406706 | 0.019533062 | 2 | 67.301 | 0.0 |
| Frequency | 2 | 1.053939769 | 0.000000000 | 5 | 134.518 | 0.0 |
| Frequency | 3 | 1.053939769 | 0.000000000 | 5 | 201.528 | 0.0 |
| Merit | 1 | 1.053939769 | 0.000000000 | 5 | 67.047 | 0.0 |
| Merit | 2 | 1.053939769 | 0.000000000 | 5 | 133.081 | 0.0 |
| Merit | 3 | 1.053939769 | 0.000000000 | 5 | 200.552 | 0.0 |
| Calibrated latency | 1 | 1.053939769 | 0.000000000 | 5 | 67.047 | 0.0 |
| Calibrated latency | 2 | 1.053939769 | 0.000000000 | 5 | 133.081 | 0.0 |
| Calibrated latency | 3 | 1.053939769 | 0.000000000 | 5 | 200.552 | 0.0 |
| Latency + cost heuristic | 1 | 1.053939769 | 0.000000000 | 5 | 67.047 | 0.0 |
| Latency + cost heuristic | 2 | 1.053939769 | 0.000000000 | 5 | 133.081 | 0.0 |
| Latency + cost heuristic | 3 | 1.053939769 | 0.000000000 | 5 | 200.552 | 0.0 |
| Random | 1 | 1.023225283 | 0.030714486 | 1 | 67.947 | 0.0 |
| Random | 2 | 1.026449861 | 0.027489908 | 1 | 134.572 | 0.0 |
| Random | 3 | 1.031797426 | 0.022142342 | 1 | 201.367 | 0.0 |
| Original XGBoost | 1 | 1.042428055 | 0.011511714 | 2 | 66.439 | 0.0 |
| Original XGBoost | 2 | 1.053939769 | 0.000000000 | 5 | 133.081 | 0.0 |
| Original XGBoost | 3 | 1.053939769 | 0.000000000 | 5 | 201.112 | 0.0 |
| Pairwise XGBoost | 1 | 1.046265293 | 0.007674476 | 3 | 66.642 | 0.0 |
| Pairwise XGBoost | 2 | 1.053939769 | 0.000000000 | 5 | 133.081 | 0.0 |
| Pairwise XGBoost | 3 | 1.053939769 | 0.000000000 | 5 | 200.275 | 0.0 |
| Normalized XGBoost | 1 | 1.053939769 | 0.000000000 | 5 | 67.047 | 0.0 |
| Normalized XGBoost | 2 | 1.053939769 | 0.000000000 | 5 | 133.081 | 0.0 |
| Normalized XGBoost | 3 | 1.053939769 | 0.000000000 | 5 | 200.552 | 0.0 |
| Hybrid GP: zero shot | 1 | 1.053939769 | 0.000000000 | 5 | 67.047 | 0.0 |
| Hybrid GP: zero shot | 2 | 1.053939769 | 0.000000000 | 5 | 133.081 | 0.0 |
| Hybrid GP: zero shot | 3 | 1.053939769 | 0.000000000 | 5 | 200.552 | 0.0 |
| Hybrid GP: paid adaptation | 1 | 1.053939769 | 0.000000000 | 5 | 67.047 | 0.0 |
| Hybrid GP: paid adaptation | 2 | 1.053939769 | 0.000000000 | 5 | 133.081 | 0.0 |
| Hybrid GP: paid adaptation | 3 | 1.053939769 | 0.000000000 | 5 | 200.552 | 0.0 |

## Costs and limits

Historical data: 27 verified labels and 3 failed attempts (30 attempts), costing 1647.956297 verified-label wall-seconds plus 50.196657 failed-attempt wall-seconds = **1698.152954 seconds**. The frozen model’s historical cost field counts successful labels only; the full attempt total above includes failures once.

Current candidate attempts: 6; known charged wall time 402.461094 seconds; wall-time accounting complete: True. Baseline ledger wall time: 35.443627 seconds. Native command time: 277.326737 seconds in 133 commands. Baseline, setup, historical qualification, calibration and inference have separate scopes. Native command times overlap evaluation wall times and must not be added. policy-endpoints.csv reports target-only and shared-history-plus-target attempt time, with inference separate.

A tie in best verified feasible performance is not a learned selection win. Faster failed attempts alone do not demonstrate better acquisition. Bootstrap/GP uncertainty is not calibrated confidence. Single-instruction outcomes do not establish the behavior of a jointly installed instruction set.

This presenter reads the sealed completed report only. It performs zero model fits and zero native measurements; raw evidence authentication and exact historical refits belong to guarded_selection replay.
