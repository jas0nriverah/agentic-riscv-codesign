# Agent decision explanation audit

Paid probes: **2/2**, unused budget: **0**. Logged model decisions: **4**; API-provider telemetry: **0**.

This report validates existing board/rationale evidence. It adds no controller intervention and infers no hidden reasoning. Public advice below precedes its probe; the feasibility observation appears afterward.

## Probe 1: `add(in0,slli(in1,2))`

Recorded model note (unverified):

> Measure the utility recommendation: rank 1 in pairwise, merit and frequency, projected cycle reduction 0.739%, versus 0.0435% for the other candidate. Its feasibility score 0.498 is uncalibrated; verify actual area, timing and correctness.

Public advice: pairwise rank **1**, utility rank **1**, utility-score ratio **1.0**. Followed pairwise/utility advice: **True / True**. Uncalibrated feasibility score **0.498327**; analytic cycle reduction **0.738827%**.

Observed host result: **area_infeasible**. Charged measurement seconds: **39.95467845899111**.

Pre-measurement context SHA256: `e5cedc949017d13ada568dc7b661cb3c153409d447e49534dd5c7205a0321f67`. Model decision call: `2`.

## Probe 2: `sub(addi(0,1),in0)`

Recorded model note (unverified):

> The first probe is +70 LUT4 and exceeds the +64 cap. Measure the sole remaining candidate, now the utility recommendation, with projected 0.0435% cycle reduction. Its 0.670 feasibility score is advisory; establish a feasible improvement or retain baseline.

Public advice: pairwise rank **2**, utility rank **1**, utility-score ratio **1.0**. Followed pairwise/utility advice: **True / True**. Uncalibrated feasibility score **0.670471**; analytic cycle reduction **0.043490%**.

Observed host result: **area_infeasible**. Charged measurement seconds: **32.89376258398988**.

Pre-measurement context SHA256: `6cc7ef275c8d3fd757b47de9b5683acf4e3deed0beec3c1a87331c7207e15fd5`. Model decision call: `3`.

## Interpretation and reproduction

- Logged reasons are unverified model/policy notes; no hidden chain of thought is inferred.
- Scores and ensemble spread are uncalibrated advice, not feasibility labels.
- Historical v1 boards did not log utility recommendations; missing advice remains unavailable rather than retroactively inferred.
- Observed outcomes are checked only against this episode’s paid ledger projection; full native replay is separate.
- One episode cannot establish that explanation or reviewer support improves decision quality.

```sh
.venv/bin/python scripts/audit_agent_episode_decisions.py --results results/2026-10-28-mibench-stringsearch-v2-selection-r1 --output reports/2026-10-28-forward-selection-checkpoint/episodes/stringsearch
```

Machine-readable advice, heuristic ties, hashes and measured feasibility: [decision-audit.json](decision-audit.json).
