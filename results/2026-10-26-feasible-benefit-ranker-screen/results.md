# Measured feasible-benefit ranker screen

Retrospective consumed-data development only; this is not an independent test.
The new ranker trains on measured cycle-reduction relevance only when area and timing are feasible; failures consume budget and time without labels.

| Budget | Mean cycle reduction | Mean regret | Complete oracles | Mean native evaluation seconds |
|---:|---:|---:|---:|---:|
| 1 | 1.1141% | 1.0988% | 12/14 | 56.16 |
| 2 | 1.4260% | 0.7349% | 12/14 | 112.40 |
| 3 | 1.4826% | 0.6689% | 12/14 | 169.96 |

## Paired comparison against the frozen screen

Positive regret difference means the feasible-benefit ranker has lower regret.
Intervals resample independent workload groups; policy seeds are averaged within workload and do not increase the sample size.

| Budget | Baseline | Mean regret advantage (pp) | 95% workload-bootstrap interval (pp) | Wins / ties / losses |
|---:|---|---:|---:|---:|
| 1 | merit | 0.0329 | [-1.0307, 1.2206] | 4 / 3 / 5 |
| 1 | latency_cost_heuristic | 0.5969 | [-0.4981, 1.8227] | 6 / 4 / 2 |
| 1 | xgb_pairwise_ranker | -0.2571 | [-1.3054, 0.9528] | 2 / 4 / 6 |
| 1 | factorized_feasibility_xgb | -0.3695 | [-1.1638, 0.2204] | 3 / 5 / 4 |
| 2 | merit | -0.2695 | [-0.7695, 0.1313] | 4 / 4 / 4 |
| 2 | latency_cost_heuristic | -0.1683 | [-0.6941, 0.2622] | 4 / 5 / 3 |
| 2 | xgb_pairwise_ranker | -0.2964 | [-0.7350, 0.0373] | 3 / 5 / 4 |
| 2 | factorized_feasibility_xgb | -0.2002 | [-0.7225, 0.2377] | 4 / 4 / 4 |
| 3 | merit | -0.6544 | [-1.1954, -0.1467] | 1 / 6 / 5 |
| 3 | latency_cost_heuristic | -0.3002 | [-0.7599, 0.0948] | 5 / 3 / 4 |
| 3 | xgb_pairwise_ranker | -0.5986 | [-1.1252, -0.1307] | 1 / 6 / 5 |
| 3 | factorized_feasibility_xgb | -0.1413 | [-0.6470, 0.2748] | 4 / 5 / 3 |

Model fit/inference wall time is recorded in `report.json` separately from measured hardware-evaluation time. UD and G.723 reference comparisons are omitted because an infrastructure-censored candidate leaves their full-pool oracle unknown.
