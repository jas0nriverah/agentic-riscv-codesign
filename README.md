# ISAForge

Predict FPGA area for RISC-V custom instructions, then check the hardware tradeoff before adding them to a CPU.

![ISAForge pipeline: predict LUT4 area from circuit features, measure original RTL with Yosys, and compare error and hardware-budget fit.](docs/assets/area-pipeline.svg)

## Quick start

```sh
git clone https://github.com/jas0nriverah/agentic-riscv-codesign.git
cd agentic-riscv-codesign
./start.sh
```

Sets up Python → verifies artifacts → runs 32 real predictions. Requires Python 3.11+ and network for the first install; later runs work offline without FPGA tools.

| Command | Action |
| --- | --- |
| `./start.sh` | Verify and run the inference demo; save outputs under `generated/start/` |
| `./start.sh --check` | Check the environment and saved evidence without installing or writing |
| `./start.sh --test` | Run the full test suite, then the demo; on macOS, uses Homebrew to install `libomp` if XGBoost needs it |

## Example

Estimate the area of `(in0 XOR in1) × 31`:

```text
Formula                              Predicted LUT4   Measured LUT4
mul(xor(in0,in1),addi(0,31))                  235.02             202
```

The prediction comes from the saved model; the measured value is a retained Yosys result. Predictions are estimates, not guarantees that a circuit fits a hardware budget.

## ML model

![217 circuit features feed a 300-tree ExtraTrees ensemble; averaged outputs estimate LUT4 area.](docs/assets/ml-model.svg)

## Improvements

![Separate studies show representation gains, an application-transfer regression, and arithmetic gains with worse underprediction.](docs/assets/model-improvement.svg)

Representation compares dual-graph with base; coverage studies compare base with added training data. These are separate benchmarks, not one learning curve.

## Results

Same **192 synthetic test circuits**, same **1,665 training circuits**, same measured FPGA target:

| Predictor | MAE ↓, LUT4 | MAPE ↓ |
| --- | ---: | ---: |
| **ISAForge base** | **32.16** | **43.63%** |
| Dual-graph control | 34.33 | 49.37% |
| Tuned operator-graph model | 46.34 | 75.63% |
| MasterRTL recipe adaptation | 61.47 | 85.67% |

MAPE compares each prediction with **measured LUT4 count**; it excludes six zero-area circuits, which remain in MAE. The MasterRTL row is our FPGA adaptation, not the paper's ASIC result. [Benchmark definitions](docs/benchmarks.md).

**Research status:** base remains the default; newer budget classifiers are not promoted. CPU measurements are a separate, provisional hardware track. [Results and limitations](results/README.md).

## Documentation

| I want to… | Guide |
| --- | --- |
| Understand the model | [Model pipeline](docs/model.md) |
| Run inference or troubleshoot setup | [Operations](docs/reproduce.md) |
| Understand MAPE and compare results | [Benchmarks](docs/benchmarks.md) · [Results](results/README.md) |
| Build and measure a custom instruction | [Hardware track](hw/README.md) |
| Contribute or reproduce an experiment | [Development](CONTRIBUTING.md) · [Research records](results/README.md#experiment-records) |
| Reuse code or cite the project | [Attribution and licensing](docs/reuse.md) |
