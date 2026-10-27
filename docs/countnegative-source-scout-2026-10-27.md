# TACLeBench countnegative source scout — October 27, 2026

## Scope and source

The pinned TACLeBench `countnegative` kernel comes from Mälardalen's integer matrix-counting benchmark. Its original deterministic initializer fills a 20×20 `int` matrix; the measured routine traverses the complete matrix, accumulates positive and negative totals/counts, and checks the original `0x1778de` checksum. The original source and change log are preserved byte-for-byte at [`benchmarks/tacle/countnegative/`](../benchmarks/tacle/countnegative/), with archive, Git blob, and SHA-256 provenance in [`COUNTNEGATIVE_SOURCES.json`](../benchmarks/tacle/COUNTNEGATIVE_SOURCES.json). The source header permits use, modification, and redistribution.

The historical corpus used by the qualification has 14 workload groups and does not contain the declared `tacle-countnegative` group. That establishes a new source identity only. Exact candidate operation-tree overlap can be checked only after target discovery and before any model fit or candidate measurement. The workload is a TACLeBench kernel, not an Embench application or arbitrary-program support.

## Host check

The external ABI adapter initializes the original matrix before the timed function, invokes the unchanged scan, and runs the upstream return check. The reproducible host smoke check is:

```sh
../work/audit-venv/bin/python -m pytest tests/test_tacle_countnegative_workload.py -q
```

That suite compiles the unmodified source through the adapter and passes the original checksum. It validates host behavior and wrapper plumbing only; it does not prove PicoRV32 compilation, full-program target correctness, memory fit, candidate count, useful opportunity, or performance.

## Frozen target gate

The qualification reuses the guarded PicoRV32/PCPI RV32I_zicsr, ILP32, `-Os` path, 8 KiB RAM, 6,400-byte program/data ceiling, 1,664-byte stack reservation, source-operand relocation guard, and the existing twelve-candidate pool. It requires at least one public candidate with a calibrated whole-program cycle-reduction projection of 0.5% and ten timed replacements. It records a routed baseline only after original-input correctness and candidate-opportunity checks pass. Candidate dispatch remains disabled; the script ends after zero-label pool freeze.

No inputs, compiler flags, candidate gates, memory limits, or correctness conditions were changed. The source-level profile suggests a repetitive integer scan worth testing, but no candidate count, measured speedup, area, timing result, or source-family independence claim exists until the frozen baseline-only qualification finishes. The first failure must be archived and not retried or replaced by another source in the same protocol.

Run only from the pushed source checkpoint:

```sh
../work/audit-venv/bin/python scripts/qualify_tacle_countnegative.py
```
