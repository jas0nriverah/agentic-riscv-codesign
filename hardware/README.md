# Measured PicoRV32 custom instructions

This page documents the core with an external memory model. The later [closed-memory SoC experiment](https://github.com/jas0nriverah/agentic-riscv-codesign/blob/b64716a2b94b332fdbced677869620bb949c073d/docs/soc-integration.md) and [matched SoC routing](https://github.com/jas0nriverah/agentic-riscv-codesign/blob/b64716a2b94b332fdbced677869620bb949c073d/docs/soc-routing.md) include on-chip RAM; [current results](https://github.com/jas0nriverah/agentic-riscv-codesign/blob/b64716a2b94b332fdbced677869620bb949c073d/docs/results.md) keeps their cycle and resource counts separate.

ISAForge now executes two extracted formulas as real instructions on the
official PicoRV32 processor. The experiment measures both a controlled formula
recurrence and a source-modified complete Embench CRC32 benchmark. These are
actual Verilator clock cycles and processor counter reads. The cycle ratios
below assume equal clocks; FPGA routing and achievable clock frequency are a
separate experiment.

## Core and protocol

The upstream source is pinned to
[`ef203c2b0a3fb793280f5114941416c425c5b461`](https://github.com/YosysHQ/picorv32/tree/ef203c2b0a3fb793280f5114941416c425c5b461).
PicoRV32 has a documented two-register-input PCPI interface, so it matches the
extractor's nonbranching, two-input, one-output instruction contract. The core
source is used unchanged. It is a small multicycle processor, making results
specific to its instruction scheduling and shift implementation.

The [official PCPI documentation](https://github.com/YosysHQ/picorv32/blob/ef203c2b0a3fb793280f5114941416c425c5b461/README.md#pico-co-processor-interface-pcpi)
describes instruction/operand delivery, `ready`/`wr` result acceptance, and the
16-cycle timeout. `pcpi_candidates.v` asserts `wait_req` immediately on a
recognized instruction and holds it until the response is ready. Latency 0 is
combinational; latency 1 registers the result; the 4/16/24-cycle configurations
delay the same result to expose protocol cost. These are **PCPI response wait
cycles**, not total instruction cycles. Simulation checks exactly one handshake
per custom instruction, `latency` wait cycles per instruction, and
`latency + 1` cycles with PCPI valid. The 24-cycle case also exercises correct
timeout suppression.

| Instruction | Exact extracted formula | Encoding | Original kernel operations |
| --- | --- | --- | --- |
| Formula 0 | `slli(andi(xor(in0,in1),255),2)` | custom-0 `0x0b`, funct7=1, funct3=0 | xor, andi, slli |
| Formula 1 | `xor(in0,srli(in1,8))` | custom-0 `0x0b`, funct7=1, funct3=1 | srli, xor |

Both formulas occur in CRC32's `benchmark_body`; neither is an identity nor a
random-generator-only candidate. The processor has the 32-register dual-port
register file, two-stage iterative shifts, 32-bit counters, and no compressed,
multiply/divide, or IRQ extension. Registers start at zero. The memory model
has 64 KiB of RAM and an immediate native-interface response (`mem_ready=1`),
with byte write strobes. Both configurations use the same model and eight reset
cycles. The synthesized DUT contains the processor plus PCPI unit and external
memory ports; it excludes external RAM and peripherals.

## Controlled recurrence

`core_start.S` retains the exact baseline ALU operations or replaces them with
one `.insn`, deleting instructions instead of patching NOPs. Both inputs vary:
each operation feeds its result into the next iteration, and the second input
increments modulo 2^32 by `0x9e3779b9`. The measured window includes the leaf
function call, loop setup, control, return, and surrounding counter-window
instructions. The zero-length cases verify identical fixed overhead, and the
instruction delta must be exactly 2N or N for formulas 0 and 1.

There are three seeded input pairs for each length 0/1/8/64/256/1024, giving 36
timed comparisons per latency. Each firmware also performs 36 boundary-pair
and 128 seeded random direct checks for each formula (328 checks). Every result
is checked by C firmware and independently by the host integer oracle. The
saved records include all inputs and results.

| PCPI response latency | Formula 0, 1024 iterations | Formula 1, 1024 iterations |
| --- | --- | --- |
| Baseline ALU sequence | 23,632 cycles | 20,555 cycles |
| 0 | 15,440 (1.5306× cycle ratio) | 15,435 (1.3317×) |
| 1 | 16,464 (1.4354×) | 16,459 (1.2489×) |
| 4 | 19,536 (1.2097×) | 19,531 (1.0524×) |
| 16 | 31,824 (0.7426×) | 31,819 (0.6460×) |
| 24 | 40,016 (0.5906×) | 40,011 (0.5137×) |

The 16/24-cycle implementations execute fewer instructions and take more
cycles. This confirms that instruction-saving merit is insufficient to establish
processor performance. It does not establish a ranking disagreement between
different formulas across the eight benchmark workloads.

## Complete CRC32 benchmark

The benchmark source is the pinned Embench submodule
`0466a18e4f6b47e19598d7c6ba72916d54b68f65`. The stock baseline compiles the
original `crc_32.c` and `beebsc.c`. Custom variants retain the source, table,
random generator, and repetitions and replace only the `UPDC32` macro with an
inline helper issuing formula 0, formula 1, or both. This is source-level
instruction lowering; it is not a binary rewrite of the previously traced ELF.
The helper compiled without custom instructions produces identical cycles,
instruction counts, and results to the stock baseline.

All variants use GCC 15.2.0, RV32I/ILP32, `-O2`, `CPU_MHZ=1` and the same
compile/link flags. RV32I changes the original measured Spike pilot's RV32IM
compiler target. GCC implements the random generator's constant multiplication
as shifts, adds, and subtracts; no `__mulsi3` call appears. Consequently these
cycle/instruction counts must not be compared directly with the earlier RV32IM
trace as though they were the same binary or processor configuration.

The timed call is the complete upstream `benchmark()`: 170 repetitions of 1,024
random-byte CRC updates, including random generation, calls, table loads, loops,
and control. A one-repetition warmup and an extra full-checksum calculation run
outside the measured window. `CPU_MHZ=1` sets upstream repetition count, not a
physical clock rate. Every variant passes upstream `verify_benchmark` (11433)
and the independent bitwise oracle's full 32-bit checksum **0x65842ca9**.

| CRC32 variant | Response latency | Cycles | Instructions | Baseline/custom cycle ratio |
| --- | --- | --- | --- | --- |
| Stock baseline | — | 27,685,314 | 6,094,532 | 1.0000 |
| Formula 0 | 0 | 26,292,674 | 5,746,372 | 1.0530 |
| Formula 1 | 0 | 26,814,914 | 5,920,452 | 1.0325 |
| Both | 0 | 25,422,274 | 5,572,292 | 1.0890 |
| Formula 0 | 1 | 26,466,754 | 5,746,372 | 1.0460 |
| Formula 1 | 1 | 26,988,994 | 5,920,452 | 1.0258 |
| Both | 1 | 25,770,434 | 5,572,292 | 1.0743 |

For each response latency, stock firmware runs identically on the baseline
core and extended core. Custom instruction handshakes include the measured
170 repeats plus the two untimed repeats: 176,128 for a single formula and
352,256 for both. In the measured window, formulas 0 and 1 delete respectively
348,160 and 174,080 instructions; together they delete 522,240. Those are
observed counter differences. A general source rewrite can alter compiler
allocation and scheduling, so the experiment does not assume that every
future source-level lowering has the extractor's exact binary saving count.

## Whole-core synthesis

Yosys 0.69+post (`143eb14f9cc55d6f8927e68523b0c9d2166ed02c`) maps the complete
core and extension with `synth_ice40`, followed by `check -assert`. The generic
mapping has no device/package placement or physical timing result. The four
`SB_RAM40_4K` resources in each configuration implement the internal register
file; external program/data RAM is outside this DUT.

| Core | Response latency | LUT4 | Delta | Carry | Flip-flops | RAM4K |
| --- | --- | --- | --- | --- | --- | --- |
| Baseline | — | 1,488 | 0 | 273 | 531 | 4 |
| Formula 0 | 1 | 1,619 | +131 | 305 | 620 | 4 |
| Formula 1 | 1 | 1,621 | +133 | 305 | 620 | 4 |
| Both | 1 | 1,625 | +137 | 305 | 620 | 4 |
| Both | 0 | 1,570 | +82 | 275 | 555 | 4 |

The earlier isolated combinational circuits used only 8 and 24 LUT4s. Whole
processor counts include PCPI decode, operand/result paths, response state,
and changes in global synthesis mapping. The isolated counts do not predict
the integrated increment by simple addition. LUT4 is a resource count, and
carry/flip-flop/RAM resources are reported separately.

## Reproduce and inspect

Run from the repository root with Verilator and Yosys on PATH:

```sh
python -m isaforge.core_experiment \
  --output-dir generated/core \
  --core-dir ../toolchains/picorv32 \
  --toolchain-prefix ../toolchains/xpack-riscv-none-elf-gcc-15.2.0-1/bin/riscv-none-elf-
python -m pytest -q tests/test_core_experiment.py
```

An absent core directory is cloned and checked out at the pinned revision;
an existing checkout must have that exact revision and be clean. The default
run includes all five recurrence latencies, both complete-benchmark latencies,
and all five synthesis configurations. `--skip-crc32` or `--skip-synthesis`
omits those stages explicitly.

`generated/core/summary.json` records source/compiler hashes, core settings,
all comparisons, full benchmark results, synthesis counts, and limitations.
`commands.json` records exact argument arrays, log paths, tool exits, and wall
durations. The directory also preserves copied licensed sources, both firmware
ELFs and binaries, complete disassemblies, raw simulation outputs, parsed input
records, synthesis scripts/logs/netlists, and negative-control logs. Verilator
5.050 was used for the recorded run.

Validation rejects missing/reordered records, checksum failures, unexpected
instruction deletion, different inputs, different zero-work overhead, and
incorrect PCPI handshakes or latency. The custom firmware traps on a baseline
core. Wrong funct7, funct3, and opcode encodings trap before a success store on
every extended latency configuration (15 additional negative controls).
The 14 unit tests exercise the evidence gates, including corruption of high
CRC bits that would pass upstream's low-15-bit check. These checks and sampled
firmware vectors are not a formal proof. No result here claims eight-workload
integrated speedup, energy reduction, or actual wall-time speedup.
