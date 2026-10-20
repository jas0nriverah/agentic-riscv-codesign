# Measured application-speedup selection — October 19, 2026

ISAForge now connects a learned selection policy to executable custom instructions and measured whole-benchmark processor cycles. The first complete experiment covers six CRC32 candidates, one instruction per design. **Merit wins this experiment; a learned-selection advantage is not demonstrated.** The next research priority is a measured speedup corpus across independent workloads, followed by an LLM instruction-selection agent with controlled measurement tools. RTL rewriting is outside scope. The existing area-prediction evidence remains preserved.

Before this change, `src/candidates.py::extractCandidates` produced legal computation graphs, `isaforge/model.py::SpeedupPredictor` and `selection.py::run_policy` supported speedup prediction and recorded-label replay, and `core_experiment.py` / `soc_experiment.py` measured two fixed CRC32 extensions separately. The heavily trained V6/V9 models predicted isolated LUT4 cost. They did not establish learned program-speedup selection. The missing connection was a callable processor evaluator for the selected candidate.

That connection is now `codesign.py::ProcessorEvaluator`: lower one supported formula into firmware, prove/check its datapath, execute the modified program, check baseline controls, synthesize the complete SoC, and route it. `LiveSelectionTools.measure` invokes this evaluator and charges the observation before returning its label. Failed attempts consume budget; final choices require a measured improvement and measured feasibility. The six source lowerings are explicit adapters, not a general compiler extension.

## Measurement contract and all outcomes

The pinned Embench CRC32 benchmark runs 170 repetitions of its complete body, including input generation and table accesses. Startup, the independent checksum call, warm-up, and serial reporting are outside the measured counter interval. This is not a kernel-only instruction-saving estimate. All designs use the same RV32I PicoRV32 configuration, synchronous 8 KiB RAM, `-march=rv32i_zicsr -mabi=ilp32 -O2`, and a common 12 MHz clock constraint. Multiply/divide extensions and compressed instructions are disabled; software helper cost remains in the program measurement.

Each custom instruction has two 32-bit register inputs, one 32-bit result, and a fixed registered PCPI response: two valid cycles, including one wait cycle. Constants belong to the fixed instruction implementation. Firmware performs the remaining masking, address setup, table load, and CRC operations. The evaluation measures that overhead instead of assuming each fused computation takes one processor cycle.

| Design | Benchmark cycles | Speedup at 12 MHz | Cycle reduction | Unit LUT4 | SoC LUT4 (added) | SoC FF | Routed internal Fmax range, MHz |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Baseline | 32,387,382 | 1.000000× | — | — | 1,653 | 655 | 68.49–77.16 |
| index_offset | 30,820,662 | **1.050833×** | **4.8374%** | 8 | 1,684 (+31) | 688 | 71.49–76.59 |
| index_byte | 31,865,142 | 1.016389× | 1.6125% | 8 | 1,689 (+36) | 688 | 65.66–68.13 |
| address_mask | 31,516,982 | 1.027617× | 2.6875% | 30 | 1,722 (+69) | 712 | 60.71–68.60 |
| address | 31,516,982 | 1.027617× | 2.6875% | 30 | 1,723 (+70) | 712 | 61.85–71.05 |
| mask_offset | 32,909,622 | 0.984131× | −1.6125% | 0 | 1,687 (+34) | 688 | 72.60–74.18 |
| shift_xor | 31,516,982 | 1.027617× | 2.6875% | 24 | 1,718 (+65) | 712 | 68.39–71.76 |

Speedup is baseline cycles divided by candidate cycles. Cycle reduction uses baseline cycles as its denominator. Every SoC uses 20 BRAM blocks, including 16 for program/data RAM. Integrated carry counts are 295 baseline, 326 for the two address candidates, and 297 for the others. The address datapaths use 29 isolated carry cells; the others use zero. HX8K has no DSP blocks in this flow. Unit LUTs exclude decode and PCPI registers; the integrated deltas include both and synthesis interactions. A zero-LUT wiring datapath can therefore still add overhead and slow the program.

All six pass the full checksum (`0x65842ca9`), upstream result (`11433`), self-check, independent integer vectors, and universal combinational equivalence. Each executes exactly **176,128** custom instructions across checksum validation, warm-up, and the benchmark; 174,080 correspond to the 170 benchmark repetitions. The directly observed totals include 352,256 valid and 176,128 wait cycles. Stock firmware on each extended core matches the baseline, and custom firmware traps on the unextended core. The source-wrapper control also matches baseline outputs, cycles, and retired instructions; its binary differs only in two commuted XOR operand encodings.

All three route seeds (1, 2, 3) meet 12 MHz and the fixed baseline-plus-128-LUT4 cap. Fmax is an internal routed estimate, not a board measurement or an externally timed I/O guarantee. At each design's own estimated Fmax, `index_byte` has paired speedups **0.865×, 1.004×, 0.984×**: fewer cycles do not guarantee less elapsed time at a different clock. Every per-seed estimate is retained in the [raw-evidence audit](../results/2026-10-19-codesign/independent-audit.json). No power or energy result is claimed.

