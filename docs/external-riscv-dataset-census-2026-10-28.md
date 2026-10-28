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
model fitted, program built or candidate evaluated for this census.

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
| PULPino sequential tests: [Sudoku solver](https://github.com/pulp-platform/pulpino/blob/master/sw/apps/sequential_tests/sudokusolver/sudokusolver.c), [expected solution](https://github.com/pulp-platform/pulpino/blob/master/sw/apps/sequential_tests/sudokusolver/sudokusolver.h), [Hanoi](https://github.com/pulp-platform/pulpino/blob/master/sw/apps/sequential_tests/towerofhanoi/towerofhanoi.c) | Inspected headers specify Solderpad Hardware License 0.51. Sudoku supplies a fixed 9×9 puzzle, two solver iterations and comparison against all 81 expected cells. Hanoi uses twelve plates and checks the destination array. | Integer kernels are plausible, but PULP harness headers, callbacks and core/timer calls need a declared adapter. Sudoku's recursion can reach roughly 81 cells, creating substantial stack risk under the unchanged 1,664-byte limit. No target compatibility is established. |
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

## Safest next screens

1. **Queens first.** Preserve all original iterations and upstream failure
   reporting; compare the [reference output](https://github.com/llvm/llvm-test-suite/blob/main/SingleSource/Benchmarks/Stanford/Queens.reference_output).
   Its four active local arrays total 200 bytes on ILP32, but this excludes
   recursion and call frames. First review the oracle and lineage, then inspect
   the exact RV32I build's retained sections and stack bound. A small footprint
   is not evidence of twelve candidates or useful opportunity.
2. **Sudoku second, with stack as the first stop/go gate.** The two mutable
   grids plus expected grid total about 972 bytes on ILP32, excluding other
   state. Preserve the original puzzle, expected solution and both iterations.
   Review recursive frames before any native qualification: a stack failure
   must stop the lead, not motivate fewer cells or a larger partition.

For either lead, pin source/license/input/oracle hashes and a separate adapter
contract before baseline-only qualification. Require the unchanged RV32I/ILP32,
compiler, 8-KiB RAM partition, stack verifier, relocation-safe extraction,
twelve-candidate pool and joint opportunity gates. Audit exact formula families
and source lineage against every historical context. Only an accepted workload
followed by a separate reviewed, committed and pushed zero-label policy release
can proceed to candidate measurements. Qualification itself adds no training
label or model-quality evidence.
