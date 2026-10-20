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

### Placeability pre-check and top-10 sweep (2026-10-20)

**Pre-check** (`make hw-placeability` → [hw/engine/results/placeability.csv](hw/engine/results/placeability.csv)): the rewriter alone, no hardware, on all 348 candidates of the 8 programs, each as if alone on a core. Placeable (the rewriter can fuse at least one counted site): aha-mont64 18 of 20, crc32 14 of 17, edn 17 of 24, huffbench 16 of 20, matmult-int 0 of 1, nettle-aes 47 of 52, nettle-sha256 57 of 67, wikisort 44 of 147. Every gap is explained; the common reasons are sites in libgcc soft-float (`__muldf3`, `__adddf3`, `__divdf3`, `__subdf3`), no legal position, and linker-filled address constants. The pre-check agrees with all 22 measured top-3 rows exactly.

**Sweep** (`make hw-sweep10 ALLOW_MUL=1` → [hw/engine/results/sweep-top10-placeable.csv](hw/engine/results/sweep-top10-placeable.csv)): each program's top 10 placeable candidates by finder `saved`, each measured alone: 70 rows from 60 cores, all clean. Rank agreement between finder `saved` and measured cycles saved ([rankcheck-top10.csv](hw/engine/results/rankcheck-top10.csv)):

