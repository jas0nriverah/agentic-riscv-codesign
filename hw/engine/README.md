# Measurement engine (PROVISIONAL)

> **Every choice here is provisional and is not a team decision.** That covers PCPI as the interface; custom-0 with funct7=2 and funct3 = slot; up to 3 units per core with a registered 1-cycle handshake; assembly-level rewriting; PicoRV32's sequential multiplier; the clock-period rule ([hw/README.md](../README.md#measurement-protocol)); and the proposed `candidate_id`.

```
make hw-measure CANDIDATES=<json> [ALLOW_MUL=1]   # one core, all 8 programs -> generated/hw/engine/<id>/results.json
make hw-sweep [CLEAN=1] [ALLOW_MUL=1]            # top 3 per program, each alone -> hw/engine/results/sweep-top3.csv
```

`CANDIDATES` is a JSON list of 1 to 3 entries like `{"formula": "add(in0,slli(in1,2))"}`, with optional `size` and `benchmark`. List order is the funct3 slot order and the rewrite priority. A formula containing `mul`, `mulh`, `mulhu` or `mulhsu` is refused unless `ALLOW_MUL=1`: a combinational multiplier is expensive on iCE40 (about 650–700 LUT4 for a 32-bit multiply by a constant). The build id is a hash of the ordered formula list, so the same request always reuses the same build.

A build takes about 50 s at `-j8` after `make hw-baseline`. The clean sweep (21 builds) takes about 20 min.

## What one build does

1. **Units** (`units.py`)
   - Each formula becomes `cx_s<slot>` via the vendored `hw/isaforge/rtl.py::generate_rtl`.
   - `pcpi_engine.v` decodes `(insn & 0xfe00707f) == 0x0400000b | funct3 << 12` per slot, latches the selected result, and acknowledges the next cycle, like the dry run's unit.
   - `core_top` with `FUSED=2` instantiates it, and the ports are unchanged.
   - Every other encoding is left to PicoRV32's PCPI timeout, so it traps.
