# Fixed AST-path feasibility challenger

Retrospective consumed-data development only; no independent confirmation or model promotion.

One fixed addition preserves the current numeric features, cap-conditioned 20-member XGBoost bootstrap recipe and seed 0. It adds a predetermined **7 AST paths × 24 operators = 168 binary columns**: root, left/right children and four grandchild positions. Leaf values are not added. No hyperparameters or decision thresholds are tuned.

All fourteen folds hold out the entire workload and remove every target operation-tree family, including families of failed target attempts. The four historical failures consume selection budgets and recorded time, but never receive numeric feasibility labels. Candidate rows and repeated contexts do not increase the number of independent workloads.

## Out-of-fold hardware-feasibility scores

| Model | Pooled Brier ↓ | Log loss ↓ | ROC AUC ↑ | Average precision ↑ |
|---|---:|---:|---:|---:|
| existing_feasibility_xgb | 0.242794 | 0.682318 | 0.633387 | 0.652362 |
| ast_path_feasibility_xgb | 0.220784 | 0.636279 | 0.709957 | 0.704982 |

Scores remain uncalibrated. Brier/log loss are proper-score diagnostics; AUC/AP are null in single-class workload folds. Pooled metrics are candidate-weighted and secondary to workload-level selection outcomes.

## Matched selection outcomes

Each policy orders the same context pool using public features and frozen OOF predictions before outcome prefixes are scored. Model order is `feasibility score × nonnegative analytic fractional cycle savings`, with the existing latency/ID tie breaks. Budgets are 1–3 attempted evaluations per context. The table averages contexts within workload before averaging workloads; oracle regret uses twelve complete groups.

| Policy | Budget | Verified cycle reduction | Oracle regret | Replayed query time (s) |
|---|---:|---:|---:|---:|
| existing_feasibility_xgb | 1 | 1.4309% | 0.7292% | 55.15 |
| existing_feasibility_xgb | 2 | 1.5976% | 0.5347% | 111.75 |
| existing_feasibility_xgb | 3 | 1.6037% | 0.5275% | 167.51 |
| ast_path_feasibility_xgb | 1 | 1.1521% | 1.0544% | 55.48 |
| ast_path_feasibility_xgb | 2 | 1.4314% | 0.7286% | 111.30 |
| ast_path_feasibility_xgb | 3 | 1.8605% | 0.2279% | 167.39 |
| merit | 1 | 1.0859% | 1.1317% | 55.67 |
| merit | 2 | 1.6570% | 0.4654% | 114.24 |
| merit | 3 | 2.0435% | 0.0145% | 169.76 |
| calibrated_latency | 1 | 1.0859% | 1.1317% | 55.67 |
| calibrated_latency | 2 | 1.4314% | 0.7286% | 111.90 |
| calibrated_latency | 3 | 2.0435% | 0.0145% | 167.15 |
| frequency | 1 | 1.2490% | 0.9414% | 55.56 |
| frequency | 2 | 1.4422% | 0.7160% | 112.06 |
| frequency | 3 | 1.6323% | 0.4942% | 167.28 |

These times sum archived candidate evaluation costs along counterfactual orders. No hardware evaluation or past time saving occurs in this replay. UD and G.723 have censored full-pool oracles; their regret remains null.

## Challenger versus existing feasibility model

Positive regret difference favors the AST-path challenger. Intervals resample the twelve complete workload groups; they describe consumed development data and do not establish confirmatory significance.

| Budget | Mean regret advantage (percentage points) | 95% workload interval | Wins / ties / losses |
|---|---:|---:|---:|
| 1 | -0.3252 | [-0.9775, +0.0019] | 1 / 10 / 1 |
| 2 | -0.1939 | [-0.5816, +0.0000] | 0 / 11 / 1 |
| 3 | +0.2996 | [+0.0000, +0.8260] | 2 / 10 / 0 |

## Fitting cost and decision

Fit and prediction times are measured separately for each fold/model in `costs.json`; they are not added to archived hardware timers.

- existing_feasibility_xgb: 1.3077 s fitting; 0.0316 s prediction across fourteen folds.
- ast_path_feasibility_xgb: 1.6482 s fitting; 0.0444 s prediction across fourteen folds.

**No model is promoted.** This single fixed feature test is retrospective consumed-data development. The frozen production model and all target protocols remain unchanged. Tiny-regex outcomes are not read. Inspect per-workload selection/regret and negative results before considering an independently frozen prospective challenger.

The current 12-MHz floor does not create difficult timing-boundary examples; this is primarily an area-feasibility study. Operator paths represent syntax and do not encode complete integrated hardware sharing or placement/routing behavior. No selection or calibration generality is inferred from improving a pooled metric.

```sh
../work/audit-venv/bin/python scripts/evaluate_ast_path_feasibility.py run
../work/audit-venv/bin/python scripts/evaluate_ast_path_feasibility.py verify --root reports/2026-10-28-ast-path-feasibility-r1
```

The verifier authenticates the historical corpus and frozen protocol/predictions/costs, then reproduces `report.json` and this README byte-for-byte. It performs no refit; recorded host timers remain intact. A fresh `run` refits the fixed recipes, produces fresh timers and requires a new output directory.
