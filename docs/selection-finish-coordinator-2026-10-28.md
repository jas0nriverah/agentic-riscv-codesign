# Serial selection-study completion

The Stringsearch evaluation was once launched while collection was still writing its native audit. That invocation failed on missing readiness evidence; its log remains preserved, and a later explicit invocation succeeded after collection finished. The frozen executors and policies remain unchanged.

`scripts/finish_selection_study.py` prevents this ordering mistake for the two allowlisted studies, `countnegative` and `stringsearch`. It never starts or chooses a live agent. Before collection it requires a sealed, completed agent ledger/report and matching manifest. It runs each executor stage as a blocking subprocess: collect must exit successfully **and** produce a sealed complete native audit, collection report and operation receipt before evaluate can start. Evaluate must exit successfully and produce a sealed final result package before verify can start.

If the final result directory already exists, the default is **verify only**. A complete collection without a final result resumes at evaluate, avoiding a second native collection. Partial collection/audit evidence, including a native collection report without the wrapper audit, fails closed for inspection. Prior partial scoring also requires inspection. A failed child or readiness check stops immediately; no stage is retried and no later stage is dispatched. A failed invocation does not erase its logs or repair evidence.

A nonblocking `flock` under `generated/selection-finish-locks/` allows one coordinator per study. This lock coordinates this wrapper's launchers; frozen executor/native locks remain authoritative for direct executor invocations. Every invocation requires a fresh receipt directory. `receipt.json` and its sidecar record source hashes, planned stages, exact argv, start/end times, monotonic durations, return codes, failures and log hashes. Separate stdout/stderr files retain each child output, and a started receipt precedes dispatch.

For completed studies, these commands perform verification only:

```sh
.venv/bin/python scripts/finish_selection_study.py countnegative --receipts generated/countnegative-finish-verify-r1
.venv/bin/python scripts/finish_selection_study.py stringsearch --receipts generated/stringsearch-finish-verify-r1
```

Omit `--receipts` to create a fresh timestamp/UUID directory beneath `generated/selection-finish-receipts/<study>/`. The allowlist controls the executor, study and result paths; arbitrary commands and agent stages are unavailable.

This is orchestration safety, not evidence of better models or decisions. Verification retains the existing archive/audit/replay checks and may refit the original GP during replay in temporary directories; it acquires no new target labels or hardware measurements. Focused tests use subprocess fakes, not real native jobs.
