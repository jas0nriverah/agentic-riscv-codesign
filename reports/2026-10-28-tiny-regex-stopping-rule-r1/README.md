# tiny-regex-c shared-stopping development diagnostic

This is a retrospective analysis of the completed, consumed tiny-regex r2 study. It changes no policy, native result, model, or prospective claim.

The shared rule compares the paid feasible incumbent with the maximum frozen analytic saved-cycle estimate over every unattempted candidate. It cannot read an unqueried outcome. Paid benefit mismatches disable stopping. The oracle and all-pool residual audit are computed after decisions. The estimates are conditional assumptions, not proved upper bounds.

The table uses the original B3 action order, shortened only by that rule. Five non-agent seeds are dependent runs on one workload. The agent is its single actual two-measurement episode, with no inferred third action.

| Policy | Actual queries | Shared-stop queries | Queries saved | Evaluation seconds saved | New missed improvements |
| --- | ---: | ---: | ---: | ---: | ---: |
| calibrated_latency | 3.00 | 2.00 | 1.00 | 37.361846 | 0 |
| codex_chat_hybrid_agent | 2.00 | 2.00 | 0.00 | 0.000000 | 0 |
| factorized_feasibility_xgb | 3.00 | 2.00 | 1.00 | 37.361846 | 0 |
| feasible_benefit_xgb | 3.00 | 2.00 | 1.00 | 34.028782 | 0 |
| frequency | 3.00 | 3.00 | 0.00 | 0.000000 | 0 |
| hybrid_gp_adapt | 3.00 | 3.00 | 0.00 | 0.000000 | 0 |
| hybrid_gp_zero_shot | 3.00 | 3.00 | 0.00 | 0.000000 | 0 |
| latency_cost_heuristic | 3.00 | 3.00 | 0.00 | 0.000000 | 0 |
| merit | 3.00 | 2.00 | 1.00 | 37.361846 | 0 |
| normalized_xgb | 3.00 | 2.00 | 1.00 | 37.361846 | 0 |
| random | 3.00 | 3.00 | 0.00 | 0.000000 | 0 |
| ranking | 3.00 | 2.00 | 1.00 | 34.028782 | 0 |
| raw_regression | 3.00 | 2.00 | 1.00 | 37.361846 | 0 |

All-pool post-decision audit: 0 exact-benefit mismatches; 0 positive residuals among 12 candidates.

The agent and several deterministic policies reach the same oracle by B2. Any saved third evaluation is explained by the shared conditional stopping rule; this is no LLM selection or total-cost advantage. Some policies still miss the oracle within their original budget: `summary.json` separates their pre-existing regret from loss caused by stopping.

Saved evaluation durations are counterfactual sums from the archived candidates. No hardware time was actually saved by this analysis. Full-pool collection still cost twelve measurements. Evaluation and outer-operation timers overlap and are reported separately; model, relay, human and inference costs are excluded.

Reproduce into a fresh directory, or verify the committed artifact byte-for-byte:

```sh
../work/audit-venv/bin/python scripts/analyze_tiny_regex_stopping_rule.py --output generated/tiny-regex-stopping-replay
../work/audit-venv/bin/python scripts/analyze_tiny_regex_stopping_rule.py --verify reports/2026-10-28-tiny-regex-stopping-rule-r1
```

The script authenticates both complete pinned input manifests and its output manifest. No model or hardware evaluator is imported. `summary.json` retains every prefix decision, conditional remaining-benefit bound, paid mismatch, original action order, cost difference and post-decision oracle comparison. Future prospective use requires a separate source-bound release.
