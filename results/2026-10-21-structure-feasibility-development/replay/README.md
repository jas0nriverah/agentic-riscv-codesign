# Fixed descriptor development ablation

Consumed development data; no native jobs. Existing GP predictions reproduce archived bytes exactly.

| Target | Variant/policy | +64 speedup at budgets 1 / 2 / 3 | Target seconds at budgets 1 / 2 / 3 |
|---|---|---|---|
| edn | existing/hybrid_gp_zero_shot | 1.000432304 / 1.000432304 / 1.000432304 | 139.583 / 275.323 / 405.370 |
| edn | existing/hybrid_gp_adapt | 1.000432304 / 1.000432304 / 1.000432304 | 139.583 / 275.323 / 405.370 |
| edn | existing/calibrated_latency | 1.000432304 / 1.000432304 / 1.000432304 | 139.583 / 275.323 / 405.370 |
| edn | existing/latency_cost_heuristic | 1.000356624 / 1.000356624 / 1.000356624 | 135.741 / 265.788 / 389.671 |
| edn | augmented/hybrid_gp_zero_shot | 1.000432304 / 1.000432304 / 1.000432304 | 139.583 / 275.323 / 405.370 |
| edn | augmented/hybrid_gp_adapt | 1.000432304 / 1.000432304 / 1.000432304 | 139.583 / 275.323 / 405.370 |
| ud | existing/hybrid_gp_zero_shot | 1.000000000 / 1.000000000 / 1.000000000 | 48.403 / 95.989 / 144.442 |
| ud | existing/hybrid_gp_adapt | 1.000000000 / 1.000000000 / 1.000000000 | 48.403 / 95.989 / 144.442 |
| ud | existing/calibrated_latency | 1.000000000 / 1.000000000 / 1.000000000 | 48.403 / 95.989 / 144.442 |
| ud | existing/latency_cost_heuristic | 1.000000000 / 1.000000000 / 1.000000000 | 48.403 / 95.707 / 103.434 |
| ud | augmented/hybrid_gp_zero_shot | 1.000000000 / 1.000000000 / 1.000000000 | 48.403 / 95.989 / 144.442 |
| ud | augmented/hybrid_gp_adapt | 1.000000000 / 1.000000000 / 1.000000000 | 48.403 / 95.989 / 144.442 |
| sha256 | existing/hybrid_gp_zero_shot | 1.000000000 / 1.000000000 / 1.021384665 | 67.047 / 133.081 / 200.552 |
| sha256 | existing/hybrid_gp_adapt | 1.000000000 / 1.021384665 / 1.021384665 | 67.047 / 134.518 / 200.552 |
| sha256 | existing/calibrated_latency | 1.000000000 / 1.000000000 / 1.021384665 | 67.047 / 133.081 / 200.552 |
| sha256 | existing/latency_cost_heuristic | 1.021384665 / 1.021384665 / 1.021384665 | 67.471 / 134.480 / 205.215 |
| sha256 | augmented/hybrid_gp_zero_shot | 1.000000000 / 1.000000000 / 1.021384665 | 67.047 / 133.081 / 200.552 |
| sha256 | augmented/hybrid_gp_adapt | 1.000000000 / 1.000000000 / 1.021384665 | 67.047 / 133.081 / 200.552 |

Full caps, seeds, attempt identities, predictions and paid update events are retained in report.json. Heuristic wins and negative outcomes are retained.

These are exact historical cohorts, not new six-fold cross-validation. EDN/UD use 15 fitting rows, SHA256 21; workload/family exclusions remain unchanged. Historical/setup costs are in protocol.json. UD includes an infrastructure-censored attempt, never assigned hardware infeasibility.