## Selection and the actual learned target

The live selector uses the existing **20 bootstrap XGBoost regressors, 80 trees each, depth 2**, to predict the measured application elapsed-speedup ratio. With equal clocks this is the cycle-speedup ratio above. It uses 35 allowed numerical discovery/structure features. Area, timing results, candidate names, IDs, and unmeasured labels are not model inputs. The legacy `synthesis_estimate` source tag is retained for compatibility; the new corpus explicitly identifies these as RTL application-cycle labels at a routed common clock, not isolated synthesis proxies or board measurements.

Training starts with **zero historical speedup labels**. The first two queried target candidates are charged bootstrap examples. Subsequent predictions use only paid observations. The live run's third query used two real measured labels, then selected the best feasible of its three measurements (`address_mask`, 1.027617×). V6/V9 LUT predictions do not participate. Area is checked after measurement, so predicted-area false acceptance/rejection is not an applicable metric here.

The complete six-design pool supplies the retrospective exact oracle. Four policies use identical budgets 1–6 and seeds 0–4: **120 replay outcomes**, not 120 new physical measurement jobs. At the predeclared budget of three:

| Policy | Mean best measured speedup, five seeds | Exact-oracle hits | Mean regret, speedup units | Mean queries to exact oracle, budgets 1–6 | Charged candidate measurement seconds at budget 3 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Frequency | 1.032260× | 1/5 | 0.018573 | 3.8 | 134.80 |
| Merit | **1.050833×** | **5/5** | **0** | **1.6** | 132.34 |
| Random | 1.032260× | 1/5 | 0.018573 | 3.8 | 134.80 |
| Learned upper-quantile acquisition | 1.032260× | 1/5 | 0.018573 | 3.8 | 134.80 |

All candidates have the same retained frequency, so frequency reduces to the seeded random order. Learned acquisition follows the same query order as random in every tested seed/budget. In the live run the first prediction gives every remaining candidate the same upper quantile despite differing means; seeded tie order decides the third query. Later predictions can differ without changing the order. Ensemble disagreement is not calibrated confidence. These six related candidates cannot establish generalization across programs.

The separate future cross-workload routine in `speedup_corpus.py` resolves equal upper scores by predicted mean, then seeded order; its behavior has contract tests. **Neither this frozen CRC32 replay nor the automatic aha-mont64 replay uses that revised routine.** No measured benefit from the tie-break revision is claimed, and model parameters are unchanged.

## Research choices and reuse

