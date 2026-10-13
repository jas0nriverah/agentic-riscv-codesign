# ISAForge: agentic RISC-V co-design

ISAForge studies whether learned performance prediction can choose useful RISC-V
custom instructions with fewer expensive measurements than frequency or merit
ranking. The repository contains Spike tracing and candidate extraction, plus a
Python dataset, prediction, and offline selection pipeline.

The [prospective research results](results/2026-10-13-prospective/README.md) now
cover all 19 Embench programs, 1,098 candidate rows, 713 distinct synthesized
formulas, frozen-model inference, and a complete CRC32 FPGA SoC experiment.
On the final 331 new formulas, a structural linear model achieves 23.15 LUT4
MAE versus 87.59 for the original XGBoost model and 33.17 for the residual model.
At the primary selection budget, models tie simple merit; superiority over
merit or published tools is not established.

The closed-memory PicoRV32 CRC32 system reduces cycles from 32,387,382 to
29,602,102 with two custom instructions and passes checksum, memory, and control
tests. Matched place-and-route runs include the on-chip memory and yield
1.022–1.140× estimated runtime ratios across three seeds. These are RTL/timing
model results, not physical-board measurements. **The ML models predict isolated
LUT4 resources, not CPU speedup.** The original `isaforge demo` remains synthetic.

## Matched research-method comparison

A [new frozen comparison](results/2026-10-13-v3/README.md) trains six predictors on
identical 713-formula data and tests all of them on 192 unseen synthesized
circuits. The **MasterRTL recipe adapted to LUT4 wins this probe: 35.07 LUT4 MAE**,
versus 41.59 for our previous residual model, 56.40 for the new structural
challenger, and 80.86 for the original architecture refitted on the same data.
The structural revision did not improve the primary endpoint. These are
synthetic compositions, not an additional executed workload. This adaptation
of the published method does not reproduce its ASIC benchmark or establish
superiority over the original system.

All 192 circuits pass 412,416 sampled/boundary RTL comparisons. Predictions and
model hashes were frozen before the test labels were opened. The
[matched reproduction guide](docs/reproduce-matched-comparison.md) covers all
six frozen inference commands, strict scoring, and the cached MasterRTL model.
MasterRTL needs label-free Yosys preprocessing for new formulas; its measured
192-formula cold inference takes 7.431 seconds, versus 0.205 seconds warm.

## Run the formula-only structural model

```sh
python -m isaforge.area_model_v2 predict \
  --model results/2026-10-13-prospective/deployment/resource-deployment.joblib \
  --candidates results/2026-10-13-prospective/final/dataset.json \
  --output generated/inference.json
```

This earlier deployment artifact refits all 713 available formulas after the
prospective-workload comparison;
it has no new independent evaluation. Reproduce the reported held-out scores
using the separate frozen models under `results/2026-10-13-prospective/models/`.
Read the [research manuscript](docs/research-manuscript.md),
[reproduction guide](docs/reproduce-research.md), [model methodology](docs/area-model-v2.md),
[processor experiment](hardware/README.md), and [SoC routing](docs/soc-routing.md).

## Reproduce the original measured pilot

```sh
python -m isaforge.area_model train \
  --rows results/2026-10-13/dataset.json \
  --output-dir generated/real/model --seed 20261013
python -m isaforge.area_model predict \
  --model generated/real/model/area-model.joblib \
  --candidates results/2026-10-13/dataset.json \
  --output generated/real/model/predictions.json
```

Prediction only needs formula text; synthesis labels are not model inputs.
See [the area model](docs/area-model.md), [actual benchmark setup](docs/toolchain.md),
[candidate correctness](docs/candidates.md), [RTL and synthesis](docs/synthesis.md),
and [budgeted selection results](docs/area-selection.md). Selection's target-budget
comparison assumes previously measured training circuits from other benchmarks;
it does not count those historical labels as free end-to-end research cost.

## Quick start

Use Python 3.11 or newer:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m pytest -q
isaforge demo --output generated/demo
```

The demo writes a synthetic dataset, leave-one-benchmark-out evaluation, and
budgeted policy comparison as JSON. It requires no RISC-V or FPGA tools.
XGBoost on macOS may require the OpenMP runtime (`brew install libomp`).

## Collect candidates

The existing tracing pipeline requires a RISC-V bare-metal toolchain and Spike
with commit logging enabled:

```sh
git submodule update --init --recursive
make all
make run
make trace
make candidates
```

The eight benchmark targets are `aha-mont64`, `crc32`, `edn`, `huffbench`,
`matmult-int`, `nettle-aes`, `nettle-sha256`, and `wikisort`. Results live under
`generated/`. The extractor supports `--max-size 4` for the proposal's
two-to-four-operation study, as used in the measured pilot. Its overlap-safe
instruction-saving estimates are not measured CPU cycles; combining different
candidates requires checking conflicts between their occurrences.

## Build a dataset and run an experiment

First construct unlabeled feature rows with stable candidate IDs:

```sh
isaforge dataset --benchmark crc32 \
  --candidates generated/candidates/crc32.json \
  --output generated/datasets/crc32-features.json
```

Supply measured cycle counts, effective clock periods, area, and provenance
using those IDs and the [data contract](docs/data-contract.md):

```sh
isaforge dataset --benchmark crc32 \
  --candidates generated/candidates/crc32.json \
  --measurements measurements/crc32.json \
  --output generated/datasets/crc32.json
```

Concatenate the JSON row arrays for all measured benchmarks into one dataset,
then run:

```sh
isaforge evaluate --dataset measurements/all-benchmarks.json \
  --seed 0 --output generated/evaluation.json
isaforge select --dataset measurements/all-benchmarks.json \
  --benchmark crc32 --budget 8 --area-cap 100 \
  --seed 0 --output generated/selection.json
```

The area cap uses the same unit as your area measurements; the example value is
not a recommended hardware budget. Keep processor configuration, input workload,
synthesis target, area units, and measurement procedure consistent within an
experiment. The source tag alone cannot establish that two configurations match.

The XGBoost bootstrap ensemble uses software-derived features only. Evaluation
holds out entire benchmarks and reports error, ranking agreement, and empirical
uncertainty coverage. Ensemble spread is not a calibrated confidence guarantee.
See [model and evaluation](docs/model.md).

Selection compares frequency, merit, random, and active learning with a common
measurement budget and a fully informed oracle. The command trains on labeled
rows from other benchmarks; those historical measurements are separate from the
target's budget. The tool interface hides target labels until measurement and
enforces the budget. It selects at most **one** verified candidate, with retaining
the unmodified processor as an option. See [selection](docs/selection.md).

## Remaining research milestones

1. Extend the measured LUT4 dataset to integrated timing and cycles, then run
   the premise check: does merit disagree with timing-aware speedup? Preserve
   simulator/build configuration and measurement artifacts alongside labels.
2. Connect real gem5 and/or synthesis measurement adapters. Keep simulator
   measurements separate from synthesis-based performance estimates.
3. Improve resource predictions on expensive multipliers, calibrate uncertainty,
   and extend the completed held-out/budgeted evaluations to measured runtime.
4. Connect an LLM selector to the budgeted tools and compare it with active
   learning under the same initial data and measurement budget.
5. Add occurrence/overlap metadata and jointly measured instruction sets before
   optimizing a two- or three-instruction set under an area constraint.
6. Implement the winners in RTL, verify semantics with Verilator, synthesize the
   integrated processor, and add a verification-gated RTL optimization loop.

The original proposal prioritizes timing-aware synthesis estimates; the newer
project description adds gem5 and RTL optimization. Both label sources are
represented, but this repository does not yet automate either measurement flow.
