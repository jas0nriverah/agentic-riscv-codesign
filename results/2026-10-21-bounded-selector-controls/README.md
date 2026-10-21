# Bounded-selector control replay

A host-enforced four-tool selector and isolated remote provider now connect the existing frozen models to a bounded selection interface. All ten deterministic controls exactly reproduce their original EDN/UD/SHA trajectories: **450 trajectories, 1,350 dependent budget endpoints**, including actual choices, verified feasible speedup and recorded attempt durations.

These are consumed-data engineering replays with **zero live LLM calls and zero new native evaluations**. The remote provider requires an explicit API model and OPENAI_API_KEY; the key is absent in this environment. Passing mocked-provider tests does not establish LLM performance.

- `run-protocol.json`: prompt, strict tool schemas, input/source hashes, limits and cost/label boundaries, saved before control execution.
- `run-report.json`: all endpoints, runs and matched-control assertions. Zero-query failures and early stops remain in allocated-budget summaries; actual charges stay distinct from allowance.
- `private-ledgers.zip`: all 450 private action/observation ledgers and seals. Analysis artifact only; never give this archive, report or oracle to a selector.
- `run-manifest.json`: original generated-run inventory. Restore protocol/report under their original names and extract the private archive to verify that inventory.
- `sources/`: exact new runtime, report, demo and test sources used for this milestone. Existing model sources remain frozen.
- `validation.json`, `full-suite-final.log`: 88 new passes, final full suite 2,961 passes plus 179 subtests, preserved earlier legacy failure, reproduction and browser checks.

The final suite passed without changing the flaky legacy capture implementation. The earlier failure is retained in validation.json; no fix to it is claimed. `make reproduce` exactly reproduces the historical six-model scores.

The separate ordered-descriptor ablation is negative and not promoted. SHA adaptive +64 selection changes from query two to three, versus the cost heuristic's one query. No model/agent superiority or calibrated confidence is established.

From the repository root with Python 3.12 and requirements-speedup.txt:

```sh
make showcase PYTHON=python
make selector-controls PYTHON=python
```

Use fresh output directories, or override SHOWCASE_OUTPUT/SELECTOR_OUTPUT. Read [the interface and live-model guide](../../docs/bounded-selection.md). Live-model development trials, guarded native dispatch and joint final instruction sets remain next work. The small consumed corpus cannot establish broad generalization; target timers retain their explicitly different record/ledger scopes and do not establish end-to-end cost superiority.
