# V7 implementation and proof scope

The new module supplies source-only semantic descriptors and operation-root
normal forms. It never changes original graph features, target labels, fitted
models or original-implementation zero overrides. There is no fit or hardware
mapping in this implementation evidence. `contract.json` binds the exact
8+8 names, source snapshots, safety bounds, solver and 124 passing tests.
Independent generic SMT queries and the fitting-formula audit live in `../audit/`.

`analyze_modes(formula, Budget())` computes bit-only, affine-only and composed
normal forms from the same original expression. One shared500ms proof engine
covers all modes/passes; identical local statements reuse a proved result. Each
record has schema/mode/input_formula/original_formula/normalized_formula/features
and metadata. `analyze_formula`, `feature_dict`, `feature_vector` select a mode;
`feature_matrix` accepts rows and ignores fields other than formula.

Every accepted local transformation has an UNSAT QF_BV32 inequality miter with
exact structural opaque-atom bindings. Its query, query digest, version/native
library digests, result and timing are retained. Ordered path replacements and
recursive congruence give an original-to-final certificate, including the final
addi(leaf,0) operation-root adapter. Products, right/variable shifts and other
nonaffine nodes remain opaque atoms to affine collection; their children may
independently undergo proved transformations. Exact original atom identity
preserves signed/high-product distinctions. A SAT result is a correctness error.
Any unknown, unavailable solver, atom/operation/reconstruction/output/pass/time
budget rolls ALL modes back to the original expression. No unproved partial
form feeds a descriptor. All attempts remain sidecar evidence. The shared
proof_engine.solver_seconds is charged once per input formula toward the runner's
separate total900CPU-second cap. Proof/budget/runtime statuses are not columns.

The affine ring is Z/(2^32). Add/addi/sub and literal-distance sll/slli traverse;
shifts use distance&31 before coefficient multiplication. Constants and exact
opaque atoms collect modulo2^32. Canonical signed nonadjacent digits reconstruct
coefficients with shift distances0..31 and a balanced addition tree. Max16atoms,
64unique eligible-operation nodes per island, four passes and output at most
min(128,2*original_TREE_operations+32) bound the process. Reconstruction cost is
checked before building an expanded tree. Root adapters retain the parser grammar.

Primary combined features concatenate the independent bit8 and affine8 values,
exactly matching the single-block views. The composed normal form supports the
separately declared rewritten-legacy119 control; it does not redefine the primary
columns. This separates additive block attribution from rewrite interaction.

All counts below are nonnegative integers. Bit pattern and affine island
enumeration deduplicate original structural subexpressions. Algebraic occurrence
multiplicity WITHIN an island remains necessary for coefficient collection.

| Suffix after v7_bit_ | Definition |
| --- | --- |
| or_sub_count | Unique original exact (x OR C)-x syntactic patterns; independent of solver outcome |
| sub_and_count | Unique original exact x-(x AND C) syntactic patterns; independent of solver outcome |
| mul_possible_one_bits | Sum of32-known_zero_bit_count over both operands of each multiply occurrence in bit-only normal form |
| mul_unsigned_width_sum | Sum of highest possible-one position+1 (zero has width0) over those operands |
| mul_interpreted_width_sum | Unsigned width, or conservative minimum signed representation width under mulh/mulhsu operand roles |
| mul_signed_unknown_sign_count | Signed high-product operands whose sign bit is unknown |
| output_unknown_bits |32 minus known-zero/known-one bit count at the normalized output |
| normalized_ops | Tree operation count of bit-only normal form, including root adapter |

| Suffix after v7_affine_ | Definition |
| --- | --- |
| island_count | Unique original maximal affine islands within bounds |
| cancelled_atom_count | Across those islands, original unique atom groups with coefficient0 modulo2^32 |
| repeated_atom_occurrences | Sum of occurrence_count-1 per original opaque atom inside each island |
| coefficient_digit_sum | Total canonical signed nonadjacent digits of collected atom coefficients; constant term excluded |
| mul_possible_one_bits | Same support equation on affine-only normal form |
| mul_interpreted_width_sum | Same role-aware width equation on affine-only normal form |
| output_unknown_bits | Same known-bit equation on affine-only normal form |
| normalized_ops | Tree operation count of affine-only normal form, including root adapter |

Known-bit transfer is a conservative independent abstraction: Boolean masks,
masked literal shifts, bit-set full-adder/subtractor carries, comparison0/1
bounds, low-product trailing zeros and multiply-by-proven-zero. Other cases
return unknown. This does not claim exact support or exact nonlinear ranges.
Per-operand sidecars retain operation/operand index/signed role/sign state,
possible-one count, unsigned/interpreted widths and unsigned known-bit bounds.
The second mulhsu operand remains unsigned even for a negative literal mask.

The tests include generic-mask boundary instances, modular overflow, all masked
shift edges, nested affine/bit interactions, right/variable/high-product negative
patterns, shared structural operands, deterministic/idempotent normal forms,
all budget/failure behavior, native-process prohibition, original-zero preservation
and known-bit oracle checks. Universal generic proofs and independent full
certificate replay supplement these finite tests; no prediction-quality claim
follows from semantic correctness alone.

The independent fitting-input audit finds **zero occurrences/changes of the two
new bit identities among1665 fitting formulas**; affine/combined change933.
This study cannot establish the predictive value of those two identity rewrites.
Other bit-block summaries may vary, so a bit-block OOF change cannot be credited
to correlation-rule activation. No rules/data/labels are expanded in response.
The updated contract binds this limitation; its pre-prevalence version is
retained as contract-before-prevalence.json.
