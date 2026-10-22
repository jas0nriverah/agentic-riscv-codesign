# Selection improvement validation

Validation for the single duration-removal ablation, the fixed six-feature semantic hypothesis and the useful-opportunity qualification/diagnostic. All commands run in Python3.12.14 with the pinned `requirements-speedup.txt` environment. [Implementation/results](../../docs/selection-improvements-2026-10-22.md) distinguish consumed-data improvement from the missing fresh-source validation.

| Check | Outcome | Evidence |
| --- | --- | --- |
| Five new test files, final source | **60 passed**,36.80s | [Focused log](focused-final.log) |
| `make test` | **3,441 passed**,179 passing subtests, **one recurring legacy failure**,214.63s | [Complete log](full-suite.log) |
| `make reproduce-count-selection` |135 new trajectories /405 endpoints exact; all12 original controls unchanged; zero native jobs | [Replay proof](count-replay-verification.json), [log](count-replay.log) |
| `make reproduce-semantic-selection` |Nine initial models and135 trajectories /405 endpoints exact; all13 preceding controls unchanged; zero native jobs | [Replay proof](semantic-replay-verification.json), [log](semantic-replay.log) |
| Final `make diagnose-workload-support` |Byte-identical archived support report; no original native roots or jobs required | [Final log](support-final-replay.log), [artifact verification](artifact-verification.json) |
| `make reproduce-speedup` |Both original seven-design/120-endpoint processor checkpoints reproduce; zero native jobs | [Log](processor-reproduction.log) |
| `make reproduce` |All six historical model scores reproduce | [Log](historical-reproduction.log) |
| Source/input and local-link checks |260 bindings authenticate;366 links resolve | [Log](source-and-link-check.log) |
| Git evidence inventory |All2,040 scientific archive files match staged bytes, including ignored Cover source/evidence | [Index check](index-verification.json) |

The unchanged failure is `tests/test_capture_v11_spooled.py::test_blocked_pipe_or_compressor_drain_has_finite_cleanup[pipe]`: a producer process group remains in its terminal receipt. This recurring historical cleanup failure is retained; no fix is claimed. The broad suite started before the diagnostic's final output-path protection tests were added. The subsequent60-test focused run covers the final implementation, including both guards that reject writes inside sealed evidence. The earlier successful [support replay](support-replay.log) is retained alongside the final one.

The two model replays exclude only the explicitly enumerated nondeterministic host timing fields in their proof files. Model states, initial and paid-prefix predictions, choices, measured labels, native costs and preceding controls remain exact. [Artifact verification](artifact-verification.json) checks every manifest member and full inventory of all four sealed new experiment packages. The historical first read-only source diagnosis remains separate evidence.

## Collection and compute accounting

[Qualification console](qualification-console.txt) preserves the expected nonzero exit: the fixed gate finds zero accepted sources. Seven original programs were compiled/profiled; Janne was statically rejected. This adds **no custom-candidate labels, custom-candidate attempts or routed designs**. The original subprocess receipts and77.769630 recorded monotonic seconds reside in the [sealed qualification](../2026-10-22-useful-source-qualification/qualification.json).

The 90 historical native attempts retain5,098.832466 recorded seconds once globally. Replaying a policy's selected prefix does not recollect those measurements; counterfactual policy costs overlap. Initial count-only predictions are reused, with270 paid-success surrogate updates. The semantic experiment makes9 initial and270 paid-update surrogate fits, each containing3 scalar GP heads. The [sealed internal timers](../2026-10-22-semantic-selection-development/runtime-costs.json) give4.481129 model-plus-run seconds; paid-update timers overlap this envelope.

Independent startup-inclusive semantic command observations are copied byte-for-byte here:

- [Prepare receipt](semantic-command-observations/prepare/record.json):3.765005333 monotonic seconds.
- [Run receipt](semantic-command-observations/run/record.json):7.564351042 monotonic seconds.
- [Independent replay receipt](semantic-command-observations/replay/record.json):14.700618334 monotonic seconds.

Prepare plus run is11.329356375 recorded monotonic seconds. Each receipt preserves raw endpoint clocks, stream hashes and its UTC/monotonic disagreement flag. These are separate scopes, not uninterrupted calendar-wall-time evidence; no clock correction, tolerance change or total-cost advantage is claimed. Native collection, model fits, startup, verification replays, tests and original-program qualification must not be added as if disjoint interchangeable evaluation budgets.

## Working commands

Run from the repository root with the pinned environment:

```sh
python -m pytest -q tests/test_count_selection.py tests/test_semantic_selection.py tests/test_semantic_selection_experiment.py tests/test_opportunity_workload.py tests/test_workload_support.py
make reproduce-count-selection PYTHON=python
make reproduce-semantic-selection PYTHON=python
make diagnose-workload-support PYTHON=python
make reproduce-speedup PYTHON=python
make reproduce PYTHON=python
```

Derived outputs must be fresh. The recorded final diagnostic uses `WORKLOAD_SUPPORT_OUTPUT=generated/reproduction/workload-support-final`; the earlier default output remains preserved. Override `COUNT_SELECTION_REPLAY_OUTPUT` and `SEMANTIC_SELECTION_REPLAY_OUTPUT` for additional replays. Do not rerun source qualification at weaker gates or overwrite frozen results. The next blocker is an untouched workload with a useful, legal executable pool and a prelabel-compatible controller, not another fitted variant on consumed labels.
