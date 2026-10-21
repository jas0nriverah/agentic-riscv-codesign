# Current handoff — October 20, 2026

Read [README](../README.md), [AGENTS](../AGENTS.md), [the primary-method review](research-foundation.md), [the expanded review](selection-methods-review.md), and [the new prospective results](prospective-slre.md). Branch: `ai-guided-ml`. The [pre-SLRE handoff](HANDOFF-before-slre-2026-10-20.md) preserves earlier findings and the resolved workload-fit priority.

## Verified now

- Original six-candidate CRC32 source-adapter evidence and both historical automatic CRC32/aha-mont64 pools remain unchanged, including negative results. The automatic historical contexts supply 12 training labels across two workloads.
- **SLRE is complete:** six automatically extracted and executable candidates from 16 eligible formulas, seven processor designs, 21 routes, full fixed-input correctness controls, and no observed partition overflow. The new context is explicit: `-Os`, 4,224-byte program limit, 3,840-byte stack; the same synthesized 8 KiB RAM/core/PCPI. Recorded maximum stack use is 3,072 bytes with 768 bytes headroom. All original `-O2`/4 KiB reservation contexts remain unchanged.
- **Prospective transfer:** predictions pushed at `1c812e1c6c09070ae45931241c37163d53ee05ee` before target candidate labels. Seven policies, budgets 1–3, five dependent seeds, 105 replay endpoints. Models fit all 12 historical rows after family exclusion. Compiler/partition/workload shift is explicit, not a uniform-context generalization claim.
- **Measured outcome:** 16,333,432 → 16,221,562 cycles, 1.006896× speedup, +77 LUT4. All six candidates meet the predeclared 1,781-LUT4 / 12 MHz limits. Frequency, merit, and calibrated latency find the optimum on query one. All three learned policies rank it fifth and miss it through query three.
- **ML diagnosis:** execution features lower MAE 21.14% but do not improve selection. Both nominal 90% ensembles have zero SLRE coverage in every seed. The independently calibrated heuristic predicts all six new cycle deltas exactly. No model is promoted and no residual model is justified by these outcomes.
- **Reproducibility and demo:** typed, transactional SQLite imports, a locally rendered HTML report, exact refit of all 90 frozen prediction rows, receipt-prefix chronology, raw extraction/lowering/processor audit, and all policy outcomes replay. `make demo` rebuilds them without native hardware jobs. SQL is analysis-only and must remain outside selector access.
- Automatic totals: **18 candidates / 21 designs / 63 routes / three real workloads**. The older adapter experiment is excluded from those counts. The oracle remains limited to each six-candidate pool.
- New native work: 133 successful-context commands plus 16 in the preserved failed initial partition attempt, 288.697 command-seconds total. Target candidate wall time is 260.120 seconds; do not add overlapping timer scopes. Historical ML labels cost 533.807 candidate wall-seconds plus separately recorded setup/baseline work.

## Validation and immutable evidence

The [latest validation](../results/2026-10-20-slre-validation/README.md) records **2,639 passing tests and 179 passing subtests**, all required research replays, and the real demo build. The previous unchanged legacy process-cleanup failure did not recur in this run; it is not claimed fixed. Preserve its earlier logs.

Do not edit the source files bound into `results/2026-10-20-slre-transfer`, its raw archives, or the prelabel checkpoint. New wrappers must preserve the source that produced evidence. `style_research_demo.py` adds presentation-only CSS after the frozen demo renderer, keeping measurement text unchanged. One initial SLRE image-packing failure and nine earlier build failures remain archived.

## Next smallest useful experiment

The immediate fit blocker is resolved. The remaining blocker is independent data that tests meaningful decisions. All current small pools improve cycles and satisfy area/timing limits; calibrated latency exactly explains their cycle deltas. More model versions on these consumed pools will not answer the research question.

Keep models fixed. Extend checked runtime support to another workload/input pool and freeze extraction rules, constraints, predictions, and measurement budget before labels. Seek an experiment in which timing/area or measured slowdowns can change the best feasible choice. Do not tighten SLRE's budgets after viewing outcomes and call that a prospective win. Use further independent data to test uncertainty-guided adaptation and constrained/cost-aware acquisition. Learn cost or latency residuals only after a measured selection failure demonstrates the need.

The original two-workload pilot remains development-only; three tiny workloads do not establish broad generalization or calibration. SLRE is now consumed data. Preserve its negative result. No new GNN, RTL-rewriting agent, isolated LUT study, or arbitrary-workload support claim.

The later LLM agent must use isolated bounded tools, the same public information and measurement budgets, and disclosed historical/inference costs. Current Python paid-label replay is cooperative, not an OS sandbox. Final one-to-three-instruction sets need joint lowering, execution, correctness, and synthesis; individual benefits and area increments cannot be summed.

## Commands

```sh
make test PYTHON=python
make reproduce reproduce-speedup reproduce-selection-research reproduce-model-analysis reproduce-prospective PYTHON=python
make demo PYTHON=python
python -m isaforge.experiment_ledger summary --db generated/reproduction/prospective-slre/experiments.sqlite
```

Use Python 3.12 and [pinned packages](../requirements-speedup.txt). The [SLRE guide](prospective-slre.md) records actual collection commands, six candidate measurements, all seven policies, costs, and limitations. Native collection remains serial with two build workers. Replay uses no native measurement tools.
