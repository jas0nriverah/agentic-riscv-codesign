# Formula-only area model v2

`isaforge.area_model_v2` implements an extrapolating resource regression and one
fixed residual ML model for the measured Yosys `synth_ice40` `SB_LUT4` count of an
isolated combinational RV32 formula. The original v1 implementation and artifact
are preserved. The v2 target remains a hardware-resource proxy: neither clock
period, physical area, nor processor performance is predicted.

The original eight-benchmark corpus has 339 benchmark/formula rows and 301
distinct synthesized formulas. V1's grouped results exposed severe errors on
EDN multiplication. Those results motivated this new design; consequently,
**all v2 scores on the original corpus are exploratory development results**.
They cannot serve as an unbiased estimate of improvement. A frozen artifact
and preregistered protocol precede evaluation on additional benchmark families.

## Why these features

Operation counts alone treat a full RV32 multiplication and a multiplication of
a sign-extended 16-bit operand similarly. A tree regressor also extrapolates
poorly outside resource sizes represented by its leaves. The small corpus has
only nine distinct multiplication formulas, so a larger search of tree or neural
architectures would add flexibility without comparable independent evidence.

V2 uses conservative formula analysis to supply hardware-size information:

- Per-bit constants, direct input wires, complements, and repeated sign bits are
  tracked. Other bits are opaque identifiers. Identical subexpressions retain
  identity; unknown bits are not assumed independent. RV32 intermediates wrap
  at 32 bits and shift distances use their five low bits.
- Output bit demand propagates backward. Immediate shifts route demand to their
  actual source positions, masks remove unused outputs, arithmetic carries keep
  necessary lower bits, and a variable shift unions all possible source bits.
  Each canonical node is costed once using the union of its consumers' demands.
- Signed and unsigned operand widths distinguish sign extension from fresh
  bits. Low multiplication can use either signed or unsigned representation
  because it is modulo `2**32`; high-half operations respect their instruction's
  signedness. Retained variable partial products count `(i,j)` pairs whose sum
  can affect the highest demanded product bit. For example, full low 32-by-32
  multiplication has 528 pairs, sign-extended 16-by-32 has 392, and a low byte
  of a full multiplication has 36. High-half unsigned multiplication retains
  the full 1024 pairs.
- Constant multiplier binary shift/add widths, popcount, and canonical signed
  digit term counts expose constant sparsity. Seven transparent resource axes
  count Boolean bits, adder active bits, adder overlapping bits, comparison
  widths, barrel-shift mux bits, variable multiplier partial products, and
  constant multiplier adder bits. These are approximate resource predictors,
  not exact circuit synthesis.
- Proved constant and wiring expressions have zero estimated cost. Examples
  include power-of-two low multiplication, `x+x` as a left shift, disjoint-bit
  addition, repeated-expression XOR, and a high unsigned product of two
  zero-extended 16-bit operands.

The augmented feature vector contains all v1 formula features plus these
resources, live-node and demanded-bit counts, operand widths, width products,
constant sparsity, and sharing. **Only `formula` is consulted.** Labels, measured
netlist features, dynamic counts, benchmark names, candidate merit and identity
never enter either model. Additional fields can accompany inference rows solely
for result identity.

## Two fixed configurations

`resource_ridge` fits seven nonnegative coefficients in raw LUT4 units, without
an intercept. It minimizes `||Xw-y||² + ||w-w0||²` with the elementary prior
`w0=[1,1,1,1,1,2,1]` and ridge alpha 1. Distinct formulas receive one training
weight. Its prediction is `max(0,Xw)`, so larger resource counts can extrapolate
beyond the training labels. The final fitted coefficients are stored plainly in
`development-evaluation.json` for inspection.

`resource_residual_xgb` first fits that resource model, then fits
`log1p(measured LUT4) - log1p(resource prediction)`. Its configuration reuses
v1's fixed XGBoost settings: 160 estimators, depth 3, learning rate 0.07,
minimum child weight 2 and L2 regularization 2, seed 20261013, one CPU thread.
The seven resource features and remaining new features use `log1p`; original
v1 features keep their original scale. The resource prediction's logarithm is
also an input. There is no architecture or hyperparameter sweep.

At inference the learned correction is clipped to `[-2,2]` and added to
`log1p(resource prediction)`, then inverted and clipped nonnegative. This keeps
the analytical scale in the prediction and limits extreme extrapolation by
the residual model. Proved zero-resource formulas return exactly zero. Neither
model supplies a calibrated uncertainty interval.