2. **Microtests** (bare assembly, unmodified harness)
   - Per slot: 1,181 operand pairs (boundaries, byte edges, 1,000 seeded random) plus 4 aliasing cases (rd=rs1, rd=rs2, rs1=rs2, rd=x0).
   - Expected values come from the ML branch's `evaluate_formula`, and a second evaluator written here independently has to agree on every vector.
   - The timing pair gives cycles per instruction; the same pair is run for a native `xor`.
   - On the engine core, these must trap: funct3 values not in use, funct7=1 (the ML branch's old slot), funct7=3, and custom-1.
   - On the stock core, every used slot must trap.
3. **Software**
   - Each program's 4 C sources are compiled with main's exact flags, stopped at `.s`, and linked with `hw/sw/startup.S` and main's linker script.
   - The round trip through `.s` is byte-identical to the baseline images for all 8 programs.
   - `rewrite.py` writes a *marked* copy (labels at every site, no code change; must equal the baseline image) and a *fused* copy.
4. **Runs:** each fused program on the engine core, and each stock baseline program on the engine core.
5. **Hardware:** Yosys `synth_ice40` with `chparam -set FUSED 2`, then nextpnr seeds 1–10 with the frozen `hw/synth/core_top.pcf`, then the critical-path table (`hw/scripts/crit*.py`, self-test first).
6. **Report** (`report.py`): every check below, the reconciliation, and the measurement rows (`rows.jsonl`). `report.json` is always written; `results.json` only for a clean build.

## How a site is matched and fused (`asmscan.py`, `rewrite.py`)

- **Seeing the code the way the finder does.**
  - Each `.s` line is assembled with a listing, and its machine words are decoded with main's `src/tracing.py::decode`.
  - Pseudo-instructions (`li`, `mv`, `not`, `call`, …) therefore look exactly like the machine code the finder saw.
  - Lines carrying a relocation (`%hi`, `%lo`, calls) are marked. Linker relaxation can rewrite them, and their values move when code shrinks.
- **Blocks** end at labels and at branches and jumps, like the finder's.
- **A match** binds the formula tree with its root at one instruction:
  - each operator equals the line's op;
  - operands come in rs1/rs2 order (never commuted, because the finder doesn't commute either);
  - immediates are equal (a linker-filled immediate can't be compared and blocks fusion);
  - `0` means x0;
  - `in0` and `in1` are two different values (register plus the line that wrote it);
  - inner nodes are the most recent writer of the operand register inside the block.
  - The member count must equal the candidate's `size`.
- **A matched site is fused only if all of these hold:**
  1. **The finder counts it:** no non-member line overwrites an input between its definition and the root. That's the finder's own rule, checked on the original code. Sites that fail it are left alone on purpose, even though some could be fused at the first member, because measurements have to test the finder's `saved` and not this rewriter's extra reach.
  2. **Intermediates are dead:** each one is overwritten later in the block and read by no non-member before that.
  3. **There's a legal position.** The default is the root, which needs no line (member or not) to change an input before it. Otherwise it goes at the first member, which needs every input ready there and no other line touching the result register up to the root. That case is common: GCC reuses an input as the destination, as in `andi a5,a5,255`.
  4. **No overlap** with an already fused site.
- **Priority:** the request's list order, then program order. Each fusion is applied to an in-memory model of the block (members removed, the fused instruction present with its real reads and writes) before the next site is checked, so later decisions see the code as rewritten.
- **The log:** every matched site, fused or skipped, is logged with its reason, its PCs (from the marked build's labels) and how often it ran (from the Spike trace). See `generated/hw/engine/<id>/sw/<program>/sites.json` and `results.json`.

## Checks per build (any failure fails the build)

- The marked build equals the baseline PicoRV32 image, for all 8 programs.
- Every fused program passes `verify_benchmark` (exit word 1) with no trap or out-of-RAM access.
- Every stock program gives the baseline's cycles and instret exactly on the engine core.
- **The instret saving equals the prediction exactly:** baseline − fused = Σ over fused sites of (size − 1) × runs.
- **Reconciliation against the finder.** `finder.py` imports `src/candidates.py`'s own functions to list every site the finder counted, and first checks that they add up to its `saved` and `places`. Every finder site must then be fused or explained:
  - skipped by the rewriter (with the reason);
  - in library code the rewriter can't see (`libgcc`/`libm`).

  A finder site in rewritten code that the rewriter didn't match, or a fused site that ran but that the finder didn't count, fails the build.
- All microtests pass, and the encodings that must trap do.
- The critical-path self-test passes and the table covers all 10 seeds.

## Measurement row

`candidate_id` (`sha256(json([benchmark, canonical_formula]))`, a list for multi-unit builds), `benchmark`, `formula`, `measurement_source: "hardware"`, `baseline_cycles`, `candidate_cycles`, `baseline_period_ns`, `candidate_period_ns` = max(T_base, T_fused_measured), `luts` (SB_LUT4), `speedup`, `speedup_cycles_only`. One row per program per build.

## Results

### Single-candidate sweep (2026-10-20): each program's top 3, each measured alone

`make hw-sweep CLEAN=1 ALLOW_MUL=1` → `results/sweep-top3.csv`, with each build's full result (every site) in `results/builds/<id>.json`. There are 22 rows from 21 builds, because huffbench's and nettle-aes's #1 are the same formula and one build serves both.

- **Reproducible:** a clean rebuild of all 21 gave a byte-identical CSV.
- **Every build is clean:**
  - `verify_benchmark` passes on all 8 programs;
  - all 8 stock programs are unchanged on the modified core;
  - all microtests pass, at 5 cycles per fused instruction against 3 for `xor`;
  - the instret saving equals the site prediction exactly.
- **The two crc32 `mul` builds were approved with `ALLOW_MUL=1`.**
- **Δ columns are fused − baseline for the source program.** Speedup uses T_fused = max(T_base, T_fused_measured); cycles-only is `base_cycles / fused_cycles`.

| program | # | formula | saved (finder) | instret Δ | cycle Δ | cycles / instr saved | LUT Δ | Fmax median [min–max] | unit on crit. path | speedup (max rule) | speedup, cycles only |
|---|---:|---|---:|---:|---:|---:|---:|---|---|---:|---:|
| aha-mont64 | 1 | `add(srli(in0,31),slli(in1,1))` | 433,152 | -433,152 | -3,681,792 | 8.5 | +49 | 58.96 [57.8–61.72] | 0/10 | 1.1198 | 1.1677 |
| aha-mont64 | 2 | `or(srli(in0,31),slli(in1,1))` | 324,864 | -324,864 | -2,761,344 | 8.5 | +50 | 58.73 [56.05–64.21] | 0/10 | 1.0707 | 1.1207 |
| aha-mont64 | 3 | `add(srli(in0,31),in1)` | 216,576 | -216,576 | -2,598,912 | 12.0 | +82 | 57.79 [55.9–60.34] | 0/10 | 1.046 | 1.1128 |
| crc32 | 1 | `slli(add(mul(in0,addi(lui(1103515648),-403)),in1),1)` ⚠mul | 696,320 | 0 | 0 | — | +653 | 58.52 [56.92–59.68] | 0/10 | 0.9519 | 1.0 |
| crc32 | 2 | `add(mul(in0,addi(lui(1103515648),-403)),in1)` ⚠mul | 522,240 | 0 | 0 | — | +690 | 60.7 [59.12–61.4] | 0/10 | 0.9873 | 1.0 |
| crc32 | 3 | `srli(slli(add(in0,in1),1),1)` | 348,160 | -348,160 | -1,392,640 | 4.0 | +51 | 62.23 [58.9–65.99] | 0/10 | 1.0661 | 1.0661 |
| edn | 1 | `add(srai(add(slli(in0,1),in0),15),in1)` | 39,150 | -39,150 | -208,800 | 5.33 | +93 | 62.31 [59.86–66.06] | 0/10 | 1.006 | 1.006 |
| edn | 2 | `srai(add(slli(in0,1),in0),15)` | 26,100 | -26,100 | -169,650 | 6.5 | +63 | 59.77 [58.17–62.69] | 0/10 | 0.977 | 1.0049 |
| edn | 3 | `srai(add(in0,in1),15)` | 21,750 | -21,750 | -174,000 | 8.0 | +48 | 64.32 [61.99–66.46] | 0/10 | 1.005 | 1.005 |
| huffbench | 1 | `add(in0,slli(in1,2))` | 46,684 | -46,684 | -186,736 | 4.0 | +76 | 60.37 [59.05–62.15] | 0/10 | 1.0037 | 1.0221 |
| huffbench | 2 | `slli(addi(in0,1),1)` | 14,674 | -14,674 | -44,022 | 3.0 | +73 | 59.2 [55.52–62.07] | 0/10 | 0.9679 | 1.0051 |
| huffbench | 3 | `addi(slli(in0,1),1)` | 14,542 | -14,542 | -43,626 | 3.0 | +42 | 59.81 [57.82–62.58] | 0/10 | 0.9778 | 1.0051 |
| matmult-int | 1 | `addi(lui(-2147475456),32)` | 1 | 0 | 0 | — | +45 | 62.14 [60.23–67.62] | 0/10 | 1.0 | 1.0 |
| nettle-aes | 1 | `add(in0,slli(in1,2))` | 527,436 | -527,436 | -2,109,744 | 4.0 | +76 | 60.37 [59.05–62.15] | 0/10 | 1.1063 | 1.1266 |
| nettle-aes | 2 | `add(in0,slli(andi(in1,255),2))` | 292,032 | -292,032 | -1,022,112 | 3.5 | +76 | 61.98 [59.21–63.62] | 0/10 | 1.0576 | 1.0576 |
| nettle-aes | 3 | `add(in0,slli(addi(andi(srli(in1,16),255),576),2))` | 259,584 | -259,584 | -1,168,128 | 4.5 | +75 | 62.51 [59.51–64.56] | 0/10 | 1.0663 | 1.0663 |
| nettle-sha256 | 1 | `xor(add(srli(in0,2),slli(in0,30)),in1)` | 182,400 | -182,400 | -1,216,000 | 6.67 | +79 | 59.44 [56.9–60.54] | 0/10 | 1.0285 | 1.0638 |
| nettle-sha256 | 2 | `xor(add(srli(in0,6),slli(in0,26)),in1)` | 182,400 | -182,400 | -1,216,000 | 6.67 | +79 | 59.35 [57.11–62.31] | 0/10 | 1.0269 | 1.0638 |
| nettle-sha256 | 3 | `xor(in0,add(srli(in1,25),slli(in1,7)))` | 182,400 | -182,400 | -1,216,000 | 6.67 | +79 | 58.9 [57.64–60.54] | 0/10 | 1.0191 | 1.0638 |
| wikisort | 1 | `addi(addi(in0,-16),16)` | 19,793 | -19,793 | -19,793 | 1.0 | +51 | 60.43 [56.76–63.84] | 0/10 | 0.9857 | 1.0029 |
| wikisort | 2 | `srli(slli(in0,16),16)` | 16,000 | 0 | 0 | — | +49 | 58.73 [56.81–61.14] | 0/10 | 0.9552 | 1.0 |
| wikisort | 3 | `or(srli(in0,29),slli(in1,3))` | 12,908 | 0 | 0 | — | +50 | 58.29 [55.79–63.16] | 0/10 | 0.9482 | 1.0 |

**Where the instret saving is smaller than the finder's `saved`.** Every gap is explained in the CSV's `gap_reasons`:
- **crc32 #1 and #2 (`mul`): no legal position for the one site.** `rand_beebs` loads 12345 into `a5` between the members, and the `mul` overwrites `in0` (`a0`). The finder counts the site because its rule ignores writes by members. Fusing it would need instructions reordered.
- **wikisort #2 and #3:** every site is in libgcc soft-float (`__divdf3`, `__muldf3`, `__adddf3`), which isn't compiled from source here.
- **matmult-int:** its only candidate is an address constant the linker fills in, and that value moves when fused code shrinks.

**Observations:**
- **The unit is never on the critical arc.** The worst path is PicoRV32's branch decision (`reg_op2` → `mem_do_rinst`) in every build and seed, including the `mul` builds, whose multiplier is about 33 cells deep against roughly 40 stages on the branch path.
- **The cores still route slower.** 15 of the 21 cores have a routed median below the baseline's 61.48 MHz (medians run from 57.8 to 64.3 MHz). Under the max rule that costs up to 6.0%, and 8 of the 22 rows end up below 1: 5 small cycle wins turn into net losses, and 3 rows with no cycle saving still pay for the slower clock.
- **Cycles per instruction saved varies widely, from 1.0 to 12.0.** Shifts by 31 are slow on this core (TWO_STAGE_SHIFT), so aha-mont64 #3 saves 12 cycles per instruction removed. wikisort #1 replaces two 3-cycle `addi`s with one 5-cycle instruction, so it saves only 1.
- **A formula can help other programs too.** For example, `add(in0,slli(in1,2))` also saves 174,080 instructions in crc32. See the `other_programs` column.

### Frequency-ranking baseline (2026-10-20): one core with the top 3 non-conflicting formulas

**Selection, done before any measurement.** Canonical formulas are ranked by the finder's `saved` summed over all 8 programs.
- **Conflict rule:** two formulas conflict if, in any program, a site the finder counted for one shares an instruction (PC) with a site it counted for the other, because they compete for the same instructions.
- **Picks:** greedy in rank order, taking a formula if it conflicts with no earlier pick, until there are 3. Picks are kept even if they turn out unplaceable or expensive.
- Request: `results/frequency-top3.request.json`. Full result: `results/frequency-top3.json` (build `4c116ca54af0`, `ALLOW_MUL=1`).

| rank | total saved | formula | outcome |
|---:|---:|---|---|
| 1 | 748,675 | `add(in0,slli(in1,2))` | picked, slot 0 |
| 2 | 704,320 | `slli(add(mul(in0,addi(lui(1103515648),-403)),in1),1)` | picked, slot 1 (`mul`) |
| 3 | 640,192 | `add(in0,slli(andi(in1,255),2))` | conflicts with rank 1 |
| 4 | 528,240 | `add(mul(in0,addi(lui(1103515648),-403)),in1)` | conflicts with rank 2 |
| 5 | 434,988 | `add(srli(in0,31),slli(in1,1))` | picked, slot 2 |

**The core:**
- 3,186 `SB_LUT4`, **+747** over the baseline.
- Fmax median 57.09 MHz (min 54.98, max 59.14), so T_fused = 17.515 ns against T_base = 16.2655 ns.
- **The unit is on the critical arc in 5 of 10 seeds** (2, 3, 4, 7, 9): `reg_op1` → multiplier → `result[26/28]`. In the other 5 the branch path is still the worst.
- All checks pass, and the microtests show 5 cycles per instruction for each slot.

| program | instructions saved | cycles saved | cycles / instr saved | speedup (max rule) | speedup, cycles only |
|---|---:|---:|---:|---:|---:|
| aha-mont64 | 433,152 | 3,681,792 | 8.50 | 1.0844 | 1.1677 |
| crc32 | 174,080 | 696,320 | 4.00 | 0.9584 | 1.0320 |
| edn | 0 | 0 | — | 0.9287 | 1.0000 |
| huffbench | 46,684 | 186,736 | 4.00 | 0.9492 | 1.0221 |
| matmult-int | 0 | 0 | — | 0.9287 | 1.0000 |
| nettle-aes | 527,436 | 2,109,744 | 4.00 | 1.0462 | 1.1266 |
| nettle-sha256 | 475 | 1,900 | 4.00 | 0.9287 | 1.0001 |
| wikisort | 0 | 0 | — | 0.9287 | 1.0000 |
| **total** | **1,181,827** | **6,676,492** | **5.65** | | |

**Reading it:**
- **The rank-2 pick fuses nothing anywhere.**
  - Its crc32 site (696,320) and its wikisort site (8,000) both have no legal position: `rand_beebs` loads 12345 between the members, and the `mul` overwrites `in0`.
  - Rank 5 also gives up 1,836 instructions in wikisort, because that site is in libm's `__ieee754_sqrt`.
  - So the core carries a ~650-LUT multiplier that never executes, and that multiplier is the critical path in half the seeds.
- **The slower clock is charged to every program.** It costs 7.1% on all of them, so the 4 programs with no fused sites (or 475 instructions) come out at 0.929. Of the programs that do gain cycles, only aha-mont64 and nettle-aes stay above 1.
- **Savings add up exactly.** The picks don't conflict, so each program's instruction and cycle savings equal the sum of the same formulas measured alone in the sweep.
- **Being on the critical arc depends on the rest of the core.** Measured alone, the same `mul` unit was never on the arc (58.52 MHz median). With two more units it becomes critical.

### Later results (2026-10-20)

The placeability pre-check (`make hw-placeability`), the top-10 placeable sweep (`make hw-sweep10`), the multiplier probe (`make hw-fastmul-probe`) and the selection experiments (`make hw-experiments`: placement-aware frequency pick and the LUT-budget oracle) are summarized in [hw/README.md](../README.md#results); the files are listed in [results/README.md](results/README.md).

## Known limits

- **One schedule only.** Sites that would need instructions reordered aren't fused. Example: crc32's `mul` candidates, where `rand_beebs` loads the constant 12345 between the members.
- **Library code isn't rewritten:** `libgcc` soft-float and `libm` are precompiled.
- **Liveness is proven only inside a block,** like the finder.
- **LUT counts carry about ±2 of synthesis noise:** the same unit logic gave 2,479 here and 2,481 in the dry run, with only names differing.
- **The fused programs can't run on Spike,** so their instret is checked against site arithmetic, not a trace.
