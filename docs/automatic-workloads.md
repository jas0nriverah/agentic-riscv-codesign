# Automatic aha-mont64 milestone — October 19, 2026

**Completed:** a second real Embench workload now runs through automatic candidate extraction, executable assembly lowering, whole-program processor measurement, correctness controls, integrated synthesis/routing, and budget-matched selection replay. The best of the six measured candidates reduces cycles **8.6024%**, with **42 added LUT4s**. Merit selects it first; this experiment does not demonstrate an ML advantage.

The [frozen snapshot](../results/2026-10-19-automatic-aha-mont64/README.md) preserves all six results and raw evidence. The original [CRC32 experiment](codesign-loop.md), including its slowdown and heuristic wins, remains unchanged. This milestone extends the existing infrastructure rather than introducing a new compiler, processor, enumerator, or RTL agent.

## Extraction and execution

The program is upstream Embench `aha-mont64/mont64.c`, revision `0466a18e4f6b47e19598d7c6ba72916d54b68f65`. GCC compiles it with RV32I/Zicsr, ILP32, `-O2`, no relaxation, and `CPU_MHZ=1`. Its 64-bit arithmetic executes through RV32 software helpers. The complete benchmark invocation is timed, including those helpers; startup, warmup, verification, and reporting are outside the measurement window. The generic harness uses the workload's own scale factor, not the CRC-specific repetition fields inherited in the common configuration record.

The profiler reads the pinned PicoRV32 instruction counter and PC through Verilator visibility annotations. It does not insert program instructions. Marker labels map 619 emitted source assembly statements; original and marked baseline firmware are byte-identical. The counter window and PC histogram reconcile, and a separate unobserved baseline run has identical cycles and retired instructions. Synthesis uses the original unannotated core.

The existing dataflow extractor finds **21 formulas**, all with executable occurrences. The predeclared pool takes the six highest overlap-safe dynamic instruction-saving formulas, with a deterministic formula tie-break, before collecting candidate performance labels. The full 21-formula list and exclusions remain in the archive. This shortlist favors merit and restricts the oracle; it is not a search over all legal instructions.

Lowering replaces nonoverlapping occurrences in GCC assembly and reassembles all branches, labels, and relocations. Only complete single-word source statements are eligible. Multi-instruction pseudo-ops, unsupported/opaque blocks, unsafe operand lifetimes, memory/control operations inside a candidate, and overlapping occurrences are rejected. Each instruction has at most two register inputs, one result, and two to four connected operations. Constants are fixed in its deterministic datapath.

## Measured designs

Every design uses the same PicoRV32 commit `ef203c2b0a3fb793280f5114941416c425c5b461`, 8 KiB synchronous RAM, 4 KiB reserved stack, one PCPI wait cycle, 12 MHz common clock target, and iCE40 HX8K CT256. The baseline program/BSS ends at byte 3,152, below the 4 KiB guard.

| ID / formula | Cycles | Speedup | Integrated LUT4 (added) | FF | Carry | Routed internal Fmax, seeds 1 / 2 / 3, MHz | Correct |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| Baseline | 62,311,489 | 1.000000× | 1,653 | 655 | 295 | 77.16 / 68.49 / 70.39 | Pass |
| 00: `add(srli(in0,31),slli(in1,1))` | **56,951,233** | **1.094120×** | 1,695 (+42) | 712 | 297 | 75.20 / 69.50 / 64.88 | Pass |
| 01: `or(srli(in0,31),slli(in1,1))` | 59,387,713 | 1.049232× | 1,693 (+40) | 712 | 297 | 59.31 / 65.78 / 77.91 | Pass |
| 02: `add(srli(in0,31),in1)` | 58,440,193 | 1.066244× | 1,726 (+73) | 712 | 328 | 72.69 / 71.27 / 65.18 | Pass |
| 03: `add(in0,slli(in1,1))` | 61,228,609 | 1.017686× | 1,733 (+80) | 712 | 327 | 70.81 / 71.19 / 65.18 | Pass |
| 04: `or(in0,slli(in1,1))` | 61,661,761 | 1.010537× | 1,725 (+72) | 712 | 297 | 73.41 / 73.68 / 75.43 | Pass |
| 05: `or(srli(in0,31),in1)` | 60,199,873 | 1.035077× | 1,696 (+43) | 712 | 297 | 69.65 / 67.87 / 67.61 | Pass |

All designs use 20 BRAM blocks, including 16 for program/data RAM, fit the device, and meet 12 MHz in all three routes. All six pass the baseline-plus-128-LUT4 cap. Baseline has 10,973,336 retired instructions; candidate 00 has 10,377,752. The measured cycle reduction is larger than the instruction reduction, illustrating why instruction count is not the performance label. The best common-clock runtime is approximately 4.746 s versus 5.193 s baseline, computed from simulated cycles, not a board stopwatch. Fmax differences are retained as timing impact; they are not substituted for the common clock. Exact per-seed values and conditional own-Fmax ratios are in [audit.json](../results/2026-10-19-automatic-aha-mont64/audit.json).

## Correctness and bounds

All six pass the upstream benchmark self-check (result 0, verification 1), expected dynamic custom counts and PCPI wait/valid counts, and exact retired-instruction reduction from the removed occurrences. Each generated datapath passes 228 independent integer-oracle vectors. Lowered blocks pass 384 sampled complete architectural-state comparisons per candidate (2,304 total), including registers, memory effects, and control flow with all occurrences lowered together.

Stock firmware on each extended processor reproduces the baseline exactly. Custom firmware traps on the unextended processor. These controls and sampled checks are not universal program equivalence or formal timing verification. The three routed seeds are engineering variability checks, not a population confidence interval.

