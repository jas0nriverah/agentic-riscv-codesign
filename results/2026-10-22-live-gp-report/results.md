# Fresh-source live GP campaign: beebs-expint

One source, six declared candidates, twelve unchanged policies. The predeclared hybrid_gp_adapt seed0 makes three actual native queries at +64 LUT4 and12MHz; the other three candidates are measured only after the completed live trace is sealed, for a separate pool oracle. All other policy/seed comparisons are charged cooperative replay. Five seeds are dependent repetitions, not five independent workloads.

Baseline:31,843 cycles. The public calibrated ceiling in this restricted pool is only 11 saved cycles (0.034544484% of baseline cycles). This tiny opportunity limits practical gains; it is not broadened after seeing outcomes. The original workload/input/verifier and frozen policies remain unchanged. A native simulated processor result is not a physical-board measurement.

Baseline integrated resources: 1653 LUT4, 655 flip-flops, 295 carry cells and 20 BRAM blocks. Routing seeds [1, 2, 3] achieve [77.16049194335938, 68.49314880371094, 70.3878402709961] MHz; minimum 68.493148804 MHz.

## Actual integrated processor outcomes

| Candidate | Formula | Cycles | Speedup | LUT4 / added | FF / carry / BRAM | Three route Fmax MHz | Minimum MHz | Correctness |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| candidate_00 | addi(andi(sub(0,sltiu(in0,1)),998),2) | 31832 | 1.000345564 | 1670 / 17 | 684 / 329 / 20 | 71.230148315, 67.713973999, 66.476097107 | 66.476097107 | Verified for recorded input |
| candidate_01 | addi(andi(sub(0,in0),998),2) | 31836 | 1.000219877 | 1686 / 33 | 688 / 306 / 20 | 69.079856873, 67.976341248, 69.415519714 | 67.976341248 | Verified for recorded input |
| candidate_03 | add(in0,slli(in1,3)) | 31837 | 1.000188460 | 1724 / 71 | 712 / 325 / 20 | 70.896850586, 67.358215332, 65.210304260 | 65.210304260 | Verified for recorded input |
| candidate_04 | addi(andi(in0,998),2) | 31840 | 1.000094221 | 1688 / 35 | 688 / 298 / 20 | 65.733253479, 66.458427429, 75.013122559 | 65.733253479 | Verified for recorded input |
| candidate_06 | sub(0,sltiu(in0,1)) | 31840 | 1.000094221 | 1694 / 41 | 681 / 328 / 20 | 65.112648010, 67.503715515, 64.846641541 | 64.846641541 | Verified for recorded input |
| candidate_07 | sub(addi(0,4),in0) | 31840 | 1.000094221 | 1754 / 101 | 712 / 327 / 20 | 70.896850586, 67.608680725, 73.035346985 | 67.608680725 | Verified for recorded input |

All resources cover the integrated processor/PCPI/RAM. Three route seeds and their minimum are retained; no faster-clock benefit is credited. Blank failed-attempt performance/hardware values remain unknown. Failures are charged and retain their classifications; unknown outcomes are never negative labels.

## Actual three-query live trace

| Query | Best cycles | Speedup | Cycle reduction | Regret | Oracle gain fraction | Ledger monotonic s |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 31843 | 1.000000000 | 0.000000000 | 0.000345445 | 0.000000000 | 39.913442458 |
| 2 | 31832 | 1.000345564 | 0.000345445 | -0.000000000 | 1.000000000 | 78.400947333 |
| 3 | 31832 | 1.000345564 | 0.000345445 | -0.000000000 | 1.000000000 | 118.611717416 |

The live trace is one seed of one fixed GP policy. Its actual query IDs, paired command receipts, paid-prefix partial audits and later oracle boundary are retained in the campaign. Three fixed-budget queries are still spent after an early optimum; this does not demonstrate automatic stopping. The local callback is cooperative isolation, not an OS sandbox. No LLM-agent, joint-set or broad model superiority is established.

## All twelve fixed-policy primary endpoints

| Policy | Mean cycle reduction | Mean regret | Oracle gain fraction | Improved-reference hits /5 | Mean ledger monotonic s |
| --- | --- | --- | --- | --- | --- |
| Frequency | 0.000194705 | 0.000150740 | 0.563636364 | 1 | 122.455154075 |
| Merit | 0.000345445 | 0.000000000 | 1.000000000 | 5 | 119.664034558 |
| Calibrated latency | 0.000345445 | 0.000000000 | 1.000000000 | 5 | 118.611717416 |
| Latency + cost heuristic | 0.000219829 | 0.000125616 | 0.636363636 | 0 | 121.405919716 |
| Random | 0.000194705 | 0.000150740 | 0.563636364 | 1 | 122.455154075 |
| Original XGBoost | 0.000345445 | 0.000000000 | 1.000000000 | 5 | 119.282046591 |
| Pairwise XGBoost | 0.000345445 | 0.000000000 | 1.000000000 | 5 | 118.611717416 |
| Normalized XGBoost | 0.000345445 | 0.000000000 | 1.000000000 | 5 | 118.611717416 |
| Hybrid GP: zero shot | 0.000345445 | 0.000000000 | 1.000000000 | 5 | 118.611717416 |
| Hybrid GP: paid adaptation | 0.000345445 | 0.000000000 | 1.000000000 | 5 | 118.611717416 |
| Feasible-benefit XGBoost | 0.000320322 | 0.000025123 | 0.927272727 | 4 | 119.423484225 |
| Factorized feasibility XGBoost | 0.000345445 | 0.000000000 | 1.000000000 | 5 | 118.611717416 |

All caps32/64/128 and budgets1/2/3 appear in endpoints.csv. Cycle reduction is1−1/speedup, computed before seed averaging. Regret subtracts achieved cycle reduction from the verified pool reference. Oracle fraction is undefined for baseline-only references; baseline retention never earns a90% improved-gain success. If any outcome is infrastructure-censored, reference gaps are lower bounds on regret to the unresolved optimum.

## Costs and clock qualification

Historical data:81 successful labels plus3 failures =84 unique attempts / 4853.804293 recorded seconds, charged once. New pool:6 attempts / 245.028173 ledger monotonic seconds; live prefix:118.611717s, oracle remainder:126.416456s. Historical plus new candidate attempts:90 / 5098.832466 recorded seconds. Baseline/setup, rejected qualification, fitting/inference, observer, CLI and native-command costs remain separate in costs.json. Overlapping scopes must not be added.

The previous corpus clock-accounting amendment and strict MD5 failures are preserved separately from this campaign’s paired UTC/monotonic endpoints. Both paired deltas, capture brackets and disagreement flags are retained in clock-accounting.json. No timestamp correction, uninterrupted calendar wall time or adaptive-time saving is claimed. Other policies have replayed paid-duration sums, not measured live-search runtimes.

This presenter runs zero model fits/predictions and zero native jobs. Raw provenance, live-choice recreation and exact model refits belong to live_gp_campaign replay. All new labels become consumed data after collection; no policy is promoted or retuned from these outcomes.
