# Model

ISAForge predicts the number of iCE40 four-input lookup tables required by an original RV32 instruction candidate. A candidate is a bounded computation with up to two inputs and one output. Training targets come from verified RTL and actual Yosys synthesis.

![Model architecture](figures/research/model.svg)

## Representation and estimator

The extractor computes 336 descriptors; the forest uses a fixed 217-feature view:

| Feature block | Count |
| --- | ---: |
| Simple operator graph | 14 |
| Original generic graph | 60 |
| Normalized generic graph | 60 |
| Absolute differences between the two graph views | 60 |
| Mapping-related graph descriptors | 23 |
| **Model inputs** | **217** |

The model is an ExtraTrees regressor with 300 trees, one-sample minimum leaves, all features considered at splits, randomized split thresholds, and no bootstrap sampling. Every tree sees the training dataset. Its prediction is the equally weighted mean of tree outputs, clipped to nonnegative values, with the frozen original-generic-zero rule preserved. Tree disagreement is recorded but is not a calibrated uncertainty bound.

Both graph views describe the same original implementation. Labels always measure original RTL, never a cheaper rewritten implementation substituted after observing the result. Cached features avoid preprocessing; a new formula still requires compatible pre-mapping graph extraction.

## Available predictors

| Name | Training circuits | Role |
| --- | ---: | --- |
| `base` | 1,665 | Default; strongest primary result on the completed application-transfer panel |
| `coverage` | 1,713 | Same representation and estimator, with 48 targeted arithmetic examples |
| `scoped` | Uses the two saved forests | Experimental input-only selection of one forest |

The scoped policy selects coverage when the original formula contains a low multiplication with a syntactic positive constant from 1 through 2047, or a signed-shift difference `sub(srai(A,k),srai(B,31))`, with input-containing A/B and k from 0 through 31. Otherwise it selects base. It does not inspect labels, predicted error or benchmark identity. The CLI computes only the required model subsets and returns the selected original points.

On the 32-case arithmetic test every case selects coverage, so the scoped policy equals coverage by construction. On the consumed 327-case application panel every case selects base. These checks do not establish routing generalization to a new mixed application distribution.

The weights and adjacent metadata in [models/](../models/) are byte-identical to their archived artifacts. Their original internal module names remain unchanged to preserve serialization and source validation. [Inference and reproduction](reproduce.md).

## Testing the feature budget

217 is a fixed representation choice, not a model capacity limit. A [matched development experiment](../results/feature-comparison/README.md) compares that view with all 336 descriptors and with 128 selected inside each training fold. The 336 view contains the same values as the extractor storage, reordered as the 217 inputs followed by 119 semantic descriptors. Feature ordering is frozen because it can affect randomized trees.

The selected view has the lowest development MAE, but its hardware-budget mistakes and worst underprediction prevent promotion. Each fold selects its own 128 columns; this experiment does not produce a single new deployable model.

The [stability follow-up](../results/selection-stability/README.md) repeats the MAE gain across three seeds, but the [fresh 40-circuit test](../results/selection-validation/README.md) worsens both accuracy and budget decisions. The experimental selected forest is retained for reproducibility; it is not exposed as the default prediction model.

## Targeted coverage candidate

The earlier [experimental predictor](../results/budget-preserving-coverage/README.md) uses the unchanged 217-feature representation and a forest trained on 1,729 circuits (1,665 original plus 64 new variable-shift/mixed-arithmetic cases). A fixed original-AST rule selects it for covered structures. A final constrained upward correction preserves all baseline decisions at 32/64/128 LUT4 and cannot increase underprediction. The correction is not calibrated, does not fix baseline budget errors, and does not guarantee lower average error on every distribution. It passes the separate 32-case fresh synthetic validation, with the documented subgroup regressions retained.

## Signed-arithmetic repair