| program | ρ(saved, cycles) | ρ(saved, instret) | finder's #1 is the best? | best by cycles |
|---|---:|---:|---|---|
| aha-mont64 | 0.939 | 1.000 | yes | `add(srli(in0,31),slli(in1,1))` |
| crc32 | 0.644 | 1.000 | no | `mul(in0,addi(lui(1103515648),-403))` (finder #4) |
| edn | 0.842 | 1.000 | yes | `add(srai(add(slli(in0,1),in0),15),in1)` |
| huffbench | 0.954 | 1.000 | yes | `add(in0,slli(in1,2))` |
| nettle-aes | 0.893 | 0.978 | yes | `add(in0,slli(in1,2))` |
| nettle-sha256 | 1.000 | 1.000 | yes | `xor(add(srli(in0,2),slli(in0,30)),in1)` |
| wikisort | 0.729 | 1.000 | no | `mul(in0,addi(lui(1103515648),-403))` (finder #21) |

- Instruction counts are predicted perfectly; the disagreement is all cycles per instruction, which runs from 1.0 to 38 across these rows.
- **The multiply-by-constant fusion is the best single result in the study:** `mul(in0,addi(lui(1103515648),-403))` replaces the ~40-cycle sequential multiply with a 5-cycle operation, 20.5 cycles per instruction removed, crc32 speedup **1.439** under the period rule (1.466 cycles only), +624 LUT4, off the critical arc. The general multiplier `mul(in0,addi(in1,-403))` is not worth it: +1,458 LUT4, 48.41 MHz, on the critical arc in every seed, 1.116 after the clock penalty.
- 51 of the 70 rows route below the baseline clock and 24 end below 1.0 under the period rule.

### Multiplier probe (PRELIMINARY, 2026-10-20)

Not a baseline change. The stock core with PicoRV32's single-cycle multiplier (`ENABLE_FAST_MUL=1`, no fused units) under the same protocol (`make hw-fastmul-probe` → [hw/results/fastmul-probe.csv](hw/results/fastmul-probe.csv)): **5,351 LUT4 (+2,912)**, Fmax median **47.05 MHz** (45.91–48.49), the multiplier is the critical arc in 10 of 10 seeds. Cycles: edn −55.9%, matmult-int −47.6%, crc32 −26.4%, wikisort −14.4%, aha-mont64 −6.4%, the other three unchanged. Geometric-mean speedup 1.283 cycles only, **0.982** under the period rule (the three programs without `mul` pay the 30.7% slower clock for nothing). The baseline multiplier choice is pending team confirmation; the numbers above and the fused-`mul` results depend on it.

### Selection experiments (2026-10-20)

Three ways to pick up to 3 formulas for one core, scored by the geometric mean of the 8 per-program speedups under both rules ([hw/engine/results/experiments.csv](hw/engine/results/experiments.csv); requests, estimates and full results beside it). Two formulas conflict if a site the finder counted for one shares an instruction with a site counted for the other, in any program.

- **E, frequency by finder `saved`** (above): one build.
- **C1, frequency by placeable saved:** the same rule with the pre-check's placeable saved instead of the finder's. Picks `add(in0,slli(in1,2))`, `add(srli(in0,31),slli(in1,1))`, `mul(in0,addi(lui(1103515648),-403))`. One build.
- **C2, oracle under a LUT budget:** from the 60 single-candidate cores, every non-conflicting set of up to 3 within the budget, assuming cycles and LUTs add and the clock is the slowest member's; the top 3 sets by estimated cycles-only geomean were built, for budgets +100, +250, +500 and +750. +500 chose the same sets as +250, because the only candidate that could use the room (the constant multiplier, +624) doesn't fit; +750 is the first budget that admits it, and its best set is the C1 core. 60 + 9 builds.

| experiment | formulas | LUT Δ (est.) | Fmax | on arc | geomean, period rule | geomean, cycles only (est.) |
|---|---|---:|---:|---:|---:|---:|
| E frequency, finder saved | `add(in0,slli(in1,2))`, `slli(add(mul(…),in1),1)`, `add(srli(in0,31),slli(in1,1))` | +747 | 57.09 | 5/10 | 0.968 | 1.042 |
| C1 frequency, placeable saved | `add(in0,slli(in1,2))`, `add(srli(in0,31),slli(in1,1))`, `mul(in0,addi(lui(1103515648),-403))` | +725 | 57.63 | 2/10 | **1.028** | **1.097** |
| C2 +100, set 1 | `add(srli(in0,31),slli(in1,1))`, `or(srli(in0,31),slli(in1,1))` | +82 (+99) | 62.67 | 0 | 1.037 | 1.037 (1.037) |
| C2 +100, set 2 | `add(srli(in0,31),slli(in1,1))`, `or(srli(in0,31),in1)` | +81 (+88) | 61.52 | 0 | 1.032 | 1.032 (1.032) |
| C2 +100, set 3 | `add(srli(in0,31),slli(in1,1))`, `srli(slli(add(in0,in1),1),1)` | +83 (+100) | 63.34 | 0 | 1.028 | 1.028 (1.028) |
| C2 +250 / +500, set 1 | `add(in0,slli(in1,2))`, `add(srli(in0,31),slli(in1,1))`, `or(srli(in0,31),slli(in1,1))` | +107 (+175) | 60.26 | 0 | 1.039 | 1.060 (1.060) |
| C2 +250 / +500, set 2 | `add(in0,slli(in1,2))`, `add(srli(in0,31),slli(in1,1))`, `or(srli(in0,31),in1)` | +139 (+164) | 62.83 | 0 | **1.054** | 1.054 (1.054) |
| C2 +250 / +500, set 3 | `add(in0,slli(in1,2))`, `add(srli(in0,31),in1)`, `or(srli(in0,31),slli(in1,1))` | +175 (+208) | 58.28 | 0 | 0.998 | 1.052 (1.052) |
| C2 +750, set 1 (= C1) | `add(in0,slli(in1,2))`, `add(srli(in0,31),slli(in1,1))`, `mul(in0,addi(lui(1103515648),-403))` | +725 (+749) | 57.63 | 2/10 | 1.028 | **1.097** (1.097) |
| C2 +750, set 2 | `add(in0,slli(in1,2))`, `mul(in0,addi(lui(1103515648),-403))`, `or(srli(in0,31),slli(in1,1))` | +736 (+750) | 57.97 | 4/10 | 1.029 | 1.091 (1.091) |
| C2 +750, set 3 | `add(in0,slli(andi(in1,255),2))`, `add(srli(in0,31),slli(in1,1))`, `mul(in0,addi(lui(1103515648),-403))` | +725 (+749) | 58.11 | 0 | 1.030 | 1.090 (1.090) |

Per-program speedups for every row are in `experiments.csv`. What the comparison shows:

- **Cycles add exactly.** In every oracle set, the measured cycles saved equals the sum of the members' single-candidate savings for every program. There were no interaction effects in cycles, because the picks don't share sites.
- **LUTs are sub-additive.** Every set cost less than the sum of its members (+107 measured against +175 estimated for the best 3-set), because the units share one PCPI decoder and result register and synthesis merges logic between them.
- **The clock is the part no estimate caught.** The pessimistic clock guess (slowest member) was too pessimistic every time, and routed Fmax decides the ranking under the period rule: the +250 set that is best cycles-only (1.060) routes at 60.26 MHz and lands at 1.039, while set 2 routes at 62.83 MHz and wins at 1.054. The two sets are identical in cycles for 6 of 8 programs.
- **Placement awareness fixes the frequency baseline:** C1 beats E on both scores (1.028 vs 0.968; 1.097 vs 1.042) by swapping the unplaceable `mul` chain for the placeable constant multiplier, which alone gives crc32 1.439. It is still a 725-LUT core at 57.6 MHz, so under the period rule it loses to a 139-LUT oracle set. At +750 the oracle picks that same core: the constant multiplier is the best use of a large budget, cycles-only (1.097 against 1.060 at +250), but under the period rule the three +750 sets are within 0.003 of each other and within 0.01 of the +100 sets, which cost a tenth of the LUTs.
- **Most set-to-set differences under the period rule are inside the Fmax noise.** Recomputing each set's geomean at its own 10-seed Fmax min and max gives an interval; of the 36 pairs among the 9 distinct oracle sets, only 2 have non-overlapping intervals (+250 set 2 against the two weaker +100 sets, differences of 0.023 and 0.026). The best set's lead over its runner-up (1.054 vs 1.039) is within noise. `experiments.json` has every pair.
- **Cost:** frequency ranking needs 1 hardware build; the oracle needed 69 (60 single-candidate cores plus the 9 distinct sets built here).

### Dry run (2026-10-20)

The first end-to-end run, one crc32 candidate (`slli(andi(xor(in0,in1),255),2)`) on a hand-wired unit: instret −348,160 (exactly the finder's `saved`), cycles −1,218,560, +42 LUT4, speedup 1.0574. Details and its critical-path table: [hw/dryrun/README.md](hw/dryrun/README.md).

## Data for the ML side

PRELIMINARY: baseline multiplier choice pending team confirmation; numbers may change.

Every file below was produced under the protocol above (frozen PCF, seeds 1–10, every check passing) and is committed. Column definitions for all of them are in [hw/engine/results/README.md](hw/engine/results/README.md#columns).

**Training labels** (one row per candidate measured alone on its own core; `speedup` and `speedup_cycles_only` are the targets, `lut_delta`, `fmax_median` and `cycle_delta` the other measured outcomes):

- [hw/engine/results/sweep-top10-placeable.csv](hw/engine/results/sweep-top10-placeable.csv): each program's top 10 placeable candidates by finder `saved`, 70 rows from 60 cores (2 with `mul`). The larger and more varied set; use this one.
- [hw/engine/results/sweep-top3.csv](hw/engine/results/sweep-top3.csv): each program's top 3 by finder `saved` regardless of placeability, 22 rows from 21 cores; 5 rows fused nothing. A subset of the above plus the unplaceable ones.

**Features and filter:**

- [hw/engine/results/placeability.csv](hw/engine/results/placeability.csv): all 348 candidates, rewriter only, no hardware: `placeable_sites`, `placeable_saved` and the gap against the finder's `saved` with its reason. Use `placeable_saved > 0` as the filter and `placeable_saved` as a feature; it predicted the measured instruction saving exactly in all 70 sweep rows.

**Context:**

- [hw/results/baseline.csv](hw/results/baseline.csv): the stock core every row is measured against: cycles and instret per program, 2,439 LUT4, Fmax 61.48 MHz median.
- [hw/results/fastmul-probe.csv](hw/results/fastmul-probe.csv): the same stock core with the single-cycle multiplier, as a reference for what the multiplier choice is worth (+2,912 LUT4, 47.05 MHz). Not the baseline.

`candidate_id` for a row is `sha256(json([benchmark, canonical_formula]))` as in `hw/engine/results/*.json`; the CSVs carry `program` and `formula` instead so the hash can be recomputed either way.

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
