# Candidate RTL correctness and actual synthesis

`isaforge.rtl` turns a discovery formula into a combinational module with two
32-bit inputs and a 32-bit result. Each operation writes a 32-bit intermediate
net, so overflow wraps at every instruction boundary. Equal pure subexpressions
share a net. This is an isolated custom-instruction datapath; processor decoding,
register access, pipeline integration, and execution timing are separate work.

The implementation covers all 24 operations accepted by `parse_formula`:
integer arithmetic, bitwise operations, five-bit shift amounts, signed and
unsigned comparisons, and the four RV32 multiply variants. Immediate arguments
are the decoded values already present in the discovery formula. In particular,
`src/tracing.py` represents LUI with its already shifted 32-bit immediate, so the
RTL does not shift that argument again. ISA semantics follow the official
[RV32I specification](https://docs.riscv.org/reference/isa/v20260120/unpriv/rv32.html)
and [M extension](https://docs.riscv.org/reference/isa/v20260120/unpriv/m-st-ext.html).

## Actual verification

`verify_rtl_batch(formulas, output_dir)` compiles a single Verilator executable
for every supplied formula. It compares the compiled RTL with an independent
Python integer interpreter, on all 100 combinations of ten architectural edge
values plus 1,024 seeded random input pairs. Edge values include zero, -1,
INT_MIN, INT_MAX, and shift amounts 31, 32, and 33. The retained vectors include
both inputs and every expected output. Exact assertions cover wraparound,
signed shifts/comparisons, and all signed/unsigned high-product combinations.

This is simulation-based equivalence on recorded test vectors. It is not an
exhaustive proof over all 2^64 input combinations. The initial operator suite
verified all 24 operations plus five nested formulas: 32,596 comparisons passed
using Verilator 5.050. Its build, executable, vectors, and verification log are
under `generated/real/synthesis/operator-correctness/`.

The actual benchmark matrix exposed an additional chained-shift regression:
Verilator 5.050 incorrectly combined some shifts by adding their shift amounts
modulo 32. The independent oracle caught the discrepancy for
`srli(slli(sll(in0,addi(in1,-11)),12),12)`. RTL generation now encodes shifts as
five explicit concatenation/multiplexer stages that preserve discarded bits.
The exact failing case is retained as a regression, and the fixed circuit passed
4,196 boundary/random comparisons. Before/after logs are under
`generated/real/synthesis/shift-regression-before/` and `shift-regression-after/`.
The full benchmark verifier uses the corrected generator.

## Real resource measurements

`run_synthesis(formula, output_dir)` runs native Yosys twice:

1. `synth -top candidate` maps the RTL into generic logic gates. The returned
   `generic_cell_count` counts actual mapped cells. `generic_logic_depth` counts
   cells on the longest combinational input-to-output path in that JSON netlist;
   inputs and constants have depth zero.
2. `synth_ice40 -top candidate` maps to iCE40 FPGA primitives with Yosys defaults.
   `ice40_lut4_count` and `ice40_carry_count` report the actual counts of SB_LUT4
   and SB_CARRY cells. DSP mapping is not enabled. Device packing and placement
   can affect final resource usage.

The result includes source SHA-256, Yosys version, exact per-cell-type counts,
UTC measurement timestamp, and explicit measurement scope/units. The source,
synthesis scripts, complete logs, JSON netlists, and `metrics.json` are retained.
The initial `add(slli(in0,2),in1)` pilot mapped to 151 generic cells, 58 gate
levels, 30 iCE40 LUT4 cells, and 29 carry cells using Yosys 0.69+post.

These are measured synthesis resource proxies. Gate levels are not nanoseconds;
LUT counts are not physical silicon area. There is no clock-period or benchmark
speedup label. The experiment therefore does not supply invented timing fields
to `build_dataset` or claim that the candidate improves a complete processor.
A predictor trained on these labels predicts isolated mapped resource cost.

## Reproduction

Install native [Verilator](https://verilator.org/guide/latest/install.html) and
[Yosys](https://yosyshq.readthedocs.io/projects/yosys/en/latest/getting_started/installation.html).
On this machine the executables are `/opt/homebrew/bin/verilator` and
`/opt/homebrew/bin/yosys`. No remote compute is required.

```python
from isaforge.rtl import verify_rtl_batch
from isaforge.synthesis import run_synthesis

formulas = ['add(slli(in0,2),in1)', 'mulhsu(in0,in1)']
verification = verify_rtl_batch(formulas, 'generated/real/synthesis/replay-verification')
for index, formula in enumerate(formulas):
    metrics = run_synthesis(formula, f'generated/real/synthesis/replay-{index}')
```

```sh
.venv/bin/pytest -q tests/test_rtl.py tests/test_synthesis.py
```

The integration tests execute the installed tools. They skip when their tool is
unavailable; skipped integration tests do not count as real hardware evidence.