The collection completed 119 bounded native commands in **301.542 command-seconds**, with one native worker and at most two build workers. Six candidate evaluations took 280.244 elapsed seconds in total; baseline evaluation took 28.052 seconds. These timers have different scopes, including Python bookkeeping versus subprocess time, and must not be added to one another. Profiling/setup is retained in the native ledger. No new native measurements were performed for the policy replay.

## Smallest follow-up experiment: existing selection policies on the new labels

Implemented `isaforge.workload_selection`: it audits the automatic experiment, reuses the existing XGBoost and four policies, and records 120 policy/budget/seed outcomes. Budgets 1–6, seeds 0–4, two charged bootstrap observations, +128 integrated LUT4, and 12 MHz match the collection plan. Policies receive only formula/profile features; the evaluator reveals a target outcome only after charging its query. Final designs must have measured correctness, improved performance, and measured area/timing feasibility. The baseline remains available.

The report also records best feasible speedup and oracle regret after every query, cumulative recorded evaluation time, and actual model fit/prediction time. It is a **development replay after collection**, not a prospective unseen-workload trial or a fresh wall-clock race. Historical speedup training rows/time are zero. The oracle consumed all six candidate evaluations, plus baseline/setup; it is a privileged reference.

| Policy | Budget 1 mean best speedup | Budget 3 mean best speedup | Budget 3 oracle hits / 5 | Budget 3 regret | Budget 3 mean recorded candidate seconds |
| --- | ---: | ---: | ---: | ---: | ---: |
| Frequency | 1.077394× | 1.094120× | 5 | 0 | 141.663 |
| Merit | **1.094120×** | **1.094120×** | **5** | **0** | 141.531 |
| Random | 1.050966× | 1.065586× | 1 | 0.028534 | 140.853 |
| Learned upper-quantile acquisition | 1.050966× | 1.065586× | 1 | 0.028534 | 140.853 |
| Exhaustive oracle | 1.094120× reference | 1.094120× reference | — | 0 | 280.244 for all six |

Merit finds the optimum after one query in every seed. At budget four, random reaches mean 1.088545× (4/5 oracle hits), while learned acquisition reaches 1.079567× (3/5). At budget six, all policies reach the oracle. These negative outcomes are preserved, with every query order and prediction in [selection-report.json](../results/2026-10-19-automatic-aha-mont64/selection-report.json).

The learned selector predicts **measured whole-program speedup**, not LUT usage. It fits 20 bootstrap XGBoost regressors, each 80 trees of depth two, on only its paid target-workload observations and 35 public formula/profile features. It chooses the largest ensemble upper quantile after two initial queries. This is neither a separately trained ranker nor calibrated confidence. No historic LUT model is called, and no prior-workload speedup labels are supplied. Strong timing-aware heuristics, constrained EI, cost-aware acquisition, and the LLM agent are explicitly missing comparators.

## Working commands

Install the README's Python extras and initialize the pinned Embench submodule. Portable evidence replay needs no RISC-V compiler, Verilator, Yosys, or nextpnr:

```sh
python scripts/reproduce_codesign.py replay
python scripts/reproduce_workload.py replay
# Or both:
make reproduce-speedup
```

Replay extracts a manifest-checked archive, re-extracts and re-lowers candidates, checks raw counters/controls, recounts integrated netlists and all routes, then recomputes all 120 selection outcomes. Only nondeterministic model wall-clock bookkeeping is excluded from numerical replay comparison. It verifies source bindings and should fail if frozen implementation sources have changed.

On the recorded host, native collection uses a fresh directory and the completed CRC reference context:

```sh
python -m isaforge.workload_experiment prepare \
  --reference-root generated/codesign-crc32-2026-10-19-r1 \
  --root generated/automatic-aha-new --workload aha-mont64 --pool-size 6
python -m isaforge.workload_experiment discover --root generated/automatic-aha-new
python -m isaforge.workload_experiment collect --root generated/automatic-aha-new
python -m isaforge.workload_selection --root generated/automatic-aha-new
python -m isaforge.workload_selection --root generated/automatic-aha-new --verify
```

Native `prepare` inherits verified tool paths/hashes from the reference. A different host must prepare and complete a new CRC context with its actual pinned tools using [the CRC commands](codesign-loop.md), then use that new reference. Editing an old plan to change absolute tool paths invalidates its identity. Portable replay and portable recollection have different requirements; automatic tool discovery for a new context remains a usability improvement.

Corpus export, including both preserved workloads:

```sh
python -m isaforge.workload_audit \
  --root generated/automatic-aha-new \
  --crc32-root generated/codesign-crc32-2026-10-19-r1 \
  --output generated/automatic-aha-new/combined-corpus.json
```

## Limitations and next blocker

The combined dataset has **12 rows, two workload groups, one processor configuration, and one fixed input configuration per workload**. Historical CRC features come from RV32IM discovery; aha features come from actual RV32I execution. The readiness gate correctly rejects a cross-workload claim. Reprofile CRC32 in a fresh automatic context and add independent workload pools before training/evaluating transferable regression or ranking. The gate's minimum three groups is only a minimum implementation requirement; more diverse data are needed for meaningful generalization.

The existing SHA-256 and matrix-workload probe failures (link dependencies/memory limits) remain preserved in the CRC snapshot. New workload collection must pass the same baseline, ISA, fit, and lowering checks; do not silently enlarge memory or mix hardware contexts. A pool larger than the top six, frozen before target labels, will be needed to reduce shortlist bias. Final compatible sets of two or three instructions still need joint lowering/execution/synthesis; this experiment measures single instructions only.
