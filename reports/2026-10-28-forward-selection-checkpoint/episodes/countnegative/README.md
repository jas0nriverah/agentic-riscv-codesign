# Agent decision explanation audit

Paid probes: **1/3**, unused budget: **2**. Logged model decisions: **3**; API-provider telemetry: **0**.

This report validates existing board/rationale evidence. It adds no controller intervention and infers no hidden reasoning. Public advice below precedes its probe; the feasibility observation appears afterward.

## Probe 1: `sub(0,sltu(0,add(in0,in1)))`

Recorded model note (unverified):

> Measure the utility recommendation, also pairwise rank 1 and highest merit: projected saving 7 cycles versus 3 for the alternatives. Feasibility score 0.379 is uncalibrated; only measurement establishes correctness, area and timing.

Public advice: pairwise rank **1**, utility rank **1**, utility-score ratio **1.0**. Followed pairwise/utility advice: **True / True**. Uncalibrated feasibility score **0.378775**; analytic cycle reduction **0.056103%**.

Observed host result: **verified_feasible_improvement**. Charged measurement seconds: **33.06758116700803**.

Pre-measurement context SHA256: `d79d8086bbbb134212a8840d68d2a56dc537d432040a701190344896431d9b8d`. Model decision call: `2`.

## Interpretation and reproduction

- Logged reasons are unverified model/policy notes; no hidden chain of thought is inferred.
- Scores and ensemble spread are uncalibrated advice, not feasibility labels.
- Historical v1 boards did not log utility recommendations; missing advice remains unavailable rather than retroactively inferred.
- Observed outcomes are checked only against this episode’s paid ledger projection; full native replay is separate.
- One episode cannot establish that explanation or reviewer support improves decision quality.

```sh
.venv/bin/python scripts/audit_agent_episode_decisions.py --results results/2026-10-28-countnegative-v2-selection-r1 --output reports/2026-10-28-forward-selection-checkpoint/episodes/countnegative
```

Machine-readable advice, heuristic ties, hashes and measured feasibility: [decision-audit.json](decision-audit.json).
