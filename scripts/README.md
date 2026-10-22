# Research entry points

Current model/data work: [completed blind source-transfer campaign](../docs/blind-source-campaign.md). `qualify_blind_campaign.py` qualifies original sources; `blind_campaign.py` freezes/releases all twelve policies; `collect_blind_campaign.py` executes each released candidate once. Preserve the original strict packer's clock failure. `reproduce_blind_campaign.py` explicitly packs/replays qualified monotonic accounting, raw evidence, exact refits and all1,620 endpoints without new native jobs. `report_blind_campaign.py`, `export_blind_corpus.py` and `plot_blind_campaign.py` derive tables, the81-label corpus and count-budget figures without fits. Actual uninterrupted wall time remains unknown. Demo and live LLM development remain paused.

Current shareable demo: `make showcase`; bounded four-tool controls: `make selector-controls`. See [the selector guide](../docs/bounded-selection.md). `scripts/run_bounded_selector.py --provider responses` requires an explicit API model and OPENAI_API_KEY; no live trial is claimed. `scripts/ablate_hardware_descriptors.py` preserves the one negative development ablation, not a promoted model.

Current processor replays: `python scripts/reproduce_codesign.py replay` and `python scripts/reproduce_workload.py replay`. New native collection uses `python -m isaforge.workload_experiment`; see [automatic workloads](../docs/automatic-workloads.md). The older commands below are historical cost-model entry points.

Run these scripts from the repository root with the Python environment activated.

| Command | Inputs | Output |
| --- | --- | --- |
| `python scripts/reproduce_matched.py` | Committed frozen models, predictions, measured probe, and protocol records | Validated score replay, independent audit, and nine figures in `generated/reproduction/` |
| `python scripts/reproduce_matched.py --skip-figures` | Same frozen evidence | Scores and audit; no plotting dependency |
| `python scripts/render_architecture.py` | Explicit architecture layout in the script | README SVG and PNG in `docs/assets/` |
| `make reproduce-v6` | Full Git history, both V6 raw archives, frozen predictions and pinned research dependencies | Restored/hash-checked evidence, all scores and bootstrap, PNG/SVG/PDF figures |

`make reproduce` and `make diagram` wrap these commands. The default replay does not retrain, call a model service, collect new hardware labels, or require a synthesis toolchain. Use `--output` to choose a fresh replay directory; the script rejects outputs inside frozen `results/`.

For new inference, training, or measurement, use the [matched comparison guide](../docs/reproduce-matched-comparison.md) and [hardware reproduction guide](../docs/reproduce-research.md). Benchmark collection programs remain under [`src/`](../src/) so existing run manifests and commands remain valid.

The replay comparison permits only floating-point roundoff (absolute tolerance `1e-10`, relative tolerance `1e-12`); cohort counts and metric structure must match exactly.

External transfer: `archive_external_v5.py restore` restores the hash-checked native evidence; `evaluate_external_v5.py score` checks the committed freeze and measurements; `report_external_v5.py` exports figures. Use `make reproduce-external-v5` with full Git history. Collection/freezing/measurement are separate explicit commands described in [the protocol](../docs/external-v5-evaluation.md).

V6: `measure_v6.py restore --scope calibration` and `--scope test` restore
the separate raw archives; `evaluate_v6.py score` checks both stage freezes
and recomputes the fixed endpoint; `report_v6.py` renders all eight predictors,
all strata and coverage. Use Python 3.13 with `requirements-research.txt`.
See [V6 reproduction and actual inference](../docs/v6-reproduction.md).

V7 development: `develop_v7_semantics.py` separates preparation, review and the
fixed 90-fit ablation. The [portable evidence helper](../results/2026-10-14-development-semantics-v7/evidence/REPRODUCE.md)
restores and independently scores the saved study without fitting or hardware.
`report_v7_development.py --prepared <restored>/prepared --output <report>`
generates all six views' figures and error tables. See [results and limits](../docs/v7-development-results.md).
