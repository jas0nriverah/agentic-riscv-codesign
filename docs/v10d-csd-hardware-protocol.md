# V10d: actual parsed-RTL algebra gate and paired hardware measurement

This is a new, input-frozen hardware development attempt. V10c's original
native SAT outcome remains **16 proofs, 16 timeouts, zero area measurements**;
its completion, all 32 outcomes and raw archive remain unchanged. V10d changes
the universal actual-RTL proof algorithm. It does not reinterpret a timeout as
a proof, relax functional equality or select a subset of circuits.

## Exact inherited inputs

Reuse all 32 V10c pairs in their original order, IDs, formulas and single CSD
implementation. Copy the exact original/CSD RTL bytes, source-proof records,
miter bytes and tools inventory; do not regenerate RTL, choose alternatives,
filter pairs, replace failed cases, extract features or fit a model.

`prepare` authenticates the V10c input manifest and all its bindings against
`f7e04033a4bf52d5095dc7027d1d8a21a4f6e884`, the native failure evidence against
`888dc3ea6cdc4403d8cbfab38a51771c0fbf07d8`, and the reviewed algebra checker/toy
frontend evidence against `73b8a2be55e0a8fae440fa09d8b38d5193eaaf92`.
The new flat manifest binds this full closure, copied inputs, new collector,
tests, protocol, checker/tests, independent auditor/tests and imported runtime
sources. The unchanged tools inventory pins Yosys, ABC, all Yosys data files,
Python/Z3 and platform. Preparation performs no new native job or solver check.

Prior V9 original measurements are copied verbatim to
`prior-v9-originals.json`. They are consumed development context, used only to
report disagreement with fresh original-arm measurements. They never select
inputs, rewrites, measurements or reported pairs.

## Fixed universal proof phase

Run **64 native frontends**, two owned workers, exactly 60 seconds per arm:

```text
read_verilog "<exact-frozen-arm-copy>"
hierarchy -check -top candidate
proc
opt_clean
check -assert
write_json "<word.json>"
```

Retain source copy, exact command/script, complete log, parsed JSON, execution
status/timing, Yosys identity and file hashes for every arm, including failures.
Reject unexpected parsed RTL input paths. No synthesis or mapping runs in this
phase. A frontend result alone is not an equivalence proof.

After all frontend jobs, evaluate all 32 pairs with the reviewed
`prove_v10_rtl_algebra.prove_pair` on the two actual JSON files at word width 32.
The checker handles its accepted unsigned equal-width cells through exact
modular affine polynomials, with exact opaque bit/mask functions and actual bit
provenance. Unsupported signedness, widths, nonlinear operations, undefined
wires, cycles or cells reject. Different normal forms mean **not proved**, not
a counterexample. Bind the checker source, both complete frontend records,
RTL/JSON/command/log hashes and proof start/completion times to each result.

This establishes universal equality of the accepted parsed original/CSD RTL
functions for every binary input. The Yosys frontend and cell semantics remain
trusted; archived lineage is authenticated, not independently retranslated by
the portable auditor. The original source-level proofs remain separately bound.
Neither this proof nor the frontend proves the technology-mapped netlist.

All **32** proofs must succeed before **any** new area job. Failed or unsupported
pairs remain in the record; any unresolved pair blocks all 64 area jobs and
leaves the complete primary result pending. There is one attempt, no automatic
retry, no timeout increase and no partial-success primary report.

## Fresh mapped measurements

After all proofs, recheck every input/source/tool binding. Write the immutable
measurement gate with all-frontend/all-proof digests and its timestamp before
submitting measurement jobs. Each arm gets a start record before invoking the
unchanged, frozen `measure_v10_csd_hardware.measure_arm`.

Run **64 fresh mapped arms**, two workers, 360 seconds per arm. Use the same
isolated combinational ports and `synth_ice40 -top candidate` defaults, carry
enabled and no DSP option. Check 100 boundary plus 2,048 seeded vectors per arm
(seed `2026101522`), at actual RTL and raw mapped LUT4/carry netlist against the
unsigned original-context oracle. These 2,148 checks are sampled mapped
verification, not universal mapped equivalence. Retain the original helper's
metric format, raw files and observed ABC/data provenance.

The global gate must follow every proof completion. Per-arm start must follow
the gate; its measurement completion must follow its start. Archive the start
record both under `measurement-start/<pair>/<arm>.json` and inside that arm's
`circuits/<pair>/<arm>/measurement-start.json`. The separate start path avoids
changing the frozen helper's exclusive arm-directory creation behavior.

Require at least 2 GiB free at startup. The scratch/attempt workspace has a
2 GiB monitored guard, checked at one-second intervals and job boundaries;
one interval of overshoot is possible. Reserve room for the raw archive before
writing the completion verdict. Resource failures cancel owned jobs and retain
partial files, primary errors and cleanup errors. Do not delete other research
data or replace resource-failed circuits. Expected evidence volume is roughly
100–250 MiB before compression, not a promised size.

## Complete report and archive

Primary quantity is `CSD LUT4 - fresh original LUT4` over all 32 cases. Publish
every constant/context pair, mean, median, range and lower/equal/higher counts
(LUT4 wins/ties/losses), with constant/context summaries. Report SB_CARRY counts
and deltas separately. Publish all 32 fresh-original versus prior-V9 LUT4/carry
differences, including zeros and RTL/tool identity flags. Do not hide drift.

Retain a raw ZIP and member hash/size manifest covering all frontend, algebra,
measurement and failure files, stage progress, gate, source proofs, collector/
checker/frozen-helper sources, input preparation, recipe, tools, exact pairs,
prior originals, parent approval, release and completion. The independent
auditor replays the shared reviewed universal checker with that dependency
disclosed, independently checks concrete word-JSON diagnostics, vectors,
mapped primitives/counts, chronology and the complete paired summary.

All outcomes are consumed hardware development evidence. Counts describe
isolated iCE40 combinational LUT4/carry resources, not ASIC area, CPU integration,
application generalization, timing, speed or power. A later timing/routing or
predictor study needs its own frozen protocol and lineage.

## Commands and release

```sh
.venv/bin/python -m pytest -q tests/test_measure_v10d_csd_hardware.py
.venv/bin/python scripts/measure_v10d_csd_hardware.py prepare \
  --root results/2026-10-15-v10d-csd-hardware
.venv/bin/python scripts/measure_v10d_csd_hardware.py validate \
  --root results/2026-10-15-v10d-csd-hardware
```

Preparation requires a fresh directory and never overwrites failed evidence.
The parent then commits the exact input/source freeze and writes
`measurement-approval.json` with status
`approved-v10d-csd-hardware-measurements`, the full 40-character `freeze_commit`,
timezone-aware `reviewed_at_utc`, and exact `preparation_sha256`,
`recipe_sha256`, `pairs_sha256`, `collector_sha256`, `checker_sha256`.
Collection verifies every prepared binding against the reviewed Git commit
before native jobs:

```sh
.venv/bin/python scripts/measure_v10d_csd_hardware.py collect \
  --root results/2026-10-15-v10d-csd-hardware \
  --approval results/2026-10-15-v10d-csd-hardware/measurement-approval.json
```

Only `attempt-0000` and two workers are permitted. A retained release marker
blocks further attempts, including after failure. V10c files are never edited.
