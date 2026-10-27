# Model-selection update — October 26, 2026

The best model depends on how many hardware evaluations are available. The current evidence does **not** support one universally best learner or a claim that ML beats the strongest heuristics.

## What the data says

The authenticated corpus now contains **122 successful, correctness-verified whole-program speedup labels from 14 workload groups, plus four charged failed attempts** (126 total attempts). The four failures were kept in held-out candidate pools and charged against the query budget. Failed candidates were never assigned fake area or speedup labels. Two infrastructure-censored candidates in UD and G.723 leave those complete-pool oracles unknown, so regret is averaged over the other **12 fully observed workload groups**. The 15 Brier-scored target contexts include two SHA256 contexts from one workload group.

Before testing more speedup regressors, we checked the measured labels directly: **all 122 measured speedups exactly equal the independent calibrated-latency estimate**. There is no residual signal for another whole-program speedup regressor to learn in this corpus. The live modeling problem is deciding which predicted-benefit candidates will satisfy integrated area and timing constraints.

The new fixed-screen diagnostic holds out an entire workload and excludes every related operation-tree family from its training rows. It compares the existing pairwise XGBoost ranker and speedup regressor, the existing factorized feasibility XGBoost, cap-specific XGBoost, workload-group-bootstrap XGBoost, logistic regression, random forest and Extra Trees. Frequency, merit, calibrated latency, the latency/cost heuristic and random selection remain matched-budget controls. It includes budgets 1/2/3 at +64 LUT4 and 12 MHz. Every model and ordering uses target public features only; outcomes are revealed only for scoring after query selection. This is retrospective consumed-data development, not a confirmatory test.

| Query budget | Lowest-regret tested learner | Mean regret to complete-pool oracle | Strongest simple policy | Mean regret |
|---:|---|---:|---|---:|
| 1 | Existing factorized feasibility XGBoost; logistic ties its selections | 0.7292% | Frequency | 0.9414% |
| 2 | Existing pairwise XGBoost ranker | 0.4385% | Merit | 0.4654% |
| 3 | Speedup-regression XGBoost | 0.0383% | Merit / calibrated latency | **0.0145%** |

At B1, factorized feasibility has **0.2121 pp lower regret than frequency**. An exploratory paired workload bootstrap gives a 95% CI of **−0.5787 to +1.2122 pp** (2 wins, 9 ties, 1 loss across 12 groups); the difference is concentrated in CRC32 (+4.8374 pp), Expint (+0.0345 pp), and SHA256 (−2.3263 pp). Its **0.4025 pp** advantage over merit is numerically correct, but merit is not the strongest simple B1 control. At B2, pairwise XGBoost improves mean regret by only **0.0268 pp** over merit (95% CI: **−0.0969 to +0.1774 pp**; one win, ten ties, one loss). At B3, the raw speedup regressor is the closest tested learner (0.0383% regret), followed by pairwise XGBoost (0.0702%); both lose to merit at 0.0145%. None of these comparisons establishes a reliable ML advantage.

For feasibility probability quality, the existing factorized XGBoost has the lowest mean Brier score (**0.2374**) among the tested models. The group-bootstrap XGBoost is 0.2482, cap-specific XGBoost 0.2519, training-prevalence prior 0.2592, logistic 0.2682, random forest 0.2891 and Extra Trees 0.3297. This is a macro average over **15 held-out benchmark contexts** (including two SHA256 contexts in one workload group), scored only on successful measured candidates. Failed and infrastructure-censored outcomes remain unknown. Scores are uncalibrated; the Brier comparison is descriptive and does not turn the policy comparison into confirmation.

## Recommendation

These are **separate budget-conditioned retrospective policies**, not one sequential selector: switching from factorized at B1 to pairwise at B2 to merit at B3 does not reproduce merit's first three queries. Any prospective comparison must freeze one exact query order per policy before labels and charge the actual paid prefix. The existing cap-conditioned utility model nearly matches, but has slightly higher regret than, factorized feasibility at B1/B2 (0.7296% vs 0.7292%; 0.5358% vs 0.5347%); it underperforms pairwise at B2 and improves over factorized at B3 while merit remains best. See the [matched utility-model screen](feasible-benefit-loco-2026-10-26.md). A follow-up decision-aware pairwise ranker that trains on measured feasible cycle reduction loses at B2/B3 and does not replace these choices; see the [separate diagnostic](feasible-benefit-ranker-2026-10-26.md). Do not replace the production selector or claim generalization from these consumed-data screens.

The prior three-source blind campaign gives the hybrid hardware GP the strongest historical B3 learned result, but the fresh bitcount test reversed it and the prospective advantage did not persist. That remains a negative-transfer warning, not evidence to choose the GP universally. Lift's one-query pairwise-ranker oracle hit is a consumed engineering result; all other Lift policy trajectories are post-collection replay, not live ML-controlled native selection.

The next useful step is a read-only inventory of genuinely unmeasured independent workload/family sources, with eligibility and prior rejections recorded before choosing a test. If a source qualifies, freeze candidate construction, exact sequential orders for frequency, merit, random, pairwise, factorized, utility and established constrained controls, and the evaluation budget before labels. Preserve the existing 12-candidate gate unless a different pool size has a separate protocol justification. Current successful labels contain no timing-boundary cases: do not fit or claim a useful joint timing/area-feasibility model from these all-positive timing labels or alter constraints to manufacture failures. Report best verified performance, charged failures, actual evaluation time and the restricted-pool oracle. Stop before native collection if no independent source qualifies; one-source success permits more testing, not promotion.

The earlier `2026-10-26-grouped-ranker-objectives` experiment is exploratory only for this question: it drops failures and treats every pool as a complete oracle. Do not combine its regret numbers with this failure-aware comparison.

## Reproduction

Use the pinned research dependencies (`requirements-speedup.txt`) and a fresh output directory:

```sh
python scripts/evaluate_feasibility_model_families.py \
  --corpus results/2026-10-26-lift-selection-corpus/corpus.json \
  --output results/2026-10-26-feasibility-model-screen
```

The sealed [screen output](../results/2026-10-26-feasibility-model-screen/results.md) includes the protocol, held-out fold definitions, full policy trajectories, source/feature-only feasibility scores, paired workload bootstrap intervals, model timings and artifact manifest. No native jobs were run for this model screen.
