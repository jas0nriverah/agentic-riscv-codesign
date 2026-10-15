# Hardware tradeoff ledger

ISAForge separates prediction quality, isolated circuit resources and integrated processor behavior. A lower prediction error is useful only if it improves a hardware decision; a smaller circuit is useful only under the required timing, correctness and integration constraints.

| Decision or measurement | Current evidence | What it establishes |
| --- | --- | --- |
| Whole CRC32 workload cycles | 32,387,382 → 29,602,102 (8.60% lower) with two custom instructions | RTL-simulated workload behavior including the implemented PCPI integration |
| Whole-SoC area | 1,633 → 1,704 LUT4 (4.35% higher); 20 BRAMs in both | Area cost of that integrated processor configuration |
| Routed processor timing | Six runs (three baseline/extended pairs) pass 12 MHz; cycle/Fmax ratios 1.022×–1.140× | Conditional timing-model runtime estimates, not physical-board speedups |
| V9 prediction quality | Consumed-application family-macro MAE 3.4092 → 2.5434 LUT4 | A development improvement in predicting original-RTL isolated area |
| V9 application budget decisions | At cap64, 0 false accepts and 3 false rejects for both models; one repaired rejection and one new rejection | Average error reduction does not automatically reduce decision errors |
| V9 historical regression budget decisions | Cap64 stays 6 false accepts / 5 false rejects; cap128 changes 1/4 → 1/6 | Some feasibility tradeoffs worsen despite lower MAE |
| Learned instruction selection | V8's best learned policies tie merit-only selection on the primary endpoint | No demonstrated learned-selection advantage |
| Constant-multiply implementation | Fixed 32-pair CSD experiment in preparation; first whole-expression source proof attempt timed out and remains preserved | No new rewrite area, timing or CPU gain established yet |

Sources: [processor and routing results](results.md), [SoC routing assumptions](soc-routing.md), [V9 complete metrics](v9-coverage-results.md), [V8 selection study](v8-application-results.md), and [CSD protocol](v10-csd-hardware-protocol.md).

## Each implementation comparison must retain

- **Correctness:** exact source semantics, emitted-RTL equivalence and separately identified sampled or universal mapped verification.
- **Resources:** LUT4 and carry counts for every original/modified pair; FF and BRAM counts when a wrapper or processor is included. Carry cells are reported separately rather than silently treated as free LUT equivalents.
- **Timing and latency:** critical-path/Fmax evidence under matched device, constraints and routing seeds; instruction latency and interface overhead for processor integration. Shift/add rewrites can increase dependency depth, so area alone cannot establish a speed benefit.
- **Workload effect:** execution frequency, saved instructions and actual full-workload cycle changes. Extracted instruction-count merit is a proxy until the processor runs the implementation.
- **Measurement cost:** new target labels, synthesis and inference work, and any fitting or acquisition budget. Existing cached feature inference has a different cost from preprocessing a new formula.
- **Failures:** proof timeouts, unsuccessful measurements, infeasible budgets, tails and worst underpredictions. Missing measurements remain unavailable rather than zero.

The new CSD stage measures isolated original/CSD LUT4 and carry counts on the same fixed inputs. It does not yet measure delay, frequency, energy, power or processor effects. Any follow-on timing study must freeze the wrapper/interface, device, constraints and paired routing seeds before looking at its results, retain every declared pair and explain failures. A common registered wrapper can characterize datapath timing, but it is still not a CPU benchmark.

V6's earlier calibrated upper bounds do not automatically transfer to the newly fitted V9 model. V9 currently reports point-estimate feasibility errors; new uncertainty or safe-selection claims require a separate calibration design and held-out validation. Power and energy remain unmeasured. FPGA LUT4 counts are also not an ASIC area measurement.
