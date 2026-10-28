# TACLeBench countnegative qualification — October 27, 2026

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

The qualification reused the guarded PicoRV32/PCPI RV32I_zicsr, ILP32, `-Os` path, 8 KiB RAM, 6,400-byte program/data ceiling, 1,664-byte stack reservation, source-operand relocation guard, and the existing twelve-candidate pool. It requires at least one public candidate with a calibrated whole-program cycle-reduction projection of 0.5% and ten timed replacements. It records a routed baseline only after original-input correctness and candidate-opportunity checks pass. Candidate dispatch was disabled throughout.

No inputs, compiler flags, candidate gates, memory limits, or correctness conditions were changed.

## Qualification result — rejected at discovery

After the pushed source checkpoint (`1b831040`), the baseline-only qualification ran once. Preparation succeeded; discovery stopped with `Too few calibrated executable candidates`. The original checksum passed. An archive-authenticated offline reconstruction found **5 raw / 5 executable / 4 relocation-safe and calibrated formulas**, below the unchanged pool requirement of **12**. Two of the four formula families are absent from the historical corpus, but this is only a public-feature screen: no candidate pool was frozen and no independent-workload claim follows.

The instrumented discovery profile recorded **12,477 cycles / 2,510 instructions**; program plus BSS ended at **2,472 / 6,400 bytes**, and observed stack use was **64 / 1,664 bytes**. These are discovery counters, not a routed baseline or speedup. The opportunity gate and routed-baseline phase were not reached. Candidate attempts, measured labels, candidate area, and candidate timing results are all **zero**. Preserve the rejection and do not retry it or reduce the frozen pool/gates.

The [sealed diagnosis and offline reproduction](../results/2026-10-27-countnegative-discovery-diagnosis/README.md) authenticate the original run archive and preserve the reconstructed counts. The raw qualification archive and source receipts are in [the qualification record](../results/2026-10-27-countnegative-qualification/).

The one-shot target command is recorded here for provenance only; **do not rerun it**:

```sh
../work/audit-venv/bin/python scripts/qualify_tacle_countnegative.py
```

Reproduce the diagnosis from the committed raw archive without the original generated native root or any target jobs. The wrapper checks exact agreement with the preserved report. Output must be a fresh directory under `generated/`:

```sh
make reproduce-countnegative-diagnosis PYTHON=../work/audit-venv/bin/python
```

For repeated checks set `COUNTNEGATIVE_REPLAY_OUTPUT` to a different fresh path. The original diagnostic and result directory are frozen evidence and remain unchanged.
