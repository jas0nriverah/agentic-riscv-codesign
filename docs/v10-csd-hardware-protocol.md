# V10: paired CSD hardware implementation study

This is a separate hardware development experiment. It changes the emitted
implementation; it does not fit an area predictor or revise any frozen V8/V9
target. The existing V9 labels are consumed context. No new hardware target may
be collected before the input preparation and collector source are frozen and
the parent releases the exact preparation hash for collection.

The existing pipeline lowers some constant multiplications only for feature
extraction. Original RTL is still measured. In the retained V9 evidence,
`mul(in0,addi(0,511))` maps to 299 LUT4 and 27 carry cells, although the exact
identity is `511*x = (x<<9)-x (mod 2^32)`. This motivates a paired measurement;
it does not establish a rewrite gain. CSD is a fixed baseline, not a guarantee
of minimum adder-graph cost. [Gustafsson et al.](https://www.yli-kaakinen.fi/publications/TCAS1_99/Gustafsson%2C%20O.%20%282006%2C%20CSSP%29%20Simplified%20design%20of%20constant%20coefficient%20multipliers.pdf)
describe improvements through other representations and sharing;
[Garcia and Volkova](https://arxiv.org/html/2210.02742v2) show why adder widths
and actual mapped cost matter. This experiment permits no approximate arithmetic
or sharing across separately measured circuits.

## Fixed inputs and one rewrite

Use precisely the 32 constant-product rows from the sealed V9 candidate file
(SHA256 `74b1ef78b3d97ab34c940f464345bef21fd8f2441a3e09d6cb21daaa686a5354`).
The eight constants `{11,44,85,340,341,511,1364,2044}` cross four contexts:

| Context | Original formula, with literal K substituted |
| --- | --- |
| Direct product | `mul(in0,addi(0,K))` |
| Add after product | `add(mul(in0,addi(0,K)),in1)` |
| Subtraction before product | `mul(sub(in0,in1),addi(0,K))` |
| Masked subtraction before product | `mul(sub(andi(in0,63),in1),addi(0,K))` |

The 16 signed-shift rows are excluded by input definition, before new targets.
All 32 defined pairs remain in order without filtering or replacements. Each
pair retains its V9 candidate ID, original formula, operation count and source
semantics. Its stable ID is `v10-csd:` plus SHA256 of the original formula. CSD
expansion describes a combinational implementation, not new ISA instructions.

For odd positive `n`, choose signed digit `d=2-(n mod 4)`, except `n=1` uses
`d=1`; even `n` uses zero. Advance `n=(n-d)/2`. Reconstruct from the highest
positive shifted operand, then add/subtract lower terms in descending position.
Rewrite exactly the one constant low-product node, leaving its operand and
surrounding context intact. This fixes 511 to `sub(slli(x,9),x)`. No measured
choice of term order or alternative graph is allowed. The grid requires at most
five nonzero digits, four add/subtract nodes and shift 11; impose a 32-operation
total formula bound. Reject noncanonical formulas, changed source rows,
unsupported operations, invalid signed12 immediates and shifts outside 0..31.

Every internal value is an unsigned 32-bit bit vector. Arithmetic wraps modulo
`2^32`, including negative intermediate values from subtraction. Keep explicit
32-bit intermediate nets and the existing emitter's staged shift convention.
Cache identical operand subexpressions through the same emitter in both arms.

## Proof and physical verification gates

Preparation performs one whole-expression universal QF_BV32 disequality check
per pair, over both unconstrained 32-bit inputs. Only UNSAT is accepted. Its
5,000 ms solver timeout is fixed; preserve query text/hash, solver identity,
result, elapsed time and SAT counterexample/unknown reason. Failed proofs leave
an immutable failure record and prevent a completed preparation. No silent
retries or timeout increases after seeing results.

Source proofs do not validate the emitter. Preparation therefore also seals a
miter made from the actual two emitted modules; only their module names change.
Before area claims, the collector must prove all 32 actual RTL miters with:

```text
read_verilog "<sealed-miter.v>"
prep -top pair_miter -flatten
check -assert
sat -timeout 60 -verify -prove trigger 0 -show-inputs -show-outputs
```

Use a fixed 60-second wall limit per miter, retain full scripts/logs and reject
SAT, unknown, timeout or tool failure. An incomplete RTL proof leaves the
complete primary comparison pending. This requirement narrows the earlier
direction memo: universal mapped-netlist proof is desirable but is not required
for this bounded study. Each measured arm instead receives **2,148 mapped
samples**, explicitly labeled sampled verification.

For each of 64 fresh arm measurements, evaluate actual sealed RTL on the same
100 boundary pairs and 2,048 seeded pairs (seed `2026101522`), against an
independent original-formula unsigned32 oracle. Independently interpret the raw
mapped netlist on those same vectors. Accept only known combinational LUT4/carry
primitives and defined bits; reject unknown cells, black boxes, undriven bits,
cycles and mismatches. These physical samples complement the universal source
and original-vs-CSD RTL proofs; they are not a universal proof of synthesis.

## Frozen synthesis and retained evidence

Predeclare **64 fresh synthesis jobs**, original and CSD for all 32 cases. Do
not reuse the earlier 32 original labels as the paired control. Use the same
`synth_ice40 -top candidate`, followed by `check -assert` and JSON/stat output,
with default carry enabled and no DSP option. Both arms use identical ports,
top, widths, attributes and synthesis settings; no asymmetric keep directives.
Two owned workers, 360-second limit per measured arm, one 64-job attempt.

The preparation binds source/test/protocol files, exact RTL/miter/proof bytes
and input files. `tools.json` binds resolved Yosys/ABC/yosys-config executables,
the complete Yosys data-directory file inventory, Python interpreter, Z3 Python
sources/native libraries and platform. The collector verifies these before and
after native work, uses the pinned ABC/data paths and prevents environment
overrides. The inventory is stronger than an executable digest alone; it is not
a portable hermetic image of OS shared-library caches. Tool or source changes
require a separately retained preparation and release, not mutation of this one.

Preserve each arm's source, script, complete logs, vectors, outputs, mapped JSON,
counts, proof outcomes, failures and timings, with raw ZIP member hashes. Count
SB_LUT4 and SB_CARRY independently from the mapped JSON. Report any change in
the fresh original measurements relative to existing V9 context before
interpreting gains. Do not change frozen V9 artifacts.

## Complete paired report

Primary quantity: `CSD LUT4 - original LUT4` over all 32 cases. Publish the full
eight-constant by four-context matrix, mean, median, extrema and wins/ties/losses.
Give context and constant summaries, with carry counts/deltas separately.
Retain every pair and every failed stage; any missing/failed pair leaves the
complete primary endpoint pending. No outcome-based substitutions, omissions,
fallback implementations or selection of a best rewrite. Cap crossings are
descriptive only. There is no CPU integration, speed, power, device timing or
application-generalization claim. Any later predictor of rewritten hardware
needs its own emitter version and target/training lineage.

## Preparation interface and replay

```sh
.venv/bin/python -m unittest discover -s tests -p 'test_prepare_v10_csd_hardware.py' -v
.venv/bin/python scripts/prepare_v10_csd_hardware.py \
  --root results/2026-10-15-v10-csd-hardware
.venv/bin/python scripts/prepare_v10_csd_hardware.py \
  --root results/2026-10-15-v10-csd-hardware --validate-only
```

Preparation creates its output directory exclusively; preserve failed first
attempts. Replays use a new directory. It opens no new measurement outcome,
fits no model and performs no synthesis/RTL execution. `validate_preparation`
returns `(manifest, recipe, pairs)` without executing a solver; it reconstructs
the exact proof queries and RTL to check their identities. `validate_tools`
separately checks runtime/data digests. The collector consumes `pairs.json`,
`recipe.json`, `tools.json`, `proofs/`, `rtl/` and flat bindings in
`preparation.json`; it must require a parent release binding the exact input
manifest and collector before native jobs begin.

Unit tests include a real universal source proof for the masked-subtraction
511 case and a deliberately wrong rewrite with a SAT counterexample. These
proof preflights precede the first complete 32-case preparation; there is no
claim that preparation is the first-ever solver invocation on these formulas.
