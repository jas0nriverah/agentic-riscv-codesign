# Targeted variable-shift and mixed-arithmetic coverage

**New training coverage improves fresh accuracy, but this first candidate still fails the retained-panel budget gate.** No default model is changed.

The experiment adds 64 measured circuits to the original 1,665 fitting circuits, using the same 217 features, 300 trees and fixed seed. A raw augmented model is compared with the base and a predeclared original-AST routing policy: use augmented for any variable shift, or for add/subtract/XOR mixtures containing no multiplication; otherwise use base. This route is fixed before new labels.

## Accuracy and decisions

| Evaluation | Base MAE | Augmented MAE | Scoped MAE |
| --- | ---: | ---: | ---: |
| research-baselines (consumed) | 32.1609 | 31.4863 | 31.6614 |
| application-transfer (consumed) | 0.8330 | 0.8159 | 0.8187 |
| arithmetic-stress (consumed) | 15.5211 | 15.2942 | 15.5819 |
| selection-validation (consumed) | 15.4586 | 14.3903 | 14.2810 |
| Fresh 40 synthetic circuits | 20.1854 | 14.3215 | 14.2580 |

MAE is in LUT4. The new 40-case prospective test improves scoped MAE **29.36%**, MAPE **17.23% →14.56%**, and worst underprediction **83.53 →82.83 LUT4**. Budget counts are unchanged: false accepts/rejects are 0/4 at 32 LUTs, 0/0 at 64, and 5/0 at 128. These are empirical synthetic results, not calibrated guarantees.

Both policies nevertheless fail the predeclared development gate: false rejections increase **5→6 at 64 LUTs** on the 192-circuit panel and **7→8 at 32 LUTs** on the previous 40-case panel. The raw model also worsens worst underprediction on two panels. All endpoints remain in [development metrics](development-metrics.json) and [fresh metrics](fresh-metrics.json). Passing the fresh test does not erase the failed development condition.

## Prospective design

Both 64 training and 40 test inputs were frozen before measurement. The new test uses ten distinct composition templates: 24 targeted circuits and 16 controls. Canonical/normalization and constant-erased composition checks separate train and test; no exact 217-feature collisions were found against the original fitting data. Screening is finite and does not prove every possible semantic distinction.

The training stage measures 64 original-RTL targets. The model is then fitted once and all 40 test predictions are frozen before test labels. All 104 circuits pass **223,392 sampled/boundary RTL comparisons** and actual Yosys iCE40 synthesis. These are fresh synthetic compositions, not independent application-family or full-processor validation.

The single fit took **4.59 seconds**. Native extraction/verification/synthesis took **120.93 seconds total**, with at most two workers and zero retries, below the 1200-second limit. Prior results and weights remain unchanged.

## Evidence and next decision

[Training cohort](../targeted-coverage-data/plan.json) · [Fresh cohort](../targeted-coverage-validation/plan.json) · [Training protocol](protocol.json) · [Independent audit](audit.json). Raw evidence is compressed in each cohort directory with member hashes. The auditor replayed 1,893 predictions exactly, recounted 104 mapped netlists and checked 2,888 archive members.

The follow-up tests a separately frozen **budget-preserving correction** without retraining, on another new cohort. It preserves the baseline decisions at 32/64/128 rather than claiming to improve those decisions. This first experiment remains unchanged, and its 40 test cases are now consumed evidence. See [follow-up](../budget-preserving-coverage/README.md).
