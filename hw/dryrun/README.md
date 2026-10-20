# Dry run: one crc32 candidate end to end (PROVISIONAL)

> **Every choice here is provisional and is not a team decision.** That covers the PCPI interface, the encoding (custom-0, funct7=2, funct3=0), assembly-level rewriting, the 1-cycle PCPI handshake, the clock-period rule (root [README](../../README.md#measurement-protocol)), and the proposed `candidate_id`. The point is to show that the whole path, from candidate to RTL, rewritten binary and measurement, works on one real candidate under the baseline's protocol.

```
make hw-dryrun          # everything below; writes hw/dryrun/results.json (about 80 s after hw-baseline)
make hw-dryrun-rtl      # regenerates the datapath and fails if hw/rtl/cx_crc32_xoridx.v differs
make hw-dryrun-micro    # directed microtests and trap tests
make hw-dryrun-route    # fused core, seeds 1-10, frozen pins
make hw-critpath        # critical path per seed, stock and fused cores -> hw/dryrun/critical_paths.csv
```

## Result (2026-10-20)

| | baseline | fused | change |
|---|---:|---:|---:|
| crc32 cycles | 22,461,391 | 21,242,831 | −1,218,560 (−5.43%) |
| crc32 instret | 3,831,152 | 3,482,992 | −348,160 (−9.09%) |
| `SB_LUT4` | 2,439 | 2,481 | +42 |
| Fmax median, routed (seeds 1–10) | 61.48 MHz | 65.04 MHz | not credited, see below |
| Fmax min / max, routed | 59.86 / 64.98 | 62.81 / 67.59 | |
| unit on the critical arc | | 0 of 10 seeds | `critical_paths.csv` |
| period used (provisional rule) | 16.2655 ns | 16.2655 ns | max(T_base, 15.376) = T_base |
| **speedup** | | **1.0574** | |
| speedup, cycles only | | 1.0574 | same here, because the routed clock isn't slower |
| speedup if the routed Fmax were credited | | 1.1185 | for reference only |

- **Correctness:** the fused crc32 passes `verify_benchmark` on the fused core (exit word 1).
- **Stock programs on the fused core:** all 8 match the baseline's cycles and instret exactly.
- **Stock flow with `FUSED=0`:** reproduces `hw/results/baseline.csv` byte for byte, and gives the same per-seed Fmax and the same Yosys stats.
- **All checks in `report.py` pass** (`"problems": []`).

**Fmax.** In short, the faster routed clock (61.48 → 65.04 MHz) is placement noise and isn't credited. The provisional rule in the root [README](../../README.md#measurement-protocol) is T_fused = max(T_base, T_fused_measured): a faster clock is never credited and a slower one is always charged. Here the routed clock is faster, so the fused core keeps the baseline's period, and the speedup equals the cycles-only figure, 1.0574. The critical-path analysis below shows why the faster clock isn't real: the unit isn't on the critical path in any seed.

In detail, `make hw-critpath` classifies every seed's post-route clk→clk path on the Yosys netlist (`critical_paths.csv`, table below):
- **Fused core:** all 10 paths are PicoRV32's branch decision. They run from `reg_op2` through the ALU compare (a carry chain in 9 seeds, the equality XOR/NOR tree in seed 7) to the `mem_do_rinst` clock enable.
- **Stock core:** seeds 2–3 and 5–10 have the same path shape. Seeds 1 and 4 are inside the divider (`dividend[1]` → `quotient[21]`).
- **No arc touches the unit:** in no seed does the arc start or end at a unit register (`active`, `result[9:2]`), or enter unit-dependent logic through unit logic.
- **The last LUT on every fused path,** the `mem_do_rinst` enable, does also read the unit's `active` register (via PCPI `ready`). That's on input I1; the arc enters on I3, the branch result.
- **Seed 7** passes one LUT shared with the unit: `reg_op1[0] ^ reg_op2[0]`, which feeds both the ALU equality compare and `result[2]`. The arc uses the comparator side; the unit only adds one load on that net.
- **Names in the reports are misleading.** A LUT named `fused.unit.active_SB_LUT4_…` sits on every fused path, but its inputs are `cpu_state`, the branch flag, `resetn` and the compare result; it's PicoRV32's branch-not-taken logic, and Yosys just borrowed the name. *An earlier version of this README read that name as the unit adding a LUT to the critical path. That was wrong.* For the same reason `critends.py` reports `pcpi_mul.pcpi_rs2` as `reg_op2`, since `picorv32.v:192` has `assign pcpi_rs2 = reg_op2`.
- **The rise is placement noise:** the fused core's branch-path delays (14.80–15.92 ns) are shorter than the stock core's (15.39–16.71 ns), even though the unit isn't on those arcs.

### Measurement row

```json
{"candidate_id": "2574c9b9f4e7c9c6565d46f81f6ab4d403b1c2b31e713ffaf5774c91aca3b2bc",
 "benchmark": "crc32", "formula": "slli(andi(xor(in0,in1),255),2)",
 "measurement_source": "hardware",
 "baseline_cycles": 22461391, "candidate_cycles": 21242831,
 "baseline_period_ns": 16.2655, "candidate_period_ns": 16.2655,
 "luts": 2481, "speedup": 1.0574, "speedup_cycles_only": 1.0574}
```

`candidate_id` is the proposed `sha256(json([benchmark, canonical_formula]))`. It's computed with the ML branch's own `candidate_id()` (compact JSON separators), so both sides hash the same way. The team still has to agree on it. `baseline_period_ns` is 1000 / the baseline's median Fmax. `candidate_period_ns` follows the provisional rule, max(T_base, T_fused_measured): the baseline period here, because the routed fused clock is faster than the baseline. The routed fused period (15.376 ns) is kept in `results.json` under `period_rule`.

### Critical paths (`critical_paths.csv`)

| seed | stock Fmax | stock path: start → end (pin) | fused Fmax | fused path: start → end (pin) | unit on arc | shared with unit |
|---:|---:|---|---:|---|---|---:|
| 1 | 60.21 | `pcpi_div.dividend[1]` → `pcpi_div.quotient[21]` (CEN) | 67.30 | `reg_op2[4]` → `mem_do_rinst` (CEN) | no | 0 |
| 2 | 61.33 | `reg_op2[4]` → `mem_do_rinst` (SR) | 65.10 | `reg_op2[0]` → `mem_do_rinst` (CEN) | no | 0 |
| 3 | 60.16 | `reg_op2[4]` → `mem_do_rinst` (SR) | 62.81 | `reg_op2[1]` → `mem_do_rinst` (CEN) | no | 0 |
| 4 | 63.19 | `pcpi_div.dividend[1]` → `pcpi_div.quotient[21]` (CEN) | 67.59 | `reg_op2[2]` → `mem_do_rinst` (CEN) | no | 0 |
| 5 | 60.31 | `reg_op2[0]` → `mem_do_rinst` (CEN) | 66.80 | `reg_op2[4]` → `mem_do_rinst` (CEN) | no | 0 |
| 6 | 61.69 | `reg_op2[0]` → `mem_do_rinst` (CEN) | 64.98 | `reg_op2[4]` → `mem_do_rinst` (CEN) | no | 0 |
| 7 | 61.64 | `reg_op2[0]` → `mem_do_rinst` (CEN) | 63.75 | `reg_op2[0]` → `mem_do_rinst` (CEN) | no | 1 (shared XOR) |
| 8 | 61.74 | `reg_op2[0]` → `mem_do_rinst` (CEN) | 63.98 | `reg_op2[0]` → `mem_do_rinst` (CEN) | no | 0 |
| 9 | 59.86 | `reg_op2[4]` → `mem_do_rinst` (CEN) | 66.46 | `reg_op2[0]` → `mem_do_rinst` (CEN) | no | 0 |
| 10 | 64.98 | `reg_op2[4]` → `mem_do_rinst` (CEN) | 64.19 | `reg_op2[0]` → `mem_do_rinst` (CEN) | no | 0 |

**How the check works** (`hw/scripts/critcone.py`):
- **Unit registers:** flip-flops whose output is `fused…active` or the result register that drives `pcpi_rd` (9 here).
- **On the arc** means any of: (a) the path starts at a unit register; (b) it ends at one; (c) it enters a cell whose output depends on unit state, through a net that feeds a unit register. Condition (c) catches a combinational decode path such as `pcpi_insn` → match → `wait` → core state.
- **Shared logic doesn't count:** a gate that also serves the ALU, like seed 7's XOR, isn't "on the arc".
- **Self-test:** before building the table, `critcone.py --selftest` runs synthetic paths that use nextpnr's real cell naming (`_LC`, `_DFFLC`) through each of (a), (b) and (c) on the fused netlist, and fails unless all three come back as on the arc.
- **Shared-logic columns:** `critgroups.py` counts how many path cells also compute the next state of the unit, the PCPI handshake (`pcpi_valid`, `pcpi_timeout`), the multiplier, or the divider.

## Steps

### 1. Candidate

**In short:** I took the top crc32 candidate that has two register inputs and no multiply. It's the CRC table index `((crc ^ byte) & 0xff) << 2`.

**In detail:** `make candidates` needs `riscv64-unknown-elf-objdump`, because `src/candidates.py` hard-codes that name, and `src/` wasn't edited. A local symlink `~/tools/bin/riscv64-unknown-elf-objdump` points to xPack's `riscv-none-elf-objdump` (GNU objdump 2.45), and `~/tools/bin` was put on `PATH` for that one command only. `RISCV_PREFIX` keys off `riscv64-unknown-elf-gcc`, which doesn't exist, so it still resolves to `riscv-none-elf-` (checked with `make -pn`).

The filter was size ≥ 2, `in1` present, and no `mul*`. Three candidates tie at `saved` = 348,160. The order of tied entries in `crc32.json` comes from Python set iteration and means nothing, so the choice among the three was made by hand:

| formula | size | runs | saved | chosen |
|---|---:|---:|---:|---|
| `srli(slli(add(in0,in1),1),1)` (PRNG in `rand_beebs`, `in1` = constant 12345) | 3 | 174,080 | 348,160 | |
| `slli(andi(xor(in0,in1),255),2)` (CRC table index) | 3 | 174,080 | 348,160 | **yes** |
| `add(in0,slli(andi(in1,255),2))` (overlaps the chosen one) | 3 | 174,080 | 348,160 | |

### 2. Hardware

**In short:** the ML branch's generator wrote the Verilog for the formula. A small PCPI unit wraps it and answers only funct7=2/funct3=0 on custom-0. The core gets it only when `FUSED=1`.

**In detail:**
- **Datapath:** `hw/rtl/cx_crc32_xoridx.v`, generated by `hw/dryrun/gen_rtl.py` with `generate_rtl()` from the vendored `hw/isaforge/rtl.py`. The generator worked unmodified, so nothing was hand-written. Its explicit shift-mux stages have a constant shift amount and fold to wiring in Yosys. `make hw-dryrun-rtl` regenerates the file and `cmp`s it with the committed copy.
- **PCPI wrapper:** `hw/rtl/pcpi_fused.v`, adapted from the ML branch's `hardware/pcpi_single.v`. It matches `(insn & 0xfe00707f) == 0x0400000b`. It latches the result on the first `pcpi_valid` edge and raises `ready`/`wr` the next cycle. `wait` goes high combinationally on decode, so the core's PCPI timeout never fires for this encoding.
- **Wiring:** `core_top` has a new `parameter FUSED = 0`. When it's 0, `ENABLE_PCPI` is 0 and the PCPI inputs are tied off exactly as before. When it's 1, `ENABLE_PCPI` is 1 and `pcpi_fused` is instantiated. The ports are unchanged, so the frozen `core_top.pcf` still applies. PicoRV32's `WITH_PCPI` is already 1 in the stock build because MUL/DIV use the PCPI path, so `ENABLE_PCPI=1` only ORs the external unit into `pcpi_int_wait`/`pcpi_int_ready`.
- **Unsupported encodings** still trap through PicoRV32's PCPI timeout plus `CATCH_ILLINSN`.
- **Encoding clash avoided:** the ML branch's `pcpi_candidates.v` used funct7=1/funct3=0 for this same formula. That slot was deliberately not reused (see the allocation table in the root [README](../../README.md#custom-instruction-encoding)).

### 3. Directed microtest

**In short:** a bare-metal program runs the new instruction on over 1,000 operand pairs and compares each result to Python. Small timing programs measure how many cycles it takes, and trap programs check that every other encoding still faults.

**In detail:** `hw/dryrun/microtest.py` writes assembly that `make` builds with main's linker script and runs in the unmodified harness.
- **`micro-check`:** 1,181 vectors. These are the ML branch's 10×10 `BOUNDARIES`, 9×9 byte edges (`0x7f`, `0x80`, `0xff`, `0x100`, `0xffffff00`, …), and 1,000 random pairs from seed 20261020. Then come 4 aliasing cases: rd=rs1, rd=rs2, rs1=rs2, and rd=x0 (x0 stays 0 and nothing else is written).
- **The expected values** come from the ML branch's `evaluate_formula`. The generator aborts unless a hand-written `((a^b)&0xff)<<2` agrees on every vector. A mismatch would exit with `(index << 1) | 1`.
- **Result:** all 1,185 checks pass on the fused core. The stock core traps on the first custom instruction.
- **Traps on the fused core:** funct3=1, funct7=1 (the ML encoding), funct7=3, and custom-1 with the same funct fields all trap.
- **Cycles:** measured with the harness window, (128× block − 64× block) / 64, so fixed overhead cancels.

| block | cycles |
|---|---:|
| fused `.insn` | 5 |
| `xor` alone (native ALU op) | 3 |
| `xor` + `andi` + `slli 2` (what it replaces) | 12 |

The PCPI overhead is **+2 cycles** over a native register-register ALU op, and each executed site saves **7 cycles**. With 174,080 executions that predicts 1,218,560 saved cycles, and the full run measured exactly 1,218,560.

### 4. Software

**In short:** I compiled crc32 to assembly with main's exact flags, swapped the three-instruction chain for the custom instruction wherever its in-between values are thrown away, and linked as usual.

**In detail:**
- **Build:** `crc_32.c` → `.s` with main's `CFLAGS` (`-march=rv32im -mabi=ilp32 -O2 -std=gnu17 -DCPU_MHZ=1 -DWARMUP_HEAT=1`). It's linked with `hw/sw/startup.S`, the other `HW_SETUP` files and main's linker script.
- **Control:** linking the unrewritten `.s` gives an image byte-identical to the baseline's PicoRV32 crc32, so going through assembly changes nothing.
- **What the rewriter does:** `hw/dryrun/rewrite.py` finds `xor X,A,B` → `andi Y,X,255` → `slli Z,Y,2` inside one basic block (blocks end at labels and jumps/branches/calls). It replaces the `slli` with `.insn r 0x0b, 0, 2, Z, A, B` and deletes the other two.
- **When a site is rewritten:**
  - X has no reader except the `andi`, and Y none except the `slli`.
  - Both are overwritten later in the same block. A value that might live past the block end counts as live, and the site is skipped and logged.
  - No instruction from the `xor` up to the `slli` writes A or B.

Rewritten sites (`generated/hw/dryrun/sw/rewrite.json`; none skipped):

| `.s` line | function | baseline PC | original | fused | runs in Spike trace |
|---:|---|---|---|---|---:|
| 29 | `benchmark_body` (crc32pseudo inlined) | `0x80000278` | `xor a5,s0,a0; andi a5,a5,0xff; slli a5,a5,2` | `.insn r 0x0b, 0, 2, a5, s0, a0` | 174,080 |
| 68 | `crc32pseudo` (out-of-line copy) | `0x800002f8` | same | same | 0 |

In both sites every intermediate is `a5`, which the `slli` itself overwrites. The out-of-line `crc32pseudo` never runs inside the window. That matches the finder's `places: 1`.

### 5. Measurement

**In short:** I used the same simulator window, pins and seeds as the baseline. Instructions dropped by exactly the predicted amount, and the stock programs didn't move by a single cycle.

**In detail:**
- **instret:** baseline − fused = 3,831,152 − 3,482,992 = **348,160**. That equals (size − 1) × sites executed = 2 × 174,080, and it equals the candidate's `saved`. There's no gap: the one executed site runs exactly as often as the candidate's block, and the dead copy contributes 0.
- **Cycles:** −1,218,560. That's 7 × 174,080, matching the microtest prediction exactly.
- **Cycles vs. instructions:** cycles fall 5.43% while instret falls 9.09%. The removed `xor`/`andi`/`slli` cost 12 cycles together and the fused instruction costs 5. The rest of the loop, including the `mul` in `rand_beebs`, which takes about 40 cycles, is unchanged.
- **Stock on the fused core:** all 8 programs match the baseline exactly (crc32: 22,461,391 cycles, 3,831,152 instret).
- **Synthesis:** `hw/dryrun/ice40_fused.ys` is `hw/synth/ice40.ys` plus `chparam -set FUSED 1`. Routing uses the same nextpnr command and the committed `hw/synth/core_top.pcf`. Per-seed Fmax for seeds 1–10: 67.30, 65.10, 62.81, 67.59, 66.80, 64.98, 63.75, 63.98, 66.46, 64.19 MHz.

## Provenance

| File | Source |
|---|---|
| `hw/isaforge/rtl.py`, `features.py`, `__init__.py` | `origin/ai-guided-ml` @ `7431a543f9c36c538f9733870884cfb88c90f61c`, `isaforge/`, copied unmodified. sha256 `45cb8bfe…219e`, `1aa3a05b…1c84`, `788b8939…109a` |
| `hw/rtl/cx_crc32_xoridx.v` | Generated by `hw/isaforge/rtl.py::generate_rtl` |
| `hw/rtl/pcpi_fused.v` | Adapted from `origin/ai-guided-ml:hardware/pcpi_single.v`: new decode mask, new datapath name |

## Known limits of this dry run

- One candidate, one benchmark, one encoding. There's no general instruction allocator.
- The rewriter matches only this formula's three operations and proves liveness only within a block.
- The fused binary can't run on Spike, so its instret is checked against arithmetic, not a trace.
- The PCPI unit has a registered output, as the ML branch's did. A combinational `ready` might save a cycle per instruction, but it would put the datapath on the register-file write path. Neither effect was measured.
