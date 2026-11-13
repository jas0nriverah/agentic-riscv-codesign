# Operations

## Start locally

```sh
./start.sh
```

**Check Python → prepare `.venv` → verify weights and datasets → run inference → save results.** This is a CLI research pipeline; there is no background service to start or stop.

| Requirement | Purpose |
| --- | --- |
| Python 3.11+ with `venv` and pip | Local runtime; use 3.13 for the recorded replay setup |
| Network on first install | Download the versions in `requirements-research.txt` |
| Writable checkout | Local environment and `generated/` outputs |
| Yosys, Verilator, RISC-V tools, Spike, nextpnr | Optional hardware measurement; not used by the cached demo |

| Command | Behavior |
| --- | --- |
| `./start.sh --check` | Read-only dependency, model and benchmark checks |
| `./start.sh --test` | Full tests followed by the inference demo |
| `PYTHON=python3.13 ./start.sh` | Choose Python when creating the environment |
| `ISAFORGE_VENV=/absolute/path/to/venv ./start.sh` | Use an isolated environment at another path |
| `.venv/bin/python scripts/reproduce.py --check` | Recompute the three curated benchmark summaries |

Each demo run creates a new `generated/start/run-*/` directory containing `predictions.json` and `summary.json`. Repeated runs preserve previous outputs. No fits, synthesis jobs or external services run. Ctrl-C stops foreground execution; completed outputs remain on disk.

## Predict a candidate set

```sh
.venv/bin/python scripts/predict.py --model base \
  --candidates results/arithmetic-stress/candidates.json \
  --features results/arithmetic-stress/features.json \
  --output generated/my-predictions.json
```

| Input / output | Contract |
| --- | --- |
| Candidates | JSON list containing `formula`; optional `candidate_id` |
| Cached features | Ordered 336-column schema; same formulas and IDs as candidates |
| Predictions | Per-circuit LUT4 estimate, model route, hashes and calibration status |
| Output path | Must be new; existing files are never overwritten |

Omitting `--features` invokes label-free native feature extraction and requires the exact Yosys identity recorded by the model. Arbitrary local Yosys versions are not interchangeable with the frozen model's feature pipeline. [Hardware setup](../hw/README.md).

## Troubleshooting

| Symptom | Action |
| --- | --- |
| Python or `venv` missing | macOS: `brew install python`; Ubuntu: install `python3 python3-venv` |
| Pinned dependency unavailable | Use a supported Python/platform with access to the required package index; do not substitute versions for saved weights |
| Dependency version mismatch | Run `./start.sh` to install pinned dependencies in the selected local environment |
| Incomplete virtual environment | Choose a fresh `ISAFORGE_VENV` path |
| Model/source/hash mismatch | Restore the matching checkout and artifacts; never bypass validation |
| Prediction output already exists | Pick a new output filename |
| Fresh experiment has missing labels | Retain it as incomplete; do not score the partial subset as the complete cohort |

## Research and hardware

| Task | Entry point |
| --- | --- |
| Replay frozen coverage audits | `make coverage-check` uses an isolated copy with the hash-verified historical results index; scientific files remain current |
| Reproduce an individual model experiment | [Experiment records](../results/README.md#experiment-records) |
| Extract candidates from Embench | `make candidates` · [Source pipeline](../src/README.md) |
| Build the stock PicoRV32 baseline | `make hw-baseline` · [Hardware guide](../hw/README.md) |
| Inspect all build targets | `make help` |

Hardware runs require the optional tools and may download pinned sources. They are explicit commands, not part of startup. [Historical replay recipes](https://github.com/jas0nriverah/agentic-riscv-codesign/blob/f8fa7b02ba56507f64893debece8d38db8aff642/docs/reproduce.md).
