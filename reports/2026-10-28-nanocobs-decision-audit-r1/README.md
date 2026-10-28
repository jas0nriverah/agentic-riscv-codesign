# Agent decision explanation audit

Paid probes: **1/3**, unused budget: **2**. Logged model decisions: **3**; API-provider telemetry: **0**.

This report validates existing board/rationale evidence. It adds no controller intervention and infers no hidden reasoning. Public advice below precedes its probe; the feasibility observation appears afterward.

## Probe 1: `addi(lui(16842752),257)`

Recorded model note (unverified):

> Measure the utility recommendation: highest pairwise rank, factorized score 0.0017768 and analytic cycle reduction 0.2517%. Its feasibility score is uncalibrated; actual correctness, area and timing must be measured.

Public advice: pairwise rank **1**, utility rank **1**, utility-score ratio **1.0**. Followed pairwise/utility advice: **True / True**. Uncalibrated feasibility score **0.705880**; analytic cycle reduction **0.251717%**.

Observed host result: **verified_feasible_improvement**. Charged measurement seconds: **46.234854082998936**.

Pre-measurement context SHA256: `1963f19ba485252ae05f475e0ebb7099371450375fa09f8738088de770535d3d`. Model decision call: `2`.

## Interpretation and reproduction

- Logged reasons are unverified model/policy notes; no hidden chain of thought is inferred.
- Scores and ensemble spread are uncalibrated advice, not feasibility labels.
- Historical v1 boards did not log utility recommendations; missing advice remains unavailable rather than retroactively inferred.
- Observed outcomes are checked only against this episode’s paid ledger projection; full native replay is separate.
- One episode cannot establish that explanation or reviewer support improves decision quality.

```sh
.venv/bin/python scripts/audit_agent_episode_decisions.py --results results/2026-10-28-nanocobs-v2-selection-r1 --output reports/2026-10-28-nanocobs-decision-audit-r1
```

Machine-readable advice, heuristic ties, hashes and measured feasibility: [decision-audit.json](decision-audit.json).
