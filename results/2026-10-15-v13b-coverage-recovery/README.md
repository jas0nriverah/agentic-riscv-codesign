# V13b coverage recovery

Status: all 48 original circuits passed 103,104 RTL comparisons and completed synthesis. The independent measurement audit verified all 48 mapped LUT4/carry counts and 540 raw archive members. Feature extraction completed for all 48 candidates using 112 graph/SOG processing runs. The shared-fold comparison is prepared; no model improvement is claimed before its results.

The fitting inputs contain 1,761 rows, 217 features and 538 groups. Both model variants use the same five assessment folds (372, 382, 349, 329 and 329 rows). Control training uses eligible original rows only; augmentation adds eligible coverage rows. The primary endpoint remains equal-nine-stratum macro MAE on the original 1,713 examples. The new 48 examples are a separate secondary endpoint. Thirty fits are planned: two variants, five folds and three paired seeds.

Raw measurement and feature archives are committed. Expanded feature cache/workers remain local because the archive preserves their complete contents. Any fitted forests remain local with committed byte receipts and held-out prediction records; score replay and model inference are reported separately.

See the [recovery methodology](../../docs/v13b-coverage-recovery.md) and [machine-readable amendment](recovery-amendment.json). The original [failed V13 attempt](../2026-10-15-v13-coverage-development/README.md) remains preserved. This stage targets area labels; timing, CPU workload benefit, power and energy require separate evidence.
