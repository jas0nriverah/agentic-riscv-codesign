# V13b coverage recovery

Status: complete measurements, features and 30 matched fits. All 48 original circuits passed 103,104 RTL comparisons and completed synthesis. The independent measurement audit verified all 48 mapped LUT4/carry counts and 540 raw archive members. Feature extraction completed for all 48 candidates using 112 graph/SOG processing runs. Independent score replay and actual inference verified all 10,566 predictions from 30 saved forests.

The fitting inputs contain 1,761 rows, 217 features and 538 groups. Both model variants use the same five assessment folds (372, 382, 349, 329 and 329 rows). Control training uses eligible original rows only; augmentation adds eligible coverage rows. The primary endpoint remains equal-nine-stratum macro MAE on the original 1,713 examples. The new 48 examples are a separate secondary endpoint. Thirty fits completed: two variants, five folds and three paired seeds.

**Result: no promotion.** Original-cohort primary MAE worsens **5.5040 → 5.7882 LUT4 (+5.16%)**. New-cohort pooled MAE improves **480.7060 → 25.7168**, but original-cohort cap64 false rejections and maximum underprediction worsen. The current V9 development predictor is retained. See [complete results](../../docs/v13-coverage-results.md), the [model diagram](../../docs/ml-model.md), [independent scores](fitting/independent-results-audit.json), and [actual saved-model inference](fitting/independent-model-inference.json).

Raw measurement and feature archives are committed. Expanded feature cache/workers remain local because the archive preserves their complete contents. Any fitted forests remain local with committed byte receipts and held-out prediction records; score replay and model inference are reported separately.

See the [recovery methodology](../../docs/v13b-coverage-recovery.md) and [machine-readable amendment](recovery-amendment.json). The original [failed V13 attempt](../2026-10-15-v13-coverage-development/README.md) remains preserved. This stage targets area labels; timing, CPU workload benefit, power and energy require separate evidence.
