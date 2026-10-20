# Current handoff — October 19, 2026

Read [README](../README.md), [AGENTS](../AGENTS.md), and [the method review](research-foundation.md) first. This handoff replaces the [historical cost-model priorities](HANDOFF-history-2026-10-19.md). The working branch is `ai-guided-ml`.

## Completed and preserved

- **CRC32:** six executable source-adapter candidates, actual whole-benchmark cycles, correctness controls, integrated resources, three routing seeds, a live bounded selector, and 120 policy replays. Best 1.050833×, 4.8374% fewer cycles, +31 LUT4. Merit wins the budget-three comparison. The slowdown from `mask_offset` remains in the evidence.
- **aha-mont64:** automatic RV32I profiling, established dataflow extraction, assembly lowering, six executable candidates, full correctness controls, integrated synthesis/routing, and 120 policy replays. Best 1.094120×, 8.6024% fewer cycles, +42 LUT4. Merit finds the optimum with one measurement in all five seeds. Learned acquisition shows no advantage and loses to random at budget four. [All measurements and commands](automatic-workloads.md).
- **Corpus:** 12 actual single-instruction outcomes, two workload groups, one pinned processor context. Features and labels have explicit provenance. Cross-workload readiness is false; do not present contract tests as measured generalization.
- **Contract and cleanup:** the README/AGENTS now define measured performance selection, historical-label costs, strong baselines, hidden target outcomes, and joint-set validation. The unused RTL-search module and its tests are retained as non-importable text in `archive/`. Historical model results and negative outcomes are preserved.
- **Literature:** actual methods reviewed for Atasu, CIDRE, LACE, Gardner, and Sun's separate 2002 conference paper, plus relevant regression/cost-aware/ranking sources. The exact Sun 2004 and Hussein 2026 full methods remain inaccessible; no detailed reproduction/novelty claim may rely on them.

## Next smallest data experiment

Preserve both checkpoints. Run CRC32 through the automatic RV32I extraction path in a **new** context to harmonize feature provenance, then try an independent proposal workload such as `edn` through the same baseline/fit gates. Do not reuse consumed CRC32 or aha outcomes as an untouched final test. Freeze the new pool, feature definitions, policies, seeds, clocks/caps, and cost accounting before its labels. Existing SHA-256 and matrix probes failed linker/memory requirements; those failures remain in the CRC archive.

The minimum group gate is three, but three small groups are not evidence of broad transfer. Keep collecting diverse manageable pools before the primary held-out-workload study. Avoid shortlisting every future pool exclusively by merit: freeze a broader legal pool when affordable, report exclusions, and charge its oracle construction separately.

## Selection experiment after the data connection

Use fixed XGBoost regression and pairwise ranking trained only on other workload/source groups. Report zero-shot predictions before any paid target observations, then a separate limited-budget adaptation curve. Add a PicoRV32 latency/timing-aware merit baseline with separately charged microbenchmark calibration, and a constrained-EI comparator. Cost-aware acquisition must use observed/predicted durations rather than hidden target durations. Use existing model recipes before introducing new variants; modify one only to address a measured selection failure.

The endpoint is best verified feasible whole-program performance versus evaluations and actual evaluation time, with oracle regret. Include training-label counts/time, profiling/baseline setup, failed attempts, inference, and shared-cost amortization. Preserve heuristic wins. Report uncertainty calibration on untouched workload groups; bootstrap spread alone is not confidence.

Only then connect an LLM **instruction-selection** agent with isolated access to list/predict/measure/choose tools and the same budget/information as non-agent policies. `LiveSelectionTools` is not an OS sandbox. Automatic multi-instruction selection needs a conflict/encoding contract and **joint** lowering, simulation, correctness, synthesis, and routing for one to three instructions; never add individual speedups or area deltas.

## Reproduce and validate

```sh
make test
make reproduce
make reproduce-speedup
```

Use the README's Python extras and initialized Embench submodule. `make reproduce` checks historical cost-model scores; `make reproduce-speedup` authenticates and replays both current processor snapshots without native jobs. [Automatic-workload instructions](automatic-workloads.md) distinguish portable evidence replay from native recollection with pinned tools.

Do not edit frozen hash-bound measurement sources to make an old audit pass. Extend with new modules/contexts and preserve source snapshots. Do not delete local raw evidence merely because a snapshot exists. The [alignment review](scope-review.md) records the remaining gaps and what the cleanup changed.
