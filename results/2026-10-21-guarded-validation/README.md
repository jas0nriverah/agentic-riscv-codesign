# Guarded SHA256 validation — October 21, 2026

All six fresh SHA256 candidates pass complete correctness/execution controls, integrated synthesis and three routing seeds. The original pool and frozen predictions were committed/pushed before collection. Raw evidence and all 450 selection endpoints replay with zero native jobs.

| Check | Result | Evidence |
| --- | --- | --- |
| Initial `make test`, before candidate labels | 2,836 passed; 179 subtests passed | [initial log](initial-full-tests.txt) and immutable prelabel copy |
| Final `make test`, including new report/export/replay tests | 2,863 passed; 179 subtests passed; one unchanged intermittent legacy cleanup failure | [final log](final-full-tests.txt) |
| All new guarded/report/export/replay tests | **83 passed** | [targeted log](new-tests.txt) |
| `make reproduce` | Six-model score replay and figures pass | [log](legacy-reproduce.txt) |
| `make reproduce-speedup` | Preserved original CRC32 and automatic aha-mont64 raw evidence and selection replay pass | [log](speedup-replay.txt) |
| Raw native audit/archive | Six complete charged attempts; no censored SHA outcomes | [pack log](native-pack.txt) |
| `make reproduce-sha256` | Exact historical refits, raw evidence, Git chronology and 450 endpoints pass; zero native jobs | [log](sha256-replay.txt) |
| Legacy runner against actual guarded SHA plan | Rejects before any native command; receipt hash unchanged | [check](legacy-entrypoint-check.json) |
| New consumed corpus | 33 labels / six groups / three preserved failures; CSV and manifest checked | [corpus](../2026-10-21-six-workload-corpus/README.md) |

The final failure is `test_blocked_pipe_or_compressor_drain_has_finite_cleanup[pipe]` in unchanged `tests/test_capture_v11_spooled.py`. Its recorded producer process-group list was not empty at the cleanup assertion. The listed process was absent when checked after the suite. The same legacy cleanup area has failed intermittently in earlier runs, while this turn's initial full run passed. We did not change that frozen capture implementation or claim to fix it; both full-run logs are retained. There are no new guarded-workload test failures.

The raw historical five-workload campaign is replayed and exactly refit by the guarded history authenticator during freeze, scoring and export. Earlier three-workload/EDN/UD data and negative outcomes are unchanged. Costs and clocks have the explicit scopes recorded in the campaign; successful unit tests are not counted as native research measurements.
