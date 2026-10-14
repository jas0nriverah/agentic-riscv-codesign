# ISAForge

**Measured RISC-V custom-instruction research: candidate discovery, learned hardware cost, and processor validation.**

ISAForge explores whether machine learning can help choose useful RISC-V instruction extensions with fewer expensive hardware measurements. It extracts small computations from real programs, verifies their RTL, learns their FPGA resource cost, and evaluates the resulting estimates under controlled data splits. A separate PicoRV32 experiment checks what two CRC32 extensions actually do to processor cycles and FPGA resources.

The current learned target is **isolated iCE40 LUT4 count**. Processor speedup is evaluated separately through RTL simulation and routing. This is a research prototype with reproducible measured evidence; an LLM-driven selector remains future work.

[Methodology](docs/methodology.md) · [Latest V4 results and replay](docs/v4-results.md) · [All results](docs/results.md) · [Documentation](docs/README.md) · [Evidence index](results/README.md)

## System architecture

![ISAForge architecture: candidate discovery and measurement, frozen model comparison, and a separate RISC-V processor validation experiment.](docs/assets/architecture.png)

The diagram is an editable vector asset; regenerate it with `make diagram`. [Editable SVG](docs/assets/architecture.svg).

## Research methodology

1. **Collect real workloads.** Compile pinned Embench programs for RISC-V, verify their self-checks, and trace execution with Spike. Extract bounded computation graphs with at most two inputs and one output.
2. **Measure verified circuits.** Generate RV32 RTL, compare Verilator outputs against an integer oracle, and synthesize with Yosys. Preserve formulas, labels, tool versions, logs, and hashes.
3. **Train comparable predictors.** Deduplicate formulas and exclude held-out formulas from training. Compare formula-derived features with a MasterRTL-inspired pre-ABC graph pipeline on identical LUT4 labels.
4. **Freeze before testing.** Fix models and predictions before releasing fresh probe labels. Report all declared circuit groups, true-zero errors, large failures, inference costs, and paired uncertainty estimates.
5. **Validate processor effects separately.** Integrate two extracted CRC32 formulas through PicoRV32 PCPI; check full-workload execution, whole-SoC resources, and paired FPGA routing.

The [methodology](docs/methodology.md) defines the data splits, feature boundary, primary endpoint, and limits of each measurement. Protocols and negative findings are retained alongside successful runs.

## Results at a glance

### Latest: semantics-aware V4 on a new 256-circuit holdout

V4 combines RV32 algebraic normalization, sparse multiplier features, and pre-ABC graph topology with a 300-tree ExtraTrees regressor selected using development-only grouped validation. It trains on **1,289 circuits**: the earlier 713 workload circuits, the now-development 192-circuit probe, and 384 newly verified/synthesized development circuits. Models and all predictions were committed before measuring the new **256-circuit test**.

| Predictor | Training circuits | MAE, LUT4 | RMSLE | Positive MAPE | Median percentage error |
| :--- | ---: | ---: | ---: | ---: | ---: |
| **V4** | 1,289 | **14.89** | 0.572 | 77.93% | **1.36%** |
| MasterRTL adaptation, same-data retrain | 1,289 | 15.32 | **0.460** | **76.02%** | 5.55% |
| MasterRTL adaptation, frozen earlier fit | 713 | 22.15 | 0.536 | 104.10% | 11.51% |
| Residual XGBoost v2, frozen | 713 | 60.68 | 0.901 | 610.95% | 24.82% |
| Structural v3, frozen | 713 | 66.75 | 0.902 | 672.91% | 21.62% |

V4 reduces MAE **75.46% versus the previous residual model** on this same test. The additional training data contributes to that improvement. Against the same-data MasterRTL retrain, the MAE difference is only −0.43 LUT4, with a descriptive paired 95% interval **[−5.52, 5.59]**: broad superiority is not established. V4 improves seven of eight stratum MAEs and makes 11 rather than 19 feasibility mistakes at a 64-LUT cap, but loses on multiplication, RMSLE, and zero-target error. One zero-LUT circuit is predicted at 556.21 LUTs; all failures remain in the scores. MAPE uses 235 positive targets; all 21 zero targets remain in MAE/RMSLE.

