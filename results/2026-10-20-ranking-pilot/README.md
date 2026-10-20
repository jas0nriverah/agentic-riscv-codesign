# Fixed measured-speedup ranking development pilot

Twelve automatically extracted/measured candidates, two workload groups, five fitting rows per held-out direction after related-family exclusion. Seven policies × five seeds × six budgets = **420 outcomes**, retained as 70 sequential traces. No hyperparameter tuning and no new native jobs during comparison.

Ranking does not improve verified selection over regression. Merit finds both pool optima after one query in every seed; learned policies reach both after three. The ensemble's nominal central-90% spread covers 26.67% of aha-mont64 outcomes and 83.33% of CRC32 outcomes, averaged over seeds; this is a diagnostic, not calibrated confidence.

`protocol.json` declares consumed-data status, parameters, package/source hashes, split rules, costs and limitations. `corpus.json` contains authenticated measurement rows; `public.json` contains only allowed discovery features. Ten prediction files precede policy scoring. `report.json` contains predictions used by adaptation, queried IDs, feasibility-filtered selections, speedup/regret trajectories, historical/target costs and inference times. `collection-costs.json` separately records native setup costs. Sources are snapshotted in `sources/`.

```sh
python -m isaforge.selection_pilot verify --root results/2026-10-20-ranking-pilot
```

[Results, commands and limitations](../../docs/selection-pilot-results.md) · [Method review](../../docs/selection-methods-review.md)
