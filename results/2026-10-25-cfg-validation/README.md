# CFG coverage checkpoint — qualification not run

The owner requested a tested commit/push and a stopping point. This archive validates additive static-CFG candidate coverage and its separate baseline-only Lift adapter. It contains **no native qualification, candidate measurement, model fit or new performance label**. Native acceptance and measured model improvement remain unestablished.

- [Focused tests](focused.log): **269 pass in 3.38 seconds**, covering new analysis/adapter/qualifier plus existing extraction, lowering, Lift/TACLe, guarded workload and relocation behavior. Independent peer review separately runs the 120 core/legacy and final 41 adapter/qualifier fixtures.
- [Full regression](full-suite/stdout.txt): **3,824 pass, 179 subtests pass, one failure**, in 272.55 seconds. The unchanged failure is `tests/test_external_v5.py::test_trace_deadline_retains_partial_evidence_and_stops_owned_process`: `PermissionError` at `os.killpg`, `scripts/collect_external_v5.py:317`. The [terminal observer](full-suite/record.json) records make exit 2. Preserve this recurrence and prior passing/failing invocations; no cleanup fix or entirely green full-suite claim is made.
- [Historical reproduction](historical-reproduce/record.json) passes all six frozen models with unchanged numerical tolerances and zero native jobs.
- [Frozen integrity](frozen-integrity.json) authenticates eight prior sealed packages and the frozen ARD/G.723 model/controller source bindings. All remain unchanged. Both new native coverage roots are absent at the stopping point.
- [CLI help](qualification-help.txt) confirms argument parsing only. It is not an executed qualification or evidence of an accepted pool.

The [full-run start receipt](full-suite/started.json) binds every actual tested new source, both test modules and the [coverage contract](../../docs/cfg-liveness-experiment.md). Root rechecks those hashes after the run. The new analyzer independently authenticates explicit default-false ABI-return/trap options, static entries, complete program/source/profile certificates and candidate legality. Unsupported control rejects extraction; the adapter checks pinned firmware source and native input bindings before opting in. Existing source mapping, relocation, calibration, stratification, gates and processor configuration remain intact. The old Lift rejection remains final.

Working focused command, with Python 3.12 and `requirements-speedup.txt`:

```sh
python -m pytest -q tests/test_cfg_liveness.py tests/test_cfg_lift_workload.py
```

The [handoff](../../docs/HANDOFF.md) records the future qualification command and fresh roots. Run it only after the owner resumes work. Lift informed this engineering improvement and cannot count as untouched confirmation. Qualification acceptance would add zero candidate training labels; a later measurement campaign needs a separate complete pushed model/controller release.

Full-suite outer observer duration is 273.619336 monotonic seconds. Raw UTC/monotonic disagreement and scopes remain unchanged; no controlled inference-latency or calendar-time saving is claimed. The preceding [model validation](../2026-10-25-model-validation/README.md) separately preserves 3,689 full-test passes at the pre-CFG checkpoint and the mixed ARD outcome. No model is promoted and the research goal remains unachieved.
