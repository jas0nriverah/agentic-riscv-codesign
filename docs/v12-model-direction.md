# V12 model direction: isolate target scale before another feature block

Status: a read-only diagnosis and proposed bounded fitting-only experiment. No V12 fit, feature extraction or target measurement has run. Implementing the runner and input-only manifest is authorized separately; fitting requires review of the completed preparation. V6 calibration/test, V8 applications, V9 adaptation/coverage and V10 hardware results are consumed development evidence. Their frozen sources, labels and results remain unchanged.

The immediate question is narrow: **does fitting the same mapping217 ExtraTrees model to `log1p(original LUT4)` improve error and budget decisions relative to raw-target fitting, under identical data and new leakage-closed folds?** This tests target scale and the resulting split/ensemble behavior. It does not claim that a logarithm repairs missing operand semantics.

## Evidence and the actual gap

The [V9 coverage result](v9-coverage-results.md) improves consumed-V8 family MAE from 3.409191 to 2.543396 and consumed-V6 regression MAE from 32.160946 to 29.053759 LUT4. However, regression P99 absolute error worsens from 259.8994 to 264.3972, maximum underprediction worsens from 94.83 to 101.96, and cap128 false rejections increase from four to six. The [risk diagnosis](../results/2026-10-15-v9-coverage-development/risk-diagnosis.json) assigns 50.30% of total absolute error to multiplication and 25.34% to arithmetic chains. None of the six cap64 false accepts is multiplication: three comparators, one parallel branch, one constant shift and one variable shift account for them. All six cap128 false rejects are arithmetic chains. Tail repair and threshold repair therefore need separate endpoints.

The largest augmented-model error remains:

`add(add(mulhsu(sub(ori(in1,255),in1),slli(in0,16)),in1),in1)`

Its original-RTL target is **357 LUT4**, point **1535.116667**, absolute error **1178.116667**. The mask `1431655765`/shift23 variant has target423 and point908.768333. The exact unsigned32 relation `(x|K)-x = (~x)&K` exposes restricted support in the first operand; it also proves nonnegative signed interpretation when bit31 of K is clear. A sparse mask and a narrow contiguous interval are different properties.

This mechanism has **already been implemented**:

- [V7 `_correlation`](../isaforge/semantic_features_v7.py) recognizes both `(x|K)-x` and `x-(x&K)` and requires retained local QF_BV32 proof/congruence before an accepted rewrite. `_known`, `_operand_rows` and `_summary` encode multiplier possible-one/support counts, unsigned/interpreted widths and signed-sign uncertainty.
- The [V7 fitting-input audit](../results/2026-10-14-development-semantics-v7/audit/fitting-inputs/fitting-input-audit.json) records **zero bit-mode rewrites and zero accepted bit steps over all1665 fitting inputs**. Neither motivating correlation pattern occurs there. Affine/combined modes change933 formulas; this is a different mechanism.
- V8's [rewritten-legacy view](../isaforge/area_model_v8.py) retains the original217 graph/mapping prefix and appends existing119 descriptors computed on the accepted rewrite. The inherited [V4 multiplier resource analysis](../isaforge/structural_features_v4.py) already supplies support partial terms, live compressor/final-adder proxies and support holes. It is incorrect to describe another support-width or partial-product column as a wholly untested idea. V7/V8 did not rebuild the original graph prefix from rewritten RTL.
- The V9 coverage model still selects217 columns; its48 new originals are32 positive-constant low products plus16 signed-shift contexts. They contain no high-half multiplication. Thus they do not fill the correlated-high-product training gap.

A formula-only inspection of the original fitting rows finds116 high-product nodes in115 rows. Existing independent known-bit analysis finds77 nodes with total possible-one operand support at most48, and21 signed-first-operand nodes whose sign is known nonnegative. These give some existing restricted-product support, but not direct evidence for the absent correlation pattern. No new solver query, feature extraction, inference or fitting was needed for this count.

For the largest V9 error, original/normalized generic gate counts are both3697 and the selected mapping cover proxy is1981. The model's tree spread is145.41, much smaller than the1178.12 error. Five of six cap64 false accepts have zero outside-range flags. Neither coordinate ranges nor tree spread is a feasibility certificate.

The [V9 residual adapter](v9-adaptation-results.md) is also a useful negative control: at three queries per family, local MAE improves only1.94%, global correction worsens it, and all eight video low-multiply formulas have zero proximity to the queried supports. Increasing an unstructured global offset or repeating the same merit-first support schedule does not address that disconnected support.

