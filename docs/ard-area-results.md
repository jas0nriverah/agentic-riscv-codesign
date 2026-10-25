# Historical-likelihood area model: mixed result, no promotion

The [declared procedure](ard-area-experiment.md) changes only the area-surrogate initializer, keeping the same 37 features, historical fitting cohorts, timing/duration/device models, calibrated benefit, paid conditioner and myopic acquisition. Source and contract were pushed at `c124452f`; all ten initial models were sealed and pushed at `b77ecf7b` before scoring. G.723 is excluded.

The experiment completes **450 trajectories / 900 curve points / 180 summaries**, retaining **1,800 exact summaries from all seventeen controls**. Exact hardware-free replay reproduces initial optimizer/numerical states, every acquisition proof, paid prefix, trajectory, endpoint and charged duration. Raw host timers are retained separately. These are six consumed sources in ten dependent cohort/context cases, not new measurements or independent holdouts.

At the primary +64 LUT4 / 12 MHz / three-query endpoint:

| Source unit | Original myopic cycle reduction % | New area model % | Decision |
| --- | ---: | ---: | --- |
| Old-cohort AHA/DES/MD5 mean | 1.602185159 | 1.602185159 | Tie |
| Expanded-cohort AHA/DES/MD5 mean | 1.602185159 | 0.839440974 | Regression |
| DCT, either cohort | 0.490120999 | 0.490120999 | Tie |
| Expint | 0.034544484 | 0.034544484 | Tie |
| Bitcount | 0 | 0.174118284 | Reaches the existing heuristic optimum |

Bitcount's successful choice remains the already measured 51,689→51,599 cycles / +39 LUT4 / 67.783 MHz design. This is a development replay repair, not a second fresh-source success. Expanded AHA instead spends all three queries on over-budget designs and returns baseline, losing the original 2.288232552% reduction. Historical-likelihood fitting does not guarantee better selection.

Across thirty case/cap query-three means, the new model wins once, loses once and ties twenty-eight times against original myopic. Against the retrospective strongest-seventeen-control envelope it wins zero, loses six and ties twenty-four. That envelope is a reporting reference selected after outcomes, not a deployable policy. Across ninety B3-prefix means, the original-myopic comparison is three wins, two losses and eighty-five ties; these dependent rows are not a significance test. Full [endpoints](../results/2026-10-25-ard-selection-development/endpoints.csv) and [comparisons](../results/2026-10-25-ard-selection-development/comparisons.csv) retain every cap and horizon.

All thirty optimizer starts converge, but selected fits reach 9–16 parameter bounds. Each preparation/reconstruction phase charges ten semantic fits (thirty scalar GPs, including ten unused area fits) plus thirty ARD fits: sixty scalar fit attempts per phase. Replay repeats and records both phases separately. There are zero fits inside search and zero new native measurements. The frozen 102-attempt historical ledger, reused target pools, counterfactual search charges and host computation overlap their declared scopes; none is free training or an actual calendar-time saving.

Run with Python 3.12 and `requirements-speedup.txt`, choosing a fresh output directory:

```sh
python scripts/evaluate_ard_selection.py replay \
  --root results/2026-10-25-ard-selection-development \
  --output generated/ard-selection-replay
```

[Validation receipts](../results/2026-10-25-model-validation/README.md) preserve source/model Git checkpoints and raw replay timers. No model is promoted, probabilities are not established as calibrated confidence, and field superiority remains unproved. The next engineering work is reusable legal-candidate coverage and independent measured workloads, rather than another kernel or policy sweep.
