# V5 development and independent family evaluation protocol

This is a new experiment motivated by the completed V4 audit. All **1,545**
previously inspected historical, V3 and V4 formulas are development evidence.
V4 sources, predictions, labels, artifacts and reported scores remain frozen.
The current task prepares inputs and implementation; it does not authorize
collecting V5 test labels before every compared model and prediction is frozen.

## Input acquisition and scope

The input-only generator predeclares **512** additional development formulas:
64 each in arithmetic_chain, shared_diamond, parallel_branches, mask_logic,
constant_shifts, variable_shifts, comparators and multiplication. These target
the earlier multiplier/output-demand failures and broaden wrapper composition.
The complete development universe is **2,057** unique canonical formulas.
Equivalent development formulas retain original syntax and measured targets;
equivalent expressions can map to different LUT counts.

The **256** fresh synthetic test formulas comprise two endpoints, each with
16 formulas in each of the same eight strata:

* **128 known-family formulas** drawn from the existing broad generator
  families with new values and formula identities. Familiar skeletons are
  allowed and explicitly reported. Their 16 multiplication rows balance eight
  operand regimes (two each) and four multiply variants (four each).
* **128 unseen-composition formulas** drawn from reserved, deeper compositions.
  Both original and normalized ordered operator skeletons must be absent from
  all 2,057 development formulas. They usually contain 5–10 distinct operations,
  exceeding V4's acquisition restriction to 2–4 operations. They test transfer
  to newly composed synthetic structure, not an independent application.

Seeds are `2026101406` for development and `2026101407` for test. Candidate
records retain strata, scope, exact original formula, normalized formula,
original and normalized skeletons, commutative equivalence key, generation
slot/attempt, provenance and full candidate identity. Canonical exclusions,
candidate bytes, generator/normalizer/protocol hashes and timestamps are
recorded before model selection. Input freezes are **provisional** until the
complete final feature vectors pass input sealing before fitting.

Test generation excludes exact canonical formulas and normalized/commutative
equivalence keys from historical and new development, and from other test rows.
This is stronger than V4 string exclusion but is not a complete equivalence
proof. Constants and wires already represented in development may consequently
be excluded from test; coverage counts must be reported, not repaired after
measuring outcomes. Label-free original/normalized feature extraction is allowed
before fitting. No RTL verification, target mapper counts/logs, carry counts or
test labels may be generated or inspected before all model predictions freeze.

The final input seal joins exact normalized formulas, normalized commutative
identities, exact full feature vectors and independently verified equivalence
records into connected components. Proof records require retained evidence and
a proved result; sampled oracle agreement is screening evidence only. The seal
requires complete unique feature coverage and zero development/test component
overlap. Current V5 extractor normalization is joined in addition to acquisition's
V4 normalization; unseen compositions must also have new current-normalizer
skeletons. If the seal fails, retain the failed input record and exclusions and prepare
a separately named deterministic input-only acquisition **before fitting**;
do not remove rows or replace candidates after mapped labels are available.
Every final model must consume the same final declared candidate pool.

Prefit acquisition amendment, 2026-10-14: the first complete V5 feature seal
rejected nine test inputs for development-overlapping identity/feature
components. No fitting or test labels existed. Preserve that input pool,
complete feature records and feature-source manifest in `input-attempts/`.
Regenerate using the same seed, generator, scope/stratum counts and cumulative
exclusion of only inputs rejected by the seal. Extract features only for newly
drawn formulas, retain every failed pool and reason in `input-rejections.json`,
and allow at most eight deterministic regenerations. If sealing still fails,
stop before fitting; no measured outcome can authorize relaxing exclusions.
Development candidates and their already collected measurements stay unchanged.
The final repaired test freeze records the updated protocol and selection
source hashes, prior candidate digest, revision and cumulative exclusions.

## Development, matched estimator budgets and calibration

Development fitting uses original mapped LUT4 targets and these matched views:
original SOG14; original SOG14 plus original graph descriptors; original SOG14
plus dual original/normalized graph descriptors; and original SOG14 plus dual
graph descriptors plus V5 semantic descriptors. The four views are strictly
nested; every larger view retains all original SOG14 features.
Every matched view uses the same six configurations: raw/log XGBoost at depth
3/6, 300 trees, learning rate 0.04, minimum child weight 3 and lambda 5; raw
ExtraTrees with 300 trees, minimum leaf size 1/3 and max-features 1.0. Predictions
are nonnegative. Every view applies the same original generic operator-free
graph zero override. The fixed public 25-tree MasterRTL recipe and frozen V4
artifact are additional references; comparisons with V4 include expanded data
and are not an isolated feature-method effect or published ASIC-score claim.

Form components from all exact feature identities, normalized identities and
verified equivalences; keep original/normalized skeleton partitions explicit.
For calibration and development folds, join both skeleton partitions as well
to prevent related structures or equivalent vectors crossing fit/validation.
Use a deterministic whole-component 80% fitting / 20% calibration split with
`GroupShuffleSplit`, seed `2026101417`. Percentages refer to components; actual
formula counts and all strata distributions must be retained. If fewer than
five fitting components remain or a required stratum is absent, stop and report
the design problem before fitting rather than silently changing the split.

