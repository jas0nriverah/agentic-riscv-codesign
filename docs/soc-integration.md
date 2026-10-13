# Complete PicoRV32 SoC with on-chip synchronous memory

The complete CRC32 benchmark now executes on a small closed-memory SoC. Both
program/data memory and the processor register file map to iCE40 block RAM,
and no external memory address, data, or acknowledgement ports leave the
design. This allows the [matched FPGA routing experiment](soc-routing.md) to
include processor-to-memory timing instead of assuming an unconstrained
external RAM response.

## Matched processor and firmware

[`soc_top.v`](../hardware/soc_top.v) instantiates the same pinned, unchanged
PicoRV32 source and configuration as the [earlier core experiment](../hardware/README.md):
RV32I, dual-port register file, iterative two-stage shifts, 32-bit counters,
and no multiply/divide, compressed, or IRQ support. The custom configuration
enables the same two exact CRC32 formulas through combinational PCPI response
latency 0. The stock configuration disables PCPI. All other CPU parameters
match, except the stack address now fits the on-chip RAM.

The original CRC32 source and a custom source macro are compiled with the same
GCC flags and upstream 170 repetitions of 1,024 CRC updates. Random generation,
table loads, calls, and control remain inside `benchmark()`. One warmup and an
extra full-checksum calculation execute outside the measured counter window.
Every measurement passes the upstream low-15-bit self-check (11433) and an
independent full 32-bit CRC oracle (**0x65842ca9**). The RV32I port implements
the random generator's constant multiplication using GCC-generated shifts,
adds, and subtracts; the earlier RV32IM Spike trace remains separate evidence.

The stock binary is 1,688 bytes; custom is 1,664 bytes. `.data` and `.bss` end
at addresses 1,692 and 1,668 respectively. Linker assertions reserve at least
4 KiB for the stack, which starts at **0x2000** and grows downward. A bytewise
comparison with each prior core-only CRC binary shows that only two bytes in
the first instruction change: `lui sp,0x10` becomes `lui sp,0x2`. Every other
program byte is identical. The prior core experiment's artifacts are preserved.

## Actual synchronous RAM and result interface

The initialized RAM is 2,048 words of 32 bits (**8 KiB**), shared by instruction
fetches and data accesses. Four byte write strobes support byte, halfword, and
word stores. The generated `.hex` initializes the entire RAM, including zero
fill for BSS, unused locations, and stack space. Yosys consumes the same image
and the same elaborated top source used by Verilator.

The memory controller samples a valid RAM request at a rising edge, performs
the synchronous read/write, and asserts the registered native `mem_ready`
together with the read result. The CPU accepts that response at the following
edge. This is the same RTL in baseline and custom simulation and synthesis;
there is no host-provided combinational memory response. Reset is held for
eight clock cycles. Reset clears controller/status state and the processor;
it does not reload the initialized RAM image.

Only eight scalar pins leave the SoC: input `clk` and `resetn`, plus output
`trap`, `done`, `passed`, `fault`, `report_strobe`, and `report_bit`. Firmware
MMIO result writes serialize one word as 32 least-significant-bit-first bits,
one bit per rising edge while `report_strobe` is high. A new write waits until
the serializer is idle. The terminal status write asserts `done` and `passed`;
an unsupported memory access asserts `fault`. All result reporting occurs
after the timed benchmark window. The host reconstructs the five words through
these pins: full checksum, upstream result, cycles, instructions, and self-check.

## Measured cycles and complete-SoC resources

| Configuration | Benchmark cycles | Instructions | LUT4 | Carry | Flip-flops | BRAM4K |
| --- | --- | --- | --- | --- | --- | --- |
| Stock baseline | 32,387,382 | 6,094,532 | 1,633 | 295 | 655 | 20 |
| Two custom instructions | 29,602,102 | 5,572,292 | 1,704 | 297 | 679 | 20 |
| Source wrapper, no fusion | 32,387,382 | 6,094,532 | 1,633 | 295 | 655 | 20 |

The observed reduction is **2,785,280 cycles** and **522,240 instructions**,
with a baseline/custom cycle ratio of **1.09409** (8.60% fewer cycles). Whole
SoC synthesis adds 71 LUT4s, two carry cells, and 24 flip-flops. Sixteen BRAM
blocks implement program/data RAM and four implement the register file; all
20 have read and write clocks connected directly to the SoC clock. The
resource counts fit the HX8K limits, and the separate routing experiment
confirms actual place-and-route feasibility.

The source wrapper without custom instructions has identical full results,
cycles, instruction counts, and protocol statistics to stock. Its binary is
not byte-identical: the compiler swaps the two XOR input register fields in
two commutative instructions. That distinction is recorded explicitly rather
than treating execution equality as binary equality. Stock firmware running
on the extended core also reproduces the baseline exactly.

These cycle counts differ from the earlier immediate-external-memory core
experiment because the on-chip memory has a synchronous response. Compare
baseline and custom within this SoC experiment. For elapsed-time implications,
use the [paired routed clocks](soc-routing.md), which report both a common
feasible clock comparison and conditional timing-model comparisons. No
physical FPGA board performance measurement is claimed.

## Checks and reproduction

The RAM self-check performs a full-word store, a byte overwrite, a halfword
overwrite, and signed/unsigned loads. The resulting word must be `0x00efdd44`.
A separate program writes address **0x2000**, immediately outside the RAM, and
must finish with a hardware bounds fault before a success store. Both run on
the same top and response controller as CRC32.

Ten unit tests check little-endian initialization and zero fill, stack
reservation, complete CRC/report validation, internal BRAM clock connections,
exact program-memory inference, resource bounds, and rejection of a top that
reintroduces external memory pins. They also reject changes to prior firmware
beyond the documented initial stack instruction. These checks are testing;
they are not a formal equivalence proof of technology mapping.

Run from the repository root with the pinned PicoRV32 checkout and installed
Verilator/Yosys:

```sh
python -m isaforge.soc_experiment \
  --output-dir generated/soc \
  --core-dir ../toolchains/picorv32 \
  --toolchain-prefix ../toolchains/xpack-riscv-none-elf-gcc-15.2.0-1/bin/riscv-none-elf-
python -m pytest -q tests/test_soc_experiment.py
```

`generated/soc/summary.json` preserves the CPU/memory/report configuration,
source/tool/firmware hashes, prior-binary comparison, all controls, cycle
results, and synthesis counts. Adjacent directories contain complete commands
and logs, copied licensed sources, compiled ELFs/binaries, initialized memory
images, disassemblies, raw serial-report simulation results, and synthesis
scripts/logs/netlists. The baseline and custom netlists used for routing are
`generated/soc/synthesis/baseline/ice40-netlist.json` and
`generated/soc/synthesis/custom/ice40-netlist.json`; routing verifies their
hashes remain unchanged.

This is one source-modified complete benchmark on one processor and FPGA
target. It does not establish an eight-workload performance predictor,
cross-processor portability, energy savings, or hardware-board timing.
