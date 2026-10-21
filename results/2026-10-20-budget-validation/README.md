# Campaign validation — October 20, 2026

The final full suite ran after the qualified UD adapter, independent partition-dispatch test, and archive handling were added: **2,732 passed, 179 subtests passed, one failed**. The remaining failure is `tests/test_external_v5.py::test_trace_deadline_retains_partial_evidence_and_stops_owned_process`: `os.killpg` raises `PermissionError: Operation not permitted` in the unchanged legacy trace collector. Its source hashes and raw fixture are preserved. No fix or fully passing suite is claimed.

The preceding full run has 2,704 passes, 179 passing subtests and three legacy process failures. That run and all 13 failure files remain here; the later run was required by new adapter and audit code, not used to remove the earlier failures. The two failures that did not recur are not claimed fixed.

Forty-nine focused campaign, qualified-adapter and archive tests pass after the final dispatcher edit. The historical six-model score replay, original CRC32 processor replay, automatic aha-mont64 replay, ranking research replay, 222-case latency calibration replay and prospective SLRE replay all pass. `historical-replays.log` retains their output.

The completed campaign's exact prediction refit and raw processor/policy replay are recorded with its result archive. No frozen historical measurement sources were modified. Timing logs use separate scopes; passing software tests are not new hardware measurements.
