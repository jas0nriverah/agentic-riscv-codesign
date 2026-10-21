# Prospective guarded SHA256 campaign

Six automatically extracted instructions from the original Embench SHA256 program passed full execution/correctness, processor controls, integrated synthesis and three routing seeds. This adds six verified labels, one baseline and 21 routes. The automatic corpus now has 33 labels, 36 attempts, 39 measured designs and 117 routes across six source workloads. Three historical failures remain preserved.

At the primary +64-LUT4, 12-MHz constraint, candidate 22 reduces cycles from 26,135,630 to 25,588,430 (1.021384665×), adding 50 LUT4. Candidate 00 is fastest at 1.053939769× but adds 68 LUT4 and is infeasible at the primary cap. All six pass timing; these are RTL simulation and FPGA synthesis/routing results, not physical-board measurements.

The cost-aware latency heuristic finds the primary pool optimum with one query, adaptive GP with two, and merit/calibrated latency/normalized XGBoost with three. Raw regression and pairwise ranking miss it in some dependent seeds. No learned policy beats the strongest heuristic. At +128 LUT4, the fastest instruction is feasible; at +32 all policies retain the baseline. The complete six-candidate oracle covers this frozen recorded-input pool only.

The source guard excluded three symbolic-address candidates before shortlisting six from 56 legal/calibrated formulas. The native pipeline enforces one attempt per candidate and rejects old entrypoints. Baseline stack use is 384 of 576 reserved bytes; full fixed-input checks pass. Original benchmark input, ISA, processor RAM and PCPI are preserved.

The [prelabel checkpoint](../2026-10-21-sha256-preregistration/README.md), predictions and native protocol were committed and pushed at `ab3789f106eab46df26ebcce56a6909e8d34c45b` before any candidate measurement. The same 27 historical labels were available, with 21 fitting rows after related-family exclusions. Ten policies × three budgets × three caps × five dependent seeds give 450 replay endpoints. SHA256 is one independent workload.

All six measured cycle deltas exactly match calibrated latency, extending that match to all 33 verified automatic labels. Normalized XGBoost speedup MAE is 0.006941309 versus 0.016548112 for raw regression; nominal 90% interval coverage is only 43.3% versus 16.7%. These diagnostics do not establish calibrated confidence or selection superiority.

Candidate ledger wall time is 402.461094 seconds, alongside 1,698.152954 historical candidate-attempt seconds. Ledger timers include validation within the attempt; repeated public discovery checks outside the ledger and other setup/inference are separate and not a complete collection or lifetime project timer. Narrower measurement-record durations are also retained. Native command time overlaps wall time; do not add the two.

- `native/`: complete raw archive, strict audit, source bindings and Git protocol proof.
- `report/`: all candidate outcomes, 90 aggregated policy endpoints, regression diagnostics and readable report.
- `provenance.json`: exact prelabel commit, complete final selection inventory and replay/report sources.
- `manifest.json`: all campaign files; original frozen campaigns remain unchanged.

```sh
make reproduce-sha256 PYTHON=python
make sha256-report PYTHON=python
```

Replay restores raw evidence, checks exact prelabel Git bytes and source bindings, refits the frozen historical predictions and reruns all 450 policy endpoints with zero new native jobs. The [guide](../../docs/guarded-sha256.md) records collection commands, limits and next blockers.
