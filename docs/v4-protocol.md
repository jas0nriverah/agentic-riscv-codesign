# V4 development expansion and frozen holdout protocol

Declared before new holdout labels are collected. This is a new experiment;
the earlier prospective workload and synthetic-probe results remain unchanged.
The old 192-circuit probe is now development data and loses independent-test
status for all newly fitted models.

## Inputs and comparisons

The new corpus predeclares eight equally weighted structural strata, with 48
development and 32 holdout formulas per stratum: 384 development and **256
holdout** formulas. Candidate identities, formulas, strata, generator settings,
source hashes, and exclusions freeze before model selection. New formulas
exclude the 713 historical unique formulas and 192 previous probe formulas;
development and holdout sets exclude one another. Exact canonical exclusion
does not establish semantic independence or real-workload generalization.

The development cohort comprises those 905 earlier formulas plus 384 new
development formulas, for **1,289 unique formulas**. New development labels may
be measured and inspected for feature engineering and grouped validation.
Holdout labels, actual RTL verification outcomes, target-mapping synthesis
logs, and resource counts may not be generated or inspected until all compared
model artifacts and holdout predictions are frozen. Label-free holdout feature
extraction is permitted, including validation of algebraic normalization by
comparing the original and normalized **formula semantics** against an RV32
integer oracle. Before fitting, this input-only validation covered all 1,545
development/holdout formulas with 401,700 input-pair comparisons. It used no
RTL verification, mapped-resource outcome, or holdout label. Sampled formula
agreement is not a formal equivalence proof or an independent test of area
accuracy. Feature/normalization sources freeze before model fitting, and the
holdout remains fixed; this allowance cannot authorize post-score changes.

Required comparisons are `v4`, `masterrtl_retrained`, `masterrtl_frozen`,
`v2_frozen`, and `v3_frozen`. The three frozen comparators retain their original
713-formula fits. The retrained MasterRTL adaptation uses the **same 1,289
development formulas** as v4, with the existing pinned SOG extraction and fixed
25-tree/depth-12 raw-target XGBoost recipe. Comparing only against old fits
would confound added data with a new method. This remains an adaptation to
isolated iCE40 LUT4, not a reproduction of published ASIC results.

V4 combines 14 normalized SOG features, deterministic graph topology, local
support and greedy four-input-cover features, and the normalized v4 structural
feature dictionary. The greedy cover is an analytical proxy, unaware of carry
mapping; extraction performs no ABC or target-cell mapping. V4 applies a fixed
exact-zero override when the normalized pre-ABC graph's `gate_count` is zero.
The same override applies to every v4 grid fit's out-of-fold predictions and
final inference; it cannot depend on measured labels. The existing frozen
comparators retain their original inference recipes. Five GroupKFold folds use normalized operator-tree
skeletons, replacing constants with `C` and inputs with `I`; an identical
normalized formula cannot cross a fold. Select by mean stratum MAE across all
out-of-fold development predictions, with historical workload rows grouped in
a single metric stratum named `workload` plus the eight synthetic strata,
giving nine equally weighted selection strata. This is exploratory development
selection, not a nested independent estimate.

The fixed six-fit grid comprises XGBoost raw and log targets, each with depth
3 or 6, 300 trees, learning rate 0.04, minimum child weight 3, and lambda 5;
and ExtraTrees raw targets with 300 trees, minimum leaf size 1 or 3, and
max-features 1.0. Log targets use log1p training and expm1 inversion. All
predictions are clipped nonnegative. Seeds, complete library parameters and
versions, tie rule, folds, grid scores, and selected fit freeze in the artifact.
Three fixed same-estimator ablations use raw depth-3 XGBoost: normalized SOG,
normalized SOG plus graph features, and all combined features. The selected v4 model comes **only
from the six combined-feature fits**. Ablations cannot expand the selected
grid or be chosen using holdout outcomes. The matched MasterRTL retrain uses
original-formula SOG features, maintaining its existing recipe.