## Development comparison and fresh evaluation

Each original benchmark is held out in turn, and every matching test formula is
excluded from training in the other benchmarks. The comparison fits v2,
`resource_ridge`, and the fixed v1 XGBoost configuration on identical training
splits. It reports all models and all folds; it does not select a winning
configuration. Original nested-v1 results are a different evaluation procedure
and must not be silently substituted for the fixed-v1 comparator here.

| Original corpus, exploratory | MAE LUT4 | RMSLE | Spearman |
| --- | ---: | ---: | ---: |
| Fixed v1 XGBoost | 31.70 | 0.983 | 0.817 |
| Resource ridge | 15.43 | 0.529 | 0.881 |
| Resource residual XGBoost v2 | 14.28 | 0.485 | 0.921 |

There are 92 zero-LUT rows. On the 247 nonzero rows, the respective RMSLE values
are 0.991, 0.525 and 0.492. Per-benchmark metrics and every development prediction
are retained. These figures help diagnose the design, not establish independent
superiority or support claims against unrelated published systems.

A packaging check caught CLI training serializing classes under `__main__`,
which prevented a separate library process from loading the models. The CLI now
delegates to the canonical imported module. Before fresh inference, both frozen
artifacts were mechanically migrated without refitting: all 339 original-row
predictions per model, coefficient hashes and XGBoost booster hashes remained
identical. `serialization-migration.json` records the pre/post artifact hashes;
schemas and the freeze manifest record the repaired source and artifact hashes.
The regression test trains through `python -m` and loads both artifacts in a
separate ordinary library process.

The final two models refit the original 301 distinct formulas. The freeze
manifest records artifact SHA-256 hashes, the normalized training dataset hash,
feature schema, configurations, UTC freeze time, and hashes of all local runtime
sources used by inference. Fresh data must use these artifacts unchanged.
The prospective protocol committed before inference makes distinct-novel-formula
MAE the primary accuracy endpoint; RMSLE is also reported. An earlier draft of
this model note called RMSLE primary, conflicting with that already frozen
protocol. The protocol takes precedence, and both metrics remain visible.
Fresh evaluation uses formulas absent from original
training (and policy calibration in the final test); overlapping formulas are
reported separately. Secondary measures are RMSLE, Spearman, nonzero-only
metrics and per-family results. Report all fixed
comparators and failure cases without retraining or winner substitution. See
the independent [fresh evaluation protocol](fresh-evaluation-protocol.md).

## Train and predict

```sh
.venv/bin/python -m isaforge.area_model_v2 train \
  --rows results/2026-10-13/dataset.json \
  --output-dir generated/real/model-v2 --seed 20261013

.venv/bin/python -m isaforge.area_model_v2 predict \
  --model generated/real/model-v2/area-model-v2.joblib \
  --candidates results/2026-10-13/candidates/crc32.json \
  --output generated/real/model-v2/crc32-predictions.json
```

The saved artifacts are `area-model-v2.joblib` and `resource-ridge.joblib`, each
with a matching JSON schema; `development-evaluation.json` and
`preregistration.json` record the comparison and freeze. Prediction requires
only a formula, and retains optional `candidate_id` and `benchmark` fields.
In Python, call `load_area_model_v2(path).predict(rows)` for either artifact.
Loading verifies hashes, configuration and schemas. Joblib uses pickle, so load
only trusted local files and use the recorded dependency versions.

## Validation and limits

Tests cover ignored outcome/frequency fields, sign extension versus unsigned
widths, retained partial products, backward demand and sharing, exact zero-cost
identities, symbol soundness against the RV32 evaluator, nonnegative resource
coefficients, extrapolation, duplicate weighting, label validation, persistence,
and configuration/artifact tampering. Numerical prediction is also checked on
all original rows using inputs with every measurement field removed.

Resource estimates deliberately simplify LUT packing, constant optimization,
adder topology and signed-multiplier correction logic. Constant multiplication
uses a binary-lane resource proxy while signed-digit sparsity is an ML feature;
dense negative constants can still be difficult. Backward arithmetic demand is
conservative, not an exact bit-dependency proof. Fitting raw LUT4 counts makes
the small number of expensive multipliers influential. These limits motivate
reporting the transparent baseline as well as the residual model and requiring
fresh benchmark-family evidence before claims of generalization.
