# Predicting measured candidate LUT4 cost

The area predictor estimates the count of `SB_LUT4` cells that Yosys
`synth_ice40` maps for an isolated combinational RV32 candidate formula. These
are real synthesis resource labels from verified candidate RTL. Predictions do
not represent physical area, clock period, or complete-processor speedup.

## Input features and labels

The predictor derives its complete feature vector from the parsed formula.
Features include operation counts, expression depth, shared subexpressions,
input count, constant widths and population counts, shift amounts, multiplication
with known constant operands, and conservative known-zero/known-one output bits.
Static operand-bit overlap helps distinguish an addition that can create carry
logic from combining disjoint bits. None of these features invokes synthesis.

Benchmark names, candidate IDs, dynamic instruction counts, merit, measured gate
counts, gate depth, and LUT4 labels cannot enter the feature vector. Training
requires `measurement_source="rtl_synthesis"`, a benchmark name, a supported
formula, and a finite nonnegative `lut4_count`. Labels are checked for consistency
across identical formulas. Each fitting step weights distinct formulas once;
repeated formulas across benchmark occurrences are retained for grouping but
are deduplicated before fitting.

## Evaluation and model selection

Five configurations are fixed before scoring: an arithmetic-mean baseline,
standardized ridge regression, ExtraTrees, RandomForest, and XGBoost. The four
learned models fit `log1p(LUT4)` and invert that transformation for prediction.
Predictions are clipped to be nonnegative. Tree models use a fixed random seed
and one CPU thread; no model configuration is changed in response to outer-fold
results.

Outer leave-one-benchmark-out evaluation tests transfer to each benchmark in
turn. Every training row with a formula identical to any test formula is also
excluded. Model selection occurs inside the remaining training benchmarks, with
another leave-one-benchmark-out loop and the same formula exclusion. It chooses
the lowest pooled inner RMSLE. The outer benchmark contributes neither labels
nor hyperparameter choices to its model. Folds without novel training formulas
are explicitly skipped. If no eligible inner fold remains, a prespecified
ExtraTrees configuration is used and the report identifies that fallback.

The report contains MAE in LUT4 cells, RMSLE, Spearman rank correlation, and the
mean baseline, for each outer fold and pooled out-of-fold predictions. Spearman
is null when the rank statistic is undefined. Every metric also includes a
separate nonzero-LUT4 subset and the count of zero-LUT4 rows: optimized constant
and wiring-only formulas must not hide poor accuracy on nontrivial hardware.
Outer per-model comparison is descriptive; it does not choose the final model.

After evaluation, an independent grouped selection on all available training
rows chooses the final deployable configuration. It is refitted on all distinct
formulas. Its in-sample predictions are not held-out performance evidence.

## Artifacts and prediction

`evaluate_and_train(rows, output_dir, seed=0)` saves:

- `evaluation.json`: full nested folds, inner model choices, predictions, and metrics.
- `area-model.joblib`: fitted predictor for local inference.
- `area-model.json`: fixed input schema, model configuration, dependency versions,
  artifact SHA-256, training dataset SHA-256, source RTL hashes, and synthesis
  tool versions available in the input dataset.

```sh
.venv/bin/python -m isaforge.area_model train \
  --rows generated/real/experiment/dataset.json \
  --output-dir generated/real/area-model --seed 20261013

.venv/bin/python -m isaforge.area_model predict \
  --model generated/real/area-model/area-model.joblib \
  --candidates generated/real/experiment/dataset.json \
  --output generated/real/area-model/predictions.json
```

Prediction requires only each candidate's `formula`; optional candidate ID and
benchmark fields are passed through for identity. The output `predicted_lut4` is
a real-valued point estimate, without a calibrated confidence interval. In
Python, use `load_area_model(path).predict(candidate_rows)`. Loading checks the
feature schema and artifact hash. Joblib uses pickle: load only trusted local
artifacts. Reuse the dependency versions recorded in the schema for reliable
model loading.

The current dataset remains small. Candidate formulas from new applications or
very different operation patterns need fresh validation. The formula exclusion
makes reported transfer errors stricter than simply memorizing formulas repeated
across benchmarks, while the fully trained artifact can use all measurements
for practical candidate screening.