## Frozen endpoint and measurement

The primary endpoint is **macro-stratum MAE in LUT4 across all 256 formulas**.
It equals pooled MAE for this balanced corpus. No zero-label, multiplier,
outlier, failed comparator, or difficult stratum may be removed. Any missing
or failed measurement makes the planned experiment incomplete; it does not
authorize scoring a smaller convenient subset as the complete holdout.

Secondary endpoints are pooled and per-stratum RMSLE, positive-label MAPE,
positive-label median absolute percentage error, zero-target MAE, and
feasibility errors at caps **16, 32, 64, 128, and 256 LUT4**. Predictions equal
to a cap are feasible. For each cap retain the confusion counts, false accepts
divided by truly infeasible cases, false rejects divided by truly feasible
cases, and false accepts divided by predicted-feasible cases. Empty
denominators yield null. These caps ignore carry, registers, routing, and CPU
integration; zero LUT4 does not mean zero hardware cost.

Every candidate is verified against independently specified RV32 semantics
before its actual `synth_ice40` label enters the dataset. Retain verification,
RTL, synthesis commands/logs, tools, hashes, and carry counts. Sampled checks
must not be presented as formal equivalence. No training, calibration, feature
change, grid selection, or model substitution follows holdout release. A
changed model requires a separately named fresh test.

## Independent score and provenance

`scripts/evaluate_v4.py` reads generic prediction lists keyed by
`(benchmark, candidate_id)`, with `predicted_lut4` and matching `formula`.
Measured rows contain `lut4_count`, `measurement_source: rtl_synthesis`, and
`correctness_verified: true`. The evaluator rejects duplicate, missing,
extra, negative, nonfinite, wrong-formula, or wrong-stratum data. It verifies
all frozen file hashes before loading measurements.

The freeze manifest has schema `isaforge-v4-freeze-v1`, UTC candidate/model
freeze timestamps, hashed file records `{path, sha256}` for `candidates`,
`development_data`, `protocol`, and `evaluator`, and a `models` mapping.
Each model entry contains `frozen_at_utc`, `predictions`, `artifact`, and
`sources` (a nonempty list of hashed file records). Paths resolve relative to
the freeze manifest's directory. The development data record is the exact
1,289-row formula-deduplicated fitting cohort. Additional model-specific
training records may be retained in the artifacts.

Before measurement, run `--validate-freeze` to check complete predictions,
identities, cohort disjointness, artifacts/sources, and timestamps. After
release, a separate JSON record has `released_at_utc` and a hashed `dataset`
record; paths resolve relative to that release record. Candidate freeze must
precede every model freeze, and every model freeze must strictly precede label
release. Timestamps and hashes document recorded consistency and ordering;
they do not independently prove blinding or authenticate previous human
access. The independent score checks its own source and this protocol hash.

For every v4-versus-comparator comparison, use **10,000 paired bootstrap
draws**, seed `2026101305`, resampling formula pairs within each of the eight
fixed strata. Report v4 absolute error minus comparator absolute error, so
negative favors v4, its macro-stratum difference, descriptive 95% percentile
interval, per-stratum differences, and smaller-error/tie counts. These
intervals do not establish population coverage, application transfer, or
multiple-comparison-adjusted significance. Report every comparator even if
v4 loses. Synthetic resource prediction cannot establish improved acquisition,
CPU speedup, energy savings, or avoided end-to-end measurement cost.

```sh
.venv/bin/python scripts/evaluate_v4.py \
  --manifest results/2026-10-13-v4/freeze.json --validate-freeze
.venv/bin/python scripts/evaluate_v4.py \
  --manifest results/2026-10-13-v4/freeze.json \
  --release results/2026-10-13-v4/label-release.json \
  --output results/2026-10-13-v4/evaluation.json
```

The score contains all per-candidate errors, per-stratum metrics, primary and
secondary metrics, paired comparisons, verified hashes, chronology, and
limits. No headline improvement is assumed in advance.
