# Existing feasible-benefit XGBoost: 14-workload LOCO screen

The repository already contains `FeasibleBenefitPredictor`, which predicts measured decision utility conditioned on area cap. Its earlier fresh SHA256 test found the best feasible candidate in two queries, but the cost-aware heuristic found it in one. The October 26 analysis adds this existing model to the current failure-aware, whole-workload comparison; it does not add or tune a model family.

The authenticated corpus has **122 successful labels, four charged failed attempts, 14 workload groups, and 15 benchmark contexts**. For each target workload, training excludes that group and every related operation-tree family in its successful and failed pool. The model ranks public candidates by predicted fractional cycle savings at **+64 LUT4 / 12 MHz**. The first one, two, or three ordered attempts count against the same budget. Failures consume their measured time but are never given invented feasibility or utility labels. Two infrastructure-censored pools are excluded from oracle regret.

| Queries | Feasible-benefit model regret | Factorized feasibility XGBoost | Pairwise XGBoost | Merit |
|---:|---:|---:|---:|---:|
| 1 | 0.7296% | **0.7292%** | 0.8417% | 1.1317% |
| 2 | 0.5358% | 0.5347% | **0.4385%** | 0.4654% |
| 3 | 0.3369% | 0.5275% | 0.0702% | **0.0145%** |

The utility model and feasibility classifier are effectively tied at query one and query two. The utility model has lower mean regret than the classifier at query three by **0.1907 percentage points**, but eleven of twelve complete workload groups tie; one group accounts for the difference and none favor the classifier. At query two the pairwise ranker has lower regret than the utility model by **0.0972 pp**, with an interval crossing zero. At query three merit has **0.3223 pp lower regret** than the utility model; ten groups tie and two favor merit. These are retrospective comparisons on data already used during engineering, not proof of superiority or generalization.

Mean fit time is **0.087 s per held-out workload** and mean scoring time is **0.0024 s per context** on the recorded host. Mean charged evaluation time is 55.55, 111.68, and 168.15 seconds at budgets 1, 2, and 3. The model's bootstrap utility spread remains uncalibrated. It estimates measured feasible decision utility, not a calibrated speedup or feasibility probability.

## Interpretation and next step

Keep the existing utility model as a matched challenger, especially at low budgets; do not promote it as the default. The current retrospective screen favors different policies by budget: factorized feasibility at B1, pairwise XGBoost at B2, and merit at B3. These differences mostly arise from a small number of workload groups and are not independent confirmation.

All measured speedups still match the independently calibrated latency model exactly, while none of the 122 routed minimum Fmax values is within 20 MHz of the 12 MHz floor. Additional benefit regression has no observed residual to learn, and timing feasibility is not meaningfully challenged. The informative next work is new hardware outcomes near the real feasibility boundary on untouched workloads, followed by a frozen, failure-aware comparison. Do not use these consumed folds to choose and then claim a winning model.

## Reproduction

With the pinned Python 3.12 research dependencies installed:

```sh
python scripts/evaluate_feasible_benefit_utility_screen.py \
  --corpus results/2026-10-26-lift-selection-corpus/corpus.json \
  --baseline-screen results/2026-10-26-feasibility-model-screen \
  --output results/2026-10-26-feasible-benefit-utility-screen
```

The [sealed output](../results/2026-10-26-feasible-benefit-utility-screen/results.md) records per-workload candidate scores and trajectories, source-bound protocol, fitting rows, fit/inference time, paired contrasts and artifact checksums. No compiler, simulator, synthesis or routing jobs were run for this model comparison.
