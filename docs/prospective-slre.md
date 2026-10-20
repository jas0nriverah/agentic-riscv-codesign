# Prospective SLRE transfer — October 20, 2026

ISAForge now executes a third real Embench workload end to end: automatic extraction, assembly lowering, correctness checks, modified-processor execution, synthesis/routing, and selection from predictions frozen before target labels. Automatic evidence totals **18 candidates, 21 designs including baselines, and 63 routes across three workloads**. The older six-candidate CRC32 source-adapter experiment remains separate and unchanged.

**Result:** frequency, merit, and calibrated latency find the six-candidate pool optimum in one evaluation. Existing XGBoost regression, ranking, and a predeclared execution-feature ablation all rank that optimum fifth and miss it through budget three. Lower prediction error does not establish a better optimizer.

## Run the demo

```sh
python -m pip install -r requirements-speedup.txt  # Python 3.12
make demo PYTHON=python
# Open generated/reproduction/prospective-slre/index.html.
python -m isaforge.experiment_ledger summary \
  --db generated/reproduction/prospective-slre/experiments.sqlite
make reproduce-prospective PYTHON=python
```

Replay authenticates raw archives and source/package bindings, exactly refits the fixed historical models and reproduces 90 frozen prediction rows, replays 105 policy/budget outcomes, and rebuilds the offline HTML/SQLite analysis view. It starts no native hardware jobs. Recorded tool paths are provenance; replay resolves evidence inside the restored archive. The HTML has no external assets or network requirement.

## Actual processor measurements

Cycles cover the complete Embench benchmark region, including its configured repetitions. Startup, warmup, and self-check execute outside that timing region. Baseline and optimized programs use the same inputs at a common **12 MHz** clock. Every row passes upstream result verification, device fit, and all three timing seeds. Fmax is the routed internal-clock estimate, not a physical-board measurement or the execution clock.

| Design | Cycles | Speedup | LUT4 (added) | Flip-flops / carry | Fmax seeds 1 / 2 / 3 MHz |
| --- | ---: | ---: | ---: | ---: | --- |
| baseline | 16,333,432 | 1.000000000× | 1653 (+0) | 655 / 295 | 77.160 / 68.493 / 70.388 |
| candidate_00 | 16,221,562 | 1.006896377× | 1730 (+77) | 712 / 328 | 74.019 / 71.266 / 72.197 |
| candidate_03 | 16,305,272 | 1.001727049× | 1748 (+95) | 712 / 350 | 78.321 / 79.789 / 71.018 |
| candidate_06 | 16,319,352 | 1.000862779× | 1713 (+60) | 708 / 323 | 64.696 / 67.866 / 68.157 |
| candidate_09 | 16,332,112 | 1.000080822× | 1716 (+63) | 712 / 320 | 71.296 / 75.603 / 66.979 |
| candidate_12 | 16,332,112 | 1.000080822× | 1684 (+31) | 680 / 297 | 71.515 / 68.041 / 68.890 |
| candidate_15 | 16,333,102 | 1.000020204× | 1663 (+10) | 681 / 328 | 68.190 / 67.336 / 67.976 |

All designs use 20 block RAMs, including 16 program/data blocks. The cap is **1,781 LUT4**, or baseline +128. The best saves **111,870 cycles**, with **1.006896× speedup**, **0.684914% fewer cycles**, and **+77 LUT4**. Firmware, generated datapath RTL, lowering records, simulated executions, netlists, and routes are preserved in the raw archive.

| Candidate | Extracted formula |
| --- | --- |
| candidate_00 | `add(in0,addi(in1,1))` |
| candidate_03 | `add(in0,slli(addi(in1,1),4))` |
| candidate_06 | `slli(addi(in0,1),4)` |
| candidate_09 | `addi(addi(in0,2047),385)` |
| candidate_12 | `addi(lui(4096),-319)` |
| candidate_15 | `sltiu(sub(in0,in1),1)` |

