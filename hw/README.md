# hw/: the hardware track

The overview, the measurement protocol, the results and the encoding table are in the [root README](../README.md). This file keeps the details that only matter when working inside `hw/`.

## Partial make targets

```
make hw-sim             # Verilator runs only  -> generated/hw/runs/<program>.json
make hw-synth           # Yosys synth_ice40    -> generated/hw/synth/
make hw-route           # nextpnr-ice40 seeds  -> generated/hw/route/seed<N>/
make hw-pcf             # regenerates synth/core_top.pcf (never part of a comparison; ask before re-pinning)
```

`hw-baseline`, `hw-measure`, `hw-sweep`, `hw-dryrun` and `hw-critpath` are described in the root README. Every rule lives in `hw.mk`, `dryrun/dryrun.mk` and `engine/engine.mk`, included from the top-level Makefile.

## Tools

| Tool | Version | Source |
|---|---|---|
| riscv-none-elf-gcc | xPack 15.2.0-1 | `~/tools/xpack-riscv-none-elf-gcc-15.2.0-1` |
| Spike | `f8a060b7bea8da6f738f193ed1b66b665978d092` (the ML branch's recorded revision) | built from source into `~/tools/spike` |
| dtc (needed by Spike) | 1.8.1 | Homebrew |
| Verilator, Yosys, nextpnr-ice40 | 5.053-devel, 0.70+157, 0.11.1-65 | OSS CAD Suite 2026-10-19, `~/tools/oss-cad-suite` |

The Makefile uses `riscv64-unknown-elf-` when it is on `PATH`, and xPack's `riscv-none-elf-` otherwise. Set `RISCV_PREFIX=` to choose one. `src/candidates.py` hard-codes `riscv64-unknown-elf-objdump`; a symlink to xPack's objdump under `~/tools/bin` satisfies it. The OSS CAD Suite Verilator needs a C++14 or newer compiler and Apple clang defaults to C++98, so the build passes `-std=c++17`.

## What differs from the ML branch's setup

- **ISA:** rv32im, not rv32i. `ENABLE_MUL=1` and `ENABLE_DIV=1` turn on PicoRV32's sequential multiplier and divider inside its PCPI path. `ENABLE_FAST_MUL=0`. All other parameters are the ML branch's (`TWO_STAGE_SHIFT`, dual-port register file, no compressed instructions, no IRQ, counters on).
- **Programs:** main's exact build, not the ML branch's 64 KiB rv32i port. The only change is in `sw/startup.S`: PicoRV32 has no `mtvec`, so `csrw mtvec` became a `nop`. `scripts/baseline.py` checks that each PicoRV32 image differs from the Spike image in exactly that one word, which proves both simulators run byte-identical benchmark code.
- **Harness:** 16 MiB of zero-wait RAM at `0x80000000`. A run ends at the store to `tohost`, the same exit Spike uses.
- **Pins:** like the ML branch, every route uses fixed I/O pins so designs can be compared. `synth/core_top.pcf` came from a pin-free seed-3 placement of the stock core (`make hw-pcf`, which uses `scripts/pcf.py` and IceStorm's `chipdb-8k.txt`). It pins all 106 scalar ports, with `clk` on P9.
- **Seeds:** 1–10, where the ML branch used 1–3.
- **PicoRV32** is vendored here; the ML branch fetched it at run time.
- **Comparison with the ML branch's core:** its rv32i core without MUL/DIV was 1,488 LUT4 and 66.8 MHz median (3 seeds, its own pins). Different core and different pins, so not like for like.

## Baseline details

- Area after `synth_ice40`: 2,439 `SB_LUT4`, 559 `SB_CARRY`, 1,010 flip-flops, and 2,751 of 7,680 logic cells after packing.
- Fmax per seed, 1–10: 60.21, 61.33, 60.16, 63.19, 60.31, 61.69, 61.64, 61.74, 59.86, 64.98 MHz.
- With the pins fixed, seed 3 gives 60.16 MHz, not the 61.56 MHz of the pin-free placement the PCF came from. Fixed pins change where the placer starts, so per-seed numbers aren't comparable across pin settings.
- Why cycles per instruction is high: edn and matmult-int run many `mul` instructions at about 40 cycles each.
- `results/baseline.csv` columns: `benchmark,cycles,instret,spike_instret,match,luts,fmax_mhz,fmax_min_mhz,fmax_max_mhz`; `fmax_mhz` is the median and the core-level columns repeat on every row.

## Critical-path check

`make hw-critpath` (and the engine, per build) classifies each seed's post-route clk→clk path from nextpnr's log on the Yosys netlist, never by cell name: synthesis borrows names from nearby signals, so a LUT named `fused.unit.active…` can be plain PicoRV32 branch logic.

- `scripts/critpath.py` reads the path and writes the table; `critends.py` resolves the launching and capturing registers; `critcone.py` decides whether the unit is on the arc; `critgroups.py` counts path cells shared with the next-state logic of the unit, the PCPI handshake, the multiplier and the divider.
- The unit is on the arc if the path starts at a unit register (`active`, `result`), ends at one, or enters unit-dependent logic through a net that feeds a unit register. Logic shared with the core (a XOR merged with the ALU compare, say) doesn't count.
- `critcone.py --selftest` builds synthetic paths with nextpnr's real cell naming (`_LC`, `_DFFLC`) through all three cases and must pass on the modified netlist before a table is written.
- Since the period rule changed to `max(T_base, T_fused_measured)`, the table is a diagnostic; it no longer decides the credited period.