The [new experimental revision](../results/guarded-revision/README.md) adds 32 signed-arithmetic training cases for a 1,761-row forest, retaining 217 features and 300 trees. Only active formulas containing a signed shift, subtraction and XOR use this repair forest; other cases retain the incumbent. The predeclared static-shift abstention and unchanged budget guard prevent the named development regressions. Selection occurred before the new 40-case test labels. The revision improves aggregate error over the incumbent in that test, with unchanged decisions at 32/64/128 LUT4 and the documented remaining tradeoffs.

## Signed-shift refinement

The [current experimental refinement](../results/signed-refinement/README.md) adds 32 measured cases for a 1,793-row forest. It changes only two predeclared signed-shift structural classes; other formulas retain the previous composite predictor. The primary passed development selection before fresh labels and improves a separate 40-case test versus the immediate incumbent. All seven retained panels meet incremental MAE/MAPE and maximum-underprediction criteria. The model remains a four-forest composite with explicit AST routing and the same cap guard; it does not repair existing budget classification errors. Fresh subgroup and older-policy tradeoffs remain documented.

## Budget-release experiment

The [latest experiment](../results/budget-release/README.md) tests whether allowing estimates to cross the old budget limits repairs false acceptances. One new forest uses 1,825 training circuits. The predeclared compound-only policy takes the maximum of the previous composite estimate and the new forest on compound signed shifts, preserving the previous policy elsewhere. This can correct false acceptances but can introduce false rejections; it is not a calibrated safety bound.

Development selection rejected the broader compound/Boolean route. The narrow fallback improved fresh accuracy and reduced false acceptances, but newly rejected one circuit that actually used 125 LUTs at a 128-LUT budget. It therefore fails promotion and remains an explicit diagnostic predictor. The unclipping-only comparator uses the broader route, so its aggregate difference from the selected fallback does not isolate the effect of added training.

## Median boundary repair

The [zero-fit boundary experiment](../results/boundary-repair/README.md) reuses the 1,825-row forest. On compound signed shifts, when budget release crosses a fixed cap but the signed incumbent and the forest median remain at or below it, the repair clamps the estimate to that cap. For 300 trees, the median averages the two middle predictions; it is not equivalent to a strict majority vote or a calibrated uncertainty bound. It fixes the known false rejection and leaves the other 782 consumed cases unchanged. A fresh 40-case test preserves the accuracy and false-acceptance gains, but never activates the repair, so it fails the preregistered transfer-activity gate.

## Direct test of the correction

The [conditional boundary challenge](../results/boundary-challenge/README.md) freezes a 200-input pool, extracts all features, then selects novel disagreements using the unchanged policy before any labels. Ten active cases and eight fixed controls meet the predeclared coverage requirements. The repair corrects eight release false rejections but creates two false acceptances, worsening both MAE and MAPE versus release. Median agreement alone is therefore insufficient. No passing subset is substituted for the complete result, and neither this negative result nor the prior inactive trial is promoted.

## Structural refinement

The [structural boundary refinement](../results/boundary-refinement/README.md) applies median adjudication only when the original formula has an XOR root, a direct addition operand and a direct compound signed-shift operand of that same addition. Both operand orders are tested; elsewhere the previous budget-release prediction is exact. This development-informed rule uses no labels, IDs or constant-specific lookup at inference.

It preserves the nine known rejection repairs and prevents both earlier new false acceptances. All16 fresh active cases pass, but the fixed general32 panel retains four false rejections introduced by release. Those four cases are inside the structural gate and have forest medians above128, so the correction does not activate. This suggests studying training coverage or representation for Boolean sharing and narrow signed arithmetic; that hypothesis is not yet validated. The candidate remains experimental and unpromoted.


## Matched coverage and localized features

The [matched coverage study](../results/boundary-coverage/README.md) adds 32 new measured training circuits to the existing 1,825 rows. Two otherwise identical 300-tree forests use either the original 217 features or those features plus 16 descriptors of local input sharing, shared subtrees, conservative data width and low-five-bit shift-control uncertainty. The new columns are a representation hypothesis; the study does not establish an information collision in the original features.

