# Nanocobs baseline qualification contract

This extends the working PicoRV32 pipeline with a protocol-framing workload.
It authorizes a baseline-only qualification, with zero candidate measurements.
The source/host/link preflight is preserved at
[nanocobs preflight](../results/2026-10-28-nanocobs-source-preflight-r1/README.md).

## Fixed source and workload

- Upstream `charlesnicholson/nanocobs`, commit
  `8d47d35ebe81c7caecc2b8954b1355d223ecabcb`; Unlicense OR 0BSD.
- Retain the original complete freestanding `tests/qemu/probe.c`: 8,191
  binary payloads of lengths 0–12 in its original mask order, then 24 all-zero
  and all-data runs. No input reduction, synthetic repetition or cherry-picked
  fast path is permitted.
- Preserve production `cobs.c`, its headers and the scalar-reference wrapper
  byte-for-byte. Compile the production, reference and probe adapter separately.
- The adapter only maps the original main/probe callbacks to the benchmark ABI,
  suppresses formatted output, initializes the counters, and verifies a zero
  result, zero failures and exactly 8,215 passes. Warmup is a no-op.
- The measured benchmark includes input generation, both codec implementations
  and original comparisons. Report this test-workload scope; it is not a measure
  of standalone codec throughput or realistic network traffic.

## Rewrite and correctness boundary

Only production `cobs.c` is eligible for extraction and replacement. Keep the
probe, reference codec, verification callbacks and generic memory routines
outside the marked assembly. The fixed reference and checker must never acquire
custom instructions when a production candidate is installed.

Keep `program.s` and `marked.S` as production-only assembly for the inherited
audit. Link precisely the same other translation units into original, marked
and later candidate firmware. Require byte-identical complete original/marked
baseline images. Retain the full linked disassembly/profile for CFG, liveness,
register semantics and dynamic-count checks; a TU boundary does not waive them.
Standalone guard-test fixtures must not accidentally link the benchmark's other
translation units.

The upstream reference is the same codec compiled with SWAR disabled. It checks
scalar/SWAR divergence and round-trip behavior but may share common-mode codec
bugs. A separate untimed host audit may compare the complete original fixed
corpus against an independently written short-frame oracle based on
[Cheshire and Baker's COBS specification](https://www.stuartcheshire.org/papers/COBSforToN/).
That audit must preserve its source, inputs and failures, stay outside the timed
target/rewrite scope, and claim only its tested short payloads. It does not
replace target execution, instruction-level equivalence or the fixed target
self-check. Neither test establishes arbitrary-payload, malformed-frame or
254-byte-boundary correctness.

## Architecture and qualification gates

Use existing RV32I/Zicsr ILP32 `-Os` flags, PicoRV32/PCPI, 8 KiB RAM, the
6,400-byte program/data limit, stack floor 6,528 and 1,664-byte stack reservation.
Retain the 12 MHz timing requirement, routing seeds 1/2/3, serialized native
evaluation and two build workers. The compiler may lower word copies into the
existing byte-memory helper; do not alter the ISA or enable unaligned accesses
to obtain better performance.

Require actual target correctness and continuous stack checks. Static compiler
frame sizes and a successful link do not establish target stack safety.
Require the existing direct-call/CFG proofs, relocation-safe lowering, twelve
legal calibrated formulas, and at least one same candidate with both 0.5%
projected cycle reduction and ten timed replacements. Projections are label-free
eligibility checks, never measured candidate speedup labels.

Preserve the first failure/rejection and its raw evidence. Do not reduce inputs,
change memory partitions, shrink the pool or weaken gates after observing an
outcome. A failed extraction may still preserve a valid baseline self-check;
report those stages separately. Stop before synthesis/routing if an earlier
eligibility phase fails.

## Model and research status

Candidate dispatch stays disabled throughout qualification. A successful
qualification requires a separate frozen, source-bound policy/model release
before candidate measurement. It does not authorize training or changing the
current model. Later evaluation must hold the workload and related formula
families out, compare the same measurement budgets, and retain failures.

COBS is a distinct protocol-framing source; independence from historical
expression families remains unproved until extraction and overlap review.
Generic bitwise arithmetic or buffer-index expressions may recur in prior pools.
No ML, agent, sample-efficiency or research-superiority claim follows from
passing this qualification.
