# Expanded measured corpus — five workloads

This consumed dataset contains **27 verified automatic candidate labels across five source workloads**: six each from aha-mont64, CRC32 and SLRE; five from EDN; four from UD. Three additional EDN/UD attempts are retained separately with no fabricated speedup or hardware labels. The original CRC32 source-adapter experiment is preserved elsewhere and excluded from these counts.

- `corpus.json`: consistent structural/runtime features, measured whole-program cycles/speedup, integrated LUT4 cost, minimum routed timing, contexts, measurement costs, failed attempts and source provenance.
- `verified-labels.csv`: the same 27 successful rows; nested feature maps use JSON cells.
- `failed-attempt-interpretation.json`: distinguishes EDN's recorded memory-contract failure, UD's self-check failure, and UD's infrastructure-censored outcome. UD candidate 10 has unknown correctness, performance and feasibility.
- `source-relocation-diagnosis.json`: source-only re-extraction using the new conservative guard; no pool or outcome changes. SLRE's flagged successful candidate remains an observed success, with source risk disclosed.
- `provenance.json`: the exact raw campaign manifest, exporter/guard/report source hashes and separate candidate cost scopes.

All five workloads are now development data. Future claims require fresh workload/source-family holdouts or explicitly disclosed new-input adaptation, not random candidate splits or retuning on these outcomes. Families excluded from EDN/UD fitting remain recorded in the frozen protocols. Baseline compiler flags and stack partitions differ across contexts; this is not a uniform-context generalization benchmark.

New candidate attempts cost 904.226627 wall-seconds; previous automatic candidates cost 793.926327, totaling 1,698.152954 candidate wall-seconds. Setup, baselines, calibration, qualifications and inference are separate; overlapping command durations must not be added to these totals.

The [campaign archive](../2026-10-20-budget-campaign/README.md) authenticates every successful raw execution/netlist/route and all failed receipts. Rebuild the corpus into a fresh output after restoring those archives:

```sh
make reproduce-budget-campaign PYTHON=python
python -m isaforge.campaign_evidence export \
  --root results/2026-10-20-budget-campaign/selection \
  --target-root generated/reproduction/budget-campaign/target-edn \
  --target-root generated/reproduction/budget-campaign/target-ud \
  --history-root generated/reproduction/budget-campaign/history/2026-10-19-automatic-aha-mont64 \
  --history-root generated/reproduction/budget-campaign/history/2026-10-20-automatic-crc32 \
  --history-root generated/reproduction/budget-campaign/history/2026-10-20-slre-transfer \
  --output generated/reproduction/expanded-corpus.json
```

This launches zero native hardware jobs and exactly refits the previously frozen models before export. The corpus itself was not available to the policies during the EDN/UD comparison.