![V4 and its frozen and same-data comparators on the new 256-circuit test.](docs/figures/v4-comparison.png)

The [V4 results and reproduction guide](docs/v4-results.md) includes the fixed protocol, semantic checks, independent audit, inference commands, and remaining failures. These are synthetic isolated-circuit results, not a new CPU-speedup or instruction-selection result.

### Historical six-model comparison: 192 circuits

All six models below train on **713 unique formulas** and predict the same **192 unseen synthetic circuits**, balanced across eight predeclared groups. Every circuit is synthesized and passes sampled/boundary RTL checks: **412,416 comparisons** in total. Lower error is better.

| Frozen predictor | MAE, LUT4 | RMSLE | Positive-label MAPE |
| :--- | ---: | ---: | ---: |
| **MasterRTL SOG adaptation** | **35.07** | **0.494** | **36.50%** |
| Residual XGBoost v2 | 41.59 | 0.808 | 320.14% |
| Structural v3 | 56.40 | 0.839 | 478.13% |
| Resource regression v2 | 60.72 | 0.930 | 514.20% |
| Original-feature v3 | 60.72 | 0.930 | 514.20% |
| Initial XGBoost architecture, retrained | 80.86 | 1.239 | 165.81% |

MAPE uses all 181 positive targets; the 11 zero targets remain in MAE and RMSLE. The large percentage errors reflect real missed simplifications on tiny circuits and are retained. Original-feature v3 selected the resource-regression configuration, so those predictions coincide.

![Matched development and fresh-probe error for all six predictors.](docs/figures/model-comparison.png)

**The MasterRTL adaptation has the lowest observed probe MAE; our structural revision did not win.** Its paired MAE advantage over residual v2 is 6.52 LUT4, with a descriptive 95% interval of −4.89 to 18.04, which includes zero. Against structural v3, the advantage is 21.33 LUT4, interval 2.88 to 40.58. These intervals condition on the eight curated circuit groups.

MasterRTL processes all 192 formulas in **7.431 s with a fresh graph cache** and **0.205 s median with cached graphs**; structural v3 takes **0.047 s warm**. The graph method has an additional preprocessing cost. This is a matched adaptation of a published recipe to our FPGA target, not replication of its ASIC benchmark.

### Processor and earlier workload experiments

| Experiment | Recorded result | Interpretation |
| :--- | :--- | :--- |
| Embench collection | 19 programs pass self-checks; 1,098 program/formula rows, 713 unique formulas | Two programs have no eligible candidates; 17 supply model data |
| Earlier prospective workload test | Resource model MAE 23.15 vs initial model 87.59 LUT4 on 331 novel formulas | Separate experiment using models frozen on 301 training formulas |
| Budgeted instruction selection | V1 and residual v2 lose to merit on first transfer; resource v2 ties. All point models tie merit on the final primary endpoint | No established selection advantage |
| Full CRC32 SoC | 32,387,382 → 29,602,102 simulated cycles (**−8.60%**) | Two custom instructions, complete workload and correctness checks |
| Whole-SoC mapping | 1,633 → 1,704 LUT4 (**+4.35%**); 20 BRAMs in both | Includes on-chip memory and integration overhead |
| Matched routing | Six runs pass 12 MHz; paired cycle/Fmax ratios **1.022×–1.140×** | Timing-model estimates across three seeds; no physical-board measurement |

See [results and interpretation](docs/results.md) for sources, per-group behavior, uncertainty, and remaining research questions.

## Reproduce the comparison

