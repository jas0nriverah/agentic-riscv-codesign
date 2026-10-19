# Matched processor place-and-route

The baseline PicoRV32 core and the core with both combinational PCPI extensions
were actually placed and routed with nextpnr for **iCE40HX8K, CT256**. This adds
an internal clock estimate after routing to the cycle-count and synthesis
experiments. It does not measure a physical FPGA board or establish timing for
the external memory system.

## Fixed setup

The experiment uses the flattened `core_top` netlists already produced by the
core synthesis experiment. Baseline netlist SHA-256 is
`25448f1c3ca3abb4814ce49eea849fece46e1e97c9d74508cddf08165fa49edd`;
both-combinational netlist SHA-256 is
`9bc86f9f6eabaa32de86582630919dd0b189844e472c60b470f66249fe229142`.
No netlist is changed for place-and-route.

The interface contains 109 scalar I/O bits, within the package's 206 available
I/O sites. A dedicated global-clock input, **J3**, is constrained first. One
baseline-only placement with seed 0 selects the remaining pins. Every subsequent
baseline and custom run uses the same complete PCF; the custom design never
guides pin selection. There are no unconstrained I/O locations in a measured
run. PCF SHA-256 is
`f18dff390a2dcff9d58f94351295bb64ac7030fc2fa408c785ea9e67bc80f457`.
These assignments define a reproducible package experiment, not a board pinout.

All six measured runs use the same 12 MHz internal clock constraint, one thread,
default timing-driven placer/router, and matched seeds **1, 2, 3**. The tool is
Homebrew's `nextpnr-ice40 0.11.1_1` bottle and IceStorm 1.1. The binary's embedded
version string is empty, so the protocol records its SHA-256 and a separate
distribution record retains the Homebrew installation receipt. No timing-failure
override is supplied. Reported frequencies come from the routed timing report,
not the initial placement estimate or the 12 MHz target.

The tool flow and options follow the upstream
[nextpnr documentation](https://github.com/YosysHQ/nextpnr) and its
[iCE40 command implementation](https://github.com/YosysHQ/nextpnr/blob/main/ice40/main.cc).
Package pins and dedicated global-clock locations are read from the installed
IceStorm chip database; its hash is saved with the experiment.

## Routed results

All six runs fit the device, route successfully, and pass the 12 MHz internal
clock constraint.

| Seed | Baseline internal Fmax, MHz | Both combinational internal Fmax, MHz |
| --- | ---: | ---: |
| 1 | 70.602 | 74.228 |
| 2 | 66.769 | 72.495 |
| 3 | 66.609 | 68.890 |
| Median | 66.769 | 72.495 |
| Minimum | 66.609 | 68.890 |

These three seeds show no internal clock penalty for this particular extension
implementation; they do not establish universal timing improvement. The packed
logic-cell count is 1625 for baseline and 1726 for custom, an increase of 101
cells (6.22%). Both use four of 32 RAM blocks, 109 of 206 I/O sites, and four of
eight global buffers. Packed logic cells include LUTs, flip-flops, carry-chain
legalization and packing effects, so their count differs from synthesis LUT4
counts (1488 and 1570).

## External memory boundary

The DUT includes the processor and PCPI extension. Its internal block RAMs hold
the register file. Program/data RAM and peripherals remain outside the DUT.
Simulation supplies a zero-wait external native memory interface. The routed
netlist exposes `mem_rdata` and `mem_ready` as inputs and
`mem_addr`, `mem_wdata`, `mem_wstrb`, `mem_valid`, and `mem_instr` as outputs.

No external RAM timing model, board trace delay, input arrival constraint,
output required-time constraint, electrical loading, or device measurement is
included. nextpnr reports those ports as asynchronous endpoints. The critical
asynchronous-input-to-register delays range from 12.684 to 13.718 ns for baseline
and 13.537 to 13.953 ns for custom. Register-to-asynchronous-output delays range
from 3.882 to 4.429 ns for baseline and 7.949 to 8.223 ns for custom. These are
on-FPGA path estimates; the endpoints can also include reset and debug I/O.
They are **not** a closed timing budget for an external RAM transaction.

Cycle savings at a shared feasible system clock can be reported directly from
the validated processor simulation. Calculating `cycles / routed internal Fmax`
gives a conditional core-only estimate; it must not be presented as achieved
whole-system execution time. A complete system requires realistic memory
integration, I/O delays and timing closure at the chosen clock, followed by
board validation for a physical performance claim.

## Reproduce and inspect

```sh
brew install nextpnr-ice40
.venv/bin/python -m isaforge.core_routing \
  --synthesis-dir generated/core/synthesis \
  --output-dir generated/core/routing-matched \
  --chipdb /opt/homebrew/Cellar/icestorm/1.1/share/icestorm/chipdb/chipdb-8k.txt \
  --frequency 12 --seeds 1 2 3
```

Locate the equivalent `chipdb-8k.txt` under your installed IceStorm distribution
on another machine. The runner checks identical port signatures, complete
unique pin constraints, source netlist stability, device fit, routed clock
constraint consistency and successful process exit. It retains bootstrap
placement, common PCF, every command/log, detailed timing/utilization JSON and
the routed ASCII configuration for each seed.

`generated/core/routing-matched/protocol.json` fixes the experiment before its
six measured routes. `runs.json` contains per-run outcomes and artifact hashes;
`summary.json` includes all outcomes and per-configuration frequency ranges.
`tool-distribution.json` records the separately collected distribution receipt.
An earlier exploratory baseline placement/route under
`generated/core/routing` used a different clock pin; it is not included in this
matched comparison.

Nine tests validate chip-database interpretation, package mapping completeness,
duplicate/unplaced I/O rejection, device-fit versus clock checks, and rejection
of missing, nonfinite or incompatible timing reports. They also reject claims
of a closed on-chip-memory boundary when data/memory inputs remain exposed.
The six real routed runs
provide integration evidence beyond these parsing tests.

The runner additionally supports a fully internal memory wrapper with
`--top soc_top --configurations baseline custom
--memory-boundary onchip_initialized_memory`. That mode requires exactly
`clk` and `resetn` as inputs, with status outputs and no exposed native memory
interface. Its evidence is kept in a separate output directory; it cannot be
mixed with the external-memory core results above. The exact original runner
source for the core experiment is retained as `runner-source.py` alongside its
protocol hash.
