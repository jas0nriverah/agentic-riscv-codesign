# Contributing to ISAForge

ISAForge is organized around reproducible experiments. Start with the [project scope contract](README.md), [agent instructions](AGENTS.md), [current handoff](docs/HANDOFF.md), and [methodology](docs/methodology.md). Historical model roadmaps do not define current work.

## Work in a branch

Install `.[dev,reports,proofs]` in a virtual environment. Keep implementation changes separate from generated experiment outputs. Use `generated/` for local runs, simulator builds, caches, and plots. Do not commit toolchains, virtual environments, instruction traces, or simulator build directories.

## Preserve frozen evidence

Files under `results/` describe completed experiments. Do not overwrite their datasets, weights, predictions, split definitions, or preregistrations. Preserve failed runs and empty candidate pools. Apparent duplicate artifacts can belong to different historical protocols and are intentionally retained.

Saved model schemas hash their runtime source files. Existing `area_model*.py`, `features.py`, `structural_features_v3.py`, `rtl.py`, `synthesis.py`, and `masterrtl_baseline.py` participate in those contracts. Preserve those modules and artifacts. A new module is justified only when it fixes an in-scope engineering or selection problem; frozen-source protection is not permission to launch another model-version study. Check each artifact's schema for the precise frozen dependencies.

## Add an experiment

Record the hypothesis, primary metric, training cohort, exclusions, candidate set, seeds, tool versions, and measurement budget before inspecting test labels. Save label-free predictions and model/source hashes before scoring. If a test set informs the next revision, call it development data and collect another untouched test set.

Write a new result snapshot with a short README, commands, input/source hashes, raw or locatable evidence, and all declared outcomes. Distinguish isolated mapped resources, instruction-saving proxies, simulated processor cycles, and conditional timing estimates. Include preprocessing and historical measurement costs when comparing methods.

## Validate a change

- Run `make test` for code changes. Hardware tests run when their required tools are installed; CI includes a hardware-tool job.
- Run `make reproduce` when changing evaluation, reporting, or its entry points. The replay checks exact agreement with the committed six-model scores.
- Run `make reproduce-speedup` for changes affecting processor evidence or selection reports.
- Run `make reproduce-count-selection`, `make reproduce-semantic-selection` and `make diagnose-workload-support` for the October 22 fixed selection changes. Use fresh output directories and retain every previous control, source/input binding, paid-prefix seal, explicit host-timer exclusion and qualification rejection. The archive-only diagnostic must work without original generated roots or native jobs and must reject writes inside sealed evidence. These are development/diagnostic commands, not new unseen-source measurements.
- Run `make reproduce-budget-campaign campaign-report` for the EDN/UD experiment. The original scorer is frozen; the derived report distinguishes correctness failures from infrastructure-censored outcomes and qualifies its best-verified reference.
- Run `make reproduce-sha256` for the guarded sixth workload and `make sha256-report` for its tables. Keep the prelabel Git proof, one-attempt ledger and consumed-corpus context/timer fields intact. Inspect [teammate compatibility](docs/teammate-branch-review-2026-10-21.md) before bringing in another hardware context.
- Run `make reproduce-jfdctint` for the new seventh source and fixed factorized model. `make jfdctint-report`, `make export-seven-source-corpus` and `make diagnose-factorized-selection` require fresh derived outputs. Preserve source holdouts, release chronology, all twelve controls/policies, distinct duration scopes, the tighter-cap miss and uncalibrated-score flags.
- Run `make reproduce-blind-campaign`, `make blind-report` and `make export-blind-corpus` for the completed three-source/36-candidate campaign. Keep the original strict clock failure, the explicit post-collection accounting amendment and all1,620 fixed-policy endpoints. Recorded monotonic seconds are not established uninterrupted calendar wall time. `make blind-figures` uses the derived report; every output directory must be fresh.
- Regenerate and visually inspect diagrams and figures after layout edits. Preserve vector exports and the numerical evidence behind research plots.
- Check relative documentation links and make sure quick-start commands work from the repository root.

Keep pull requests focused on the concrete change and its verification. Update the documentation index and results index when adding a new guide or experiment. Do not present a synthetic-formula improvement as evidence of general application or processor superiority.
