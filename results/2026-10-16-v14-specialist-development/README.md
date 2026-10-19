# V14 exploratory structural routing

One input-only gate chooses between the two already evaluated V13 predictors. It matches 0 original examples and 16 new high-product examples. All original predictions are preserved exactly; new-cohort pooled MAE changes 480.7060 → 27.4819 LUT4, while new-cohort maximum underprediction remains worse. No new fits, native measurements or model promotion.

This is post-hoc consumed-development analysis, not independent validation. [Full result and limits](../../docs/v14-specialist-results.md) · [V13 regression diagnosis](../../docs/v13-regression-diagnosis.md).

`routing-plan.json` binds source and inputs before the one score computation; `routing-results.json` and `routing-predictions.json` retain all seeds and decisions. The input-only gate tests pass on general constants, all high-product kinds, nested expressions and fallback cases. Broader operation coverage in those unit tests does not prove prediction accuracy on those structures.

Validation: the full local suite passes 1,808 tests and 129 subtests; [retained log](publication-full-suite.log). The routing audit reproduces all 5,283 decisions and scores; [replay log](reproduction.log). The 41 focused routing/transport tests are recorded in [focused-tests.log](focused-tests.log). The transport fixtures are synthetic engineering tests, not new program-transfer measurements.
