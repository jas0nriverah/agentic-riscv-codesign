# Prospective EDN/UD equal-budget campaign

Predictions and both workload pools were committed and pushed at `993d5d95ad7edb2539782f49151419f479836969` before candidate measurement. The cohort uses 18 historical labels, with 15 fitting rows per target after related-family exclusion. No new target supplies training data to the other.

The completed campaign retains 12 candidate attempts: nine verified implementations, two recorded correctness failures, and one infrastructure-censored result. Ten policies, three budgets, three LUT4 limits and five dependent seeds produce **900 endpoints**. The primary endpoint is best verified feasible speedup after three queries, +64 LUT4 and 12 MHz.

**No ML selection advantage:** the five learned policies tie calibrated latency on both targets. EDN reaches 1.000432304× with +32 LUT4; UD retains baseline because all four completed candidates exceed +64 LUT4. At the predeclared +128 limit, normalized XGBoost improves the original regressor's UD choice from 1.002584162× to 1.004117455× but only ties merit.

**Oracle qualification:** UD candidate 10 failed a free-disk-space preflight before simulation/synthesis. It has unknown correctness and hardware feasibility and remains charged at 31.322582 seconds. The immutable scorer's original `oracle`/`regret` fields describe the best verified completed reference. They do not establish an exhaustive full-pool optimum; gaps are lower bounds on regret to the unresolved full pool. At +64, UD reference hits are baseline retention, not successful discovery. The derived report names these quantities explicitly.

`manifest.json` binds the raw archives, selection reports, source manifest, qualification/diagnostic costs and provenance. The archives include all commands, failures, firmware, RTL, netlists and three routing seeds for completed designs; disposable simulator build directories are excluded. Seven qualification failures and three static linker diagnostics remain preserved. Prior workload archives are referenced by their exact manifests rather than copied or overwritten.

```sh
make reproduce-budget-campaign campaign-report PYTHON=python
```

Use Python 3.12 and `requirements-speedup.txt`. Replay authenticates raw evidence, chronology and exact historical-only prediction refits, starts zero native jobs, and reproduces every endpoint. The readable report, candidate CSV, endpoint CSV and figure are in `generated/reproduction/budget-campaign-report/`; a sealed copy is retained in `report/` alongside its reference-status qualifications.

[Full methods, results and collection commands](../../docs/budget-campaign.md) · [Expanded corpus](../2026-10-21-expanded-corpus/README.md) · [Prelabel evidence](../2026-10-20-budget-preregistration/README.md) · [Preserved validation](../2026-10-20-budget-validation/README.md)