## Immediate fitting-only comparison

Use exactly **1713 unique original formulas**: the original1665 fitting rows plus all48 paid V9 coverage originals. Keep original physical LUT4 targets, equal formula weights, the selected217 feature names/order and the existing original-generic-graph zero override. A semantic zero or wire never forces original area to zero.

Input lineage is explicit:

- `results/2026-10-15-v9-coverage-development/original-training.json`: rows, original336 values, development indices and original fitting provenance; verify equality of its selected217 prefix with frozen V8 training data.
- `results/2026-10-15-v9-coverage-development/fit-attempt-0000/coverage-features.json`, `candidates.json` and `measurements/attempt-0000/labels.json`: all48 features, identities and original targets, authenticated by V9 preparation/recipe, measurement completion and fit point-freeze. No model input is taken from outcome metadata.
- `results/2026-10-14-v5/development-data.json` and `split.json`: original row metadata and inherited component map. The combined development file has2057 rows; `corpus/development/dataset.json` has only512 and is not the development-index lookup table.

Two views only:

| View | Fit target | Returned point |
|---|---|---|
| Matched raw control | original LUT4 y | max(0, forest mean prediction) |
| Declared log candidate | log1p(y) | max(0, expm1(forest mean log prediction)) |

Both use300 trees, `criterion='squared_error'`, `min_samples_leaf=1`, `max_features=1.0`, `n_jobs=1`, and paired seeds2026101421,2026101422,2026101423. Five folds give **30 fits maximum**. No hyperparameter search, seed selection, new feature block, weighting, target clipping, fitted bias/smearing correction, per-tree inverse averaging or calibration fit is included. These inverse/averaging choices are different predictors and must not be substituted after scoring. [Official transformed-target API/source](https://github.com/scikit-learn/scikit-learn/blob/main/sklearn/compose/_target.py), [ExtraTrees documentation](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.ExtraTreesRegressor.html).

A log target changes the loss scale and reduces the influence of large absolute target differences in splitting; inverse-transforming an ensemble mean does not recover the same arithmetic conditional mean. It may worsen underprediction or high-area tails. An RMSLE/MAPE improvement alone is insufficient for the stated LUT4/budget objective. No GNN, knowledge distillation or a borrowed literature percentage is warranted by these1713 rows.

## Freeze grouping before labels enter the runner

Preparation may read the authorized fitting targets for validation/hashing, but group/fold construction must use whitelisted formula/source/feature fields only. Do not read V6 calibration/test or V8 target files in preparation, fitting, fold assignment, model selection or thresholds.

Build a transitive union over the1713 rows using:

1. Original V5 `split.component_by_formula` membership. These inherited groups already include their frozen skeleton/equivalence construction; preserve them rather than inventing unavailable `structural_family_id` fields.
2. Shared canonical originals and shared saved accepted normal forms, including their frozen commutative `isaforge.v5_corpus.equivalence_key`. Original-row aliases come from V9's complete `consumed-input-ledger.json` filtered to these1665 formulas. New48 aliases come from `identity-analysis.json`: original/V5 normalization and only V7 bit/affine/combined modes whose saved `metadata.status` is `accepted`. Rejected/fallback modes add no proposed aliases. Reuse the retained evidence; **no new normalization solver run or timeout retry** is needed.
3. Exact selected217 vectors after the same float32 conversion the learner uses, normalizing signed zero before byte-key comparison. This is a split safeguard, not functional equivalence; retain the edge reason separately.
4. Each new V9 context as one group: all eight constants in each of four product contexts, or all eight shift values in each of the two signed-shift contexts. Keep complete contexts together even when this makes validation harder. Cross-link these to inherited groups only through the declared rules above.

All equivalence edges compose transitively. Do not union arbitrary new skeleton matches globally; report them as diagnostics. In particular, V7 found a linked eight-row component spanning inherited folds and exact-vector collisions across folds, so replaying the old folds without closure would perpetuate a known split defect.

Assign new folds deterministically, without label values: order components by decreasing member count, then SHA256 of compact sorted canonical-formula JSON. For component stratum counts `c[s]`, choose the fold minimizing `(sum_s c[s]*current_fold_count[s], current_fold_total_rows, fold_index)` and update its counts. Use strata from combined V5 metadata (`workload` when absent); assign new product rows to `multiplication` and new signed-shift rows to `constant_shifts`. There is no fold-seed search. Train on four folds and assess the fifth. Require at least five components, nonempty assessment folds and all nine strata in every training partition. Missing assessment-fold strata are reported; primary metrics aggregate all OOF rows by stratum. If closure makes this infeasible, retain the manifest and stop for review; do not weaken grouping after seeing scores.

Freeze the complete components/edge reasons, collision classes, fold memberships/counts, stratum/zero denominators, data/source/runtime hashes and30-fit schedule before any fit. Whitelist feature records. Synthetic poison tests must show labels/residual/benchmark outcome fields cannot change matrices, groups or folds. Exact save/load point agreement and all-row forecast completeness are required before scoring.

## Endpoints, decisions and promotion

The declared point primary is the three-seed mean **nine-stratum macro OOF MAE difference, log minus matched raw**, with each stratum weighted equally. Preserve each seed and every formula. Report pooled MAE/bias/RMSLE, positive MAPE with denominator, zero-target error, P95/P99/worst absolute error, maximum underprediction, and every stratum. The restricted-high-product counts above are input-coverage diagnostics; no additional subset score is predeclared. Complete formula-level forecasts remain available for separately labeled error diagnosis. Algorithm-seed SD is not a population interval.

Budget co-endpoints are **cap64 false accepts and false rejects separately**, with feasible/infeasible denominators and paired changed decisions. Caps32/128 are fixed sensitivity analyses. Report P99 and maximum underprediction beside mean improvement. Do not optimize a post-hoc combined score or call fewer accepts a win while hiding additional false rejections. A candidate that improves mean error but worsens the cap64 tradeoff or tail is a mixed result requiring review, not automatic promotion.

This fitting-only corpus has no uniform complete application pools/merit metadata and many groups cannot support five queries. Do not manufacture a B1/3/5 selection claim from it. A later full1713 refit and consumed-V6/V8 diagnostic replay require a separate fixed release; save all points before opening those evaluation targets. Those already consumed sets remain regression/development evidence, even if they improve. Never choose the best of the three development seeds; any final single-model seed is fixed2026101401 in advance.

Risk intervals and acquisition are separate subsequent experiments. A common upper offset can exchange false accepts for false rejects and cannot be called a better point estimator. Two-sided bands must retain ambiguous/abstained counts on the full pool and charge every resolved target to the same budget as merit/random controls. Any conformal-style claim needs disjoint calibration groups and relevant exchangeability assumptions; correlated generated families or shifted applications do not automatically satisfy them. [Conformalized quantile regression](https://arxiv.org/abs/1905.03222), [conformal prediction beyond exchangeability](https://arxiv.org/abs/2202.13415).

## Conditional coverage batch and genuinely reserved transfer

The immediate experiment costs **zero new physical labels**. If its failure trace still supports missing correlated-product/affine/comparator coverage, prepare a separate batch of **at most48 original circuits**, not another feature-count expansion. A bounded allocation is16 correlated high products (two exact correlation identities × four masks × two fixed shifts),16 multi-atom affine-chain contexts, and16 comparator/shift composition contexts. Masks, shifts and all exact ASTs must be input-sealed before measurement, checked against the complete consumed ledger and immediate encodings, with original RTL targets and all failures retained. These counts are a recipe direction, not authorization to invent replacements or measure now. Freeze the exact48 and matched same-data controls in a new protocol first. This would still be targeted development, not independent confirmation of those known failure mechanisms.

After selecting and freezing the final predictor, feature/proof code, calibration history and decision policy, reserve **up to48 new original targets from at least eight previously unconsumed source groups** in independently sourced computation regions. Seal source snapshots, complete eligibility/pool extraction, group membership and the total measurement budget before labels; do not trim a pool using target outcomes. If complete input regions exceed the budget, revise scope before release rather than retaining favorable cases. Keep related sources, accepted identities and feature-collision groups on one side of any boundary. A previously reserved cohort whose outcomes informed this design is consumed, regardless of its old name.

Score all reserved originals and source-weighted errors, all threshold decisions and fixed B1/3/5 measurement policies versus frozen/raw, merit and seeded random controls on identical pools. Exhausted pools get explicit undefined remaining-case denominators. Full oracle synthesis is experimental collection cost; each policy's charged reveals are reported separately. This small reserved cohort can provide independent evidence for its declared sources, not a calibrated population guarantee or CPU claim. A new calibration claim needs a separately budgeted calibration cohort; it must not borrow these evaluation labels or silently reuse the old V6 margin.
