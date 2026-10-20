PRELIMINARY: baseline multiplier choice pending team confirmation; numbers may change.

Committed results of the PROVISIONAL measurement engine. Every row was produced by `make hw-measure` / `make hw-sweep*` under the protocol in the root README (frozen PCF, seeds 1–10, every check passing).

| File | What it is |
|---|---|
| `sweep-top3.csv` | each program's top 3 candidates by finder `saved`, each measured alone (21 cores, 22 rows) |
| `sweep-top10-placeable.csv` | each program's top 10 candidates the rewriter can fuse, each measured alone (60 cores, 70 rows) |
| `rankcheck-top10.csv` | Spearman rank agreement between finder `saved` and measured cycles saved, per program |
| `placeability.csv` | rewriter-only pre-check of all 348 candidates: placeable sites and placeable saved vs finder saved |
| `frequency-top3.*` | the frequency-ranking baseline: request, full result, measurement rows |
| `sweep-top10-placeable.csv`, `rankcheck-top10.csv` | the top-10 placeable sweep and its rank check |
| `frequency-placeable-top3.*` | the placement-aware frequency pick (request, selection log) |
| `oracle-lut<budget>.estimates.json`, `oracle-lut<budget>-set<n>.request.json` | the oracle's estimated sets per LUT budget and the requests built |
| `experiments.csv`, `experiments.json` | the comparison of all selection experiments: per-program speedups under both rules, geomeans, LUTs, Fmax, builds needed |
| `builds/<id>.json` | the full result of every measured core, including every fused and skipped site |