Names retain original merit ranks. The frozen pool samples indices 0, 3, 6, 9, 12, and 15 from 16 eligible formulas, broadening the benefit range beyond a top-merit shortlist. The oracle measures only these six; ten eligible formulas remain unmeasured.

## Prospective selection

Predictions and public features were pushed in [commit 1c812e1](https://github.com/jas0nriverah/agentic-riscv-codesign/commit/1c812e1c6c09070ae45931241c37163d53ee05ee) before any target candidate evaluation. Replay checks the exact committed manifest digest, unchanged baseline/discovery artifacts, and the frozen 31-command prefix of the final 133-command receipt list. The Python interface enforces cooperative paid-label replay; it is not an OS isolation boundary for an external LLM.

Policies share the six candidates, baseline fallback, area/timing limits, and budgets of 1–3 target evaluations. Models receive the same historical training data; heuristics need no training labels, and per-policy costs remain visible. Five seeds repeat model/random choices on one workload; they are not five independent tests.

| Policy | Speedup after 1 evaluation | Speedup after 3 | Regret after 3 | Oracle hits at 1 / 3 | Wall seconds at 3 |
| --- | ---: | ---: | ---: | ---: | ---: |
| frequency | 1.006896377× | 1.006896377× | 0.000000000 | 5/5 / 5/5 | 133.264 |
| merit | 1.006896377× | 1.006896377× | 0.000000000 | 5/5 / 5/5 | 133.264 |
| calibrated_latency | 1.006896377× | 1.006896377× | 0.000000000 | 5/5 / 5/5 | 133.264 |
| random | 1.001756716× | 1.002258815× | 0.004637561 | 1/5 / 1/5 | 129.287 |
| regression_zero_shot | 1.001727049× | 1.001727049× | 0.005169328 | 0/5 / 0/5 | 132.122 |
| ranking_zero_shot | 1.001727049× | 1.001727049× | 0.005169328 | 0/5 / 0/5 | 130.853 |
| execution_regression_zero_shot | 1.001727049× | 1.001727049× | 0.005169328 | 0/5 / 0/5 | 132.263 |

The oracle is **1.006896377×**. Frequency, merit, and latency reach it in one evaluation (47.162 candidate wall-seconds). All learned policies first choose `candidate_03`, the second-best speedup, and do not improve through three evaluations. Random results describe the five frozen orderings. The 105 replay endpoints reuse six hardware evaluations; they are not 105 newly synthesized designs.

## What the models predict

The original bootstrap XGBoost regressor predicts **measured whole-program speedup**, not LUT cost. The pairwise XGBoost ranker uses those outcomes within historical workload groups. Both use 35 public candidate features. One predeclared ablation adds eight baseline-normalized and execution-latency features with the same regression settings and bootstrap draws. Twelve prior automatic CRC32/aha-mont64 outcomes across two workloads survive workload/family exclusion; no SLRE labels enter fitting. No hyperparameter tuning or model-version search followed these outcomes.

Mean speedup MAE decreases **0.024039751 → 0.018958693**, a **21.14% reduction**, with **no selection improvement**. Both ensembles' central 90% ranges miss all six outcomes in every seed. Ensemble spread is not calibrated confidence. Every SLRE vector has features outside historical ranges, and SLRE benefits are below the historical minimum. Limited training diversity and tree extrapolation are concrete limitations.

The independently calibrated latency heuristic predicts all six new cycle deltas exactly. There is no demonstrated residual-performance error for another residual model to solve in this restricted operation set. This supports the heuristic baseline; it does not establish learned generalization.

## Costs and the SQLite ledger

| Disjoint native-command scope | Commands | Seconds |
| --- | ---: | ---: |
| Setup and guard controls | 23 | 8.477 |
| Baseline | 8 | 28.640 |
| Six candidates | 102 | 246.284 |
| Failed initial partition attempt | 16 | 5.296 |
| Total new work including failure | **149** | **288.697** |

The six evaluations separately total **260.120 candidate wall-seconds**; baseline evaluation takes **29.628 wall-seconds**. These timers overlap command durations and must not be added. ML also requires **12 historical labels / 533.807 historical candidate wall-seconds**. Historical setup/baseline costs remain in the context records. Independent latency calibration costs **5.096 command-seconds**. Recorded fit/predict time is separate. This is offline policy replay with recorded costs, not live end-to-end agent timing or a complete training-cost amortization study.

Typed SQLite tables cover contexts, source files, candidates, measurements, routes, failures, and costs, with SQL summary views. Imports authenticate raw receipts before writing, roll back on errors, and permit only identical repeat imports. Incomplete contexts contribute costs/failures, never verified labels. The report joins paid outcomes to exact candidates and processor contexts. The ledger contains hidden outcomes and is analysis-only; selectors must never receive it.

## Runtime and correctness

SLRE originally exceeded the 4,096-byte program guard. Its new context retains 8 KiB RAM and the original synthesized processor RTL, with a declared 4,224-byte program/data limit, guard, and 3,840-byte stack starting at address 4,352. `-Os` produces 4,164 program/data bytes. Continuous observation records minimum SP 5,120 and maximum stack use 3,072 bytes, leaving **768 bytes headroom** for these inputs. Two real negative controls detect stack-pointer underflow and a guard write. Observed/unobserved baseline results and counters match exactly.

Candidate runs pass upstream self-checks, expected custom execution counts, stock firmware on the extended processor, custom-op rejection on the unextended processor, and partition checks. This establishes fixed-input correctness and **no observed partition overflow**, not arbitrary-input safety, object bounds, invalid-read detection, or board operation. Historical workloads use `-O2` and the old partition; the target context shift is explicit. The first new partition attempt failed at an old image-builder limit before baseline execution; its original source, receipts, and failure are archived.

## Collection commands and next blocker

These were the actual ordered entry points; never reuse a completed output directory for a new protocol. Native collection needs the pinned compiler, Verilator, Yosys, nextpnr, and a prepared reference context with valid local tools. See [processor setup](codesign-loop.md).

```sh
python -m isaforge.partitioned_workload prepare \
  --reference-root generated/codesign-crc32-2026-10-19-r1 \
  --root generated/partitioned-slre-2026-10-20-r2 --pool-size 6
python -m isaforge.partitioned_workload discover --root generated/partitioned-slre-2026-10-20-r2
python -m isaforge.partitioned_workload baseline --root generated/partitioned-slre-2026-10-20-r2
python -m isaforge.prospective_inputs freeze \
  --target-root generated/partitioned-slre-2026-10-20-r2 \
  --root generated/prospective-slre-2026-10-20
# Commit/push the prediction checkpoint before collecting candidate outcomes.
python -m isaforge.partitioned_workload collect --root generated/partitioned-slre-2026-10-20-r2
python -m isaforge.prospective_inputs evaluate \
  --target-root generated/partitioned-slre-2026-10-20-r2 \
  --root generated/prospective-slre-2026-10-20
```

The next blocker is independent data where constraints affect decisions. All three small measured pools have positive candidates and pass the declared limits, while calibrated latency already explains their cycles. Keep models fixed. Add another independently frozen workload/input pool with checked runtime support, then test whether area/timing constraints or actual slowdowns create selection errors the analytic ranking cannot solve. Predeclare tighter budgets as a new experiment; do not change SLRE's constraints after seeing outcomes. Only then test uncertainty-guided adaptation or a learned feasibility/cost model.

Non-agent constrained active learning, the bounded LLM selection agent, and jointly measured instruction sets remain future stages. No isolated LUT study, GNN, RTL-rewriting agent, or production-serving claim is introduced.

[Raw snapshot](../results/2026-10-20-slre-transfer/README.md) · [Prelabel checkpoint](../results/2026-10-20-slre-preregistration/README.md) · [Validation](../results/2026-10-20-slre-validation/README.md) · [Handoff](HANDOFF.md)
