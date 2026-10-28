# Ascon training augmentation ablation

Consumed-data development analysis. It changes only the historical training cohort for two existing grouped XGBoost recipes; no model family, feature set, target, or hardware label changes.

- Target contexts: 15 across 14 workload groups.
- Authenticated Ascon training rows: 3 (three measured, nine unmeasured remain excluded).
- Target holdout: full workload plus every expression family in that workload roster.
- Area/timing decision constraint: +64 LUT4 and at least 12 MHz.
- No native jobs, new target labels, or promoted model versions.

| Model policy | Budget | Contexts | Base workload-macro regret | + Ascon regret | Paired workload wins / ties / losses |
| --- | ---: | ---: | ---: | ---: | ---: |
| pairwise_rank | 1 | 13 | 0.00841660 | 0.00900788 | 0 / 11 / 1 |
| pairwise_rank | 2 | 13 | 0.00438540 | 0.00438540 | 0 / 12 / 0 |
| pairwise_rank | 3 | 13 | 0.00070245 | 0.00014510 | 1 / 11 / 0 |
| factorized_decision | 1 | 13 | 0.00729212 | 0.00729212 | 0 / 12 / 0 |
| factorized_decision | 2 | 13 | 0.00534721 | 0.00534721 | 0 / 12 / 0 |
| factorized_decision | 3 | 13 | 0.00527538 | 0.00527538 | 0 / 12 / 0 |

The Ascon supplement does not change factorized-feasibility regret at any tested budget. Pairwise ranking changes one correlated context at B1 (a loss) and one at B3 (a win); other comparisons tie. These retrospective folds do not justify promotion or a claim that added data improves generalization.

Reproduce with:

```sh
../work/audit-venv/bin/python scripts/evaluate_ascon_training_augmentation.py --output results/2026-10-28-ascon-training-ablation-reproduction
```

Predictions are sealed before target outcomes are reopened for scoring. The separate Ascon supplement remains training-only and cannot be loaded as a test pool or oracle.
