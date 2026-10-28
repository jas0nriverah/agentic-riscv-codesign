# External RISC-V data and source census — October 28, 2026

No external release inspected is ready to pool with ISAForge's candidate-level
PicoRV32 training labels. Published outcomes below describe different cores,
interfaces, design choices or physical flows. Source suites can instead supply
programs for new measurements through our existing qualification pipeline.
**No new eligible workload was established by this read-only search.**

This supplements the [existing dataset census](training-dataset-census-2026-10-28.md).
Links were inspected on October 28; upstream branch URLs are mutable. Pin exact
commits, inputs and applicable license notices before any future intake.
“Observed” below means inspected public source or release contents, not an
independent reproduction of the authors' measurements. No data was imported,
model fitted, program built or candidate evaluated for this census. **Later
project work on October 28 qualified and measured the PULPino Sudoku source
listed below; that work is documented separately and does not change the
external-dataset compatibility decision.**

## External outcome releases: keep separate

| Release | Observed contents and reuse caveat | ISAForge boundary |
| --- | --- | --- |
| [embedded_mlkem_bench](https://github.com/ishanrk/embedded_mlkem_bench), [machine-readable results](https://github.com/ishanrk/embedded_mlkem_bench/blob/main/results/summary.json) | The author reports complete ML-KEM cycle counts from PicoRV32 RTL simulation and ECP5 synthesis/routing results. Three named instructions include two implementations of FSRI. No clear root reuse license was found. | Closest external comparison, but RV32M/multiplier sharing, PCPI latencies, ECP5 resources, software changes and crypto lineage differ. Do not copy or train on these labels without resolving reuse terms and a separately justified target mapping. |
| [ASPO configurable-processor platform](https://github.com/GeorgeWu1204/Configurable-Processor-Design-Platform-and-Dataset), [BOOM database](https://github.com/GeorgeWu1204/Configurable-Processor-Design-Platform-and-Dataset/blob/main/dataset/PPA/BOOM_PPA.db), [RocketChip database](https://github.com/GeorgeWu1204/Configurable-Processor-Design-Platform-and-Dataset/blob/main/dataset/PPA/RocketChip_PPA.db) | Read-only SQLite inspection in memory found 21 stored BOOM configuration rows and zero rows in the named RocketChip database. Columns include LUT/FF/BRAM/DSP, power/timing and per-workload cycles/instructions. No clear root reuse license was found. Raw measurement provenance was not independently validated. | Processor-configuration labels, not custom-instruction formulas or candidate speedups. Different cores and FPGA flow. Useful provenance/schema reference; keep outside the training table. |
| [BOOM-Explorer public release](https://github.com/baichen318/boom-explorer-public), [configuration](https://github.com/baichen318/boom-explorer-public/blob/master/configs/boom-explorer.yml), [license](https://github.com/baichen318/boom-explorer-public/blob/master/LICENSE) | GPL-3.0 repository. Public configuration selects `dataset/demo.csv`, identifies it as a demonstration, and says online mode is not public. | Do not describe the public demo as a complete released measured dataset. BOOM microarchitecture exploration also differs from PicoRV32 candidate selection. |
| [ICCAD22 contest platform](https://github.com/iccad-contest/iccad-contest-platform), [dataset notice](https://github.com/iccad-contest/iccad-contest-platform/blob/master/iccad_contest/contest-dataset/README.md), [license](https://github.com/iccad-contest/iccad-contest-platform/blob/master/LICENSE) | Apache-2.0 platform. The dataset notice explicitly identifies `contest.csv` as dummy data. | Do not use that table as measured outcomes or evidence of additional training labels. |

The broader census already covers CIDRE, PARISCV, ARVIS, MasterRTL/HLS and
physical-design datasets. Their reported results do not supply interchangeable
whole-program PicoRV32 speedup, integrated iCE40 area and routed-timing labels.

## Source-only pools

| Pool and candidates | Direct source facts | Compatibility assessment — inference unless stated |
| --- | --- | --- |
| [LLVM test-suite](https://llvm.org/docs/TestSuiteGuide.html): Stanford [Queens](https://github.com/llvm/llvm-test-suite/blob/main/SingleSource/Benchmarks/Stanford/Queens.c) and [Towers](https://github.com/llvm/llvm-test-suite/blob/main/SingleSource/Benchmarks/Stanford/Towers.c) | C sources and reference outputs are public. Queens uses integer backtracking with direct recursion; Towers uses integer recursion and an array-backed freelist. Neither executed solver calls `malloc`. The [root license](https://github.com/llvm/llvm-test-suite/blob/main/LICENSE.TXT) is Apache-2.0 with LLVM exceptions and separately identifies third-party terms; retain the applicable notices at the pinned revision. | Plausible RV32I source screens. Unused suite-wide globals require linker garbage collection. Recursive stack, code/data fit, CFG support, twelve legal candidates and opportunity remain untested. These classic kernels are not automatically independent application families. |
| PULPino sequential tests: [Sudoku solver](https://github.com/pulp-platform/pulpino/blob/master/sw/apps/sequential_tests/sudokusolver/sudokusolver.c), [expected solution](https://github.com/pulp-platform/pulpino/blob/master/sw/apps/sequential_tests/sudokusolver/sudokusolver.h), [Hanoi](https://github.com/pulp-platform/pulpino/blob/6631c49ba38a9258da44d6b120d902f7b81f9233/sw/apps/sequential_tests/towerofhanoi/towerofhanoi.c) | Inspected headers specify Solderpad Hardware License 0.51. Sudoku supplies a fixed 9×9 puzzle, two solver iterations and comparison against all 81 expected cells. Hanoi uses twelve plates and checks the destination array. | **Sudoku was subsequently qualified** with a pinned adapter, preserved solver, fixed 9×9 input and all-81-cell output check. Its preregistered memory split is 2,304-byte program / 5,760-byte stack within the same 8 KiB RAM, deliberately different from the earlier 6,400/1,664 split. The 12-candidate campaign produced all-correct outcomes and a +64-LUT4 oracle speedup of 1.017634×. See the [measured report](../reports/2026-10-28-pulpino-sudoku-selector-r4/README.md). **Hanoi was later rejected** with the unchanged 12-candidate pool: its baseline self-check passed, but only three formulas were executable and all three were symbolic global-array address sequences rejected by the relocation guard. It produced no candidate labels; see the [qualification and diagnosis](../results/2026-10-28-pulpino-hanoi-qualification-r1/README.md). Neither fixed-input program establishes a generalized input distribution. |
| [rv8-bench](https://github.com/larkmjc/rv8-bench) | Integer-oriented programs include qsort, AES, NORX, Dhrystone, primes, miniz and SHA-512. README documents RISC-V 32/64 builds with a musl toolchain and rv8/QEMU execution. No clear repository-wide reuse license was found. | Hosted runtime and memory assumptions need review. Many algorithms overlap consumed sorting/crypto/compression families. Emulator benchmark results are not custom-instruction hardware labels. Lower priority. |

Some attractive names already fail a source-level size/interface screen:

- LLVM [Puzzle](https://github.com/llvm/llvm-test-suite/blob/main/SingleSource/Benchmarks/Stanford/Puzzle.c)
  actively uses `p[13][512]`: 26,624 bytes for that array alone with 32-bit
  integers, exceeding our 6,400-byte code/data partition.
- VersaBench [8b10b's official small configuration](https://github.com/llvm/llvm-test-suite/blob/main/MultiSource/Benchmarks/VersaBench/8b10b/CMakeLists.txt)
  selects 2,000 words. Its [harness](https://github.com/llvm/llvm-test-suite/blob/main/MultiSource/Benchmarks/VersaBench/8b10b/testbench.c)
  allocates two arrays totaling 16,000 bytes on ILP32 and uses file I/O. Its
  per-file notice is permissive, but that does not resolve the memory mismatch.
- PULP [bitDescriptor](https://github.com/pulp-platform/pulpino/blob/master/sw/apps/sequential_tests/bitDescriptor/bitDescriptor.c)
  invokes a function-pointer action inside its processing loop; this conflicts
  with our current unresolved-indirect-call CFG restriction unless the unchanged
  compiler resolves it. Its source also uses a PULP-specific memory section.

These are source observations, not target-tested qualification rejections.
Do not shrink inputs or relax gates to rescue them.

## Source-screen decisions and follow-up

1. **Queens was screened and rejected** under the unchanged pool/opportunity
   requirements: three calibrated executable formulas and at most 600
   analytically saved cycles (0.000129%), below the preregistered opportunity
   threshold. The original 5,000-solve self-check passed; no candidate was
   measured. Preserve the [discovery diagnosis](../reports/2026-10-28-llvm-stanford-queens-discovery-diagnosis-r1/README.md)
   and do not retry by weakening the gate.
2. **Sudoku is now completed as a fixed-input pilot.** The r4 report records
   baseline qualification, full-pool measured outcomes, selected-family
   exclusion, and matched-budget policy replay. Do not present its 12 candidate
   rows as 12 independent workloads or rerun this consumed target as
   prospective evidence.

For any new source, pin source/license/input/oracle hashes and a separate
adapter contract before baseline-only qualification. Require the declared
RV32I/ILP32 compiler and PCPI interface, an explicit 8-KiB RAM partition and
stack verifier, relocation-safe extraction, the frozen candidate-pool and joint
opportunity gates, and a formula-family/source-lineage audit. Only an accepted
workload followed by a separate reviewed, committed and pushed zero-label
policy release can proceed to candidate measurements. Qualification alone
adds no candidate label or model-quality evidence.
