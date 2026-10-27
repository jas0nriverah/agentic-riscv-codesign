# Existing feasible-benefit model: failure-aware LOCO screen

Retrospective consumed-data development only. The model was not tuned in this screen.
All failed attempts remain charged target choices with their measured duration and unknown labels.

| Budget | Mean cycle reduction | Mean regret | Complete oracles | Mean native evaluation seconds |
|---:|---:|---:|---:|---:|
| 1 | 1.4305% | 0.7296% | 12/14 | 55.55 |
| 2 | 1.5967% | 0.5358% | 12/14 | 111.68 |
| 3 | 1.7672% | 0.3369% | 12/14 | 168.15 |

## Paired comparisons

Positive advantage means the existing feasible-benefit model has lower regret.
Workload is the bootstrap unit; the five policy seeds are dependent repetitions.

| Budget | Baseline | Mean regret advantage (pp) | 95% workload interval (pp) | Wins / ties / losses |
|---:|---|---:|---:|---:|
| 1 | merit | 0.4021 | [-0.0031, 1.2094] | 1 / 10 / 1 |
| 1 | latency_cost_heuristic | 0.9660 | [-0.3497, 2.6805] | 5 / 6 / 1 |
| 1 | xgb_pairwise_ranker | 0.1120 | [-0.7605, 1.1825] | 2 / 7 / 3 |
| 1 | factorized_feasibility_xgb | -0.0004 | [-0.0031, 0.0019] | 1 / 10 / 1 |
| 2 | merit | -0.0704 | [-0.7907, 0.5805] | 1 / 9 / 2 |
| 2 | latency_cost_heuristic | 0.0309 | [-0.0209, 0.1129] | 2 / 9 / 1 |
| 2 | xgb_pairwise_ranker | -0.0972 | [-0.7907, 0.5445] | 2 / 7 / 3 |
| 2 | factorized_feasibility_xgb | -0.0010 | [-0.0031, 0.0000] | 0 / 11 / 1 |
| 3 | merit | -0.3223 | [-0.8488, 0.0000] | 0 / 10 / 2 |
| 3 | latency_cost_heuristic | 0.0318 | [-0.4619, 0.5680] | 4 / 5 / 3 |
| 3 | xgb_pairwise_ranker | -0.2666 | [-0.8488, 0.1115] | 1 / 9 / 2 |
| 3 | factorized_feasibility_xgb | 0.1907 | [0.0000, 0.5721] | 1 / 11 / 0 |
