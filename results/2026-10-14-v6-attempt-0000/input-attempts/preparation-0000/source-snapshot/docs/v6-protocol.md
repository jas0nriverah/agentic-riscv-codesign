# V6: mapping representation and new synthetic structural families

V4, V5 and external-transfer results remain frozen. This V6 hypothesis follows
inspection of consumed development and V5 test results; those scores cannot be
repaired or relabeled as fresh evaluation. New inputs below are synthetic RV32
formulas, not independently sourced applications. No source-program, published
MasterRTL accuracy, whole-CPU performance or universal workload claim follows.

## Inputs and bounded acquisition

Prepare192 calibration and192 test formulas: each of eight existing strata
(arithmetic chain, shared diamond, parallel branches, mask logic, constant
shifts, variable shifts, comparators, multiplication) has12 distinct structural
families, each with two constant variants. A family varies operator choices and
expression topology, rather than using one fixed skeleton with many literals.
Grammar seeds are2026101441(calibration) and2026101442(test). Both use the SAME
random grammar and constraints, giving a clearer calibration/test distribution
relationship than V5's known versus deliberately deeper novel scopes. Separate
seeds do not prove statistical independence or exchangeability.

Every candidate uses both RV32 inputs, one RV32 output, only supported parser/RTL
operations, and at most15 original expression-tree operations. This stronger
bound also bounds distinct DAG operations. Shared-diamond repeated operands
retain the same indexed literal bindings. Each unrelated template literal node
is sampled independently; only copies of a shared subtree reuse token IDs and
values. Multiplication has one product operator;
operand/output wrappers vary. Constants include+1,-1 and+/-1365, shifts1..31,
and nontrivial masks. Every stratum varies merge/branch topology and operator
mix; stratum labels describe generator intent, not proved disjoint semantics.

The consumed reference is the union of frozen input-feature manifests for
V5 development2057, V5 test256 and external79 unique formulas. The listed
per-source sum is2392, while canonical deduplication is computed and retained
(actual expected2380); the80 external program rows are not80 unique inputs.
Only input/formula/features manifests are read for exclusions, never target
label files or model predictions. All consumed data, including previous test
and external labels, remains development evidence and cannot be reused as a
fresh evaluation. V6 fitting remains the exact frozen1665 V5 fitting rows;
remaining consumed labels do not enter any V6 fit or selection.

Acquisition rejects overlap with ANY consumed or other acquired structural
family using exact/original/current-V5 and V4 normalized formula identities,
normalized commutative identities, ordered operator skeletons across all
original/normalizer channels, exact frozenV5(313-column) vectors, and exact
V6(336-column) vectors. Input names are preserved by identity rules; skeletons
abstract inputs/literals. Grouping joins these sufficient identities into
connected components. It does not prove complete functional nonequivalence:
no sampled fingerprint is promoted to proof, no target verification or oracle
outcome is used. Constants/wires already consumed can therefore exclude new
candidates that collapse to them, even when original syntax differs.

A complete component must belong to one cohort, one stratum and one declared
structural family. Each pair of variants must share one original skeleton.
All components are disjoint from consumed inputs and the other scope. The
target is12 components per stratum in each cohort; at least8 are mandatory.
The implementation rejects merged families before labels, preserving the
12-family target rather than merely accepting reduced coverage.

For each family slot draw at most2000 candidates per call in deterministic
order; record every rejected candidate pair and reason. The initial384-row pool
is provisional. Label-free generic synthesis uses the frozenV5 pipeline with
no ABC/target technology mapping. Append the fixed23-column original-graph
mapping block (four-leaf/eight-cut budgets) and retain cache/tool/source hashes.
Seal both the old313 and complete336 feature-vector identities. On any feature
collision, reject ALL involved structural families, retain the entire failed
pool/features/seal and draw replacements from the same streams with cumulative
input exclusions. At most eight feature-repair rounds are allowed. Missing or
failed extraction stops acquisition with retained evidence; it is not an
unrecorded reason to replace a costly or unfavorable input. If budget or
coverage constraints cannot be met, stop before labels and amend the design
explicitly; do not relax novelty after outcomes. No target counts, predictions,
residuals, disagreement ranking or measured area guide acquisition.

Files reside in results/2026-10-14-v6/corpus/: acquisition-plan.json,
consumed-manifest.json, consumed-features.json, generation-rejections.json,
acquisition-history.json, attempts/, input-seal.json, and calibration/ and test/
with candidates.json, features.json, components.json and freeze.json each.
Each feature record contains all336 values and an identical first313 v5_values
prefix; candidate and component hashes are bound before label release. A later
lineage must use a new output directory; completed acquisition is immutable.

