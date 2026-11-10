# Is feature selection stable?

**The MAE improvement repeats across seeds, but budget mistakes still worsen. The candidate is not eligible for promotion.**

We added two seeds fixed before scoring and retained the original seed as a descriptive reference. All runs use the same 1,665 development rows, 522 groups, five folds and 300-tree settings. Each fold selects 128 features using only its training rows. These seed replicates measure training randomness, not independent data or population uncertainty.

| Seed | Fixed 217 MAE | All 336 MAE | Selected 128 MAE |
| --- | ---: | ---: | ---: |
| 2026101401, retained | 10.5678 | 10.4034 | **10.0054** |
| 2026110901 | 10.7647 | 10.2866 | **10.0201** |
| 2026110902 | 10.5356 | 10.3655 | **10.0791** |
| Mean across seeds | 10.6227 | 10.3518 | **10.0349** |

MAE is the equal-group primary endpoint in LUT4. Selected128 improves mean seed MAE **5.53%**. Its MAPE is also lower on each seed. [All metrics](summary.json).

## Hardware-budget tradeoffs

The following counts sum three repeated evaluations of the same circuits; they are **not counts of distinct independent test circuits**.

| LUT4 cap | 217 false accepts | 128 false accepts | 217 false rejects | 128 false rejects |
| --- | ---: | ---: | ---: | ---: |
| 32 | 65 | **60** | 289 | **278** |
| 64 | **45** | 56 | **115** | 121 |
| 128 | **31** | 38 | **19** | 21 |

Worst underprediction across seeds rises **193.59 → 194.72 LUT4**. The frozen eligibility rule requires lower primary MAE on every seed, neither type of budget mistake worsening at any cap in the descriptive seed aggregate, and no worse maximum underprediction. The candidate passes only the MAE condition. No post-result threshold adjustment was applied.

## Selection consistency

For the same validation fold, the mean feature-set Jaccard similarity across seeds is **0.845** (minimum 0.803). Across all 15 selections it averages 0.729; **82 columns** appear in every selection, and 202 appear at least once. Jaccard is intersection size divided by union size. These results support a repeatable selection tendency, not one universally optimal 128-feature list.

After cross-validation, the predeclared original seed fits a full-data 217 control, a 336 selector and a 128 candidate. Their weights and schemas live in [models/](models/). The candidate uses the full-data selector, not a subset chosen by validation error. These artifacts are experimental, point-only and uncalibrated. The deployed model remains unchanged. The separate [fresh validation](../selection-validation/README.md) freezes these models and predictions before collecting new targets.

## Compute and reproduction

Exactly **33 new fits completed in 96.56 seconds**, with one worker and native thread, below the 600-second limit: 30 cross-validation fits plus three final fits. The original 15 fits were reused, not rerun. No synthesis or independent targets enter this stability experiment.

```sh
python scripts/replay_selection_stability.py
```

This replays scores, selections, eligibility and hashes with zero fits. To repeat training, use a fresh directory:

```sh
python scripts/test_selection_stability.py prepare --output generated/selection-stability-repeat
python scripts/test_selection_stability.py run --output generated/selection-stability-repeat
```

[Pre-score protocol](protocol.json) · [Predictions](predictions.json) · [Selection records](selected-columns.json) · [Independent audit](audit.json). The original experiment remains byte-for-byte preserved.
