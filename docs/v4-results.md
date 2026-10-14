# V4: semantics-aware circuit prediction

V4 substantially improves isolated hardware-cost prediction over the previous
custom models on a newly reserved synthetic test. Its small primary-score
advantage over a MasterRTL adaptation retrained on the same data is
inconclusive, and it retains important multiplier failures. This experiment
does not measure new instruction-selection or processor-performance gains.

## What changed

`structural_features_v4.py` preserves active multiplier bit positions, handles
signed constant products with exact two-word carry/borrow rewrites, adds
product-range proofs and XOR cancellation, and emits 90 structural features.
`area_model_v4.py` combines those with 14 normalized pre-ABC SOG descriptors and
45 topology/support descriptors. These include shared signals, depth, fanout,
operator edges, and a greedy four-input-cover proxy. The proxy is not exact LUT
mapping and does not account for dedicated carry resources. No measured cell
counts enter inference features.

Five group folds hold out normalized operator-tree skeletons. A fixed six-fit
grid compares raw/log XGBoost at depths 3/6 and raw ExtraTrees at minimum leaf
sizes 1/3. Development macro-stratum MAE selects **300-tree ExtraTrees, leaf
size 1**. Development ablations hold the estimator fixed; they are not new test
results. See [development evaluation](../results/2026-10-13-v4/development-evaluation.json)
and the unchanged [protocol](v4-protocol.md).

The 1,289 training circuits comprise the earlier 713 workload circuits, the
192-circuit historical probe (now development), and 384 new development
circuits. A new 256-circuit test has eight strata of 32. Canonical formulas are
disjoint, but structural/semantic independence and application transfer are
not established. Five complete prediction sets and artifacts were committed
at **2383818** before the test labels were collected. Label release is recorded
at **2026-10-14 03:42:52 UTC**; the directory retains the experiment's original
`2026-10-13-v4` name.

## Complete held-out results

| Predictor | Training formulas | MAE LUT4 | RMSLE | Positive MAPE | Median APE | Zero-target MAE |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| V4 | 1,289 | 14.8921 | 0.5717 | 77.9278% | 1.3627% | 26.4863 |
| Same-data MasterRTL retrain | 1,289 | 15.3243 | 0.4600 | 76.0172% | 5.5506% | 0.0780 |
| Frozen MasterRTL | 713 | 22.1496 | 0.5356 | 104.1019% | 11.5066% | 0.0252 |
| Frozen residual v2 | 713 | 60.6815 | 0.9012 | 610.9514% | 24.8191% | 19.1078 |
| Frozen structural v3 | 713 | 66.7478 | 0.9018 | 672.9124% | 21.6245% | 24.7033 |

All 256 targets contribute to MAE/RMSLE; percentage metrics use 235 positive
targets, and the 21 zeros have a separate error measure. No cases are removed.
The full [evaluation](../results/2026-10-13-v4/evaluation.json) includes all
per-candidate errors, strata, and cap confusion counts.

![Five frozen predictors on the new test](figures/v4-comparison.png)

V4's MAE is **75.46% lower than frozen residual v2** and **77.69% lower than
frozen v3**, on the same new test. These comparisons include the benefit of
expanded training data. Against same-data MasterRTL, the difference is only
−0.4322 LUT4 (2.82%), with descriptive paired 95% interval **[−5.5241, 5.5906]**.
The interval includes zero. Against frozen residual v2, it is −45.7895 LUT4,
interval [−71.5125, −23.3626]. The 10,000 paired bootstrap replicates resample
within the eight fixed strata; they do not establish population coverage.

V4 has smaller absolute error on 206/256 circuits versus same-data MasterRTL
and lower MAE in seven of eight strata. Multiplication remains worse:
105.0531 versus 91.6488 LUT4. At a 64-LUT cap, V4 has one false accept and ten
false rejects, compared with three and sixteen for same-data MasterRTL.
These are synthetic feasibility diagnostics, not measured acquisition benefit.

## Remaining failures

Twenty true-zero circuits receive exactly zero from V4, but
`srli(mulhsu(andi(in1,511),-129),31)` receives **556.2133 LUT4**. This is why
V4's zero-target error and RMSLE regress. Its pre-ABC zero override recognizes
operator-free graphs, not every expression that the target mapper reduces.

