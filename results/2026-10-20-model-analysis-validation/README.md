# Model-analysis validation — October 20, 2026

The new latency/calibration tests and all research replays pass. **The complete test suite does not pass:** both full runs have 2,550 passing tests, 179 passing subtests, and one failure in the unchanged legacy subprocess-cleanup test. The failure is preserved rather than retried until a favorable result.

| Check | Result | Evidence |
| --- | --- | --- |
| New analysis tests plus legacy capture tests | 49 passed: 27 new and 22 legacy, 8.90 s | [Targeted log](targeted-retry.log) |
| Complete suite | 2,550 passed, 1 failed, 179 subtests passed, 141.51 s | [First full run](full-suite.log) |
| Complete suite, serial retry | Same failure/counts, 139.24 s | [Serial retry](full-suite-serial-retry.log) |
| Historical six-model score replay | All six metrics and 10,000-replicate bootstrap reproduced | [Replay log](replays.log) |
| Original CRC32, automatic aha-mont64, automatic CRC32 | Raw evidence, seven designs and 120 policy outcomes per experiment verified | [Replay log](replays.log) |
| Fixed ranking and failed workload probes | 420 policy outcomes; nine failed build contexts preserved | [Replay log](replays.log) |
| New latency calibration and model analysis | 222 cases authenticated; 420 old plus 60 new policy outcomes match | [Replay log](replays.log) |

The replay commands execute no new native measurements. The separately collected calibration used eight native commands, 5.095776 command-seconds, two RTL simulation runs, and no synthesis. It added no application candidate labels. All current and historical learned settings remain unchanged.

## Unresolved legacy cleanup failure

`tests/test_capture_v11_spooled.py::test_blocked_pipe_or_compressor_drain_has_finite_cleanup[pipe]` expects an empty `remaining_owned_children` list. Both full-suite journals instead retain a producer process-group entry after `killpg` returns `PermissionError(1, 'Operation not permitted')`. The producer exits with code 1 and `BrokenPipeError`; the compressor exits with code -9. The cleanup code conservatively retains the entry after the signal failure.

The [first raw journal](first-failure/capture.json) and [retry journal](serial-retry-failure/capture.json), their producer/compressor output, and the synthetic compressor fixture are retained. The legacy implementation and test match base commit `0b0559c9612a70547c8a82802c83d341a7e6ac59` byte for byte. The targeted capture suite passes, but that does not resolve the full-suite failure. The cause of the macOS signal denial remains unknown; this record does not establish that the baseline full suite would pass or that the failure is harmless.

Both full runs also contain the existing intentional duplicate-ZIP-member warning from a rejection test. It is separate from the failed cleanup assertion.

Source/document whitespace checks pass. Four trailing-space lines in the raw pytest failure logs are retained byte for byte and excluded from that formatting check. All 75 manifest-bound calibration, analysis and validation files match their staged Git contents; all 220 relative documentation links checked resolve locally.

## Commands and provenance

Use Python 3.12 with [the pinned packages](../../requirements-speedup.txt):

```sh
python -m pytest tests/test_capture_v11_spooled.py tests/test_latency_analysis.py -q
make test PYTHON=python
make reproduce reproduce-speedup reproduce-selection-research reproduce-model-analysis PYTHON=python
```

[Validation metadata](validation.json) records exact interpreter paths, package versions, commands, results, source hashes, base commit, and the three GPT-6.1-Sol review scopes. [The manifest](manifest.json) hashes all retained logs, failure fixtures and metadata; this explanatory README was added afterward and is outside that manifest.

The supported new replay is `make reproduce-model-analysis`. Its wrapper uses canonical JSON to correct a tuple/list comparison defect in the frozen analyzer's direct `verify` path. It retains every scientific field, authenticates the raw calibration and source bindings, and excludes only varying analysis wall time from equality. The source that produced the original snapshot remains unchanged.

See [the model analysis](../../docs/model-analysis.md) for measured findings, limits, and the next independent-workload experiment.
