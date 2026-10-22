# TACLeBench bitcount: fixed fourteen-policy selection

One untouched source, twelve automatically lowered formulas, RV32I with 8 KiB RAM and a common 12 MHz target. Five seeds are dependent repetitions; the twelve candidates share one workload and are not twelve independent source tests. The independent test unit is one source. Native simulated processor results and integrated synthesis/routing cover the recorded input and verifier.

Baseline: 51,689 cycles, 1653 LUT4, 655 flip-flops, 295 carry cells, 20 BRAM blocks; minimum routed Fmax 68.493148804 MHz.

## All twelve native candidate outcomes

| Candidate / formula | Baseline cycles | Optimized cycles | Speedup | LUT4 / added | FF / carry / BRAM | Minimum MHz | Check status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| candidate_00 / add(in0,andi(in1,15)) | 51689 | 51239 | 1.008782373 | 1718 / 65 | 712 / 328 / 20 | 61.823806763 | Verified for recorded input; verified; device=True; timing=True |
| candidate_03 / add(and(srli(in0,1),in1),and(in0,in1)) | 51689 | 51569 | 1.002326979 | 1789 / 136 | 712 / 328 / 20 | 64.787818909 | Verified for recorded input; verified; device=True; timing=True |
| candidate_08 / add(in0,andi(srli(in1,16),15)) | 51689 | 51579 | 1.002132651 | 1726 / 73 | 712 / 328 / 20 | 70.911926270 | Verified for recorded input; verified; device=True; timing=True |
| candidate_11 / add(in0,andi(srli(in1,24),15)) | 51689 | 51559 | 1.002521383 | 1726 / 73 | 712 / 328 / 20 | 68.203521729 | Verified for recorded input; verified; device=True; timing=True |
| candidate_14 / add(in0,srli(in1,24)) | 51689 | 51509 | 1.003494535 | 1730 / 77 | 712 / 328 / 20 | 74.732833862 | Verified for recorded input; verified; device=True; timing=True |
| candidate_18 / addi(lui(126976),797) | 51689 | 51641 | 1.000929494 | 1679 / 26 | 680 / 297 / 20 | 68.719078064 | Verified for recorded input; verified; device=True; timing=True |
| candidate_22 / addi(lui(252645376),-241) | 51689 | 51659 | 1.000580731 | 1677 / 24 | 680 / 297 / 20 | 67.096076965 | Verified for recorded input; verified; device=True; timing=True |
| candidate_25 / and(srli(in0,2),in1) | 51689 | 51639 | 1.000968260 | 1725 / 72 | 710 / 297 / 20 | 64.905563354 | Verified for recorded input; verified; device=True; timing=True |
| candidate_28 / andi(srli(in0,12),15) | 51689 | 51629 | 1.001162138 | 1692 / 39 | 684 / 297 / 20 | 66.045837402 | Verified for recorded input; verified; device=True; timing=True |
| candidate_31 / andi(srli(in0,24),15) | 51689 | 51599 | 1.001744220 | 1692 / 39 | 684 / 297 / 20 | 67.782821655 | Verified for recorded input; verified; device=True; timing=True |
| candidate_35 / add(slli(in0,2),in1) | 51689 | 51649 | 1.000774458 | 1723 / 70 | 712 / 326 / 20 | 68.856300354 | Verified for recorded input; verified; device=True; timing=True |
| candidate_39 / sltu(0,addi(in0,-1095)) | 51689 | 51686 | 1.000058043 | 1712 / 59 | 681 / 358 / 20 | 69.348129272 | Verified for recorded input; verified; device=True; timing=True |

Resources cover the integrated processor/PCPI/RAM. All three routing seeds are retained in candidates.csv. Blank or unknown failure values remain unverified; infrastructure failures carry no negative performance or correctness label.

## Primary +64 LUT4 comparison at every charged budget

