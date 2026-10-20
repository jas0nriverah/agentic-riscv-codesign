# Hardware track: measuring fused RISC-V instructions on PicoRV32

> **Status: PROVISIONAL.** Everything on this branch is the hardware team member's proposal for how fused custom instructions get built and measured. The interface, encodings, rewriting method and scoring rule are listed under [Provisional decisions](#provisional-decisions) and are not team decisions yet. The team's original README is preserved [at the bottom](#project-readme-from-the-default-branch-unchanged).

The project finds short dependent chains of RISC-V instructions in the Embench programs, proposes fusing each chain into one custom instruction, and asks the hardware to say what that fusion is worth. This track answers the last question: for a candidate formula such as `add(in0,slli(in1,2))`, it builds a PicoRV32 core that executes the formula as one instruction, rewrites the program to use it, runs all 8 programs on the modified core, synthesizes and routes it for an iCE40 FPGA, and reports cycles, instructions, LUTs, Fmax and a speedup, with every number cross-checked against a prediction.

## Quick start

```
make hw-baseline                                  # stock core: 8 programs in Verilator, Spike cross-check,
                                                  #   synthesis, routing -> hw/results/baseline.csv (about 1 min)
make hw-measure CANDIDATES=<json> [ALLOW_MUL=1]   # one fused core, all 8 programs
                                                  #   -> generated/hw/engine/<id>/results.json, rows.csv (about 50 s)
make hw-sweep [CLEAN=1] [ALLOW_MUL=1]             # each program's top 3 candidates, each measured alone
                                                  #   -> hw/engine/results/sweep-top3.csv (about 20 min from clean)
make hw-dryrun                                    # the first end-to-end run, one crc32 candidate -> hw/dryrun/results.json
make hw-critpath                                  # critical path per seed, stock and dry-run cores
```

`CANDIDATES` is a JSON list of 1 to 3 entries like `{"formula": "add(in0,slli(in1,2))"}`. The tools (xPack GCC, Spike, OSS CAD Suite) and the knobs for them are listed in [hw/README.md](hw/README.md). The Embench submodule is cloned on first use.

## Directory map

```
hw/
  rtl/         picorv32.v (vendored, unmodified) · core_top.v (FUSED=0 stock, 1 dry run, 2 engine)
               pcpi_fused.v, cx_crc32_xoridx.v (the dry-run unit)
  sim/         core_sim.cpp, the Verilator harness
  sw/          startup.S, PicoRV32's copy of main's startup (csrw mtvec -> nop)
  synth/       ice40.ys · core_top.pcf, the frozen pins every comparison uses
  isaforge/    rtl.py, features.py: the ML branch's RTL generator and formula parser, vendored unmodified
  engine/      the measurement engine: units.py, asmscan.py, rewrite.py, finder.py, report.py, sweep.py
               results/ (committed CSVs and per-build results) · README.md (full detail and tables)
  dryrun/      the first end-to-end run of one candidate · README.md
  scripts/     baseline.py, pcf.py · critpath.py, critcone.py, critends.py, critgroups.py
  results/     baseline.csv
  hw.mk        the make targets, included from the top-level Makefile
generated/     every build output, git-ignored
src/, benchmarks/   the team's pipeline: Spike tracing and the candidate finder (not changed by this track)
```

## Where this sits in the pipeline

Embench programs → Spike trace (`src/tracing.py`) → candidate finder (`src/candidates.py`, candidates JSON with `formula`, `size`, `runs`, `places`, `saved`) → selection (frequency ranking or ML-guided, 1 to 3 formulas per core) → **hardware measurement (this track)** → measurement rows back to the ML side.

The hardware stage takes selected formulas in and gives measurement rows back. A row carries `candidate_id`, the baseline and candidate cycles, the two clock periods, the LUT count, and the speedup under the [protocol](#measurement-protocol) below, plus the cycles-only speedup.

## How a measurement works

Two lanes run independently and meet at the checks.

- **Hardware lane.** The formula goes through the ML branch's `generate_rtl` unchanged. The result is a combinational unit wrapped in a PCPI module that decodes one custom-0 encoding, latches the result, and acknowledges on the next cycle. `core_top` instantiates it when `FUSED` is set, with the same ports as the stock core, so the frozen pin file applies. Yosys and nextpnr run exactly as for the baseline.
- **Software lane.** Each program is compiled with main's exact flags, stopped at assembly. The rewriter decodes every line with main's own decoder, matches the formula's operator tree with the operands in order and the same immediates, confirms every intermediate is dead inside the block, and replaces the chain with `.insn r 0x0b, <funct3>, 2, rd, rs1, rs2`. It fuses only sites the candidate finder counted, so the measurement tests the finder's `saved` and not the rewriter's reach. Every fused and skipped site is logged with its reason.
- **Checks.** A build fails unless every fused program passes `verify_benchmark`, every stock program gives the baseline's cycles and instret on the modified core, the labelled control build is byte-identical to the baseline image, the instret saving equals Σ (size − 1) × runs over the fused sites, every finder site is fused or explained, the per-slot microtests pass against two independent Python references, and every unclaimed custom encoding traps.

The dry run in [hw/dryrun/README.md](hw/dryrun/README.md) walks one candidate through this by hand. [hw/engine/README.md](hw/engine/README.md) has the full matching rules, the check list, and every result table.

## Measurement protocol

The baseline and every modified core are measured the same way.

| Quantity | Definition |
|---|---|
| program | main's exact Embench build: `-march=rv32im -mabi=ilp32 -O2`, main's linker script, RAM at `0x80000000`; `hw/sw/startup.S` differs from main's startup in one word (`csrw mtvec` → `nop`), which `baseline.py` verifies |
| `cycles` | clock cycles between the store to `instret_start` and the store to `instret_stop` in `benchmarks/embench-hooks.c`, the same window Spike traces |
| end of run | the store to `tohost`; the exit word must be 1 (`verify_benchmark` passed); a trap, an access outside RAM or the cycle limit is a failure |
| `instret` | PicoRV32's own `rdinstret` delta; on the stock core it must equal Spike's (trace lines + 1) |
| core | stock PicoRV32 `ef203c2b`, unmodified: `ENABLE_MUL=1`, `ENABLE_DIV=1`, `FAST_MUL=0`, `TWO_STAGE_SHIFT`, dual-port register file, no compressed instructions, no IRQ |
| FPGA | iCE40 HX8K, CT256, `--freq 12`, `synth_ice40` defaults (no DSP); pins from the frozen `hw/synth/core_top.pcf`; seeds 1–10; Fmax reported as median, min and max |
| `luts` | `SB_LUT4` count in the Yosys netlist |

**Clock period of a modified core (PROVISIONAL, pending team agreement).** `T_fused = max(T_base, T_fused_measured)`, where `T_base` = 1000 / 61.48 MHz = 16.2655 ns is the baseline's median period and `T_fused_measured` = 1000 / the modified core's routed median Fmax.

- Speedup = `(base_cycles · T_base) / (fused_cycles · T_fused)`. The cycles-only speedup, `base_cycles / fused_cycles`, is reported beside it everywhere.
- A faster routed clock is never credited: extra logic changes where the placer starts, so Fmax moves by several MHz even when the new logic is nowhere near the slowest path. The dry run gained 3.6 MHz from +42 LUTs with its unit off the critical arc in every seed.
- A slower one is always charged: a large unit can lower Fmax without being on the critical arc. The two `mul` cores of the sweep routed at 58.52 and 60.70 MHz with their multiplier off the arc in every seed.
- `make hw-critpath` still reports, per seed, whether the unit's logic is on the critical arc. It's classified on the Yosys netlist, never by cell name, and kept as a diagnostic. The method is in [hw/README.md](hw/README.md#critical-path-check).

PicoRV32 is a multicycle core and its `mul` takes about 40 cycles, so cycle savings are not instruction savings. Both are always reported.

## Results

### Stock baseline (2026-10-19)

2,439 `SB_LUT4`; Fmax over seeds 1–10 with the frozen pins: median 61.48 MHz, min 59.86, max 64.98. Source: [hw/results/baseline.csv](hw/results/baseline.csv).

| program | cycles | instret | = Spike | cycles / instr |
|---|---:|---:|---|---:|
| aha-mont64 | 25,631,371 | 4,475,851 | yes | 5.73 |
| crc32 | 22,461,391 | 3,831,152 | yes | 5.86 |
| edn | 34,849,402 | 3,466,139 | yes | 10.05 |
| huffbench | 8,638,203 | 2,131,016 | yes | 4.05 |
| matmult-int | 26,300,272 | 3,179,290 | yes | 8.27 |
| nettle-aes | 18,773,912 | 4,083,360 | yes | 4.60 |
| nettle-sha256 | 20,276,586 | 3,854,209 | yes | 5.26 |
| wikisort | 6,916,129 | 1,182,160 | yes | 5.85 |

### Single-candidate sweep (2026-10-20)

Each program's top 3 candidates by the finder's `saved`, each built and measured alone on its own core: 21 cores, 22 rows (one formula tops two programs). All 21 pass every check, and a clean rebuild reproduces the CSV byte for byte. Source: [hw/engine/results/sweep-top3.csv](hw/engine/results/sweep-top3.csv); the full 22-row table with gap reasons is in [hw/engine/README.md](hw/engine/README.md#single-candidate-sweep-2026-10-20-each-programs-top-3-each-measured-alone).

The rank-1 candidate of each program:

| program | formula | instr saved | cycles saved | cycles / instr | LUT Δ | Fmax median | speedup | cycles only |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| aha-mont64 | `add(srli(in0,31),slli(in1,1))` | 433,152 | 3,681,792 | 8.5 | +49 | 58.96 | 1.1198 | 1.1677 |
| crc32 | `slli(add(mul(in0,addi(lui(1103515648),-403)),in1),1)` | 0 | 0 | — | +653 | 58.52 | 0.9519 | 1.0000 |
| edn | `add(srai(add(slli(in0,1),in0),15),in1)` | 39,150 | 208,800 | 5.3 | +93 | 62.31 | 1.0060 | 1.0060 |
| huffbench | `add(in0,slli(in1,2))` | 46,684 | 186,736 | 4.0 | +76 | 60.37 | 1.0037 | 1.0221 |
| matmult-int | `addi(lui(-2147475456),32)` | 0 | 0 | — | +45 | 62.14 | 1.0000 | 1.0000 |
| nettle-aes | `add(in0,slli(in1,2))` | 527,436 | 2,109,744 | 4.0 | +76 | 60.37 | 1.1063 | 1.1266 |
| nettle-sha256 | `xor(add(srli(in0,2),slli(in0,30)),in1)` | 182,400 | 1,216,000 | 6.7 | +79 | 59.44 | 1.0285 | 1.0638 |
| wikisort | `addi(addi(in0,-16),16)` | 19,793 | 19,793 | 1.0 | +51 | 60.43 | 0.9857 | 1.0029 |

- **Every shortfall against the finder's `saved` is explained.** crc32's two `mul` candidates have a site with no legal placement: `rand_beebs` loads a constant between the chain's members and the `mul` overwrites an input, so fusing needs reordering, which the rewriter doesn't do. matmult-int's only candidate is an address constant the linker fills in. wikisort's #2 and #3 sit only in libgcc soft-float code, which isn't compiled from source.
- **Cycles saved per instruction saved runs from 1.0 to 12.0.** Shifts by 31 are slow on this core, so aha-mont64's candidates save 8.5 to 12 cycles per instruction removed. wikisort #1 replaces two 3-cycle `addi`s with one 5-cycle instruction and saves 1.
- **The unit was never on the critical arc, yet 15 of the 21 cores route slower than the baseline** (medians 57.8 to 64.3 MHz). Under the period rule that costs up to 6.0%, and 8 of the 22 rows end below 1.0.
- **Each fused instruction takes 5 cycles against 3 for a native ALU op:** 2 cycles of PCPI overhead.

### Frequency-ranking baseline (2026-10-20)

Formulas ranked by the finder's `saved` summed over all 8 programs; two formulas conflict if, in any program, a site counted for one shares an instruction with a site counted for the other; the top 3 non-conflicting were taken as they came. Picks: `add(in0,slli(in1,2))`, `slli(add(mul(in0,addi(lui(1103515648),-403)),in1),1)` (`mul`, built with `ALLOW_MUL=1`), `add(srli(in0,31),slli(in1,1))`. Ranks 3 and 4 were skipped as conflicting. One core with all three: **3,186 LUT4 (+747)**, Fmax median **57.09 MHz** (54.98–59.14), and the unit **on the critical arc in 5 of 10 seeds** through the multiplier. Source: [hw/engine/results/frequency-top3.csv](hw/engine/results/frequency-top3.csv) (the measurement rows) and [frequency-top3.json](hw/engine/results/frequency-top3.json) (the full result).

| program | instr saved | cycles saved | cycles / instr | speedup | cycles only |
|---|---:|---:|---:|---:|---:|
| aha-mont64 | 433,152 | 3,681,792 | 8.5 | 1.0844 | 1.1677 |
| crc32 | 174,080 | 696,320 | 4.0 | 0.9584 | 1.0320 |
| edn | 0 | 0 | — | 0.9287 | 1.0000 |
| huffbench | 46,684 | 186,736 | 4.0 | 0.9492 | 1.0221 |
| matmult-int | 0 | 0 | — | 0.9287 | 1.0000 |
| nettle-aes | 527,436 | 2,109,744 | 4.0 | 1.0462 | 1.1266 |
| nettle-sha256 | 475 | 1,900 | 4.0 | 0.9287 | 1.0001 |
| wikisort | 0 | 0 | — | 0.9287 | 1.0000 |
| **total** | **1,181,827** | **6,676,492** | **5.65** | | |

The rank-2 pick fuses nothing anywhere (its sites have no legal placement) yet costs about 650 LUTs and sets the clock, so every program pays the 7.1% slower period. Savings equal the sum of the same formulas measured alone, because the picks don't conflict. The lesson for selection: ranking by the finder's `saved` alone chose a candidate that can't be placed.

### Dry run (2026-10-20)

The first end-to-end run, one crc32 candidate (`slli(andi(xor(in0,in1),255),2)`) on a hand-wired unit: instret −348,160 (exactly the finder's `saved`), cycles −1,218,560, +42 LUT4, speedup 1.0574. Details and its critical-path table: [hw/dryrun/README.md](hw/dryrun/README.md).

## Custom instruction encoding

custom-0 (opcode `0x0b`), R-type, `rd = f(rs1, rs2)`. `core_top`'s `FUSED` parameter selects the unit: 0 is the stock core (`ENABLE_PCPI=0`, reproduces `baseline.csv` exactly), 1 the dry-run unit, 2 the engine's per-build unit. The ports are the same in every case. Update this table in the same commit as any decode change.

| funct7 | funct3 | operation | status |
|---:|---:|---|---|
| 1 | 0 | `((rs1 ^ rs2) & 255) << 2` | used by the ML branch's earlier PicoRV32 experiment (`hardware/pcpi_candidates.v`); not used here, don't reuse without checking with the team |
| 1 | 1 | `rs1 ^ (rs2 >> 8)` | same as above |
| 2 | 0 | `slli(andi(xor(in0,in1),255),2)` | **provisional**, dry-run core only (`FUSED=1`, `hw/rtl/pcpi_fused.v`) |
| 2 | 0, 1, 2 | engine slots 0–2, formula chosen per build in request order | **provisional**, engine cores only (`FUSED=2`); each build's assignment is in its `manifest.json` and `results.json` |
| 2 | 3–7 | none | reserved; the engine's microtests check that they trap |

Every other custom-0 encoding traps through PicoRV32's PCPI timeout and `CATCH_ILLINSN`.

## Provisional decisions

Each of these is a working choice made to get measurements flowing, not a team decision:

- **PCPI** as the way into the core, rather than a decoder change. It keeps `picorv32.v` untouched but costs 2 cycles per fused instruction.
- **Encoding:** custom-0, funct7 = 2, funct3 = slot, up to 3 units per core.
- **A registered 1-cycle PCPI handshake**, as in the ML branch's unit.
- **Assembly-level rewriting** of the compiler's `.s` output, instead of a compiler change or binary patching.
- **Fusing only sites the finder counted**, so the measured instret saving can be checked against `saved` exactly.
- **PicoRV32's sequential multiplier** (`FAST_MUL=0`): a `mul` costs about 40 cycles, which inflates any fusion that removes one.
- **The period rule** `T_fused = max(T_base, T_fused_measured)`.
- **`candidate_id` = sha256(json([benchmark, canonical_formula]))**, computed with the ML branch's own `candidate_id()`.
- **The conflict rule** used for the frequency-ranking baseline (shared instruction between counted sites).

## Limitations

- **One schedule only.** Sites that need instructions reordered aren't fused; crc32's `mul` candidates are the standing example.
- **Library code isn't rewritten.** libgcc soft-float and libm are precompiled, so their sites count toward `saved` but can't be fused.
- **Liveness is proven inside a basic block only**, like the finder.
- **The fused programs can't run on Spike**, so their instret is checked against site arithmetic, not a trace.
- **LUT counts carry about ±2 of synthesis noise** (the same unit logic gave 2,479 and 2,481 under different module names).
- **A combinational multiplier costs 650–700 LUT4** on this FPGA, so `mul` formulas are refused unless `ALLOW_MUL=1`.
- **Routed Fmax moves by several MHz with placement**, which is why the period rule exists.

## Provenance

| Input | Source |
|---|---|
| `hw/rtl/picorv32.v`, `hw/rtl/PICORV32-COPYING` | [YosysHQ/picorv32 @ `ef203c2b0a3fb793280f5114941416c425c5b461`](https://github.com/YosysHQ/picorv32/tree/ef203c2b0a3fb793280f5114941416c425c5b461), unmodified, ISC license; sha256 of `picorv32.v`: `0836050971b3c6cdd28ac3b1e5719a67fb645161912bef1e472e63995ceb0622` |
| `hw/rtl/core_top.v`, `hw/sim/core_sim.cpp`, synthesis and routing settings | adapted from `origin/codex/isaforge-ml-foundation` @ `dc9ae16` (`hardware/core_top.v`, `hardware/core_sim.cpp`, `isaforge/core_experiment.py`, `isaforge/core_routing.py`); the CRC32 PCPI unit and its tests were left out |
| `hw/sw/startup.S` | copy of main's `src/spike-setup/startup.S` with `csrw mtvec` → `nop` |
| `hw/isaforge/rtl.py`, `features.py`, `__init__.py` | `origin/ai-guided-ml` @ `7431a54`, `isaforge/`, unmodified (sha256 `45cb8bfe…219e`, `1aa3a05b…1c84`, `788b8939…109a`) |
| `hw/rtl/pcpi_fused.v`, `hw/engine/units.py`'s PCPI wrapper | adapted from that branch's `hardware/pcpi_single.v` |
| `hw/rtl/cx_crc32_xoridx.v`, every engine unit | generated by `hw/isaforge/rtl.py` |
| `hw/synth/core_top.pcf` | a pin-free seed-3 placement of the stock core (`make hw-pcf`), frozen since the baseline |

---

# Project README (from the default branch, unchanged)

# agentic-riscv-codesign
AI-guided hardware-software co-design for RISC-V kernel acceleration using custom instructions and matched software implementations.
