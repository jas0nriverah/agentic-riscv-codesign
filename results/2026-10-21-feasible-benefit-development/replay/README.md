# Feasible-benefit XGBoost development experiment

One fixed model; consumed data; no native measurements. All frozen comparators reproduce their archived curves exactly.

| Target | Policy | +64 mean speedup at budgets 1 / 2 / 3 | Mean target seconds at budgets 1 / 2 / 3 |
|---|---|---|---|
| edn | frequency | 1.000356624 / 1.000432304 / 1.000432304 | 135.741 / 275.323 / 405.370 |
| edn | merit | 1.000432304 / 1.000432304 / 1.000432304 | 139.583 / 275.323 / 405.370 |
| edn | calibrated_latency | 1.000432304 / 1.000432304 / 1.000432304 | 139.583 / 275.323 / 405.370 |
| edn | latency_cost_heuristic | 1.000356624 / 1.000356624 / 1.000356624 | 135.741 / 265.788 / 389.671 |
| edn | random | 1.000086731 / 1.000087271 / 1.000229650 | 131.318 / 235.120 / 343.028 |
| edn | raw_regression | 1.000432304 / 1.000432304 / 1.000432304 | 139.583 / 275.323 / 309.017 |
| edn | ranking | 1.000432304 / 1.000432304 / 1.000432304 | 139.583 / 267.164 / 393.513 |
| edn | normalized_xgb | 1.000432304 / 1.000432304 / 1.000432304 | 139.583 / 275.323 / 405.370 |
| edn | hybrid_gp_zero_shot | 1.000432304 / 1.000432304 / 1.000432304 | 139.583 / 275.323 / 405.370 |
| edn | hybrid_gp_adapt | 1.000432304 / 1.000432304 / 1.000432304 | 139.583 / 275.323 / 405.370 |
| edn | feasible_benefit_xgb | 1.000432304 / 1.000432304 / 1.000432304 | 139.583 / 275.323 / 405.370 |
| ud | frequency | 1.000000000 / 1.000000000 / 1.000000000 | 48.403 / 95.989 / 144.442 |
| ud | merit | 1.000000000 / 1.000000000 / 1.000000000 | 48.403 / 95.989 / 144.442 |
| ud | calibrated_latency | 1.000000000 / 1.000000000 / 1.000000000 | 48.403 / 95.989 / 144.442 |
| ud | latency_cost_heuristic | 1.000000000 / 1.000000000 / 1.000000000 | 48.403 / 95.707 / 117.591 |
| ud | random | 1.000000000 / 1.000000000 / 1.000000000 | 39.721 / 83.941 / 120.593 |
| ud | raw_regression | 1.000000000 / 1.000000000 / 1.000000000 | 47.586 / 96.039 / 117.923 |
| ud | ranking | 1.000000000 / 1.000000000 / 1.000000000 | 47.586 / 96.039 / 144.442 |
| ud | normalized_xgb | 1.000000000 / 1.000000000 / 1.000000000 | 48.403 / 95.989 / 144.442 |
| ud | hybrid_gp_zero_shot | 1.000000000 / 1.000000000 / 1.000000000 | 48.403 / 95.989 / 144.442 |
| ud | hybrid_gp_adapt | 1.000000000 / 1.000000000 / 1.000000000 | 48.403 / 95.989 / 144.442 |
| ud | feasible_benefit_xgb | 1.000000000 / 1.000000000 / 1.000000000 | 48.403 / 95.989 / 144.442 |
| sha256 | frequency | 1.012830799 / 1.021384665 / 1.021384665 | 67.301 / 134.518 / 201.528 |
| sha256 | merit | 1.000000000 / 1.000000000 / 1.021384665 | 67.047 / 133.081 / 200.552 |
| sha256 | calibrated_latency | 1.000000000 / 1.000000000 / 1.021384665 | 67.047 / 133.081 / 200.552 |
| sha256 | latency_cost_heuristic | 1.021384665 / 1.021384665 / 1.021384665 | 67.471 / 134.480 / 205.215 |
| sha256 | random | 1.012437329 / 1.019938840 / 1.019938840 | 67.947 / 134.572 / 201.367 |
| sha256 | raw_regression | 1.000000000 / 1.000000000 / 1.016714262 | 66.439 / 133.081 / 201.112 |
| sha256 | ranking | 1.000000000 / 1.000000000 / 1.017047190 | 66.642 / 133.081 / 200.275 |
| sha256 | normalized_xgb | 1.000000000 / 1.000000000 / 1.021384665 | 67.047 / 133.081 / 200.552 |
| sha256 | hybrid_gp_zero_shot | 1.000000000 / 1.000000000 / 1.021384665 | 67.047 / 133.081 / 200.552 |
| sha256 | hybrid_gp_adapt | 1.000000000 / 1.021384665 / 1.021384665 | 67.047 / 134.518 / 200.552 |
| sha256 | feasible_benefit_xgb | 1.000000000 / 1.021384665 / 1.021384665 | 67.047 / 134.518 / 200.552 |

Complete events, all caps/seeds, unknown and known-infeasible attempts, regret and utility diagnostics are in report.json. Historical attempt/setup/context costs are in protocol.json; fit/predict host costs are separate in fitting.json. Target times are replayed historical costs, not live wall time.
