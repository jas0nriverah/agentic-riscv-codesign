# Agent decision explanation audit

Paid probes: **3/3**, unused budget: **0**. Logged model decisions: **6**; API-provider telemetry: **0**.

This report validates existing board/rationale evidence. It adds no controller intervention and infers no hidden reasoning. Public advice below precedes its probe; the feasibility observation appears afterward.

## Probe 1: `add(in0,slli(in1,2))`

Recorded model note (unverified):

> Top pairwise XGBoost rank and factorized score, with the largest public analytic cycle reduction (~4.54%). Feasibility remains uncertain and uncalibrated, so spend one of three measurements.

Public advice: pairwise rank **1**, utility rank **not logged**, utility-score ratio **not logged**. Followed pairwise/utility advice: **True / not logged**. Uncalibrated feasibility score **0.496489**; analytic cycle reduction **4.543907%**.

Observed host result: **area_infeasible**. Charged measurement seconds: **41.057731541004614**.

Pre-measurement context SHA256: `3889a1bee95fb826f21f8820d0f2e2611e3b3a9d26eefb65e3a7b9cd1bb2a33c`. Model decision call: `2`.

## Probe 2: `add(slli(in0,3),in0)`

Recorded model note (unverified):

> The first high-speed candidate exceeded the area cap. Among unmeasured candidates, this remains the next-highest factorized utility and pairwise rank; its feasibility score is uncalibrated, so another paid result tests whether the smaller predicted gain fits area.

Public advice: pairwise rank **2**, utility rank **not logged**, utility-score ratio **not logged**. Followed pairwise/utility advice: **True / not logged**. Uncalibrated feasibility score **0.496489**; analytic cycle reduction **2.079445%**.

Observed host result: **area_infeasible**. Charged measurement seconds: **36.0205463339953**.

Pre-measurement context SHA256: `602a134878a8459baafe9f559e7b5afbe84cc0092967a40a7c3970b49a99b71a`. Model decision call: `4`.

## Probe 3: `sub(slli(in0,3),in0)`

Recorded model note (unverified):

> Both highest-speed candidates exceeded the 64-LUT4 cap. This remaining candidate ties for the highest uncalibrated feasibility score (~0.529) and has the largest analytic gain in that tier; use the final measurement to test feasible benefit.

Public advice: pairwise rank **11**, utility rank **not logged**, utility-score ratio **not logged**. Followed pairwise/utility advice: **False / not logged**. Uncalibrated feasibility score **0.528771**; analytic cycle reduction **0.179141%**.

Observed host result: **area_infeasible**. Charged measurement seconds: **43.44496279199666**.

Pre-measurement context SHA256: `da750fe760d4b7b302aa40a74caca4dfd05960d29b7a2fe6bbb29d3ce4fef119`. Model decision call: `5`.

## Interpretation and reproduction

- Logged reasons are unverified model/policy notes; no hidden chain of thought is inferred.
- Scores and ensemble spread are uncalibrated advice, not feasibility labels.
- Historical v1 boards did not log utility recommendations; missing advice remains unavailable rather than retroactively inferred.
- Observed outcomes are checked only against this episode’s paid ledger projection; full native replay is separate.
- One episode cannot establish that explanation or reviewer support improves decision quality.

```sh
.venv/bin/python scripts/audit_agent_episode_decisions.py --results results/2026-10-28-pulpino-sudoku-selection-r4 --output reports/2026-10-28-sudoku-decision-audit-r1
```

Machine-readable advice, heuristic ties, hashes and measured feasibility: [decision-audit.json](decision-audit.json).
