# Factorized-model and fresh-source validation

`make test` passed **3,117 tests and 179 subtests**, including **102 new tests**, in 180.29 seconds. The complete log and command wall/status are retained. One existing ZIP duplicate-member fixture warning remains; no test failed. The earlier intermittent process-cleanup failure is preserved in the previous validation snapshot. A passing run does not establish a legacy fix; no such code was changed.

`make reproduce` passes all six historical frozen metrics and the 10,000-replicate bootstrap audit. `make reproduce-jfdctint` passes raw archive authentication, prelabel Git/source/zero-attempt chronology, complete outer timers, all five original prediction-package refits, five exact utility-model refits, five exact feasibility-model refits,180 trajectories and540 endpoints. Both commands launch zero native jobs.

The actual reporting CLI and seven-source dataset-export CLI pass after complete replay. The public-only prediction CLI returns six predictions and reads zero target labels. The retrospective six-source/seven-context diagnosis exactly refits/replays210 trajectories; both SHA contexts stay in the same source fold. The original39-row corpus manifest and its prelabel-bound digest were checked before the diagnosis.

All commands used the pinned Python3.12 `requirements-speedup.txt` environment. `source-bindings.json` records the tested code. JSON model exports retain settings, dependencies, cohort IDs and exact booster hashes. The six live native measurements are new evidence; these validation/replay commands are not additional hardware observations.

Commands:

```sh
make test PYTHON=python
make reproduce PYTHON=python
make reproduce-jfdctint PYTHON=python
python scripts/report_jfdctint.py --output results/2026-10-21-jfdctint-report
python scripts/export_jfdctint_corpus.py --output results/2026-10-21-seven-source-corpus
python scripts/diagnose_factorized_selection.py --output results/2026-10-21-factorized-development
python scripts/diagnose_factorized_selection.py --replay results/2026-10-21-factorized-development --output generated/reproduction/factorized-source-diagnosis
```

Use fresh output paths for another derived report/export/diagnosis. Never overwrite frozen results. Current limitations and negative outcomes are in [the model guide](../../docs/ml-factorized-selection.md) and [all candidate/policy tables](../2026-10-21-jfdctint-report/results.md).
