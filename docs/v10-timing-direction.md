# Prospective timing validation for the fixed V10 hardware pairs

**Status: direction only; no timing experiment has run.** The V10c input
preparation has source-equivalence evidence, but this follow-on study is gated
on complete, audited V10 actual-RTL proofs and fresh area measurements. It must
retain the same 32 original/CSD pairs regardless of whether their area changes
are favorable. This document authorizes neither native jobs nor changes to the
frozen V10 sources. A separate wrapper, runner, tests, tool inventory and release
must be reviewed and sealed before collecting timing targets.

The feasible question is: **what resource and routed-clock tradeoffs do these
two implementations have inside the same registered test harness?** This can
provide internal timing-model evidence. It cannot by itself establish the
unwrapped circuit's unique critical delay, FPGA-board operation, instruction
latency in a CPU or workload speedup.

## Existing flow and fixed choices

The repository already routes registered designs through
[`isaforge/core_routing.py`](../isaforge/core_routing.py). The retained
[closed-memory SoC protocol](../generated/soc/routing/protocol.json),
[published summary](../results/2026-10-13-prospective/soc/routing-summary.json)
and [PCF](../results/2026-10-13-prospective/soc/routing-common.pcf) establish the
device, target and seed choices below. The new study uses its own runner;
changing the processor-routing runner would not improve this experiment.

| Item | Prospective fixed setting |
| --- | --- |
| FPGA/package | iCE40HX8K / CT256 |
| Clock target | **12 MHz**, inherited from the existing flow, not selected from V10 outcomes |
| Routing seeds | **1, 2, 3**, paired between original and CSD for every formula |
| Threads | One per route; at most two owned workers |
| Mapping | Same sealed Yosys/ABC/data inventory as the completed V10 run; default carry, no DSP, no retiming or added arithmetic pipeline |
| Routing | Default timing-driven flow; no timing-failure override or clock-frequency sweep |
| Limits | 360 seconds per wrapped synthesis/verification arm; 180 seconds per route |

The installed nextpnr executable and IceStorm pin database exist, and read-only
hashing on 2026-10-15 matches the retained SoC records:

- Homebrew `nextpnr-ice40 0.11.1_1`, executable SHA256
  `c3df2ed2fb9be697db09e3bb5332ce2474b5437bde79e8edf9397c213048722e`.
- IceStorm 1.1 `chipdb-8k.txt`, SHA256
  `07a93c71edab68363db302a01cafde9bf9412397a63242c4a9d0de3a9b952087`.

No nextpnr/Yosys invocation was made for this direction review. The existing
nextpnr version banner omits its embedded version; retain binary hashes and the
[distribution receipt](../generated/soc/routing/tool-distribution.json), not
only that banner. Seal any runtime database/dependency records used by the new
runner and check all tool/input hashes before and after collection. The text
IceStorm database supplies package-pin provenance; it is not by itself the
nextpnr timing model.

## One common four-pin wrapper

Use `timing_top(clk, serial_in, capture, serial_out)` in every arm. One common
wrapper source is byte-identical; only the instantiated sealed `candidate`
module differs. Use one rising-edge clock on the existing global-clock pin.
Reuse four locations from the prior complete SoC PCF, with these explicit port
names; no new pin-search placement is needed:

```text
set_io clk J3
set_io serial_in L5
set_io capture T6
set_io serial_out D8
```

