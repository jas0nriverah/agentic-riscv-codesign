# LLVM Stanford Queens adapter contract — October 28, 2026

## Source, workload and oracle

This is a source-only increment, not a qualified target workload or measured
selection result. Pin LLVM test-suite commit
[`9d9184e6ae2d7d4b1fe8dca7a41a90b9d53b6003`](https://github.com/llvm/llvm-test-suite/tree/9d9184e6ae2d7d4b1fe8dca7a41a90b9d53b6003).
The exact [Queens source](../benchmarks/llvm-queens/upstream/Queens.c),
[reference output](../benchmarks/llvm-queens/upstream/Queens.reference_output)
and complete applicable [LLVM root license](../benchmarks/llvm-queens/LICENSE.TXT)
are preserved byte-for-byte. No ancestor or source-specific license override
was found at this revision. Preserve the Apache-2.0/LLVM exceptions and legacy
notice together. [SOURCE_PIN.json](../benchmarks/llvm-queens/SOURCE_PIN.json)
binds SHA-256 and Git blob identities for source/reference and the license hash.

The unchanged source runs 100 outer iterations of 50 fixed eight-queens searches:
**5,000 solves**, with no size or repetition reduction. Direct recursion reaches
at most eight `Try` levels. The original main always returns zero; its only
solver-failure signal is `printf(" Error in Queens.\n")`. Successful stdout is
the ordered lines 1 through 100 (292 bytes). The reference's final `exit 0` line
is test-runner metadata, not stdout emitted by Queens.

The [adapter](../benchmarks/llvm-queens/adapter.c) renames upstream `main` and
`printf` through include-time macros without editing the original C file. Its
volatile output sink records failure or unexpected text, validates each `%d\n`
argument against the next integer, and requires exactly 100 progress calls.
These observable checks preserve the original error branch; output is not a
no-op. The benchmark returns failure for any upstream failure, nonzero main
return, missing/extra/reordered progress output or unknown output format.
`verify_benchmark` checks both the result and final sink state. The adapter
does not link target libc or allocate an output buffer; local empty stdio/stdlib
header shims satisfy the unused upstream header dependencies. Standard compiler
`stdarg.h` supplies the output sink's variadic argument handling.

This is the original fixed-search self-check, not a separate full-board oracle
or arbitrary-input proof. The reference sequence alone does not establish a
valid board. Host tests separately compare unchanged upstream stdout/exit to
the reference and inject output failures into the adapter's sink.

## Baseline-only qualification boundary

[llvm_queens_workload.py](../isaforge/llvm_queens_workload.py) and
[qualify_llvm_queens.py](../scripts/qualify_llvm_queens.py) register only this new
source with the existing guarded pipeline. They do not modify its extractor,
lowering verifier, calibration, compiler, processor or gate implementations.
Candidate dispatch is hard-disabled in the evaluator and absent from the CLI.
The scripted phases are prepare, discover, opportunity, baseline, public and
freeze; a pool freeze does not authorize candidate measurement.

Retain RV32I/Zicsr ILP32 `-Os`, the established pinned toolchain, PicoRV32/PCPI,
synchronous 8-KiB RAM, 6,400-byte program/data limit, 128-byte guard,
1,664-byte stack partition, twelve legal executable candidates, three routing
seeds and a 12-MHz floor. The joint opportunity gate requires the same candidate
to project at least 0.5% cycle reduction and at least ten timed replacements.
No thresholds or input sizes may be relaxed. Preserve the first failure and its
raw archive; distinguish source rejection from an integration failure.

Target qualification has **not run**. No baseline cycles, stack measurement,
candidate pool, area, routed timing or candidate labels are established. The
200 bytes of source-level local arrays exclude recursive frames and alignment.
Unused suite-wide global arrays should be removed by the existing section-GC
build, but that is an inference pending linked-image checks. Output checking and
adapter reset remain inside the measured whole-workload region.

This classic Stanford recursive-search program needs source-lineage review
against earlier BEEBS recursion/tarai and other suite origins. Its benchmark
name alone does not establish an independent application family. Any extracted
formula pool is audited against the pinned 122-label historical corpus; every
overlapping operation-tree family must be excluded from future fitting. An
accepted baseline would still require a separate reviewed, committed and pushed
zero-label policy/controller release before any candidate measurement.

## Host-only validation

```sh
../work/audit-venv/bin/python -m pytest tests/test_llvm_queens_workload.py -q
```

These tests compile and run host C only and exercise source identity, output
oracle failures, unchanged gates, registration restoration and dispatch denial.
They do not invoke the qualification command or native RISC-V/hardware tools.
