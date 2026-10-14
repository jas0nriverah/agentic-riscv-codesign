# V7 development protocol: correlated bits and modular affine structure

This is a bounded, fitting-only representation study. V6 is published/frozen;
its192 test and192 calibration circuits are consumed mechanism evidence, not
V7 improvement endpoints. Their worst errors motivate hypotheses, not new
labels, rewritten targets or a repaired V6 score. This protocol permits preparation and independent proof audits; fitting requires a separate parent review of the pre-score freeze.
Final feature/proof schemas must be frozen before any V7 OOF scoring.

## Fixed data, estimator and endpoint

Use exactly the original1665 V5 fitting rows/targets, their original order,
frozen five grouped validation folds and original component map. Check all
input hashes against the V5 freeze and retained V6 fitting-feature provenance.
Neither the392 old calibration rows nor any V5/V6 test, fresh V6 calibration or
external-transfer labels enter a fit, feature calculation, rule threshold or
reported V7 development metric. No new target acquisition, held-out-target
feature, hyperparameter search, feature selection or fitted router is allowed.

Each view uses ExtraTrees300,min_samples_leaf1,max_features1.0,n_jobs1, and all
three paired seeds2026101421,2026101422,2026101423 on the same five folds. These
are the earlier development seeds, not a replacement for the frozen V6 primary
seed2026101401. Preserve the original generic-graph operator-free zero override
for every view. A semantic wire/constant NEVER forces the original RTL area to
zero. Predict unchanged original-implementation LUT4 targets.

The development primary is mean nine-stratum macro OOF MAE difference of
base+both new blocks minus base: historical workload plus eight synthetic
strata, each equally weighted. Report every view, seed and stratum, full paired
OOF predictions, bias, RMSLE, positive-only MAPE, zero errors, p95/p99/worst
absolute error, worst underprediction and cap false accepts/rejects. Seed SD is
algorithm sensitivity on shared data, not a population confidence interval.
No OOF gain is an independent accuracy, coverage or application-transfer claim.

## Small blocks and controls

The base is the EXACT217 columns of frozen V6 mapping: V5 dual graph194
(including SOG14) plus mapping23. Original/normalized graphs, mapping descriptors,
column order and values remain unchanged. Reuse validated existing generic
caches only; no new technology mapping or normalized generic graphs this round.

Freeze at most8 bit-correlation and8 affine columns, each a deterministic,
finite nonnegative formula-only descriptor. The frozen bit block measures original exact-pattern counts, multiplier
possible-one/support/unsigned and interpreted widths/sign uncertainty, output
unknown bits and normalized operations. The affine block measures original
maximal-island count/cancellation/repeated occurrences/coefficient digit sum,
normalized multiplier support/interpreted widths, output unknown bits and
normalized operations. Pattern counts describe ORIGINAL syntax, independent of
proof outcome; they are not counts of accepted rewrites. Count unique original subexpressions
consistently. Exact names, equations, units, pass order and empty/fallback values
must be recorded before scoring; this is not permission to expand the block
after seeing errors. Budget/proof/runtime statuses are retained sidecar evidence,
not learned feature columns. Exact ordered bit suffixes after `v7_bit_` are
`or_sub_count`, `sub_and_count`, `mul_possible_one_bits`,
`mul_unsigned_width_sum`, `mul_interpreted_width_sum`,
`mul_signed_unknown_sign_count`, `output_unknown_bits`, `normalized_ops`.
Exact ordered affine suffixes after `v7_affine_` are `island_count`,
`cancelled_atom_count`, `repeated_atom_occurrences`, `coefficient_digit_sum`,
`mul_possible_one_bits`, `mul_interpreted_width_sum`, `output_unknown_bits`,
`normalized_ops`. Combined learned columns concatenate the independent bit8
and affine8 values. A separately composed combined rewrite feeds only the
legacy(rewritten)119 control; it never recomputes the primary16 columns.

Retain these SIX fixed views, at most90 fits(6x3seedsx5folds):

| View | Columns | Purpose |
| --- | ---: | --- |
| Base | 217 | Matched representation control |
| Base+bit | <=225 | Correlated-bit contribution |
| Base+affine | <=225 | Affine contribution |
| Base+bit+affine | <=233 | Declared development primary |
| Base+legacy(original) | 336 | Same119 frozen V5 semantic descriptors on original formula |
| Base+legacy(rewritten) | 336 | Same119 descriptors on accepted combined semantic rewrite |

The last two retain identical feature names/budget and isolate the effect of
stronger normalization on OLD semantic measurements. They do not append the
new descriptors, and never replace the217-column original base. Comparing
combined to base alone cannot distinguish useful normalization from genuinely
new descriptors; report both legacy controls. Do not infer mechanism merely
from feature importance or a seed-stable improvement. If entire matrices are
bit-identical, record that equality and reuse predictions rather than refit a
nominally different view.

Preparation hashes and validates ONLY original fitting targets for later metrics;
features and prevalence never consume target values. Before fitting, report
input-only descriptor prevalence,
unique values, changed-formula counts and training-side variance per fold. A
block absent/constant on all fitting data cannot demonstrate a learned effect;
report that limitation rather than inventing examples, excluding failures or
adding labels within this study. Features consume only formula ASTs and frozen
input caches; no cohort/stratum/target/residual/model score is a feature input.
No scaling, vocabulary, rewrite rule or cache may learn from validation labels.