| Connection | Source-backed choice | Reused implementation; effort and priority |
| --- | --- | --- |
| Legal workload candidates | [CIDRE](https://arxiv.org/html/2509.15782v2) motivates ISA-aware, operand-constrained graphs and processor-aware assessment. | Reuse `extractCandidates`, `followsRules`, and occurrence metadata. CRC32 features retain historical RV32IM proxies. The automatic aha path now profiles actual RV32I and reuses the same legality checks; harmonizing CRC features remains work. |
| Executable instructions | [PicoRV32 PCPI](https://github.com/YosysHQ/picorv32#pico-co-processor-interface-pcpi) provides the existing two-input/one-output integration boundary. | Reuse the pinned core and SoC. Added six source adapters and a fixed response wrapper. The automatic assembly lowerer now supplies register-lifetime and relocation checks for restricted candidates; an arbitrary formula alone is insufficient. |
| Program performance | [gem5 MinorCPU](https://www.gem5.org/documentation/general_docs/cpu_models/minor_cpu) is a configurable pipeline model; its custom operations require matching decoder and functional-unit modeling. [Spike](https://github.com/riscv-software-src/riscv-isa-sim) remains useful for functional profiling. | Use Verilator on the actual existing SoC for cycles and the same RTL for synthesis/routing. This avoids a second timing model now. Spike instruction counts are not cycle labels. PicoRV32 upstream is archived; the exact known revision is pinned for reproduction. |
| Speedup prediction and ranking | [Snoek et al.](https://arxiv.org/abs/1206.2944) and the [Brochu tutorial](https://arxiv.org/abs/1012.2599) support sequential allocation of expensive observations. They do not prove our XGBoost acquisition works. | Reuse `SpeedupPredictor`; collect measured labels and test decision quality before another learner. No new hyperparameter sweep. |
| Cost constraints | [CIDRE](https://arxiv.org/html/2509.15782v2) accounts for processor integration and clock effects. | Measure whole-SoC cost and feasibility first. The saved LUT models remain optional future screening tools whose feature cost and decision errors must be charged if used. |

## Working next-stage components and remaining blocker

`speedup_corpus.py` exports authenticated measurements with workload/source family, input configuration, processor/compiler identity, formula, implementation hash, firmware hash, and measurement context. It enforces whole-workload-family holdouts, removes shared operation-tree families from training, keeps zero-shot predictions separate from paid target adaptation, and freezes predictions before scoring. Its future evaluator reports Spearman, regret, fixed-budget policies, and acquisition costs using the existing XGBoost model. **Only its contracts have multi-workload unit fixtures; there is no measured multi-workload model result yet.** This CRC-only export has six rows. The newer combined export has twelve rows across two workloads, still below the group gate and with mixed discovery-ISA provenance.

The new generic Embench harness preserves the upstream `initialise_benchmark`, `warm_caches`, `benchmark`, and `verify_benchmark` functions. A bounded baseline-only pilot reuses the same ISA and processor:

| Program | Actual outcome |
| --- | --- |
| aha-mont64 | Passes upstream self-check; 62,311,489 cycles; 3,152-byte program/BSS footprint; zero custom instructions. |
| nettle-sha256 | Link fails the 4 KiB program/data reservation; also requires freestanding `exit` support. |
| matmult-int | Link fails the current RAM contract; `.bss` causes 2,708 bytes of overflow beyond 8 KiB, before the stack reservation. |

The automatic `aha-mont64` milestone is now complete: six extracted, lowered, measured designs and a matched policy replay are preserved in the [second-workload report](automatic-workloads.md). It reuses the extractor and PCPI evaluator, observes the actual RV32I processor profile, removes eligible member operations in assembly, and reassembles labels/branches. Next harmonize CRC32 discovery features in a fresh automatic context and collect a third independent workload under the same memory contract.

Before collecting the cross-workload cohort, freeze the same compiler/processor/latency/clock contract for all programs. Either retain the current memory budget or deliberately revise and revalidate it for every baseline. The automatic path profiles the actual PicoRV32; any later Spike adapter must match the ISA, including counter reads. Do not feed RV32IM executable code to the M-disabled core. The new disassembly gate rejects M/C/F/D/A instructions, unsupported CSRs, and unknown custom encodings, and actual execution supplies a second compatibility check.

The next milestone is accepted when at least three independently grouped programs have several legally extracted, executable candidates and complete measured reference pools; fixed XGBoost parameters train on other programs; held-out ranking and equal-budget selection are reported separately from adaptation; chosen instructions pass full-program checks and measured area/timing constraints; and all costs and negative outcomes are preserved. A heuristic win remains a valid outcome. No further isolated area-model study is on the critical path.

## Reproduce and preserve

The completed experiment used **127 native commands / 281.00 native seconds**, one native job at a time and two compilation workers. Routing took 140.51 s, synthesis 56.54 s, native builds 52.93 s, and processor simulation 27.11 s. Candidate evaluation took 39.41–48.17 s including checks. Baseline setup cost is separate. A failed initial byte-identical source-control check consumed another 30.41 native seconds; its inputs, raw output, failure, and exact runner source are retained. The historical trace-discovery cost is inherited and not reconstructed; it is common to all policies. These are measured job costs, not a controlled host-throughput improvement claim.

Install the project and versions recorded in the [checkpoint environment](../results/2026-10-19-codesign/environment.json). Portable evidence/model replay requires no native hardware tools:

```sh
python scripts/reproduce_codesign.py replay
```

Fresh collection uses existing pinned tools and a fresh output directory:

```sh
python -m isaforge.codesign prepare --output generated/new-codesign \
  --core-dir /path/to/pinned/picorv32 --toolchain-prefix /path/to/riscv-none-elf-
python -m isaforge.codesign pilot --root generated/new-codesign
python -m isaforge.codesign run --root generated/new-codesign
python -m isaforge.codesign_audit --root generated/new-codesign \
  --output generated/new-codesign/audit.json --replay
python -m isaforge.speedup_corpus export --root generated/new-codesign \
  --output generated/new-codesign/speedup-corpus.json
```

Completed designs are cached with context/source/tool/input hashes and authenticated raw evidence. The verified cache replay took 3.89 s, returned 13 cached results, and added zero native commands. An interrupted candidate receives a new native attempt; previous attempts and native charges remain. Logical policy budgets currently describe one uninterrupted acquisition invocation: recovery of a partially completed policy journal still needs implementation before interrupted runs can support the same fixed-query-budget claim. The reported live run completed without that interruption.

Native deadlines, command-count limits, free-space checks, and a single-owner lock bound collection. This is an internal trusted-tool workflow, not an OS sandbox for arbitrary external code. At this original checkpoint, the suite passed 2,527 tests and 179 subtests; the historical six-model replay and portable seven-design/120-outcome checkpoint replay passed. An earlier full-suite run had two historical process-cleanup test failures; their isolated rerun and the final suite passed, and both logs are retained. [Checkpoint, all budgets/seeds, and archives](../results/2026-10-19-codesign/README.md).

The later scope cleanup archives the unused RTL-search tests and adds automatic-lowering coverage. The [current validation receipt](../results/2026-10-19-research-contract-validation/README.md) records 2,506 tests plus 179 subtests and replay of both processor checkpoints.
