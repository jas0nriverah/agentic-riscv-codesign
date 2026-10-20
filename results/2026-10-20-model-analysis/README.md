# Full model diagnosis and calibrated latency baseline

This is a consumed-data diagnostic of the fixed speedup regressor/ranker, with a separately calibrated architecture heuristic. No new learned model or hyperparameter search was introduced. Twelve automatic candidate labels, two workload groups, five fitting rows from one workload per transfer direction. Eighteen of 35 features are constant; regression collapses aha into two predictions and CRC into three in every seed.

The new latency baseline matches all twelve measured cycle savings exactly and finds both restricted-pool optima with one measurement in all five seeds. This matches simple merit's result; it is not an ML superiority or generalization claim. All current candidates are feasible and beneficial. Hardware cost, routed timing, and sets of instructions still need their own measurements.

- [Protocol](protocol.json): fixed methods/seeds/budgets, source/package hashes, public-baseline inputs, opaque bindings to original pilot evidence, and independent calibration cost.
- [Public predictions](public-predictions.json): original features and added baseline-normalized execution/latency estimates, generated before this comparison opens candidate outcomes.
- [Baseline input projection](baseline-inputs.json) and `baseline-evidence/`: exact lowering occurrences and baseline disassembly/provenance. No candidate outcome is an input to the heuristic.
- [Report](report.json): tree-use/support checks, measured labels, uncertainty, 420 existing and 60 added budget/seed outcomes, and limitations.
- [Manifest](manifest.json): immutable evidence and frozen source-copy hashes. This later explanatory README is outside it.

```sh
make reproduce-model-analysis
```

The replay wrapper authenticates raw calibration, then recomputes results into a temporary directory. Canonical JSON comparison handles the frozen analyzer's tuple/list round-trip defect; direct `analyze_speedup_model.py verify` should not be used for this snapshot. Scientific values are unchanged and only actual analysis wall time is excluded from exact equality. No new native work is performed.

See [the full diagnosis and prioritized next experiment](../../docs/model-analysis.md). Current models remain frozen. The next blocker is an independent workload that fits with checked memory/runtime support, followed by one prospectively declared feature ablation.