`srli(mulhsu(andi(in1,129),srai(in0,16)),7)` maps to one LUT but receives
119.2933; `xori(mul(xori(in0,17),1073741823),2147483647)` maps to 622 but receives
101.4133. Algebraically equivalent normalized RTL need not map identically to
the original syntax, whose measured label remains the target. Typical error
is much smaller, but the model is not uniformly reliable. No post-test repair
or model substitution changes this result; a revision needs another fresh test.

## Correctness, inference, and audit

The 384 development circuits pass **824,832** RTL comparisons; all 256 test
circuits pass **549,888**. Python original-versus-normalized checks cover
1,545 input formulas and **401,700** boundary/random input pairs before fitting.
These are sampled tests, not formal equivalence proofs.

Development validation uncovered a Verilator-generated C++ signed-overflow
issue in a high unsigned product. The separate `v4_validation.py` wrapper
retains the failed build, uses the explicit `-fwrapv` compiler flag, records
compiler/tool identities, and checks 100 boundary cases independently with
Yosys. All original frozen RTL and collector sources remain unchanged. The
test cohort passed without triggering the workaround. Validation and original
incident evidence are retained in the raw archive.

The [independent audit](../results/2026-10-13-v4/independent-validation.txt)
recounts all **640** new mapped netlists, regenerates original RTL hashes,
checks frozen files against commit 2383818, independently recomputes five
metric sets and all four paired comparisons, and passes. The full local suite
passes **327 tests and 40 subtests**.

Sequential same-machine inference timings use a fresh cache, then five warm
repeats, with one worker and exactly the frozen 256 inputs:

| Predictor | Cold features + prediction | Median warm | Model load |
| --- | ---: | ---: | ---: |
| V4 | 10.8979 s | 1.0788 s | 0.1352 s |
| Same-data MasterRTL | 11.7203 s | 0.3458 s | 0.0468 s |

Every cold and warm prediction equals its frozen prediction. Startup and JSON
serialization are excluded. These timings do not establish net measurement
savings; both models require cold Yosys preprocessing. See
[runtime-cost.json](../results/2026-10-13-v4/runtime-cost.json).

## Replay scores and figures

From an installed checkout with the `reports` extras:

```sh
make reproduce-v4
```

This verifies frozen inputs/artifacts/sources, recomputes all scores and paired
comparisons without loading estimators or invoking hardware tools, and writes
an HTML report plus PDF/SVG/PNG figures under `generated/reproduction/v4/`.
The older `make reproduce` retains the historical six-model experiment.
To audit raw netlists too, restore the V4 evidence archive and run:

```sh
python scripts/audit_v4.py --output-prefix generated/v4-audit/independent-validation
```

The raw audit needs the retained generated artifacts and freeze commit in Git
history; score replay needs only committed files. Keep all replay output outside
the frozen result directory.

## Run frozen V4 inference

The artifact records NumPy 2.5.4, SciPy 1.18.1, scikit-learn 1.9.1,
XGBoost 3.4.1 and joblib 1.6.0. Match recorded versions for trusted joblib
compatibility. Only load artifacts from a trusted checkout/archive.

```sh
python -m isaforge.area_model_v4 \
  --model results/2026-10-13-v4/models/v4.joblib \
  --candidates results/2026-10-13-v4/corpus/test/candidates.json \
  --cache-dir generated/masterrtl-baseline/sog-cache \
  --output generated/inference/v4.json
```

Specify the cache path when moving the checkout: the original artifact records
the training host's absolute cache location. Cached inference verifies retained
graph files and uses the frozen tool identity. Cold extraction requires the
recorded Yosys version and executable hash; merely installing a different
Yosys is insufficient. The evidence archive restores the compatible cache.

To repeat runtime measurements, use a previously absent cache directory:

```sh
python scripts/benchmark_v4.py --cache-root generated/new-v4-timing-cache \
  --output generated/new-v4-timing.json
```

Training remains reproducible through `scripts/train_v4.py`, which refuses to
overwrite the frozen directory. A new output directory must contain its own
prepared corpus and protocol-consistent measurements. Retraining cannot inherit
this holdout's independent-test status after its results are inspected.