These are reproducible package locations, not a validated board wiring plan.
Check all four against the pinned CT256 database and require complete, unique
pin assignment for every route. Do not use `--pcf-allow-unconstrained` in a
measured run. PCF fixes location; it does not supply external arrival times,
electrical loads or output-required times. The upstream
[constraint documentation](https://github.com/YosysHQ/nextpnr/blob/main/docs/constraints.md)
separates pin placement from clock constraints; `--freq 12` is the common
default clock target.

The proposed register stages are:

```text
serial_in → two input-sampling FFs → S[63:0] launch/scan register
                                     │
                     in0=S[31:0], in1=S[63:32]
                                     │
                           sealed candidate logic
                                     │
                        Q[31:0] result register
                                     │
                         O[31:0] output serializer → serial_out
                                     ↑
                       capture → two sampling FFs
```

`S` shifts on **every** clock. Every 64-bit launch state is reachable by a
64-bit serial frame; operands are never constants, LFSR-generated restrictions
or a subset selected from measured behavior. `Q` captures the complete candidate
result on **every** clock, with no enable or mode mux between the arithmetic
output and `Q`. `O` loads the previous `Q` on a one-cycle synchronized capture
pulse and otherwise shifts out its 32 bits. There is no counter, arithmetic
result reduction tree or variable output-bit selector.

The common logical boundary is **132 FFs**: 64 launch, 32 result, 32 output and
four input/control sampling FFs. Use named, retained boundary FF instances and
one identical preservation policy in both arms; preserve no candidate-internal
arithmetic nodes. The implementation must verify the actual mapped boundary
inventory and correspondence, including unused operand bits and constant
result bits, before routes are released. If the chosen synthesis flow does not
retain the declared 132 boundary FFs in both arms, the wrapper preparation fails;
it does not silently switch wrappers, accept unequal overhead or route a
different register boundary. Test this contract on synthetic circuits first.
The proposal does not assume that a `keep` annotation alone guarantees it.

The standalone [preparer/checker](../scripts/prepare_v10_timing.py) now emits
explicit, individually named `SB_DFF` cells with `keep=1`. Its first native
preflight used only a literal XOR toy: all 132 FFs survived. The initial checker
rejected Yosys's portless `$scopeinfo` hierarchy metadata; that failed check and
the unchanged mapped toy are retained under
`generated/v10-timing-prep-synthetic-0000/`. Narrow metadata handling was added,
then the same raw netlist replay passed without a native rerun. A separate full
smoke under `generated/v10-timing-prep-synthetic-0001/` mapped literal XOR and
constant-zero toys. Both retain 132 named FFs and pass 2,148 serial transactions.
The constant-zero toy exercises preservation of unused operands and constant
result bits. These are synthetic wrapper checks, not any of the 32 study cases
or a timing result. Every actual arm still needs the same boundary checks.

If the final input frame reaches `S` at edge `n`, `Q` contains its result after
edge `n+1`. Loading `O` at edge `n+2` exposes its first output bit, followed by
31 more shifts. The testbench accounts explicitly for the two sampling stages
on external serial/capture signals. Operand loading and result readout are
test-interface overhead, identical in both arms. The candidate has one
launch-to-result register interval; serial transaction latency is not a custom
CPU instruction latency.

There is **no divided, gated, PLL or generated clock**, and no multicycle or
false-path exception on the candidate. A low-rate serial transaction does not
give the arithmetic 64 cycles to settle. All candidate paths must satisfy the
same single clock interval. Initial contents are unspecified; flush and fill
the scan chain before observing a checked result. No asynchronous-reset tree
is added. This remains a digital test harness, without a board-level
metastability or I/O timing claim.

## What timing can be attributed to the arithmetic

The primary timing endpoint is the **complete wrapper's routed single-clock
Fmax**, with the common 12 MHz pass/fail result. Retain its full critical path
and classify launch/capture cells using the mapped boundary inventory:

- `S → candidate → Q`: arithmetic path between the declared operand/result
  boundaries; retain every delay segment and endpoint.
- Scan, sampling, capture-control or `Q → O` path: wrapper-limited clock.
- Unidentified, removed or merged boundary: attribution unavailable, not an
  arithmetic timing result.

Separating `Q` from the serializer prevents capture/readout muxes from entering
the arithmetic capture boundary. Omitting a counter and output reduction tree
reduces avoidable wrapper depth. It does **not** guarantee that high-fanout
capture control or scan routing will never dominate after placement. Report
wrapper dominance for every arm/seed, including when only one arm is dominated;
do not discard such a seed or redesign its wrapper after seeing the path.

Unregistered 64-input/32-output combinational RTL with unconstrained I/O has no
meaningful register-to-register Fmax endpoint. Registering the candidate
isolates a clocked internal window even though external pins have no I/O timing
budget. The wrapper's Fmax remains a valid harness result when another internal
path dominates, but its period is then not the candidate's exact critical
period. Publish candidate-specific attribution as unavailable in those cases.
Do not subtract a wrapper-only delay or invert an arbitrary endpoint arrival
time to manufacture a datapath Fmax.

The existing detailed JSON includes clock Fmax, clock-domain critical paths
and endpoint timing information. The
[upstream report implementation](https://github.com/YosysHQ/nextpnr/blob/main/common/kernel/report.cc)
does not export every possible startpoint-to-endpoint critical path. Its
`detailed_net_timings` entries are not a substitute for the full setup/clock
model. The [timing implementation](https://github.com/YosysHQ/nextpnr/blob/main/common/kernel/timing.cc)
includes register and clock terms when producing Fmax. An exact candidate-path
endpoint analysis beyond the globally critical path would need a separately
validated, frozen extractor; it is outside this initial bounded study. Missing
arithmetic attribution must remain visible instead of being inferred from
cell-name substrings alone.

## Budget and collection contract

Run only after the fixed V10 32 source proofs, 32 universal actual-RTL pair
proofs, 64 fresh area arms and independent raw audit are complete. Bind those
exact manifests, formulas, emitted original/CSD bytes and proof records. A
small or negative area gain does not change timing eligibility: all 32 remain.

| New work | Declared count |
| --- | ---: |
| Wrapped original/CSD synthesis and functional checks | **64 arms**, synthesized once each |
| Original/CSD routes per fixed formula | **2 arms × 3 seeds** |
| Total route jobs | **192**, yielding 96 matched arm/seed comparisons |
| New model fits, rewrites, replacement cases or CPU runs | **0** |
| Clock sweeps, exploratory routing seeds or pin bootstrap jobs | **0** |

Use an independent source/mapped sequential checker for the common wrapper and
candidate behavior. For every arm, replay the same fixed V10 100 boundary plus
2,048 seeded operand pairs through complete serial load/capture/readout frames
and compare with the unsigned32 oracle. Check exact frame latency and all 32
result bits. The chosen checker is the standalone standard-library
`SequentialNetlist` state interpreter in `prepare_v10_timing.py`; it imports no
collector, emitter or existing experimental evaluator. It evaluates LUT4/carry
logic in parallel bit planes and updates all 132 FFs simultaneously at each
edge. The output-mux cones are also checked exhaustively over their permitted
local state inputs. FF clocks, names, preservation, exact scan wiring, input
sampling and result-cone dependencies are checked structurally.

Each frame has **99 rising edges**. The 64-bit operand frame is followed by
two input-sampling flush edges; edge66 completes launch, edge67 captures the
oracle result and edge68 loads the serializer. Observe its bit0, then the next
31 shifting edges. Seed `2026101524` assigns arbitrary initial FF bit planes;
the checked frame must flush them out. The original V10 operand seed remains
`2026101522`. These 137,472 checked
transactions are sampled mapped verification, not a new universal proof of
synthesis. Common-wrapper substitution relies on the existing universal
candidate equivalence plus checked identical state/control structure.

The input-only `prepare` action requires the complete independent portable area
audit, binds its preparation/completion/archive/record digests and copies every
sealed original/CSD source without editing it. It emits one common wrapper,
the fixed PCF, all 32 pair identities, the 64 arm source references, a fixed
recipe and native tool records. `validate` rechecks every flat file binding;
`--check-runtime` additionally hashes installed tools/data. Neither action
synthesizes or routes a study candidate. `synthetic-smoke` is a separate explicit
action restricted to a new `generated/v10-timing-prep-*` directory and its two
literal toys. No actual timing preparation has been executed yet.

The job wall limits sum to **16 process-hours** (64×360 + 192×180 seconds),
before preparation/audit overhead; two workers provide concurrency, not a
guaranteed completion time. Reserve a 5 GiB raw-evidence working allowance and
record actual bytes and wall/process times. These are prospective resource
limits, not observed timing or storage results. Record all 64 wrapped mappings
as new measurement work; do not present their cost as three routes of a free
pre-existing netlist. Freeze the exact simulator/checker and its cost before
release as part of this 64-arm stage.

Use owned process groups, fixed timeouts and a single released attempt.
Continue all declared independent jobs after ordinary per-job failure where
inputs remain valid. Retain partial logs and count all failures. Tool/input
mutation blocks further jobs. Never raise a limit, relax frequency, add a seed,
choose another package or retain only successful placements after outcomes.

## Complete tradeoff report and limits

For every one of the 192 slots, preserve formula/pair/arm/seed, exact RTL and
mapped-netlist hashes, complete commands/environment, PCF, binary/database
identities, synthesis counts, packed placement JSON, routed ASC, logs, timing
JSON, route status, timing-pass status and elapsed time. Distinguish mapper
failure, fit failure, route failure, timeout, 12 MHz timing failure, missing
report, invalid clock/boundary and successful route. Partial Fmax values on a
failed run remain diagnostic; no zero or imputed value replaces missing timing.

Report LUT4, FF, carry and BRAM counts from synthesis, plus packed LC, I/O,
global-buffer and RAM utilization after routing. Expected wrapper FF count is
132 and BRAM count is zero; verify rather than assume both. Counts include the
test harness and must not be called unwrapped V10 area. Packed LC combines
LUT/FF/carry packing effects and is not interchangeable with LUT4. Place these
beside the already completed bare-circuit area deltas. Do not subtract nominal
wrapper LUTs to infer an unmeasured physical datapath area. Yosys `$scopeinfo`
records are accepted only with module metadata and no ports/connections, and
are listed separately from hardware resource counts.

For each paired seed, publish original/CSD Fmax and
`ΔT = 1000/Fmax_CSD − 1000/Fmax_original` in ns, together with critical-path
classification. Primary numerical summary, if all 192 slots pass the declared
validity requirements, is mean paired `ΔT`: average the three paired deltas
within each formula, then weight all 32 formulas equally. Also show every seed,
per-formula median/range, overall extrema, and the full constant/context grid.
Three seeds describe placement sensitivity, not a population confidence
interval. If any slot is missing or invalid, the complete numerical endpoint
is pending; publish the complete failure matrix and label any available-subset
numbers secondary with their exact denominators.

Show resource improvements together with timing deterioration and vice versa.
A smaller wrapped LUT4 count does not imply a higher Fmax. If scan/control
limits Fmax, explicitly limit interpretation to the common wrapper. A later
CPU integration needs its own register boundaries, instruction response
latency/handshake, area, memory system and workload-cycle validation. This
study supplies no physical-board frequency, energy, power, ASIC-area, CPU
speedup or independent application-generalization claim.
