# V5 frozen experiment

Read [results and limitations](../../docs/v5-results.md),
[protocol](../../docs/v5-protocol.md), and
[reproduction](../../docs/v5-reproduction.md).

`freeze.json` and all six predictions were committed in `fc338e8` before
`label-release.json` authorized test collection. Four nested V5 views share
fitting rows, grouped folds, six estimator configurations and calibration rows.
The fixed MasterRTL recipe and unchanged V4 artifact are additional references.

* `corpus/development/`: 512 newly verified and measured development circuits.
* `development-data.json`: 2,057-row ledger, including all historical labels.
* `split.json`: 1,665 fitting and 392 calibration formulas, structural groups
  and fitting-only fold assignments.
* `development-evaluation.json`: all configuration scores and calibration.
* `models/`, `predictions/`: frozen artifacts, schemas and test predictions.
* `corpus/test/`: 256 fresh inputs, original-RTL verification and synthesis.
* `input-seal.json`, `test-clusters.json`: separate acquisition and uncertainty
  group definitions. Input-only rejected pools remain in `input-attempts/`.
* `evaluation.json`: all six scores, both scopes, every candidate error,
  thresholds, coverage and paired descriptive intervals.

Original RTL is the measured target. Raw netlists, logs and feature caches live
under ignored `generated/`; tracked scores can be replayed without them. A
new model requires a new evaluation lineage, not edits to this freeze.
