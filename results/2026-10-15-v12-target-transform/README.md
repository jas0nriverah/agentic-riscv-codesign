# V12 matched target-scale experiment

All 30 fits completed with no failures. **Raw-target fitting is retained:** log-target fitting worsens nine-stratum macro MAE by 4.77% and increases cap64 false accepts in every paired seed, despite lower MAPE.

[Full results and interpretation](../../docs/v12-target-transform-results.md) · [Frozen protocol](../../docs/v12-model-direction.md) · [Complete summary](fit-attempt-0000/summary.json) · [Completion](fit-attempt-0000/completion.json) · [Training log](fit-run.log)

## Evidence

- [Preparation](preparation.json), [recipe](recipe.json), [training inputs](fitting.json), [matrix](matrix.npy), [groups](groups.json), [folds](split.json), and [runtime](runtime.json) freeze 1,713 rows and 217 features before fitting.
- [Independent input audit](independent-input-audit.json) and [release review](independent-release-review.json) precede the [parent release](fit-approval.json) and [fit claim](fit-claim.json).
- [Every fit receipt](fit-attempt-0000/receipts/) records training/validation indices, model hash and parameters, timestamps, and exact save/load inference agreement.
- [All six forecast files](fit-attempt-0000/predictions/) retain 10,278 OOF points; [all metrics](fit-attempt-0000/metrics/) retain zeros, tails, strata, caps32/64/128, and their denominators.

Thirty local joblib forests total 179,716,740 bytes and are excluded from Git. They remain in `fit-attempt-0000/models/` in the originating workspace. No single full-data deployment model was fit. This checkout provides saved-point evidence; executing model inference requires those separate local model artifacts and compatible dependencies.

No new physical labels, normalization queries or outside evaluation targets were used. These are consumed-development results. Three algorithm seeds do not establish population confidence intervals or fresh transfer. V9 remains the current full-data development predictor.

Run `make reproduce-v12 PYTHON=.venv/bin/python` for saved-point score replay and vector/raster figures in a new output directory. [Reproduction details](../../docs/v12-target-transform-results.md#reproduction-and-artifacts) distinguish portable score replay from local-model inference.

Independent validation passed in two separate ways: [saved-point/receipt replay](independent-results-audit.json) reconstructs every metric and threshold decision with the standard library; [actual model inference](independent-model-inference.json) reloads all 30 local forests and reproduces all 10,278 encoded, decoded, and final points exactly, with no fitting. The numerical score replay retains 218 floating-point rounding differences within its declared 1e-12/8-ULP tolerance; all counts and JSON types match exactly.

Validation: **1,592 tests and 111 subtests pass** ([full-suite log](publication-full-suite.log)). The documented score/figure reproduction also completes ([log](reproduction.log)).
