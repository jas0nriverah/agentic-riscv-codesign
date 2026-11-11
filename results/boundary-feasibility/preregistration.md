# Direct budget feasibility: preregistration

This is a preparation artifact. No classifier fits, native features, verification or synthesis labels are authorized by it. Execution requires independent approval of the frozen protocol and a parent authorization bound to that exact protocol.

## Fixed method

Two native scikit-learn `ExtraTreesClassifier` models jointly learn three nested indicators: area≤32, area≤64 and area≤128 LUT 4. Each forest uses shared multioutput partitions; `MultiOutputClassifier` and independent per-cap estimators are excluded. The two fits differ only in their input columns: frozen 217 versus frozen 217+16 localized carry-aware descriptors. Both reuse the exact ordered 1,889 training rows, area targets and matrices from boundary-corroboration. There are zero new training labels and zero consumed evaluation labels in fitting.

Both fits use 300 trees, seed 2026101401, one thread, `max_features=1.0`, Gini impurity, no bootstrap, no class or sample weights, and the fully explicit parameter dictionary in the runner. Order and selection are fixed: augmented 233 first, coverage 217 second; select the first passing every development gate, otherwise select none and evaluate the augmented diagnostic. Maximum two fits and a 120-second model-stage deadline; no retries, grids or additional variants.

At inference, locate positive class 1 in each output's own `classes_`, including singleton outputs. Retain all probabilities and check their nondecreasing order across caps; never sort, clip or repair them. These probabilities are uncalibrated.

Start at the frozen budget-release prediction. On the same original-AST root-XOR/add/direct-compound-SRA scope and formula-only per-chain support as the previous trial, a cap qualifies only if signed≤cap<release and learned feasibility probability≥0.5. Exact 0.5 ties accept. Return the smallest qualifying physical cap, otherwise release. No legacy median or learned-regression bypass. Bounds remain signed≤candidate≤release.

All four training width/sharing cells are already represented, so the coarse support guard is inactive inside this scope. The classifier comparison tests the full 16-column block; it cannot isolate carry analysis. Comparing classification with prior regression also changes the learning objective.

## Retained evidence and gates

The retained corpus has 22 panels,1,049 metric rows and 1,017 circuit records;32 metric rows repeat shared controls. Preserve 25 named subgroups and the evaluation-only inventory of 50 required acceptances and 23 rejections, including 10 core override rejections. IDs and old labels are used only to evaluate these gates, never as prediction inputs or fitted targets.

Every retained full panel and named group must preserve MAE, positive-target MAPE and maximum underprediction against all six frozen policies: release, structural, learned 217, abstention, corroborated 233 and corroborated 217. At each cap 32/64/128 require FA≤release, FR≤signed and explicitly zero newly introduced FA/FR cases. Record feasible/infeasible denominators, corrected and new errors separately. Positive MAPE is 100×mean(abs(actual−prediction)/actual) over positive targets; zero targets remain in MAE/cap/tail metrics.

The bounds make some existing release false acceptances and signed false rejections unrepairable. The six examples in `policy-limitations.json` stay visible. This trial tests excess rejections while protecting existing gains; a pass must not be described as solving every budget mistake.

## Prospective populations

Freeze one 128-input pool: complete general 32, mandatory sharing 8, mandatory legacy 8 and challenge 80. All 128 original formulas, normalized novelty evidence, features and twelve-model predictions/probabilities remain consumed for future experiments, including unlabelled rows. No labels may influence input choice or selection.

Always label the first 48 mandatory cases. Add up to 16 genuinely new acceptances relative to the frozen `corroborated_augmented` policy, using fixed template ordering and deterministic round-robin. Selection excludes historical/fixed/selected feature collisions in either 217 or 233 representation. Mandatory collisions block eligibility without replacement. Canonical/alias/skeleton and modular low-shift novelty are checked before the input freeze; no semantics-preserving wrapper alone establishes novelty.

Prospective activity requires at least four new actions from at least two templates including cap 128; at least one mandatory legacy 64 veto versus old abstention; and at least one mandatory sharing 128 veto versus old learned 217. These are prediction-defined coverage checks, not correctness claims before labels. Insufficient coverage remains a failed trial; no pool extension or quota refill.

Report and gate general 32, sharing 8, legacy 8, conditional full(actions+the same eight general controls), and active-only separately. Disclose shared controls; do not pool metrics or claim independent samples. Fresh general requires strict MAE/MAPE and total FA-event gains versus signed plus all hard no-loss gates. Every other population must pass the same hard performance gates. No post-label model switch or threshold adjustment.

## Freeze and authorization sequence

1. Final source/tests, cohort/novelty audit, required inventory, rationale, policy limitations and all goal snapshots are bound by the protocol before fits or native features.
2. Independent preflight approval must bind that exact protocol. A separate parent authorization must explicitly permit the two classifier fits. Native stages require their own exact plan/protocol authorization.
3. If separately authorized, extract all frozen fresh-pool features and freeze 217/233 freshness first. Features may reveal collisions but cannot change the model recipe, candidates, columns, gates or pool; mandatory collisions block eligibility.
4. Fit exactly the two matched classifiers on the old 1,889 rows; save matrices, ordered membership, labels, weights, classes, parameters and development selection. Independently reconstruct shared-tree leaf probabilities without refitting.
5. Freeze every pool probability/prediction and deterministic selection before any fresh verification or label attempt. Classifier weights and the full pool are immutable at this checkpoint.
6. Independent prelabel approval precedes proof/labels for the entire mandatory-plus-selected cohort. Preserve missing/failing cases; no retry, replacement or scope change.
7. Independently audit scoring, raw evidence and chronology. Promote only if every frozen gate passes; otherwise retain the complete negative evidence and leave the goal active.

Native execution is bounded by 300 summed worker-process seconds and peak two workers, with conservative wall deadlines and separate accounting for tool and process time. No paid compute or overlapping expensive stages. This preregistration authorizes no native work. Exact cohort formulas, budget accounting and authorization bindings are supplied by the frozen measurement plan.
