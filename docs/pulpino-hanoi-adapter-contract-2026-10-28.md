# PULPino Tower of Hanoi workload contract

This is a baseline-only qualification of the pinned PULPino sequential-test
Tower of Hanoi program. Its purpose is to determine whether a fresh fixed-input
program can supply a legal, useful candidate pool on the existing PicoRV32
pipeline. The program uses the original twelve plates, recursive `ToH` and
`computeGold` bodies, and upstream destination-array check. The only software
adapter is the freestanding benchmark ABI and deterministic initialization.

## Frozen source and interface

- Repository: `https://github.com/pulp-platform/pulpino`
- Commit: `6631c49ba38a9258da44d6b120d902f7b81f9233`
- Source: `benchmarks/pulpino-hanoi/upstream/towerofhanoi.c`
- License: exact Solderpad Hardware License 0.51 copy in `LICENSE`.
- The extracted `computeGold()` and `ToH()` function bodies in `algorithm.c`
  must stay text-identical to the pinned upstream bodies; the source test checks
  that invariant. Harness, timer callbacks, output formatting, and unsupported
  PULPino headers are not included in the measured program.
- Input: `NR_PLATES == 12`; initialize `A[i] = i`, `B[i] = C[i] = 0`.
- Correctness: after one solve, require each `B[i] == i`, matching the upstream
  check. This says nothing about arbitrary plate counts or alternate inputs.

## Hardware and candidate gates

Use the existing guarded PicoRV32/PCPI toolchain: RV32I/Zicsr, ILP32, `-Os`,
8 KiB RAM, 6,400-byte program/data ceiling, 6,528-byte stack floor, 12 MHz
target, and routed seeds 1, 2, and 3. Preserve the twelve-candidate pool and
joint opportunity threshold: at least 0.5% calibrated cycle reduction and at
least ten timed replacements for the same candidate. Do not shrink the pool,
increase memory, change input or compiler flags, or dispatch candidate jobs to
rescue this source.

Qualification runs source authentication, automatic discovery/lowering,
stack/baseline checks, the source-family audit, opportunity gate, baseline
measurement, public projection, and zero-candidate pool freeze. Candidate
attempts remain disabled. A successful freeze authorizes no measurement.
Before candidate labels are collected, archive and push a source-bound release
that fixes the eligible historical data, model/predictions, controls, budgets,
hardware evaluator, and analysis. Treat Hanoi as a separate workload group;
keep formula-family overlap out of its zero-shot training rows. Report it as
related PULPino recursive-program evidence, not independent application-family
confirmation.

The final task endpoint remains measured feasible whole-program speedup under
area and timing constraints. Static opportunity estimates, source-family
differences, host correctness, and model scores are not substitute labels.
