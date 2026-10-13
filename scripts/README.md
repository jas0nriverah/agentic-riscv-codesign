# Research entry points

Run these scripts from the repository root with the Python environment activated.

| Command | Inputs | Output |
| --- | --- | --- |
| `python scripts/reproduce_matched.py` | Committed frozen models, predictions, measured probe, and protocol records | Validated score replay, independent audit, and nine figures in `generated/reproduction/` |
| `python scripts/reproduce_matched.py --skip-figures` | Same frozen evidence | Scores and audit; no plotting dependency |
| `python scripts/render_architecture.py` | Explicit architecture layout in the script | README SVG and PNG in `docs/assets/` |

`make reproduce` and `make diagram` wrap these commands. The default replay does not retrain, call a model service, collect new hardware labels, or require a synthesis toolchain. Use `--output` to choose a fresh replay directory; the script rejects outputs inside frozen `results/`.

For new inference, training, or measurement, use the [matched comparison guide](../docs/reproduce-matched-comparison.md) and [hardware reproduction guide](../docs/reproduce-research.md). Benchmark collection programs remain under [`src/`](../src/) so existing run manifests and commands remain valid.

The replay comparison permits only floating-point roundoff (absolute tolerance `1e-10`, relative tolerance `1e-12`); cohort counts and metric structure must match exactly.