## Bounded semantics and proof gate

Initially allow only the exact32-bit correlation identities
`(x|C)-x = (~x)&C` and `x-(x&C) = x&~C`, with exact structural equality of repeated
operands and C reduced modulo2^32. Preserve signed interpretation explicitly:
a sparse mask is not necessarily a narrow interval or nonnegative signed word.
Existing V3 already collects add/sub/addi atoms; the new affine hypothesis is
bounded reconstruction of multiatom forms and traversal through FIXED left
shifts as multiplication by2^(k&31) over Z/(2^32). Right/variable shifts,
comparisons, bitwise nonlinear atoms and all products remain opaque to affine
distribution. Do not generalize high-half or signed multiplication identities.

Proposed hard bounds: four deterministic bottom-up passes,16 opaque atoms per
affine island,64 unique input operations per analyzed island, and reconstructed
TREE operation count at most min(128,2*original_tree_ops+32). The64-island bound
counts unique input operations; the reconstructed-output bound counts repeated
tree occurrences. Original structural pattern/island counts are unique, while
coefficient multiplicity within an island remains algebraic. Use one canonical atom/coefficient
order; never oscillate rewrites. All rows remain if a budget is reached.
Record exact original/intermediate/final formulas, applied rules, atom maps,
truncation/fallback reasons and hashes. A proof failure is a correctness failure;
solver timeout/unknown/unavailable or any size-budget failure rolls ALL THREE
modes back to the original semantic representation for that formula. Previously
accepted local steps are discarded, with attempts retained in the ledger. No formula is dropped. Final budgets must
agree with implementation and proof-audit contracts before scoring.

Require universal RV32 bit-vector proofs of each generic rule and affine/shift
reconstruction, plus recursive translation validation for EVERY changed formula:
a full inequality miter must be UNSAT, or a retained compositional proof must
cover every local rewrite and its congruent context. No unproved intermediate
rewrite may feed a feature. Explicitly mask shifts by31 and distinguish signed
mulh/mulhsu from unsigned operands. Frozen solver budget:500ms total solver-check wall time shared by each original
formula across bit, affine and combined modes/passes, with statement-proof reuse;
900 solver CPU-seconds total, one worker. Charge the shared proof engine once per
formula. A formula timeout follows the all-mode fallback policy. Global900-second
exhaustion stops preparation, retains partial evidence and permits no fits or row
dropping. Retain solver version/options/input/result/digest and rule
proof identifiers. If formal validation is unavailable, stop before fitting;
random agreement alone does not authorize accepting a rewrite.

An independent interpreter/proof audit must cover negative operand-order and
nonidentical-operand patterns, modular overflow, shifts0/31/32/63, signed-edge
values, zero/all-one/alternating/single-bit masks, repeated subexpressions,
determinism, idempotence, termination and all budgets. Exhaustive small widths
and boundary/random32-bit checks supplement universal proofs. Prove originals
and rewrites as functions; NEVER synthesize a rewrite and relabel it as the
original implementation's cost.

## Provenance and the next independent evaluation

Write a pre-score manifest containing all sources, exact feature columns,
formula/feature hashes, proof/fallback ledger, library/tool versions, five
folds,1665 indices, seeds/parameters and all six views. Store every result outside
the repository until reviewed; frozen V4/V5/V6 sources/artifacts stay untouched.
After OOF results, any additional rule, feature, seed or condition is a separately
recorded development revision. No new calibration or deployment artifact is
produced by this protocol, and existing margins cannot be transferred to a revised
predictor.


The preparation command is `scripts/develop_v7_semantics.py prepare`; it writes
a source-bound plan before feature generation, then full proof/feature ledgers,
all six matrices, prevalence and a pre-score freeze. `fit` requires a separately
authored parent review that binds the freeze, ledger, semantic source and a
passing independent proof audit. The base217 OOF predictions must exactly replay
the archived mapping development predictions for all three seeds before any
changed-view result is accepted. Exact-matrix reuse requires identical dimensions
and values; constant columns are never dropped to force equality.

Before fitting, union original components with original and accepted normalized
formula/commutative identities for EACH mode. Report all new cross-fold
components and exact full-vector duplicates per view, including original baseline
counts. Stop for parent assessment if a newly proved functional equivalence spans
old validation folds. Keep the original folds and replay metrics descriptive; no
silent regrouping, dropping equivalent rows or independent-novelty claim. Any
safe-group rerun needs a separate pre-score amendment within the fixed fit budget.

Input-only prevalence has already shown that the two proposed correlated-bit
identity patterns do not occur in the original1665 fitting formulas. Their
known-bit descriptors may still vary, but any OOF gain cannot validate learning
these absent identity mechanisms. Retain all six controls without inventing
examples or adding labels.

The next improvement endpoint must use untouched, independently sourced complete
application families with source/license/compiler/input/extraction provenance,
all-consumed identity/equivalence/skeleton exclusions, matched target/device
settings and frozen primary/controls. Reserve fresh calibration families for the
FINAL composite predictor and separate test families before outcomes. Report
equal-family and per-family errors, tails and cap decisions; a novelty subset
missing families cannot replace the complete primary. Do not keep repairing or
rescoring V6 as independent evidence. Integrated instruction-selection/cycle and
clock benefits remain separate future measurements.
