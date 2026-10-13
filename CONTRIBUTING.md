# Contributing to ISAForge

ISAForge is organized around reproducible experiments. Start with the [methodology](docs/methodology.md), [results](docs/results.md), and [evidence index](results/README.md) before changing an experiment.

## Work in a branch

Install `.[dev,reports]` in a virtual environment. Keep implementation changes separate from generated experiment outputs. Use `generated/` for local runs, simulator builds, caches, and plots. Do not commit toolchains, virtual environments, instruction traces, or simulator build directories.

## Preserve frozen evidence

Files under `results/` describe completed experiments. Do not overwrite their datasets, weights, predictions, split definitions, or preregistrations. Preserve failed runs and empty candidate pools. Apparent duplicate artifacts can belong to different historical protocols and are intentionally retained.

Saved model schemas hash their runtime source files. Existing `area_model*.py`, `features.py`, `structural_features_v3.py`, `rtl.py`, `synthesis.py`, and `masterrtl_baseline.py` participate in those contracts. A new research variant should use separately versioned modules and artifacts rather than silently breaking an old model's loader. Check each artifact's schema for the precise frozen dependencies.

## Add an experiment

Record the hypothesis, primary metric, training cohort, exclusions, candidate set, seeds, tool versions, and measurement budget before inspecting test labels. Save label-free predictions and model/source hashes before scoring. If a test set informs the next revision, call it development data and collect another untouched test set.

Write a new result snapshot with a short README, commands, input/source hashes, raw or locatable evidence, and all declared outcomes. Distinguish isolated mapped resources, instruction-saving proxies, simulated processor cycles, and conditional timing estimates. Include preprocessing and historical measurement costs when comparing methods.

## Validate a change

- Run `make test` for code changes. Hardware tests run when their required tools are installed; CI includes a hardware-tool job.
- Run `make reproduce` when changing evaluation, reporting, or its entry points. The replay checks exact agreement with the committed six-model scores.
- Regenerate and visually inspect diagrams and figures after layout edits. Preserve vector exports and the numerical evidence behind research plots.
- Check relative documentation links and make sure quick-start commands work from the repository root.

Keep pull requests focused on the concrete change and its verification. Update the documentation index and results index when adding a new guide or experiment. Do not present a synthetic-formula improvement as evidence of general application or processor superiority.
