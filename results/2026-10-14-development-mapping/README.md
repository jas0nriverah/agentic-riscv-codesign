# Mapping-feature development ablation

[Findings](findings.md) retain both feature views, all three predeclared seeds and nine strata. 1,665 fitting rows, five component folds, fixed 300-tree configuration, 30 fits. Macro MAE improves 6.87% on average; all eight nonmultiplication strata improve, multiplication worsens, tails are not uniformly better. These are development scores, not fresh validation.

`features.json` contains all 23 generic graph descriptors and cache provenance; `plan.json` fixes inputs/source hashes/configuration before fits; `predictions/` retains every OOF prediction. `independent-source-audit.json` records 27 focused tests and a separate 500-DAG correctness probe. No target synthesis or calibration/test outcomes enter this experiment.

Reproduce with `scripts/develop_v6_mapping.py` and the recorded original graph caches. Render the committed result with `python scripts/report_v6_mapping_development.py --root results/2026-10-14-development-mapping --output generated/reproduction/v6-development`.
