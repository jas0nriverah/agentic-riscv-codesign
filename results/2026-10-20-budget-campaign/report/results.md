# ISAForge: prospective equal-budget results

Primary comparison: three paid candidate evaluations, at most 64 added LUT4, 12 MHz, five dependent seeds. Two source workloads are the independent test units. The reference is the best verified feasible design found in each frozen six-candidate pool. Any infrastructure-censored attempt makes that reference a lower bound on the pool optimum. Figures are RTL simulation and integrated FPGA synthesis/routing, not physical-board measurements.

## embench-edn

Baseline: 386,561,849 cycles; 1,653 LUT4. All routing seeds are retained in the raw evidence.

Best verified pool reference. Reference over verified candidates, baseline, and observed invalid recorded runs in the declared pool.

| Candidate | Verified cycles | Speedup | LUT4 / added | FF | Carry | Min Fmax MHz | Feasible at +64 | Correctness | Charged seconds |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| candidate_00 | 386394809 | 1.000432304 | 1685 / 32 | 696 | 297 | 71.11869812011719 | True | Verified for recorded input | 139.583 |
| candidate_03 | 386424041 | 1.000356624 | 1683 / 30 | 696 | 297 | 67.54930877685547 | True | Verified for recorded input | 135.741 |
| candidate_08 | 386540099 | 1.000056268 | 1723 / 70 | 712 | 326 | 61.85439682006836 | False | Verified for recorded input | 130.047 |
| candidate_11 | 386561327 | 1.000001350 | 1715 / 62 | 712 | 320 | 67.76904296875 | True | Verified for recorded input | 123.883 |
| candidate_14 | 386561501 | 1.000000900 | 1718 / 65 | 711 | 326 | 62.16972732543945 | False | Verified for recorded input | 133.031 |
| candidate_17 |  |  |  |  |  |  | False | Memory-contract failure on recorded run | 11.147 |

| Failed attempt | Classification | Charged seconds | Reason |
| --- | --- | --- | --- |
| candidate_17 | memory_contract_failure | 11.147 | ValueError('Command exited 10; see /Users/jasonrivera/Documents/Codex/2026-10-19/clo/agentic-riscv-codesign/generated/extended-edn-2026-10-20/measurements/candidate_17/attempt-000/simulation/simulation.json') |

Recorded-run self-check or memory-contract failures are not proofs about all inputs. Blank hardware/performance values were not verified. Unverified observed cycles, where available, are diagnostic only and are retained separately in candidates.csv. Every failed attempt consumes its query and recorded wall time.

All five learned policies tie calibrated latency at the primary endpoint; this comparison shows no learned selection win.

| Policy | Mean best speedup | Verified-reference hits / 5 | Mean candidate seconds |
| --- | --- | --- | --- |
| Frequency | 1.000432304 | 5 | 405.370 |
| Merit | 1.000432304 | 5 | 405.370 |
| Calibrated latency | 1.000432304 | 5 | 405.370 |
| Latency + cost heuristic | 1.000356624 | 0 | 389.671 |
| Random | 1.000229650 | 1 | 343.028 |
| Original XGBoost | 1.000432304 | 5 | 309.017 |
| Pairwise XGBoost | 1.000432304 | 5 | 393.513 |
| Normalized XGBoost | 1.000432304 | 5 | 405.370 |
| Hybrid GP: zero shot | 1.000432304 | 5 | 405.370 |
| Hybrid GP: paid adaptation | 1.000432304 | 5 | 405.370 |

## embench-ud

Baseline: 37,845,951 cycles; 1,653 LUT4. All routing seeds are retained in the raw evidence.

Best verified pool reference. Lower bound on the frozen-pool optimum: interrupted attempts have unknown performance, hardware feasibility and/or correctness.

| Candidate | Verified cycles | Speedup | LUT4 / added | FF | Carry | Min Fmax MHz | Feasible at +64 | Correctness | Charged seconds |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| candidate_00 | 37690761 | 1.004117455 | 1723 / 70 | 712 | 326 | 68.8563003540039 | False | Verified for recorded input | 48.403 |
| candidate_02 | 37766139 | 1.002113322 | 1719 / 66 | 712 | 326 | 66.48936462402344 | False | Verified for recorded input | 48.453 |
| candidate_04 | 37748403 | 1.002584162 | 1718 / 65 | 710 | 324 | 70.40766143798828 | False | Verified for recorded input | 47.586 |
| candidate_06 | 37816391 | 1.000781672 | 1725 / 72 | 712 | 324 | 69.7690658569336 | False | Verified for recorded input | 47.303 |
| candidate_08 |  |  |  |  |  |  | False | Self-check failed on recorded run | 7.727 |
| candidate_10 |  |  |  |  |  |  |  | Unverified: infrastructure interrupted attempt | 31.323 |

| Failed attempt | Classification | Charged seconds | Reason |
| --- | --- | --- | --- |
| candidate_08 | self_check_failure | 7.727 | ValueError('Command exited 7; see /Users/jasonrivera/Documents/Codex/2026-10-19/clo/agentic-riscv-codesign/generated/qualified-ud-2026-10-20/measurements/candidate_08/attempt-000/simulation/simulation.json') |
| candidate_10 | infrastructure_unknown | 31.323 | ValueError('Less than 2 GiB free') |

Recorded-run self-check or memory-contract failures are not proofs about all inputs. Blank hardware/performance values were not verified. Unverified observed cycles, where available, are diagnostic only and are retained separately in candidates.csv. Every failed attempt consumes its query and recorded wall time.

All five learned policies tie calibrated latency at the primary endpoint; this comparison shows no learned selection win.

| Policy | Mean best speedup | Verified-reference hits / 5 | Mean candidate seconds |
| --- | --- | --- | --- |
| Frequency | 1.000000000 | 5 | 144.442 |
| Merit | 1.000000000 | 5 | 144.442 |
| Calibrated latency | 1.000000000 | 5 | 144.442 |
| Latency + cost heuristic | 1.000000000 | 5 | 117.591 |
| Random | 1.000000000 | 5 | 120.593 |
| Original XGBoost | 1.000000000 | 5 | 117.923 |
| Pairwise XGBoost | 1.000000000 | 5 | 144.442 |
| Normalized XGBoost | 1.000000000 | 5 | 144.442 |
| Hybrid GP: zero shot | 1.000000000 | 5 | 144.442 |
| Hybrid GP: paid adaptation | 1.000000000 | 5 | 144.442 |

## Interpretation and limits

Read the paired workload comparisons in campaign-report.json before claiming an advantage. A tie in best feasible speedup is not an ML win. Lower prediction error alone is not a selection win. These workloads become development data after this report; changes need fresh held-out workloads or inputs.

The fixed historical training corpus has 18 candidate labels and 793.926327 candidate wall-seconds. Baseline/setup work, calibration, failed qualification attempts, static diagnostics and inference are separate reported scopes. This is not a complete lifetime project-cost total. Never add native command durations to overlapping evaluation wall durations. Individual candidate benefits do not establish a combined instruction set.

The LLM selection agent, additional independent inputs, calibrated uncertainty and jointly evaluated instruction sets remain missing.

Reproduce: `python scripts/report_budget_campaign.py`. Replay authenticates all raw measurements, refits frozen predictions exactly and starts zero native hardware jobs.
