# ISAForge: agentic RISC-V co-design

ISAForge studies whether learned performance prediction can choose useful RISC-V
custom instructions with fewer expensive measurements than frequency or merit
ranking. The repository contains Spike tracing and candidate extraction, plus a
Python dataset, prediction, and offline selection pipeline.

The ML pipeline is runnable now. **No measured benchmark dataset or demonstrated
hardware speedup is included.** The demo is synthetic and only verifies that the
software works together.

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
`generated/`. The current extractor enumerates up to five connected operations;
the proposal's two-to-four-operation study needs an explicit size filter or a
later extractor change. Its occurrence-based savings are a heuristic, not a
measurement of cycles or overlap-safe combined savings.

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

1. Collect real candidate measurements and run the premise check: does merit
   disagree with timing-aware speedup? Preserve simulator/build configuration
   and measurement artifacts alongside labels.
2. Connect real gem5 and/or synthesis measurement adapters. Keep simulator
   measurements separate from synthesis-based performance estimates.
3. Evaluate generalization and uncertainty on the measured data. Compare
   repeated random seeds and learning curves at several measurement budgets.
4. Connect an LLM selector to the budgeted tools and compare it with active
   learning under the same initial data and measurement budget.
5. Add occurrence/overlap metadata and jointly measured instruction sets before
   optimizing a two- or three-instruction set under an area constraint.
6. Implement the winners in RTL, verify semantics with Verilator, synthesize the
   integrated processor, and add a verification-gated RTL optimization loop.

The original proposal prioritizes timing-aware synthesis estimates; the newer
project description adds gem5 and RTL optimization. Both label sources are
represented, but this repository does not yet automate either measurement flow.
