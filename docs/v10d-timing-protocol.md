# V10d registered-harness timing protocol

This prospective timing stage consumes the completed, independently audited
[V10d area study](../results/2026-10-15-v10d-csd-hardware/independent-audit.json).
It measures the exact same 32 formulas and their one fixed CSD implementation.
It changes no original-RTL predictor labels and fits no model. The completed
area result motivated timing measurement; it is not held-out discovery evidence.

## Inputs and release

New collector: [measure_v10d_timing.py](../scripts/measure_v10d_timing.py).
The explicit V10d adapter requires exact completed preparation/completion hashes,
64 successful word frontends, 32 universal algebra proofs, 64 fresh area arms,
no failures, and a complete passing portable raw audit from the bound auditor.
It binds the entire area preparation closure, approval/release, all frontend,
proof, area-arm, gate and summary ledgers, raw archive and member manifest,
and independent audit. The prior incomplete V10c SAT outcome stays unchanged. The two separately authorized
[synthetic route preflights](../results/2026-10-15-v10d-timing-preflight/README.md),
including both immutable archives, historical reviews and the final
test-source review, are also bound. They contain two toy routes and zero
study jobs; earlier reviews retain their historical test hashes.
No filtering, alternate rewrite, replacement, feature extraction or new fit.

Preparation copies exactly 64 sealed candidate RTL files, the identical
[reviewed wrapper](v10-timing-direction.md), PCF, and frozen timing recipe.
It uses the unchanged `prepare_v10_timing.wrapper_rtl`, `SequentialNetlist`,
`check_transactions`, `recipe`, `timing_tools` and tool validation functions.
Its new adapter, collector, tests, protocol, portable auditor and tests, path
checker and tests, and complete imported support-module closure are flat-bound.

The tool inventory retains the area Yosys/ABC/data/Python/solver inventory and
nextpnr binary, install receipt, HX8K chip database and fixed package pins.
A read-only `otool -L/-l` inventory adds every resolvable transitive non-system
nextpnr dynamic library, install-name edge, alias, resolved path and SHA-256.
Unresolved/ambiguous dependencies reject preparation. Runtime validation checks
all frozen file hashes and alias resolutions before release, at bounded job
submission, at the phase gate and after collection. System libraries, macOS
loader/kernel and host environment remain outside a hermetic-image claim.
Native children inherit only the frozen owner's sanitized environment.

Parent alone prepares, reviews and releases the actual cohort, for example:

```sh
.venv/bin/python scripts/measure_v10d_timing.py prepare \
  --root results/2026-10-15-v10d-timing
.venv/bin/python scripts/measure_v10d_timing.py validate \
  --root results/2026-10-15-v10d-timing
```

Preparation is input-only. Parent commits its manifest and every bound byte,
then writes `measurement-approval.json` with status
`approved-v10d-timing-measurements`, `freeze_commit`, UTC `reviewed_at_utc`,
`preparation_sha256`, `recipe_sha256`, `pairs_sha256`, `collector_sha256` and
`sequential_checker_sha256`. Collection Git-verifies all inputs against that
commit; no implicit approval or release from elapsed time.

```sh
.venv/bin/python scripts/measure_v10d_timing.py collect \
  --root results/2026-10-15-v10d-timing \
  --approval results/2026-10-15-v10d-timing/measurement-approval.json
```

One `attempt-0000` only. Existing release, measurements or scratch directories
reject a retry. No bootstrap run, seed replacement or relaxed clock is allowed.

## Fixed native work and phase gate

First run all 64 independent wrapped syntheses, at most two owned jobs together,
360 seconds wall time per arm. The exact script separately reads the sealed
candidate and common wrapper, runs `synth_ice40 -top timing_top`, `check -assert`
and writes the mapped JSON. No retiming, DSP option, arithmetic pipeline,
clock division or alternative synthesis flags are introduced. Authenticate
logged Yosys/ABC and share-library paths against the pinned tool inventory.

Every successful mapped arm must contain exactly the named 132 boundary
`SB_DFF`s, zero BRAM and only reviewed LUT4/carry/FF primitives (the narrow
portless `$scopeinfo` metadata exception remains nonhardware). The unchanged
sequential checker independently validates wiring, clock, state boundaries and
serializer mux functions, then checks all 2,148 fixed transactions at 99 rising
edges per parallel frame. Operands use seed 2026101522 and initial state uses
2026101524. An arm failure still receives an explicit sequential failure record.
This sampled mapped check does not become a universal synthesis proof.

