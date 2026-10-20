# Automatic aha-mont64 processor checkpoint

Six automatically extracted, lowered, executed, and measured custom instructions, one per design, plus the unmodified baseline. [Complete methods, results, commands, and limitations](../../docs/automatic-workloads.md).

Best: `add(srli(in0,31),slli(in1,1))`, 62,311,489 → 56,951,233 cycles (**8.6024% reduction; 1.094120×**) at 12 MHz, with 1,653 → 1,695 integrated LUT4 (+42). All six pass correctness and declared area/timing constraints. These are RTL simulation and FPGA synthesis/routing results, not board measurements.

Merit finds the optimum at budget one in all five seeds. At budget three, frequency/merit reach mean 1.094120×; random/learned acquisition reach 1.065586×. Learned acquisition loses to random at budget four. No learned superiority or held-out-workload claim is supported.

| Artifact | Contents |
| --- | --- |
| [plan.json](plan.json) | Frozen pool rule, workload, source/tools, ISA, hardware, seeds, limits |
| [report.json](report.json) | Baseline, six candidates, features/occurrences, cycles, correctness, resources, routes |
| [audit.json](audit.json) | Re-extraction/lowering, raw counter/control checks, netlist/route recount, exact Fmax and conditional ratios |
| [selection-report.json](selection-report.json) | All 120 policy/seed/budget outcomes, paid query orders, predictions, regret/time curves |
| [combined-corpus.json](combined-corpus.json) | Twelve rows/two groups, readiness and mixed-ISA provenance limitations |
| [raw.tar.gz](raw.tar.gz) | Sources, assembly, firmware, disassembly, profile, receipts/logs, verification/control records, netlists/routes; excludes rebuildable objects |
| [archive-manifest.json](archive-manifest.json) | SHA-256, sizes, complete membership |
| [source-manifest.json](source-manifest.json), `sources/` | Exact implementation/dependency snapshots |
| [environment.json](environment.json) | Python and numerical-library versions |

Collection: 119 native commands, 301.542 command-seconds, one worker and at most two build workers. Candidate evaluation wall times total 280.244 s; baseline evaluation is 28.052 s. Timers have different scopes. Replay adds no native measurements; historical speedup training labels supplied to policies are zero.

With the README's Python dependencies and initialized Embench submodule, from the repository root:

```sh
python scripts/reproduce_workload.py replay
```

Replay authenticates the archive, re-extracts/re-lowers candidates, recounts seven designs and all routes, and recomputes all policy outcomes. No native tools run. Source bindings must match. The full 21-formula executable list is retained, but only the predeclared top six were measured. No joint instruction sets were evaluated.
