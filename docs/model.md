# Speedup prediction and benchmark-held-out evaluation

`SpeedupPredictor` estimates measured elapsed-time speedup using small XGBoost
regressors trained on bootstrap samples. Training rows must contain the fixed
`FEATURE_COLUMNS`, positive `speedup`, and one consistent `measurement_source`.
Only those feature columns reach the model; area, cycle counts, benchmark names,
formulas, IDs, and labels are excluded from its inputs.

```python
from isaforge.model import SpeedupPredictor
from isaforge.evaluation import leave_one_benchmark_out

model = SpeedupPredictor(seed=0).fit(measured_rows)
predictions = model.predict(unmeasured_rows)
report = leave_one_benchmark_out(measured_rows, seed=0)
```

Prediction rows can omit all measurement fields but need `candidate_id` and every
feature. Each returned dictionary contains `candidate_id`, `mean`, `lower`,
`upper`, and `std`. The default interval spans the ensemble's 5th and 95th
percentiles. Standard deviation measures disagreement between ensemble members.
The seed and single-threaded training make reruns deterministic within the same
dependency/platform environment. XGBoost is required for nonconstant regression;
NumPy and SciPy support prediction and evaluation.

These intervals are **not calibrated prediction intervals**. They omit several
sources of error, including benchmark distribution shift and measurement noise.
With a singleton or constant-label training set, the model returns a constant
prediction and zero disagreement, accompanied by explicit warnings. Zero
disagreement does not establish confidence. Fewer than ten training rows also
trigger a warning.

Leave-one-benchmark-out evaluation trains a fresh ensemble after excluding every
row belonging to the held-out benchmark. The JSON report includes training
benchmarks/counts, held-out predictions, MAE, Spearman correlation, interval
coverage, and average interval width. Spearman is `null` for singleton or constant
cases. Pooled metrics concatenate all held-out predictions and weight each row
equally; they are not macro-averages of folds. At least two benchmarks are required.
Hyperparameter tuning must use training benchmarks only; selecting settings after
reading held-out scores invalidates an unbiased generalization claim.

Training and evaluation reject mixed measurement sources, including mixtures of
synthetic, synthesis-estimate, gem5, and hardware labels. Synthetic reports are
explicitly marked and establish software behavior only. Synthesis estimates and
gem5 results are distinct from hardware measurements. An evaluation run does not
establish actual hardware acceleration unless its input labels were measured on
the hardware under the stated experimental conditions.
