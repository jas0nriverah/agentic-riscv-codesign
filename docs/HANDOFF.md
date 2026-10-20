# Current handoff — October 20, 2026

Read [README](../README.md), [AGENTS](../AGENTS.md), [the original method review](research-foundation.md), and [the expanded review](selection-methods-review.md). Branch: `ai-guided-ml`. The [previous research handoff](HANDOFF-research-history-2026-10-19.md) is preserved as history.

## Completed

- The original six-candidate CRC32 source-adapter and automatic aha-mont64 experiments remain untouched, including negative outcomes.
- **Automatic CRC32 is complete:** actual RV32I features, legal extraction, assembly lowering, six candidates, seven integrated designs, 21 routes, 119 native commands and 272.778 command-seconds. Best 1.050833×, +31 LUT4; some formulas differ from their older adapter performance because the modified software differs. [Measurements](../results/2026-10-20-automatic-crc32/README.md).
- **Uniform corpus:** twelve automatically measured candidates across two workloads. The six older CRC32 adapter rows remain separate historical evidence. Do not count another CRC32 build as an independent workload.
- **Fixed ranking experiment:** one XGBoost pairwise ranker, original regression ensemble, seven policies, 420 consumed-data budget/seed outcomes. Whole-workload exclusion plus related operation-tree exclusion leaves five fitting rows per direction. Ranking does not improve verified selection over regression; merit reaches both pool optima in one query in all five seeds. [Full comparison](selection-pilot-results.md).
- **Uncertainty diagnostic:** the central 90% ensemble range covers only 26.67% of aha outcomes and 83.33% of CRC outcomes, averaged over model seeds. This is not calibrated confidence or 30 independent tests. Preserve the negative result.
- **Literature:** primary methods read for AutoTVM, SMAC, RGPE (2018 v1), Ithemal, covariate-shift conformal prediction, and arbitration delay/area modeling. These extend the prior Atasu/CIDRE/LACE/Gardner and Sun 2002 review. Exact Sun 2004 and Hussein 2026 methods remain inaccessible. No novelty claim is supported.

## Next blocker: an independent workload that fits

Nine failed workload/build contexts are archived. EDN needs 6,356 program/data bytes with `-Os`; huffbench/AES/wikisort exceed memory and some need missing runtime functions. SLRE now has tested C-locale character/string support, but the `-Os` build occupies 4,164 bytes, 68 beyond the unchanged 4,096-byte guard. A recorded `-Oz` benchmark-function fallback also fails. No third measured workload exists.

Stop compiler-flag trial proliferation. The next smallest engineering experiment should establish stack usage and a checked program/stack partition for SLRE, or explicitly prepare a separate memory context. Preserve the 8 KiB SoC and 4 KiB reservation in all existing evidence. Any new partition needs overflow detection, baseline self-checks, and exact tool/input binding before candidate collection; never silently remove the guard. Runtime helper component tests do not establish workload correctness.

`compact_workload` and `additional_workload` are serial preparation adapters around the frozen evaluator, not broad workload support. The SLRE preparation scripts are preserved failed protocols. Use their recorded entry points; do not run a compact context through the original `-O2` compiler entry point. Native collection still uses one evaluation at a time and two build workers.

## Next research comparison

Freeze a new legal pool and fixed existing regression/ranking settings before its labels. Hold out the whole new workload, exclude related candidate families, and save zero-shot predictions before scoring. Then allow paid adaptation. Add a charged PicoRV32 latency/timing-aware heuristic and constrained-EI comparator; all current tiny pools pass constraints, so they cannot establish feasibility-learning value.

The explicit two-workload pilot is development only and does not relax the primary three-group gate. Three small groups would still be insufficient for broad generalization or reliable calibration. Avoid another model variant, isolated area predictor, GNN, or RTL agent. The next data should test the current models, not be used to tune them immediately.

After these connections work, implement the LLM instruction-selection agent with isolated bounded tools, equal public information, evaluation budgets and historical/inference costs. The current Python interface is not an OS sandbox. Final one-to-three-instruction sets require joint lowering, correctness, execution, and synthesis; do not add individual speedups or area deltas.

## Reproduce

```sh
make test
make reproduce
make reproduce-speedup
make reproduce-selection-research
```

Use Python 3.12, the [pinned replay requirements](../requirements-speedup.txt), and the initialized Embench submodule. The last command authenticates automatic CRC32, all 420 development outcomes and nine failed fit contexts without native jobs. Source hashes and negative evidence must remain intact.
