# Results

Three curated datasets retain every original circuit, measured LUT count and comparator prediction. Run `make reproduce` to verify their hashes and regenerate [summary.json](summary.json). No training or synthesis is needed.

## 1. Research-baseline comparison

192 synthetic circuits, eight equally sized structural strata. All models below use the same 1,665 fitting circuits and original-RTL targets. MAE includes all 192 circuits; MAPE uses 186 positive targets, with six zeros retained separately.

| Model | MAE, LUT4 ↓ | MAPE ↓ |
| --- | ---: | ---: |
| **ISAForge base** | **32.1609** | **43.63%** |
| Dual-graph control | 34.3322 | 49.37% |
| Tuned simple operator graph | 46.3390 | 75.63% |
| MasterRTL recipe adaptation | 61.4686 | 85.67% |

Adding mapping descriptors lowers primary MAE by **6.32%** against the dual-graph control. These are our FPGA recipe comparisons, not the published MasterRTL ASIC results. All eight historical comparator predictions, including additional ablations, remain in [observations](research-baselines/observations.json).

## 2. Application transfer

327 unique original circuits across five nonempty application families. All base/coverage predictions were frozen before new labels. The original input pool has recorded overlap with earlier data. The scoped policy was designed afterward and selects base on every case.

| Model | Primary family-macro MAE, LUT4 ↓ | Unique positive-circuit MAPE ↓ |
| --- | ---: | ---: |
| **Base** | **0.506605** | 29.27% |
| Coverage | 0.525239 | **28.28%** |
| Scoped, retrospective | 0.506605 | 29.27% |

Coverage **worsens the primary endpoint by 3.68%**, despite slightly lower MAPE. MAPE uses 228 positive physical circuits; all 99 zero targets remain in MAE. Family-macro MAE weights families equally through 521 program/formula memberships. Circuit-pooled MAE is 0.832987 for base and 0.831651 for coverage; changing that weighting changes the conclusion, so the original primary remains explicit. Threshold mistakes are unchanged. [Observations](application-transfer/observations.json) · [Audit](application-transfer/audit.json).

## 3. Prospective arithmetic stress

32 new related synthetic circuits, four templates with eight parameters each. All 32 route to coverage, so scoped and coverage predictions are identical. This tests arithmetic coverage, not transfer to new application families.

| Model | MAE, LUT4 ↓ | MAPE ↓ | Cap64 false rejections ↓ | Worst underprediction, LUT4 ↓ |
| --- | ---: | ---: | ---: | ---: |
| Base | 15.5211 | 13.42% | 4 | **2.83** |
| Coverage / scoped | **12.0093** | **11.57%** | **2** | 32.01 |

All 32 targets are positive. All four template MAEs improve; aggregate MAE falls **22.63%**. The larger underprediction tail keeps the scoped policy experimental. All 68,736 sampled RTL checks and 32 measurements passed. [Observations](arithmetic-stress/observations.json) · [Audit](arithmetic-stress/audit.json).

## Evidence and interpretation

The iteration diagram also shows an earlier **25.40% development improvement** on previously examined applications. It uses a different cohort and is not another independent test. Its full measured record is linked from the diagram source to the immutable archive.

Each dataset has `candidates.json`, cached `features.json`, `observations.json` and an original audit receipt. [Provenance](provenance.json) records the source commit and SHA256 of every source/export. Audits retain their original historical paths; resolve those paths in the [preserved archive](https://github.com/jas0nriverah/agentic-riscv-codesign/tree/b64716a2b94b332fdbced677869620bb949c073d), where raw netlists, verification logs, protocols, input amendments and failed experiments remain available. No failed case was removed to produce this presentation.

These are three different benchmark distributions. Their raw error values do not form a learning curve. The estimates concern isolated FPGA area; no learned instruction-selection or CPU-performance advantage follows from these scores alone. [Definitions and MAPE calculation](../docs/benchmarks.md).