On the fitting portion alone, use five `GroupKFold` folds and select each view's
configuration by macro-stratum OOF MAE, with one historical `workload` stratum
and eight synthetic strata. Use the same fold assignment for every view. Ties
use lexicographic configuration names. These are development selection scores,
not nested independent estimates. Fit all final matched models on the same
80% fitting subset. Calibration rows never enter fitting, hyperparameter or
feature selection. Record the six-fit scores, fold indices, component rules,
full parameters, source/tool hashes, library versions and seeds.

Calibrate a **90% one-sided upper prediction bound** using maxima of `y-p`
within each reserved calibration component, with rank
`ceil((component_count+1)*0.9)` in the sorted component maxima. If that rank
exceeds the number of available components, the upper bound is infinite;
do not report a finite guarantee. A negative quantile may be raised to zero
to keep upper estimates above their point estimates. This is a cluster-bound
construction under exchangeable calibration and future clusters; exchangeability
is not established for these synthetic families, novel compositions, different
cluster sizes, hardware targets or applications. Coverage is therefore measured
descriptively on every test scope. ExtraTrees tree dispersion, if emitted, is
a model diagnostic and is not automatically a calibrated confidence interval.

## Frozen endpoint, release and scoring

The primary endpoint is **macro-stratum MAE across all 128 unseen-composition
formulas**, with primary comparison **dual_semantics minus equally tuned
original SOG14 (`sog_tuned`)**. A negative difference favors the full V5 view.
No other comparator or endpoint may replace this primary comparison after
observing outcomes. Known-family macro-stratum MAE is the declared secondary transfer
endpoint. Balanced strata make each scope's macro MAE equal its pooled MAE.
Report all 256 rows and both scopes; pooled all-test MAE is supplementary.
No zeros, multiplier cases, outliers, failed comparators or unfavorable strata
may be omitted. A failed/missing measurement makes the experiment incomplete.

Secondary metrics retain pooled/per-stratum RMSLE, positive-label MAPE/median
APE, zero-target MAE, signed error, median and 90/95/99th percentile absolute
error, worst underprediction, and cap confusion counts at 16/32/64/128/256 LUT4.
Report cap false accepts and rejects with all three V4 denominators. Report
upper-bound coverage by scope/stratum and candidate and whole-component units,
average slack. This round measures bounds and prediction diagnostics; it does
not fit an abstention/acquisition policy or claim a tested screening-policy benefit.

For each V5 view/reference comparison use 10,000 paired bootstrap cluster draws,
seed `2026101418`, keeping a whole test component together globally if it spans
strata. Freeze `test-clusters.json` from `group_components(test, test_features,
include_skeletons=True)`, using the same original/current-normalized skeleton,
exact feature and equivalence joining rule as calibration. These uncertainty
clusters are broader than the identity-only acquisition seal, because the
known-family endpoint intentionally permits familiar skeletons. Use the frozen
test clusters for both resampling and whole-component bound coverage.
Retain the planned macro-stratum weighting through cluster-weighted
error sums/counts. Reject and redraw draws missing any declared stratum, record
all attempts and rejections, and fail closed if the required valid replicates
are not reached within **100 times the requested replicate count**. This
conditioning and its effect on uncertainty are retained as a limitation.
Report signed MAE differences (V5 minus reference),
descriptive 95% percentile intervals, per-stratum errors and smaller-error/tie
counts. Report cluster definitions, cluster sizes and all comparisons. These
intervals do not prove population coverage, independence, significance after
multiple comparisons or deployment transfer. No fitting, calibration, source
changes or model substitution follows test release.

Before test measurement, freeze every model, prediction list, calibration
threshold, endpoint, evaluator and runtime source, plus input seal, final
candidate pool and exact fitting/calibration rows. Holdout verification and
mapping may then run only after explicit model/prediction release. Verify
original RTL against RV32 semantics; preserve every command, log, raw netlist,
sampled-verification record, failure and wraparound-workaround evidence. Use the
unchanged original synthesis target. Hashes and recorded chronology establish
consistency; they do not independently prove absence of unrecorded prior access.

## Application transfer and end-to-end benefit remain separate

The repository currently provides 19 Embench source directories. Seventeen
already contribute historical labeled development circuits. `nsichneu` and
`statemate` were previously exercised but produced no safe candidates; they are
coverage-recovery cases, not untouched independent application sources. They
may be rerun with a corrected extraction policy, reporting failed or empty
pools, but cannot establish transfer to an unconsumed application family.

Before an application-transfer claim, acquire and freeze separately versioned
external source programs, licenses, compiler/flags, program/input identities,
trace/extraction settings and family-level exclusions. Reserve complete
application families and deduplicate equivalence components against every
development row. Prefer multiple independent families spanning integer DSP,
control, cryptography and general computation, with complete program-level
coverage, including programs yielding zero candidates. Changing inputs within
an already consumed source family is an input-transfer diagnostic only.

A lower synthetic LUT4 error does not establish instruction-selection gains,
CPU speedup, energy savings or avoided measurement cost. Those claims need a
prospective acquisition policy with equal attempted-measurement budgets and
complete isolated/integrated synthesis, timing and executed-program validation.
Carry, registers, routing, decoder/control cost and CPU integration are outside
the current isolated LUT4 target.