| Policy | Queries | Mean cycle cut (%) | Mean cycle-cut regret (%) | Verified reference hits /5 | Mean paid ledger s | Mean outer-operation s |
| --- | --- | --- | --- | --- | --- | --- |
| frequency | 1 | 0.000000000 | 0.174118284 | 0 | 63.047095041 | 68.014036875 |
| frequency | 2 | 0.000000000 | 0.174118284 | 0 | 118.025473082 | 129.366157917 |
| frequency | 3 | 0.092863085 | 0.081255199 | 0 | 174.617268457 | 193.910522459 |
| merit | 1 | 0.000000000 | 0.174118284 | 0 | 63.047095041 | 68.014036875 |
| merit | 2 | 0.000000000 | 0.174118284 | 0 | 154.337680916 | 165.059360208 |
| merit | 3 | 0.000000000 | 0.174118284 | 0 | 225.688212508 | 243.655089233 |
| calibrated_latency | 1 | 0.000000000 | 0.174118284 | 0 | 63.047095041 | 68.014036875 |
| calibrated_latency | 2 | 0.000000000 | 0.174118284 | 0 | 118.025473082 | 129.366157917 |
| calibrated_latency | 3 | 0.000000000 | 0.174118284 | 0 | 189.515684416 | 206.594582292 |
| latency_cost_heuristic | 1 | 0.000000000 | 0.174118284 | 0 | 63.047095041 | 68.014036875 |
| latency_cost_heuristic | 2 | 0.000000000 | 0.174118284 | 0 | 118.025473082 | 129.366157917 |
| latency_cost_heuristic | 3 | 0.174118284 | 0.000000000 | 5 | 202.809167332 | 220.411829084 |
| random | 1 | 0.035984445 | 0.138133839 | 1 | 93.798510725 | 100.981520192 |
| random | 2 | 0.071968891 | 0.102149393 | 2 | 195.220832292 | 210.493654750 |
| random | 3 | 0.094023874 | 0.080094411 | 2 | 260.541491533 | 283.485742517 |
| raw_regression | 1 | 0.000000000 | 0.174118284 | 0 | 63.047095041 | 68.014036875 |
| raw_regression | 2 | 0.000000000 | 0.174118284 | 0 | 154.337680916 | 165.059360208 |
| raw_regression | 3 | 0.000000000 | 0.174118284 | 0 | 209.316058957 | 226.411481250 |
| ranking | 1 | 0.000000000 | 0.174118284 | 0 | 63.047095041 | 68.014036875 |
| ranking | 2 | 0.037145234 | 0.136973050 | 0 | 140.458164716 | 152.058976692 |
| ranking | 3 | 0.055717851 | 0.118400433 | 0 | 207.247669658 | 225.846611092 |
| normalized_xgb | 1 | 0.000000000 | 0.174118284 | 0 | 63.047095041 | 68.014036875 |
| normalized_xgb | 2 | 0.000000000 | 0.174118284 | 0 | 118.025473082 | 129.366157917 |
| normalized_xgb | 3 | 0.000000000 | 0.174118284 | 0 | 199.017177691 | 216.792624534 |
| hybrid_gp_zero_shot | 1 | 0.000000000 | 0.174118284 | 0 | 63.047095041 | 68.014036875 |
| hybrid_gp_zero_shot | 2 | 0.000000000 | 0.174118284 | 0 | 118.025473082 | 129.366157917 |
| hybrid_gp_zero_shot | 3 | 0.000000000 | 0.174118284 | 0 | 189.515684416 | 206.594582292 |
| hybrid_gp_adapt | 1 | 0.000000000 | 0.174118284 | 0 | 63.047095041 | 68.014036875 |
| hybrid_gp_adapt | 2 | 0.000000000 | 0.174118284 | 0 | 118.025473082 | 129.366157917 |
| hybrid_gp_adapt | 3 | 0.000000000 | 0.174118284 | 0 | 189.515684416 | 206.594582292 |
| feasible_benefit_xgb | 1 | 0.000000000 | 0.174118284 | 0 | 63.047095041 | 68.014036875 |
| feasible_benefit_xgb | 2 | 0.000000000 | 0.174118284 | 0 | 118.025473082 | 129.366157917 |
| feasible_benefit_xgb | 3 | 0.000000000 | 0.174118284 | 0 | 189.515684416 | 206.594582292 |
| factorized_feasibility_xgb | 1 | 0.000000000 | 0.174118284 | 0 | 63.047095041 | 68.014036875 |
| factorized_feasibility_xgb | 2 | 0.000000000 | 0.174118284 | 0 | 118.025473082 | 129.366157917 |
| factorized_feasibility_xgb | 3 | 0.000000000 | 0.174118284 | 0 | 189.515684416 | 206.594582292 |
| hybrid_gp_adapt_count | 1 | 0.000000000 | 0.174118284 | 0 | 63.047095041 | 68.014036875 |
| hybrid_gp_adapt_count | 2 | 0.000000000 | 0.174118284 | 0 | 118.025473082 | 129.366157917 |
| hybrid_gp_adapt_count | 3 | 0.000000000 | 0.174118284 | 0 | 189.515684416 | 206.594582292 |
| hybrid_gp_adapt_count_semantic | 1 | 0.000000000 | 0.174118284 | 0 | 63.047095041 | 68.014036875 |
| hybrid_gp_adapt_count_semantic | 2 | 0.000000000 | 0.174118284 | 0 | 118.025473082 | 129.366157917 |
| hybrid_gp_adapt_count_semantic | 3 | 0.000000000 | 0.174118284 | 0 | 189.515684416 | 206.594582292 |

The primary endpoint is budget three at +64 LUT4. All fourteen policies, caps32/64/128 and budgets1/2/3 are retained in endpoints.csv. Cycle cut is 1−1/speedup before seed averaging. Baseline retention is not an improved-design discovery. Censored references give only lower bounds on regret to the unresolved complete-pool optimum. Combined reporting counts classified noncensored recorded correctness/memory failures as known invalid; only censored failures are unknown. This diagnostic qualification changes no policy acquisition, prediction or choice; the raw legacy twelve-policy reports remain preserved.

## Measurement accounting and limitations

Current pool: 12 charged native attempts, 12 verified labels, 0 failed/interrupted rows; 921.081197541 recorded ledger seconds (complete: True). Baseline ledger: 28.101970541 s; native commands: 235 / 860.892177654 s.

Shared history: 87 verified labels and 3 failures, 90 attempts / 5098.832466042 recorded seconds, charged once. Baseline/setup, qualification, fitting and host-dependent inference are separate scopes in costs.json. Ledger, outer-operation, subprocess and native-command scopes overlap and must not be added. Other-policy paid-duration sums are replay accounting, not measured live-search lifetimes.

The actual live trace is retained in live.json; policy replay does not create extra native measurements. Fixed three-query runs spend every attempt even after reaching a reference. No automatic stopping, source generalization, statistical significance, model superiority, calibrated uncertainty, uninterrupted wall-time savings, joint-set behavior or LLM advantage is established by this single fresh source. After collection these labels are consumed development data. This presenter performs zero model fits, predictions and native jobs.
