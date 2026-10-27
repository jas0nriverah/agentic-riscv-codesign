# Feasibility-model family screen (retrospective)

Consumed-data development only; no independent confirmation.

| Policy | Budget | Mean verified cycle reduction | Mean regret on complete pools | Complete pools | Mean charged evaluation seconds |
|---|---:|---:|---:|---:|---:|
| frequency | 1 | 1.2490% | 0.9414% | 12/14 | 55.56 |
| frequency | 2 | 1.4422% | 0.7160% | 12/14 | 112.06 |
| frequency | 3 | 1.6323% | 0.4942% | 12/14 | 167.28 |
| merit | 1 | 1.0859% | 1.1317% | 12/14 | 55.67 |
| merit | 2 | 1.6570% | 0.4654% | 12/14 | 114.24 |
| merit | 3 | 2.0435% | 0.0145% | 12/14 | 169.76 |
| calibrated_latency | 1 | 1.0859% | 1.1317% | 12/14 | 55.67 |
| calibrated_latency | 2 | 1.4314% | 0.7286% | 12/14 | 111.90 |
| calibrated_latency | 3 | 2.0435% | 0.0145% | 12/14 | 167.15 |
| latency_cost_heuristic | 1 | 0.6025% | 1.6957% | 12/14 | 55.42 |
| latency_cost_heuristic | 2 | 1.5702% | 0.5667% | 12/14 | 110.31 |
| latency_cost_heuristic | 3 | 1.7399% | 0.3686% | 12/14 | 166.67 |
| random | 1 | 0.3978% | 1.5961% | 12/14 | 55.14 |
| random | 2 | 0.6981% | 1.2494% | 12/14 | 109.95 |
| random | 3 | 1.1420% | 0.7998% | 12/14 | 162.52 |
| xgb_speedup_regression | 1 | 1.0834% | 1.1346% | 12/14 | 55.77 |
| xgb_speedup_regression | 2 | 1.6546% | 0.4682% | 12/14 | 114.61 |
| xgb_speedup_regression | 3 | 2.0231% | 0.0383% | 12/14 | 168.26 |
| xgb_pairwise_ranker | 1 | 1.3345% | 0.8417% | 12/14 | 56.29 |
| xgb_pairwise_ranker | 2 | 1.6800% | 0.4385% | 12/14 | 115.69 |
| xgb_pairwise_ranker | 3 | 1.9957% | 0.0702% | 12/14 | 171.46 |
| factorized_feasibility_xgb | 1 | 1.4309% | 0.7292% | 12/14 | 55.15 |
| factorized_feasibility_xgb | 2 | 1.5976% | 0.5347% | 12/14 | 111.75 |
| factorized_feasibility_xgb | 3 | 1.6037% | 0.5275% | 12/14 | 167.51 |
| xgb_feasibility_64 | 1 | 0.8060% | 1.4582% | 12/14 | 55.45 |
| xgb_feasibility_64 | 2 | 1.4920% | 0.6579% | 12/14 | 110.87 |
| xgb_feasibility_64 | 3 | 1.8179% | 0.2777% | 12/14 | 166.96 |
| group_bootstrap_xgb_feasibility_64 | 1 | 1.1516% | 1.0551% | 12/14 | 55.20 |
| group_bootstrap_xgb_feasibility_64 | 2 | 1.4314% | 0.7286% | 12/14 | 111.00 |
| group_bootstrap_xgb_feasibility_64 | 3 | 1.8179% | 0.2777% | 12/14 | 166.48 |
| logistic_feasibility_64 | 1 | 1.4309% | 0.7292% | 12/14 | 54.85 |
| logistic_feasibility_64 | 2 | 1.4821% | 0.6695% | 12/14 | 111.27 |
| logistic_feasibility_64 | 3 | 1.6544% | 0.4684% | 12/14 | 167.89 |
| random_forest_feasibility_64 | 1 | 0.8060% | 1.4582% | 12/14 | 55.45 |
| random_forest_feasibility_64 | 2 | 1.2778% | 0.9077% | 12/14 | 111.24 |
| random_forest_feasibility_64 | 3 | 1.8179% | 0.2777% | 12/14 | 166.44 |
| extra_trees_feasibility_64 | 1 | 0.6628% | 1.6252% | 12/14 | 54.94 |
| extra_trees_feasibility_64 | 2 | 1.0492% | 1.1745% | 12/14 | 110.89 |
| extra_trees_feasibility_64 | 3 | 1.8179% | 0.2777% | 12/14 | 168.50 |

Failed attempts remain in the target query pools and consume budget and measured time. They are never assigned fabricated feasibility labels. UD and G.723 are excluded from oracle regret because an infrastructure-censored candidate leaves the full pool unresolved.