Only all 64 successful mappings and all 64 passing sequential checks release
`route-gate.json`, binding both ledgers and the gate UTC timestamp. No route is
submitted earlier. Route records preserve start and end timestamps and gate hash.

Then run exactly 192 routes: every arm with paired seeds 1, 2 and 3, 180 seconds
wall time each, at most two processes, one thread each. Fixed device iCE40HX8K,
package CT256, 12 MHz, and pins clk J3, serial_in L5, capture T6, serial_out D8.
Use `--hx8k --package ct256 --json ... --pcf ... --asc ... --report ...
--detailed-timing-report --write ... --freq 12 --seed N --threads 1`.
No timing-failure override or unconstrained-PCF flag. Preserve full logs,
critical paths, detailed net timings, packed JSON and ASC even on failure.
A nonzero exit, timeout, absent/invalid output or changed target is a failure;
a valid reported Fmax below 12 MHz is retained as a measured timing miss if
the tool returns success. No missing slot is silently replaced.

Packed output must retain 132 enabled FFs, four IOs and one global buffer,
only the expected packed LC/IO/GB types, zero RAM/PLL, the exact device,
frequency and one-thread settings, agreement with native resource counts, and unique actual packed IO
PACKAGE_PIN/top-port/BEL locations matching all four fixed package pins.
Actual topclock IO→global-buffer→all 132 positive-edge FF clocks and the
reported Fmax clock net alias must agree; this is mandatory even when path
attribution is unavailable. The conservative reviewed path checker authenticates mapped boundary identities,
packed connectivity and reported timing endpoints. Classification is
`datapath-boundary`, `wrapper-boundary` or `unknown`; unknown attribution does
not erase a valid whole-harness Fmax. Preserve its full reason and certificate.
Do not infer arithmetic delay from the global critical path or subtract a
wrapper estimate. Asynchronous IO paths are not arithmetic register paths.

## Endpoints and retained evidence

Primary: for each formula and seed compute
`1000/Fmax_CSD - 1000/Fmax_original` ns; average its three paired seed deltas,
then report the mean, median, range and lower/equal/higher counts over all 32
formulas with equal weight. Report fixed constant/context groups. Seeds are
repeated implementation realizations, not 96 independent application samples.
All 192 valid routes and all prior gates are necessary for a complete primary.
Any incomplete route, provenance failure or resource violation leaves primary
`null` and publishes the exact 192-slot failure matrix and all available records.
No bootstrap confidence interval or selected-subset headline.

Retain all 96 per-seed pairs and 32 formula means, per-arm Fmax/reciprocal
period and 12 MHz pass/fail, wrapped mapped LUT4/carry/132FF, bare V10d
LUT4/carry separately, and packed LC/IO/GB/RAM resource counts. The wrapper
changes the mapping context; do not subtract bare area or equate bare LUT
savings with packed resource savings. Existing original-target model labels
remain original-target labels. No CPU instruction latency, board throughput,
power, ASIC or population claim follows from this harness.

Root evidence: `preparation.json`, `measurement-approval.json`,
`timing-release.json`; `measurements/attempt-0000/` contains `mappings.json`,
`sequential-checks.json`, optional `route-gate.json`, `routes.json`,
`summary.json`, `completion.json`, `raw-evidence.zip` and its SHA-256 member
manifest. Every raw mapping/check/route record, exact RTL/wrapper/PCF, commands,
logs, mapped netlist, report, packed JSON, ASC, release and helper source is
archived under `generated/v10d-timing/attempt-0000/`. No native rerun is needed
for the portable auditor's evidence replay; sequential and path checks share
reviewed helpers, explicitly disclosed.

Startup needs at least 8 GiB free. Scratch plus stage is monitored against a
4 GiB bound every second/job boundary, with conservative archive reservation.
The expected raw volume is approximately 0.3–1 GiB plus 64 mapped JSONs;
actual volume remains recorded. On guard/interruption/provenance failures,
cancel only owned process groups, preserve primary and cleanup errors, retain
partial evidence and mark the study incomplete. Never delete unrelated data.
Maximum native budgets are 64×360 + 192×180 seconds, approximately16 process
hours before bounded checks and orchestration, with two-job concurrency.
