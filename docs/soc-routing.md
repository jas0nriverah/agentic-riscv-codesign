# Routed closed-memory SoC comparison

The baseline and custom PicoRV32 SoCs were placed and routed for **iCE40HX8K
CT256** with initialized instruction/data memory on the FPGA. All six runs
fit, route and pass the same 12 MHz clock constraint. This resolves the external
RAM timing boundary in the earlier [core-only routing](core-routing.md).
Clock frequencies remain nextpnr timing-model estimates, not measurements on
a physical FPGA board.

## Matched experiment

Both DUTs use the same synchronous 8 KiB byte-write memory implementation,
the same CPU configuration and memory handshake latency, and combinational
PCPI response latency 0. The baseline firmware runs full Embench CRC32;
custom firmware substitutes the two validated instruction fusions. Only
`clk` and `resetn` are inputs. Six outputs expose trap, done, passed, fault,
report strobe and report bit. No memory address, data or ready ports leave the
SoC. Twenty block RAMs, including 16 program/data blocks and four register-file
blocks, are clocked by the DUT clock and included in timing analysis.

Baseline netlist SHA-256 is
`eea94a48070a467cff1d70d4a3668231bd5be26b970e09de79dddd61628bd43b`;
custom netlist SHA-256 is
`448d7d4a6f6677a7d2cedd27c82f7273a09c630e648ac09c896314c35a8d0a1c`.
Both were frozen before routing. The runner checks their stability during all
six runs, matches their port signatures and rejects a closed-memory claim if
any external memory interface or non-reset data input is exposed.

A dedicated clock input on **J3** is fixed first. Baseline-only seed-0 placement
chooses seven remaining pins; all measured baseline and custom runs then use
the same eight-pin PCF. PCF SHA-256 is
`90f30f5e0ab7657903b7e0ef8e094c5217eaffcb56697c3d4887deb30b04f010`.
Matched seeds **1, 2, 3**, one thread, device/package, clock target, timing-driven
placement and default router are identical. Homebrew distributes the tool as
`nextpnr-ice40 0.11.1_1` with IceStorm 1.1; the executable and database hashes,
installation receipt, commands, logs, detailed routed timing reports and
ASCII configurations are retained. No timing-failure override is used.

## Cycles, clocks and conditional elapsed time

Both implementations pass the complete checksum **`0x65842ca9`** and Embench
self-check. The validated benchmark region takes **32,387,382 cycles** on
baseline and **29,602,102 cycles** on custom. This is 8.60% fewer cycles, or a
baseline/custom cycle ratio of **1.09409**. At a shared feasible clock, the ratio
applies directly. For the fixed 12 MHz timing target, the benchmark-region
estimates are 2.69895 and 2.46684 seconds. These exclude startup, warmup, result
reporting and the independent final checksum calculation outside the region.

| Seed | Baseline routed Fmax, MHz | Custom routed Fmax, MHz | Conditional time ratio, baseline/custom |
| --- | ---: | ---: | ---: |
| 1 | 71.803 | 67.074 | 1.02203 |
| 2 | 70.897 | 67.454 | 1.04095 |
| 3 | 69.080 | 72.005 | 1.14041 |
| Median | 70.897 | 67.454 | 1.04095 |

Each time ratio above is `(baseline cycles / baseline Fmax) /
(custom cycles / custom Fmax)` for the same seed. The custom SoC has a clock
penalty in two seeds, yet the cycle savings remain larger in each of these
three comparisons. Report every seed: choosing only seed 3 would overstate
the result. Three placements do not establish a statistical population or
guarantee a clock advantage on other designs.

The packed logic-cell count increases from **1870 to 1961**, or 91 cells
(4.87%). Both consume 20 of 32 block RAMs, eight of 206 I/O sites and four of
eight global buffers. Synthesis LUT4 counts, a different unit, are 1633 and
1704 (+71, or 4.35%). These measurements concern this implementation and
benchmark, not superiority over all published custom-instruction systems.

## Timing and validation limits

All processor and on-chip RAM synchronous paths are in the routed DUT. The
clock report has one clock domain. Reset arrival/release and status output
observation remain asynchronous, with no board trace/load constraints.
A physical implementation must synchronize reset release and observe the
result interface correctly. The experiment does not measure board frequency,
temperature, power, external I/O electrical behavior or silicon runtime.

Functional cycle measurements and routed clock estimates are different kinds
of evidence. Their combination supplies a conditional FPGA timing estimate,
while the common-clock cycle reduction is established by matched simulation.
The source-control firmware and stock-firmware-on-custom-core controls match
baseline cycles, instructions and results, so the observed cycle change can be
attributed to the validated fusions within this experiment's scope.

## Reproduce and inspect

After regenerating and verifying the SoC simulation/synthesis experiment:

```sh
.venv/bin/python -m isaforge.core_routing \
  --synthesis-dir generated/soc/synthesis \
  --output-dir generated/soc/routing \
  --chipdb /opt/homebrew/Cellar/icestorm/1.1/share/icestorm/chipdb/chipdb-8k.txt \
  --top soc_top --configurations baseline custom \
  --memory-boundary onchip_initialized_memory --frequency 12 --seeds 1 2 3
```

`generated/soc/routing/protocol.json` records the setup before measured routes.
`summary.json` and `runs.json` preserve all six outcomes.
`timing-cycle-comparison.json` joins routed clocks to the independently
validated benchmark cycles and records the hashes of both source reports.
The exact runner source is copied beside its hash as `runner-source.py`.
The detailed report and routed ASC for every seed permit inspection of
utilization, clock paths and actual device routing.
