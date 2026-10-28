# tiny-regex-c workload adapter contract — October 28, 2026

## Scope and source identity

This is a fixed-input regex-engine test-suite workload, not a claim of an
independent general-purpose application family. The exact upstream source is
`kokke/tiny-regex-c` commit
`f2632c6d9ed25272987471cdb8b70395c2460bdb`; the unchanged implementation,
header, 76-case test source, and Unlicense are in
[`benchmarks/tiny-regex/`](../benchmarks/tiny-regex/). `SOURCE_PIN.json` binds
SHA-256 and Git blob identities. The test suite's match/fail expectations and
match lengths are part of the fixed input and are not altered.

The new `adapter.c` renames and calls the upstream `main`, suppresses console
output, and returns the upstream failure count as the benchmark result. The
existing generic harness invokes `verify_benchmark` after the cycle window;
that check requires a zero failure count. The wrapper verifies that all 76
source test vectors remain present. A local freestanding `ctype.h` supplies
ASCII C-locale implementations of `isdigit`, `isalpha`, and `isspace`, which
the upstream implementation uses. The pinned inputs are ASCII. No arbitrary
locale or non-ASCII behavior is claimed. The print routine remains upstream;
only its `printf`/`fprintf` calls are compiled to no-ops.

## Frozen qualification gates

The qualification uses the existing PicoRV32, PCPI, synchronous 8 KiB RAM,
RV32I/Zicsr ILP32, pinned xPack GCC 15.2, `-Os`, guarded stack monitor, and
common 12 MHz routing target. It retains the established 6,400-byte
program/data limit, 128-byte guard, and 1,664-byte observed stack. The 12-item
candidate pool and joint public opportunity rule are unchanged: at least one
same candidate must project at least 0.5% cycle reduction and at least ten
timed replacements. The family/lineage audit compares extracted operation
trees against the current 122-label history before any candidate result could
be considered for confirmation.

Qualification is baseline-only and label-free. It can discover and freeze the
public pool and measure the baseline only after the public opportunity gate
passes. Candidate dispatch remains disabled; a failure is preserved at its
first phase and cannot be rescued by changing tests, compiler, pool, memory
partition, or thresholds. An accepted freeze is not candidate-measurement
authorization. Any later selection study requires a separate source-bound,
prelabel release and must classify this pool as regex/text-processing transfer
unless the prelabel family audit justifies a narrower claim.

## Known limitations before qualification

The fixed tests are short library checks. The host result does not show that the
target image fits, passes the target stack monitor, yields 12 legal candidates,
or clears the opportunity gate. The integration is a source-level lead until
the sealed PicoRV32 qualification completes. Even if accepted, it does not by
itself establish unseen-workload generalization or independence from prior
string-processing families.
