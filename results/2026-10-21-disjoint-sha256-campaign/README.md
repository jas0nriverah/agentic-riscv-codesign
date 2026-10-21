# Fresh disjoint SHA256 measurements and fixed ML comparison

Six new literal formulas, six successful one-attempt evaluations, full original SHA source/input, integrated RV32I/PicoRV32/8KiBSoC and18candidate routes. Baseline plus six candidates yield seven processor evaluations and21routes. No native retry, source/input edit or hardware-context relaxation. These new candidates share already consumed SHA families; this is not a seventh workload or independent-source test.

At+64LUT4/12MHz, candidate23 is the declared-pool optimum:26,135,630→25,466,830cycles,1.026261612×,+43LUT4, minimumFmax62.992MHz. New budget-conditioned XGBoost reaches it at query2/131.808 recorded target seconds, versus normalized XGBoost query3/201.231seconds, across all five dependent seeds. The cost-aware heuristic wins at query1/63.840seconds. Adaptive GP ties the new model at query2. Fixedthree-query policies still spend all three attempts; oracle attainment is not an automatic stopping rule.

All eleven policies and495 budget/cap/seed endpoints are preserved in the separate final selection directory; the report and CSV tables are in `../2026-10-21-feasible-benefit-report/`. Full measured outcomes and raw controls/netlists/routes are authenticated before policy replay. Every new measured cycle delta exactly equals the calibrated latency estimate.

The complete157-file model/prediction/native-baseline preregistration was pushed at25322573b86b933253f36a8316a18f7b1a058e67 before any candidate attempt. The release verification retains exact Git bytes and zero-attempt state. The protocol was committed as `../2026-10-21-feasible-benefit-preregistration/baseline/evaluation-protocol.json`, not under the ignored generated native path. Consequently the generic native-pack precheck for that original path was rejected before any archive write; the diagnostic is retained. The native archive has receipt/source authentication, and the OUTER reproducer supplies complete Git/protocol-copy authentication. No retroactive commit is claimed.

Candidate ledger time totals396.754094seconds; baseline ledger39.346900seconds;133native commands total275.054454seconds. Timers overlap and must not be added. All36 previous consumed development attempts cost2100.614048recorded seconds, including six old SHA labels excluded from fitting;27non-SHA available successes plus three failures cost1698.152954seconds. Full-project lifetime and automatic stopping savings are not established.

```sh
make reproduce-feasible-benefit PYTHON=python
make feasible-benefit-report PYTHON=python
make export-model-corpus PYTHON=python
```

Use Python3.12/pinned requirements. Derived output paths must be fresh. No new native jobs run during replay. Raw archive, canonical audit/outcomes, failed archive precheck and all previous studies remain preserved.
