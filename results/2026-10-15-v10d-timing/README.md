# V10d matched registered-harness timing

Completed: 32 fixed original/CSD pairs, 64 mappings and sequential checks, 192 routes; no failures, timing misses or new fits. All 32 formula means improve in period; 95/96 individual seed pairs improve and one regresses. All carry/resource tradeoffs remain visible. See [results and figures](../../docs/v10d-timing-results.md) and the [frozen protocol](../../docs/v10d-timing-protocol.md).

| Evidence | File |
| --- | --- |
| Prepared input and source closure | [preparation.json](preparation.json) |
| Pre-measurement release | [measurement-approval.json](measurement-approval.json), [timing-release.json](timing-release.json) |
| Completion and paired results | [completion](measurements/completion.json), [summary](measurements/attempt-0000/summary.json) |
| Wrapped mapped inventories | [mappings](measurements/attempt-0000/mappings.json) |
| Sequential checks and route gate | [checks](measurements/attempt-0000/sequential-checks.json), [gate](measurements/attempt-0000/route-gate.json) |
| All 192 native routes | [routes](measurements/attempt-0000/routes.json) |
| Raw logs, commands, mapped/packed JSON, ASC and reports | [archive](measurements/attempt-0000/raw-evidence.zip), [hash manifest](measurements/attempt-0000/raw-evidence.json) |
| Independent replay | [separate-agent report](independent-second-review.json), [figure replay](../../docs/figures/v10d-timing/independent-audit.json) |

Run `make reproduce-v10d-timing` from the repository root, writing to a new output file. This verifies retained raw evidence without native hardware tools. The full local suite before collection passed 1,475 tests and 111 subtests; its [log](full-suite.log) is retained. No files in the frozen measurement closure were changed after collection.

Reported Fmax concerns the complete fixed 132-FF harness. 120 paths have a datapath-boundary certificate and 72 remain unknown; no unknown is filtered. It is not a CPU, board, power, energy, ASIC or independent-program result. The historical area proofs and failed V10c SAT attempt retain their original meaning.
