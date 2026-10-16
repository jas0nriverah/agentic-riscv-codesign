# The ISAForge area model

ISAForge's current predictor estimates the number of iCE40 four-input lookup tables needed to implement an original RISC-V computation. It uses a **300-tree ExtraTrees regression model with 217 circuit features**. The V9 development artifact was fitted on **1,713 verified, synthesized circuits**. Its output is an area estimate; processor performance and routed timing have separate experiments.

![ISAForge area-model pipeline, training labels, improvement process and measured experiment outcomes.](figures/ml-model/ml-model-overview.png)

[Editable SVG](figures/ml-model/ml-model-overview.svg) · [Presentation PDF](figures/ml-model/ml-model-overview.pdf) · [Figure data and provenance](figures/ml-model/figure-data.json)

## What the model sees

A candidate is a bounded RV32 computation with up to two inputs and one output. The feature pipeline builds original and normalized generic circuit graphs, plus a simple operator graph (SOG), before technology mapping. It computes 336 descriptors and selects a fixed 217 for this model:

| Input features | Count | Purpose |
| --- | ---: | --- |
| Simple operator graph | 14 | Summarize primitive structure |
| Original generic graph | 60 | Describe the circuit whose area is predicted |
| Normalized generic graph | 60 | Expose structure after algebraic simplification |
| Absolute differences between graph descriptors | 60 | Describe how much simplification changes the structure |
| Mapping descriptors | 23 | Describe structure relevant to LUT mapping |
| **Total used by the forest** | **217** | Fixed input representation |

Each tree predicts a LUT count and the forest averages those predictions. The existing decoding rule clips predictions to nonnegative values and applies the saved original-generic-zero override. Normalized features help explain the original circuit; they do not change which implementation supplies the target label.

Training labels come from actual Yosys iCE40 synthesis after RTL verification. Mapped target counts are kept out of predictor inputs. Inference on a new formula still requires graph preprocessing unless its feature cache already exists; the model does not eliminate all EDA work.

## How improvement is tested

1. Diagnose errors by circuit family, large underpredictions and resource-budget mistakes.
2. Define new examples before measuring them, preserving failures and overlap checks.
3. Verify RTL, synthesize the original implementations and retain raw evidence.
4. Compare training variants on common groups and folds, keeping related examples together.
5. Report average error, tails and budget decisions separately before choosing a new model.

The V13 coverage experiment adds 48 measured examples covering correlated high products, masked arithmetic chains and comparator/shift compositions. All 48 passed 103,104 RTL comparisons; all measurements passed an independent replay. Feature extraction required 112 graph/SOG processing runs.

The comparison uses 1,761 rows in 538 groups, five common folds and three paired seeds: **30 fits** across control and augmented training. The control trains only on eligible original examples. The augmented model may also train on eligible new examples. Both predict the same held-out rows. The primary endpoint remains equal-nine-stratum macro MAE on the original 1,713 examples; the 48 new examples are scored separately. This is consumed-development evidence, with no automatic full-data refit or model promotion.

## What the existing evidence says

| Experiment | Measured finding | Interpretation |
| --- | --- | --- |
| V6 mapping descriptors | Fresh structural-test macro MAE improved **6.32%** against the dual-graph control | A matched improvement on that frozen test cohort |
| V9 targeted training coverage | Consumed-application family-macro MAE **3.4092 → 2.5434 LUT4**, down **25.40%** | A development improvement; some tails and budget mistakes remain |
| V12 log-target training | Primary macro MAE **5.0777 → 5.3200 LUT4**, up **4.77%** | Rejected despite lower percentage error and better zero-target error |
| V13 targeted coverage | Original-cohort macro MAE **5.5040 → 5.7882 LUT4**, up **5.16%**; new-cohort pooled MAE **480.7060 → 25.7168** | New coverage improves sharply, but original performance regresses; V9 retained |

These experiments use different cohorts and endpoints. Their numbers are not a single learning curve. See [V6](v6-results.md), [V9](v9-coverage-results.md), [V12](v12-target-transform-results.md), and the [complete V13 comparison](v13-coverage-results.md).

The remaining research questions are whether gains transfer to unseen programs and whether predictions improve instruction selection under synthesis budgets. Timing-aware prediction, trustworthy uncertainty on new families, and power/energy measurement remain incomplete. The [hardware tradeoff ledger](hardware-tradeoffs.md) keeps measured processor and circuit results separate from ML prediction quality.
