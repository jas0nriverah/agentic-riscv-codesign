# Narrow post-test normalization experiment

This is a diagnosis of consumed V6 test outcomes, not a new independent result. No model, frozen source, feature vector, target, or score was changed. The companion `inspect_normalization.py` only reads the completed diagnostic and sealed vectors, parses formulas, and reports modular coefficients; it generates no replacement AST. Its exact inputs/source hashes and ten largest mapping errors are in `normalization-diagnosis.json`.

The strongest narrow direction is correlation-aware word arithmetic before range/support analysis, with the original implementation graph retained. It may expose useful structure; there is no measured prediction or hardware gain from these proposed rules.

## What already exists and what is missing

`isaforge/structural_features_v3.py:67` already collects additive atoms over Z/(2^32), so additive cancellation is not absent. Its `_normalize` at line 84 rebuilds only when every atom cancels, or exactly one atom has coefficient one, plus an adjacent-constant case. Multi-atom expressions keep their association. The collector does not traverse fixed left shifts. Local `add(x,x)` becomes `slli(x,1)`, which then becomes an opaque atom to subsequent additive collection.

V4 inherits V3 normalization (`structural_features_v4.py:159`), adds shifts/XOR/multiplication rules, and V5 iterates its prepass plus V4 (`structural_features_v5.py:295`). V5's range abstraction explicitly uses independent intervals (`structural_features_v5.py:99`); it cannot generally recover correlations between repeated arithmetic operands. Semantic normalization is already distinguished from original synthesis cost in V5's module contract and `proven_zero_lut` documentation; retain that distinction.

## Concrete motivating errors

The largest mapping error is `add(add(mulhsu(sub(ori(in1,255),in1),slli(in0,16)),in1),in1)`: original target 357 LUT4, prediction 1538.8467, absolute error 1181.8467. Its sealed normalized formula is unchanged. The exact 32-bit identity `(x | C) - x = (~x) & C` proves that the first signed high-multiply operand is in [0,255] with only eight possible support bits. This removes the independent-operand uncertainty in that subtraction. The second-largest error uses the same identity with C=0x55555555, target 423, prediction 905.3717. That mask exposes sixteen positions rather than a contiguous narrow range; support and sign information must be handled separately.

The 156-LUT arithmetic-chain case (prediction 358.0133) collects exactly to `3429 - in1 - (in1 & 65535) - (in0 & 65535)` modulo 2^32, eliminating the affine in0 term. The current sealed normalized formula retains its long chain. Another 108-LUT case (prediction 285.1233) collects to `2*in1 - 2*in0 - (in1 | 0xAAAAAAAA)`; the current normalizer turns a repeated add into a left shift but does not combine it with the surrounding affine terms. These are functional descriptions, not estimates of the original circuit's cost.

The third-largest error already folds `xor(in0,in0)` away; further rules will not address every multiplication failure. Prioritize the two verified gaps rather than treating simplification as a universal explanation.

## Bounded implementation direction for a future version

1. Extend the existing affine collector through constant `sll`/`slli` as multiplication by `2^(shift & 31)`. Combine identical opaque atoms and constants modulo 2^32. Reconstruct a deterministic bounded coefficient DAG, or initially expose coefficient/cancellation descriptors without rewriting. Keep right shifts, variable shifts, comparisons, and high-half products opaque. Do not distribute through them.
2. Add a small proved correlation-rule set, initially `(x|C)-x -> (~x)&C` and `x-(x&C) -> x&~C`, with constants reduced to 32 bits and exact structural operand equality. Analogous identities for two symbolic words can be proved separately; avoid unverified pattern generalization.
3. Run existing known-bit/range/demand analyses on the resulting semantic representation. For the eight-bit multiply operand, this can expose signed nonnegativity and reduced product support. Keep original graph/mapping descriptors and labels. A semantic constant or wire must never force the original RTL area to zero.
4. Put a deterministic operation/depth budget and a single canonical direction on every rule. A full equality-saturation engine is unnecessary for these two gaps; consider one only if measured rewrite-order failures remain and its cache/latency budget is justified.

## Primary-source basis and differences from this task

LLVM's current [InstCombine contributor guide](https://llvm.org/docs/InstCombineContributorGuide.html) requests generic-value correctness proofs, negative and commuted tests, and gives add/sub cancellation examples. This supports a proof-first local rule workflow. LLVM IR includes poison/undef and optional no-wrap flags, whereas these formulas use fixed RV32 wrapping words. Encode this project's semantics directly; do not import LLVM's flag assumptions or unmasked shift semantics.

LLVM's [InstCombineAddSub.cpp source](https://llvm.org/doxygen/InstCombineAddSub_8cpp_source.html) contains related bit/arithmetic transformations, including disjoint-bit addition and an add/or subtraction identity. It demonstrates practical correlation-sensitive compiler rules, not the benefit or correctness of our proposed implementation. Each proposed RV32 identity still needs its own proof.

The PLDI 2021 [Alive2 paper](https://users.cs.utah.edu/~regehr/alive2-pldi21.pdf) reports 47 newly identified LLVM miscompilations, with 28 fixed at publication. It motivates independent translation validation even when unit tests pass; its bounded LLVM control-flow/memory validation is broader and semantically different from our loop-free bit-vector expressions.

The POPL 2021 [egg paper](https://homes.cs.washington.edu/~cnandi/docs/popl21-cr.pdf) explains equality saturation's response to rewrite phase ordering and reports a 20.96x aggregate saturation-algorithm speedup from deferred rebuilding on its test suite. That is an e-graph implementation comparison, not FPGA area prediction, circuit improvement, or expected ISAForge speedup. Its useful transfer is representing multiple equivalents without prematurely choosing one, subject to explicit size/time limits and a cost objective that preserves original-implementation attribution.

## Proof and evaluation gates

Before accepting any rule, encode source and target as 32-bit SMT bit vectors and require UNSAT for their inequality over all inputs and generic masks/constants. Model every shift distance with `&31`; explicitly sign-extend the signed operand for high-half multiplication. A solver timeout/unknown leaves the original expression intact. Per-rule proofs establish soundness; per-formula translation validation can catch reconstruction and rule-interaction bugs.

Add negative patterns where the repeated operand differs, operand order changes subtraction, a right shift is involved, or a high-half product is mistaken for low multiplication. Check signed-edge inputs, zero/all-one/alternating/single-bit masks, constants modulo 2^32, shifts 0/31/32/63, shared subexpressions, stable ordering, idempotence, termination, and size limits. Exhaustive small widths plus boundary/random 32-bit checks supplement, but do not replace, the universal 32-bit proof. Keep the RTL/postfix/recursive oracle implementations separate.

Use only the existing fitting partition for development, then predeclare a matched-budget ablation (original graph+mapping baseline versus added correlation/affine descriptors) and failure policy. The current V6 test and its motivating formulas are consumed development evidence; any claimed improvement needs fresh sealed calibration and test groups. Preserve original-target synthesis rather than silently relabeling normalized RTL. Report error by stratum, tails and group coverage as well as macro MAE, including extractor overhead. No claim of mapping optimality or CPU benefit follows from semantic simplification alone.
