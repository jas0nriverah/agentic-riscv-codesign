# Original-input complex_updates: baseline-only qualification

Qualification outcome: **rejected at `discover`** in the single root-owned,
baseline-only attempt on October 26, 2026. The exact source-bound protocol and
raw archive are preserved at
[`results/2026-10-26-complex-updates-qualification`](../results/2026-10-26-complex-updates-qualification/).
This is not a qualified pool, independent-family proof, timing-boundary test,
or learned-selection result. It adds no candidate measurements or speedup
labels.

The separate source-bound adapter is `isaforge/complex_updates_workload.py`;
`scripts/qualify_complex_updates.py` is its single-source, first-rejection
controller. Existing frozen source modules and historical evidence remain
unchanged. The new benchmark directory retains byte-identical upstream
`complex_updates.c` and `ChangeLog.txt`; the separate provenance record binds
TACLeBench commit `c6a0d73e47bbd2bc86e34637156fb26dd4d5cf08`, directory
`bench/kernel/complex_updates`, file SHA256s, byte counts and Git blob SHA1s.
The original source notice permits use, modification and redistribution.

## Fixed scientific and execution contract

Keep original `N=16`, four 32-float arrays, initialization A=(2,1), B=(2,5),
C=(3,4), D=(0,0), volatile-zero initialization and the exact original float
operations. The external ABI adapter renames only the original `main`, calls
original initialization/computation/return, provides a no-op warm-cache hook,
and asserts ILP32 and 32-bit float. The original exact checksum is 144.0f.
**Its verifier sums only the first 16 of 32 D elements.** It does not separately
check all outputs or intermediate values; no stronger verification is claimed.

Compiler flags are the existing guarded RV32I_zicsr/ILP32 `-Os` flags without
fast-math or hardware floating-point extensions. The failed GCC link used the
inherited `-lgcc` software-helper contract, but did not preserve selected helper
members or hash the archive. The failure cannot be attributed to those helpers;
this source/protocol remains rejected.
Extraction remains integer-only,
two-to-four connected operations, at most two register inputs and one output;
there is no float-instruction grammar or linked-helper rewriting. The source's
512 bytes of declared float arrays do not establish code/helper/stack fit.

Retain integrated PicoRV32/PCPI with 8 KiB RAM, explicit program limit 6400,
stack floor 6528, 128-byte guard and 1664-byte stack reservation. Existing
partition observation and deliberate guard controls apply to original inputs
only. Retain 12 MHz and all three routing seeds (1, 2, 3). Minimum routed Fmax
is a tool estimate, not a board measurement.

Discovery must supply at least twelve legal executable, relocation-safe and
calibrated formulas. The frozen public twelve-formula stratification and gate
are reused unchanged: **the same candidate** must project at least 0.5%
whole-program cycle reduction and at least ten timed replacements. Public
projections are not candidate measurements. No input, checksum, compiler,
partition or gate rescue is permitted after a rejection.

## Phases and hard boundary

The fixed phase order is prepare, discover, opportunity, baseline, public,
freeze. Discovery includes original baseline profiling; baseline routing runs
only after discovery and public opportunity pass. One native phase is observed
at a time, with existing two-worker build limits. Preserve the first rejection,
interruption and raw archive; do not retry or continue to another source.

The new evaluator rejects **every non-baseline measurement name before the
opportunity gate or inherited native call**. Every input validation and observed
phase requires no candidate ledger/measurement artifacts. Pool freeze binds a
12-candidate inventory through the existing guarded protocol but does not
authorize candidate dispatch; the wrapper remains disabled after freezing.
The inherited one-attempt marker is a dispatcher budget, not permission to
collect one candidate. Candidate attempts and measured candidate labels must
remain zero throughout.

The controller hashes the latest historical corpus for provenance; it does not
parse its outcomes, fit models, prepare predictions or construct training rows.
A future selection campaign needs its own complete source/model/controller
release and workload/family exclusions. This checkpoint does not create that
campaign.

The baseline-only command was run once by root:

```sh
../work/audit-venv/bin/python scripts/qualify_complex_updates.py
```

It used `generated/tacle-complex-updates-2026-10-26` and
`results/2026-10-26-complex-updates-qualification`. Prepare succeeded in
1.049487167 seconds. Discovery stopped when the linker rejected the generated
firmware at the unchanged `_program_end <= 6400` assertion, which reserves the
128-byte guard and 1,664-byte stack inside 8 KiB RAM. The preserved diagnostic
is `firmware must leave the declared guard and 1664-byte stack`. The failure
establishes that this exact linked image exceeded the 6,400-byte program/data
limit. It does **not** establish that it exceeded physical RAM, that the stack
needs more than 1,664 bytes, or whether code versus software-float helpers
caused the excess. No map was produced. Opportunity, baseline, correctness,
routing, and freeze phases did not run. The qualification records zero
candidate attempts and zero candidate labels.

Discovery's observed monotonic duration was 9.300423167 seconds. Its UTC
duration differed outside the captured monotonic bracket, so the record marks
clock disagreement; use the monotonic observation and retain that caveat.

This is the first protocol rejection. Preserve it and do not rerun the same
source/protocol, enlarge its program partition, or weaken its stack, guard, or
candidate gates to rescue it. Any future source requires a separately reviewed
prelabel contract and a genuinely new output identity. Rejection gives no
evidence about candidate count, opportunity, ML performance, or speedup.

## Offline validation

Run only the isolated synthetic fixture suite:

```sh
PYTHONDONTWRITEBYTECODE=1 ../work/audit-venv/bin/python -m pytest -q -p no:cacheprovider tests/test_complex_updates_workload.py
```

Tests stub all phase execution and preparation, forbid subprocess dispatch and
model fitting/prediction, and prohibit reading repository historical result or
model files. Their public rows, corpus metadata, phase records and accepted
freeze are synthetic. They test source/provenance and compiler bindings,
registration restoration, original checksum semantics, partition/gate tampering,
same-candidate opportunity, failed-gate retention, rejection/interruption
archiving, CLI restrictions and zero candidate attempts after a synthetic
freeze. Passing these tests does not establish workload qualification.

Focused offline validation: 17 tests passed (root rerun, 0.92 seconds; the
original agent run took 15.66 seconds). The single baseline-only qualification
then ran and was rejected as described above; no candidate evaluation ran.