## Models, primary comparison and fresh calibration

The primary comparison is NEW dual-graph-plus-mapping minus frozen V5 dual
graph, on the fresh192-row test's equal-eight-stratum MAE. A negative difference
favors the mapping view. Freeze all point models and input-only test predictions
before calibration release. The mapping model uses217 columns: the original
194-column V5 dual-graph view (already including14 SOG columns) plus23 mapping
columns. Stored lineage vectors have
all336 columns. Both controls retain the same1665 fitting formulas, frozen five
component folds, original-target zero override, ExtraTrees300 trees/minimum
leaf1/maxfeatures1.0 and random_state2026101401, exactly matching the frozen
V5 dual-graph primary artifact. Earlier three-seed development ablations retain
their original2026101421..23 seeds and are not rewritten. No hyperparameter search is added for
mapping. Existing V5 SOG, original graph, dual graph, full semantics, fixed
public25-tree baseline and frozenV4 reference remain visible; their prior
selection/calibration histories are retained, not presented as freshly tuned.

A fixed exploratory router selects full semantics if the original AST contains
mul/mulh/mulhu/mulhsu, otherwise the new mapping model. Keep both full semantics
and mapping controls and report all strata. This is a preregistered secondary
hypothesis motivated by fitting-only OOF evidence; no gate fitting or tuned
blend is allowed. The router requires calibration of its OWN complete point
predictor. Existing experts' margins cannot be copied to the composite model.
No test result may substitute a different primary model/comparator.

After reviewed input/model/point-prediction freeze and commit, explicitly
release ONLY192 calibration labels and original-RTL semantic verification.
No test measurement or verification is authorized in that stage. The calibration
labels only determine one-sided90% group-max conformal margins: rank
ceil((G+1)*0.9) among complete structural-component maxima(y-point). Raise a
negative margin to0; if rank>G emit an unbounded upper, never a false finite
claim. With96 target calibration components, rank is88. The calibration cohort
cannot select features, estimators, gate rules, acquisition policy or margins
other than this declared rule. Then freeze calibration data/provenance,
thresholds, all test point/upper predictions, evaluator and runtime sources,
review/commit them, and require a separate explicit TEST label release.

The same generator/stratum balance and two-row component size support a stated
exchangeability assumption but cannot guarantee it: novelty filtering against
calibration changes the test sampling process, family components are heuristic,
and strata differ. Report observed bounds honestly. These intervals do not
provide whole-application, different-target or whole-population90% guarantees.

## Test scoring and uncertainty

The primary is the paired equal-eight-stratum test MAE difference for mapping
minus original dual graph. Retain every declared candidate, unfavorable stratum,
zero and outlier. Any failed/missing label makes the experiment incomplete;
there is no postlabel replacement. Report MAE by stratum/component, pooled MAE,
RMSLE, positive-only MAPE/medianAPE, zero-target MAE, signed bias, median and
p90/p95/p99 absolute error, worst underprediction, all point-model predictions,
and cap false acceptance/rejection at16/32/64/128/256 with denominators.

Use10000 paired bootstrap replicates, seed2026101443. Within EACH of eight
strata, sample its COMPLETE test components with replacement, keeping both
variants together and shared comparison draws. No component may span strata;
if one does, acquisition must fail before labels. Every draw retains all strata
without the empty-stratum rejection conditioning of V5. Recompute stratum
error sums/counts and equal-eight macro. Report descriptive95% percentile
intervals, component sizes/counts and the fixed-strata/synthetic-grammar scope.
Intervals condition on declared strata/grammar and do not establish independently
sampled operator-family/application population effects, significance after
multiple comparisons or deployment coverage. Five inherited model seeds are
algorithm sensitivity, not independent experimental units.

Report finite upper fraction, candidate and complete-component coverage,
coverage by stratum, average/minimum slack and tree spread/domain diagnostics
where available. Tree spread and min/max feature-range flags are diagnostics,
not calibrated confidence or a fitted abstention policy. This experiment fits
no decision/acquisition/abstention policy. Report extraction/mapping overhead
separately from accuracy. Four-feasible-cut/reuse/area-flow descriptors are
bounded generic structural proxies, not optimal LUT mapping, Boolean matching
or dedicated carry counts. No new model score may be called independent until
its frozen test is released and completed under this sequence.