Python 3.11+ is required. Replay uses committed predictions and needs no RISC-V or FPGA tools. Install the [recorded numerical-library versions](docs/reproduce-matched-comparison.md#runtime-requirements-and-cache) for exact artifact compatibility.

```sh
git clone https://github.com/jas0nriverah/agentic-riscv-codesign.git
cd agentic-riscv-codesign
git checkout codex/isaforge-ml-foundation
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev,reports]'
make reproduce
make reproduce-v4
```

This validates both model freezes, reproduces all six scores within floating-point roundoff, reruns the independent audit, and exports nine figures to `generated/reproduction/figures/` as vector PDF/SVG and 300 dpi PNG. It neither retrains models nor synthesizes new circuits.

```sh
make test                         # Python suite; hardware checks run when tools exist
make help                         # Research and hardware entry points
python scripts/reproduce_matched.py --skip-figures  # Scores + audit only
```

On macOS, XGBoost may require `brew install libomp`. Hardware regeneration additionally requires the pinned GCC, Spike, Yosys, Verilator, and nextpnr tools described in the [toolchain](docs/toolchain.md) and [full research reproduction guide](docs/reproduce-research.md).

### Run actual frozen-model inference

This example predicts from formula inputs with the previous residual model; it does not need Yosys:

```sh
python -m isaforge.frozen_inference \
  --kind v2 \
  --model results/2026-10-13-v3/models/area-model-v2-full.joblib \
  --candidates results/2026-10-13-v3/probe/candidates.json \
  --output generated/inference/residual-v2.json
```

For the latest model, use the [V4 inference command](docs/v4-results.md#run-frozen-v4-inference). V4 and MasterRTL require retained graph caches or their compatible frozen Yosys tool; the older formula-only models remain available when that dependency is unsuitable. The [six-model inference guide](docs/reproduce-matched-comparison.md#run-all-six-frozen-predictors-then-score) covers earlier artifacts. Large raw logs, netlists, and graph caches are outside Git; committed predictions suffice for score and figure replay.

## Repository map

| Path | Purpose |
| :--- | :--- |
| [`isaforge/`](isaforge/) | Prediction, evaluation, synthesis, verification, and processor experiment modules |
| [`src/`](src/) | Benchmark collection, instruction tracing, candidate extraction, and bare-metal startup |
| [`hardware/`](hardware/) | PicoRV32 integration RTL, firmware, simulation harnesses, and hardware methodology |
| [`benchmarks/`](benchmarks/) | Pinned Embench submodule and platform hooks |
| [`results/`](results/README.md) | Immutable experiment snapshots: data, models, predictions, protocols, and provenance |
| [`docs/`](docs/README.md) | Methodology, results, reproduction guides, protocol records, diagrams, and figures |
| [`scripts/`](scripts/README.md) | Short entry points for result replay and architecture-diagram generation |
| [`tests/`](tests/) | Unit, evidence-contract, artifact-integrity, and installed-tool checks |
| `generated/` | Ignored local outputs: traces, builds, caches, replays, and new experiments |

Frozen model modules and experiment paths remain stable because saved artifacts validate their source hashes. New research revisions should use new modules and snapshots. See [contribution and evidence conventions](CONTRIBUTING.md).

## Scope and next steps

The next research targets are the remaining multiplier/zero-cost failures, another untouched real-workload evaluation, calibrated selection under a total measurement budget, and jointly measured multi-instruction sets. V4 improves isolated prediction substantially over the previous custom models but does not establish useful acquisition gains over merit. LLM-guided selection and power/energy prediction remain unimplemented. Current evidence does not establish published-system superiority or a general CPU speedup model.

The [related-work comparison](docs/research-model-comparison.md) and [MasterRTL adaptation protocol](docs/masterrtl-matched-protocol.md) identify the primary research sources and the differences from their settings. The code and measurements are a research checkpoint, not a peer-reviewed result. Third-party components retain their upstream licenses; see [reuse and attribution](docs/reuse.md).
