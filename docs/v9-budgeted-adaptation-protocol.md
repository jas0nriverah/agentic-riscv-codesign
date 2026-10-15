# V9 development: a fixed measurement-budget correction

Status: implementation and review before real evaluation. This is a **consumed-V8 development study**, not an independent confirmation. V8 results and all historical model artifacts remain unchanged.

## Question

Can one, three or five paid target measurements improve an existing area predictor's remaining predictions without retraining its forest? The [MARU review](research-update-2026-10-15.md) motivates separating paid adaptation from untouched transfer. Our absolute measurement budgets and iCE40 target are different from its percentage-based adaptation experiments.

## Fixed models and inputs

Use the exact frozen V6 mapping artifact, its original 300 trees, its recorded points and the V8 first-extraction full455 features. Select the named mapping217 columns in their frozen order. No estimator fitting, parameter search, fresh feature extraction, normalization retries or additional hardware measurements occur.

For two formulas, similarity `K` is the fraction of corresponding frozen trees in which their vectors land in the same leaf. Leaf IDs are compared within the same tree, never across trees. For measured residuals `r_i = measured_i - frozen_point_i`, compute:

```
local correction(x)  = sum(K(x, i) * r_i) / (1 + sum(K(x, i)))
global correction(x) = sum(r_i) / (1 + count(measured residuals))
adapted point(x)     = max(0, frozen point(x) + correction(x))
```

The global correction is one fixed ablation. The unmodified point predictor is the baseline. Keep the existing original generic-graph zero override; do not infer a zero target from rewritten semantics. No rounding, cap clipping, extra margin or calibrated uncertainty claim. More observations can worsen error; monotonic improvement is not assumed.

## Query schedule and information boundary

Keep every complete V8 pool and its existing primary/secondary role. Bitcount, DES, FFT and video are the four primary families; related-source isqrt is secondary. Each family has one admitted program in this dataset. A family shares one unique-original-formula budget across its program memberships, and label visibility resets between family episodes.

Use only the frozen cap64 predicted-feasible-merit order for this bounded implementation: feasible predictions first by descending overlap-safe savings, then formula and candidate ID; predicted-infeasible candidates follow by cap excess, then savings and the same ties. A lexicographic program round-robin would allocate queries for a multi-program family. Freeze nested prefixes of at most1,3,5 distinct original formulas. Every queried formula costs one measurement, even when it is infeasible. Existing labels simulate these paid reveals; they are not free policy inputs.

Preparation must not read application target labels or evaluation files. It emits an immutable, hash-bound schedule, original points, same-tree leaf IDs, identity groups, exclusions and source bindings. Complete source and tests are reviewed before the first real evaluation. A separate evaluation stage exposes only queried residuals to the correction function. Save query logs and all unqueried forecasts before scoring those forecasts against the remaining targets. Tests must show that changing unrevealed outcomes cannot change schedules or adapted forecasts.

Dynamic acquisition, additional query policies, extra caps and bandwidth choices are outside this minimal correction experiment. Its outcome cannot establish improved instruction selection; the V8 merit-only selection result is unchanged.

## Grouping and endpoints

Construct conservative within-cohort identity components from canonical originals and the accepted normalized formulas already retained with proofs. Use transitive closure and retain first-run fallbacks. No new equivalence proofs or target-aware grouping. Querying one member excludes its entire identity component from unqueried prediction scoring. Do not transfer a measured area to another RTL representation merely because its function is equivalent.

The **primary descriptive endpoint** is local-adapter minus frozen-point MAE after **three** paid queries per primary family. Both predictions are scored on precisely the same surviving original-formula rows: equal original formulas within each program, equal programs within each family, then equal primary families. Identity groups govern exclusion, not weighting. Report every family difference and all three adapters; budgets1 and5 and the global offset are secondary.

Retain exact queried counts, excluded components/rows, surviving formulas, programs and families. If any primary program has no surviving cases, the complete-family endpoint is unavailable. Never score an empty pool as zero or silently reweight the remaining families. FFT begins with only six formulas; budget5 is especially fragile. Isqrt begins with two and can be exhausted; its score then remains undefined. Include MAE, bias, positive-target MAPE with denominator, true-zero error and cap64 false accepts/rejects where defined.

This study uses known V8 outcomes to motivate the question and consumes those data for method development. Any chosen adapter or revised query policy must later be frozen and evaluated on new reserved source families with the same paid-label budget. A positive result here alone is not a new generalization or literature-superiority claim.