Both forests support a fixed budget correction rather than replacing every point estimate. Within the declared structural scope, a correction requires the signed incumbent and new raw forest mean to be at or below a physical cap that the prior structural policy exceeds; the output becomes the smallest qualifying cap. Other predictions remain unchanged. This is an uncalibrated decision rule, not an uncertainty bound.

The development-selected 217-feature candidate fixes all four remaining known rejections and preserves all 30 required repairs. Two raw means are only 0.1233 and 0.1467 LUT below 128, so those repairs have narrow margins. The 233-feature candidate retains two development errors. On the fresh general panel both policies remove one remaining rejection, but both incorrectly accept a 159-LUT conditional case at 128. Agreement between the two forests does not prevent that failure. The conditional sample also misses the declared activity minimum; neither candidate is promoted.


## Coverage-based abstention

The [zero-fit abstention experiment](../results/boundary-abstention/README.md) derives support cells from the 1,857 frozen training formulas: narrow/shared (4 chains), narrow/unshared (8), and wide/unshared (20); wide/shared is absent. Narrow means conservative unknown-bit span at most 16, and wide means greater than 16. Sharing means an input-bearing nonleaf subtree occurs in both the shift data and that same chain's post-add operand. If any eligible chain has an unsupported cell, the policy retains the previous structural prediction. It never combines the minimum width of one chain with the sharing of another.

All earlier repairs remain intact. Fresh active validation confirms six rejection repairs versus the structural predictor, and a separate fixed unsupported panel confirms one prevented false acceptance. The complete general and unsupported panels still fail the declared gates: four general false rejections remain, while inherited median corrections introduce false acceptances at 64 LUTs. The abstention rule is therefore a partially validated mechanism within an unpromoted composite predictor. Its fallback is not a safety guarantee, and correcting one source of error does not certify the complete pipeline.


## Unified budget corroboration

The [matched corroboration experiment](../results/boundary-corroboration/README.md) trains two forests on the same 1,889 circuits, using 217 features or 233 with 16 localized descriptors. A new pure helper retains conservative known-bit information through ADD/ADDI using possible carry states; old feature implementations remain unchanged. The ablation tests all 16 added descriptors, not carry propagation alone.

Both policies start from budget release. Any lowering across 32, 64 or 128 LUTs requires the signed incumbent and new forest mean to accept that cap. There is no inherited median bypass. The scope includes all original root-XOR/add/direct-compound-signed-shift chains. All four training width/sharing cells are represented, so the cell-support guard is inactive within that scope.

The unified rule rejects all six protected unsafe cases and fixes three remaining rejection cases, but the augmented candidate loses five established repairs and coverage-only loses eight. Neither is selected. Fresh general accuracy improves over release, while two or three excess false rejections remain at 128. The subsequent direct-feasibility experiment is described below; neither regression candidate was promoted.


## Direct budget feasibility

The [matched classifier experiment](../results/boundary-feasibility/README.md) reuses the exact 1,889 training circuits and compares the same 217 and 233 input columns. Each native multioutput ExtraTrees classifier shares tree partitions across three nested targets: measured area at most 32, 64 and 128 LUT4. The fixed 0.5 threshold includes ties; output probabilities are uncalibrated. Class mappings and shared-leaf probabilities are independently reconstructed.

The final policy retains the signed-incumbent lower bound and budget-release upper bound. Within the declared signed-shift scope it chooses the smallest crossed cap supported by the classifier, otherwise retaining release. These bounds cannot repair all inherited errors; six consumed examples are explicitly documented in the experiment. The extra 16 descriptors are tested as a block, not as an isolated carry-analysis contribution.

The 233-feature variant passes all 22 retained panels, 25 named groups, 50 required acceptances and 23 protected rejections. Both classifiers improve fresh general accuracy and remove its five excess cap128 rejections. However, both accept three targeted circuits measuring 129, 130 and 129 LUT4 at a 128-LUT budget, and reject one shared-AND circuit measuring 125 LUT4. The highest feasibility probability among those unsafe acceptances is 0.8733, illustrating why it is not a safety certificate. The selected development candidate fails fresh validation and is not promoted; no threshold was changed after labels.
