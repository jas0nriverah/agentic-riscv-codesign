# Final selection scorecard — October 27, 2026

This is a reproducible summary of the archived, retrospective, consumed-data
whole-workload-holdout screen at
[`2026-10-26-feasibility-model-screen`](../2026-10-26-feasibility-model-screen/).
It is not an independent test and no selector is promoted by this scorecard.

## Decision

Carry **XGBoost `rank:pairwise`** forward as the single ML challenger for the
next frozen, prospective cohort. Keep the existing merit heuristic as the
operational fallback and strongest comparison. This is a test-priority choice,
not evidence that ML wins. Pairwise ranking is the most balanced candidate
across budgets: its measured regret is 0.290 percentage
points lower than merit at one query and 0.027 points
lower at two queries, then 0.056 points worse at three.
The archived paired intervals cross zero at the first two budgets; at budget
three the point estimate favors merit and its interval touches zero at the
boundary. The matched XGBoost-versus-merit contrasts are:
- B1: +0.290 percentage points (95% CI -0.065 to +0.849; workload wins/ties/losses 2/9/1).
- B2: +0.027 percentage points (95% CI -0.097 to +0.177; workload wins/ties/losses 1/10/1).
- B3: -0.056 percentage points (95% CI -0.167 to +0.000; workload wins/ties/losses 0/11/1).
A feasibility XGBoost policy is stronger at the
one-query point estimate (regret 0.729%)
but degrades to 0.528% by three
queries. The mixed ranking is why none is promoted as the universal winner.

## What was evaluated

- 122 successful, measured candidate labels and four charged failures across
  14 held-out workload groups; 12 groups have complete verified candidate-pool
  oracles. The two incomplete oracles are excluded from regret, while observed
  best verified speedup is still summarized across all 14.
- Each fold holds out an entire workload and removes related operation-tree
  families from training. Five selector seeds and repeated contexts are
  averaged within workload; they do not increase the independent sample size.
- These 14 workload-group folds are still a consumed development cohort, not
  the six-independent-source-family confirmatory cohort required by the
  project contract. Candidate selection here is single-instruction; combined
  instruction sets have not been measured in this scorecard.
- All methods receive the same 1, 2, or 3 attempted hardware evaluations.
  The endpoint is the best actually measured, correct result meeting the
  +64-LUT4 and 12-MHz constraints. Failed attempts consume budget and time.
- Selected-design area and minimum routed Fmax are joined to the hash-bound
  measured corpus. These resource means are conditional on finding a verified
  feasible winner; selection coverage is shown separately, so a missing winner
  is not treated as a zero-area result.
- The paired confidence intervals below are the source report's workload
  bootstrap intervals. The frontier intervals are independently recomputed
  with 20,000 deterministic workload bootstrap draws. They are
  descriptive intervals over consumed data, not confirmatory inference.

## Research outcome

The regret leader changes with budget: factorized feasibility XGBoost (tied
with logistic feasibility) at one query, pairwise XGBoost at two, and merit at
three. At three queries pairwise
regret is 0.070%
versus merit's 0.015% (a
0.056-point disadvantage for pairwise).
The measured pairwise advantage at budgets one and two is too uncertain and
small to support an ML-superiority claim. There is no justification for another
model-family sweep on these same 122 labels.

| Policy | Budget | Best verified cycle reduction (95% workload CI) | Oracle regret (95% CI; 12 complete pools) | Target evaluation time (s) |
|---|---:|---:|---:|---:|
| Merit | 1 | 1.086% [0.076, 2.498] | 1.132% [0.323, 2.084] | 55.67 |
| Merit | 2 | 1.657% [0.474, 3.113] | 0.465% [0.043, 0.996] | 114.24 |
| Merit | 3 | 2.043% [0.912, 3.401] | 0.015% [0.000, 0.044] | 169.76 |
| XGB pairwise ranker | 1 | 1.334% [0.287, 2.733] | 0.842% [0.097, 1.801] | 56.29 |
| XGB pairwise ranker | 2 | 1.680% [0.509, 3.106] | 0.439% [0.036, 0.992] | 115.69 |
| XGB pairwise ranker | 3 | 1.996% [0.864, 3.354] | 0.070% [0.000, 0.182] | 171.46 |
| XGB speedup regression | 1 | 1.083% [0.073, 2.496] | 1.135% [0.326, 2.082] | 55.77 |
| XGB speedup regression | 2 | 1.655% [0.472, 3.118] | 0.468% [0.049, 0.995] | 114.61 |
| XGB speedup regression | 3 | 2.023% [0.876, 3.400] | 0.038% [0.000, 0.091] | 168.26 |
| Factorized feasibility XGB | 1 | 1.431% [0.298, 2.888] | 0.729% [0.156, 1.409] | 55.15 |
| Factorized feasibility XGB | 2 | 1.598% [0.437, 3.043] | 0.535% [0.043, 1.185] | 111.75 |
| Factorized feasibility XGB | 3 | 1.604% [0.437, 3.060] | 0.528% [0.029, 1.172] | 167.51 |

For the selected feasible winners, mean added area and mean minimum routed
Fmax compare as follows. The minimum selected-design Fmax is
59.13 MHz, 47.13 MHz above
the frozen timing floor; timing is not boundary-challenging in this cohort.

| Budget | Merit: coverage / mean added LUT4 / mean min-routed Fmax | Pairwise XGB: coverage / mean added LUT4 / mean min-routed Fmax |
|---:|---:|---:|
| 1 | 42.9% / 39.5 LUT4 / 68.2 MHz | 57.1% / 34.6 LUT4 / 67.5 MHz |
| 2 | 57.1% / 34.5 LUT4 / 68.2 MHz | 64.3% / 34.2 LUT4 / 67.9 MHz |
| 3 | 85.7% / 39.3 LUT4 / 67.2 MHz | 85.7% / 40.0 LUT4 / 67.4 MHz |

The speedup labels equal the independent calibrated-latency estimates exactly,
so this corpus does not yet demonstrate that XGBoost learns residual
program-level speedup behavior. The selector comparison mainly tests ranking
and hardware-feasibility decisions. The broad screen's combined order-generation
timer (XGB regression, pairwise ranking and ordering together) averages
0.404 seconds across 15 contexts; it does not isolate the
pairwise model. A separate measured-benefit ranker example fit in
0.659 seconds and scored twelve candidates
in 0.0008 seconds, but it uses a different
training relevance target. These host timings are small relative to target
evaluation time, yet the exact selected ranker's fit/inference duration should
be recorded in the next frozen run.

## Figures and files

- [`best_verified_cycle_reduction.svg`](best_verified_cycle_reduction.svg):
  achieved measured improvement versus query budget.
- [`oracle_regret.svg`](oracle_regret.svg): regret versus complete measured
  feasible-pool oracle; censored pools are excluded.
- [`paired_regret_vs_merit.svg`](paired_regret_vs_merit.svg): matched,
  workload-level ML-versus-merit contrasts and archived intervals.
- [`workload_regret_differences.svg`](workload_regret_differences.svg):
  per-workload heterogeneity; gray cells are oracle-censored.
- [`measured_area_performance.svg`](measured_area_performance.svg): measured
  area/performance trade-off among selected feasible designs.
- [`policy_metrics.csv`](policy_metrics.csv): policy-by-budget aggregate
  metrics and uncertainty intervals.
- [`workload_level_metrics.csv`](workload_level_metrics.csv): one row per
  workload, policy and budget.
- [`selected_hardware_metrics.csv`](selected_hardware_metrics.csv): selected
  area, minimum routed Fmax, and selection coverage under the fixed constraints.
- [`paired_regret_vs_merit.csv`](paired_regret_vs_merit.csv): matched paired
  contrasts from the archived experiment.
- [`model_scoring_overhead.csv`](model_scoring_overhead.csv): fit/inference and
  combined-order timing with each timing scope stated; not pooled with
  target-measurement time.

## Next confirmatory milestone

Freeze the pairwise ranker, merit, frequency, timing-aware merit, and random
policies before any fresh candidate outcomes. Use an untouched eligible
workload/family cohort, identical measurement budgets, and complete-oracle
regret where feasible. Report query count, actual target measurement time,
fit/inference time, correctness, area, timing, best verified performance, and
paired workload-level intervals. If no independent cohort qualifies under the
unchanged gates, say so and retain this as development-only evidence.

## Provenance

- Primary result: `results/2026-10-26-feasibility-model-screen/report.json` (SHA-256 `b5f28629493d90d11151be88a7996a0b9027362d5c92f463ca5621cc54080660`).
- Frozen protocol SHA-256: `7eff9339c71619fdf55dd24b2681314ac0740906f8ffdd36c452b645f810de5c`; source manifest SHA-256:
  `235cfe3a6c993f78c184676f24441438facdaf1f7760ece7dacddc93ecff9f93`.
- Source data corpus SHA-256: `901413111da94933a1c14f0e758c1cf96f959bde44325e79ded6e47c4b8743ef`.
- Regenerate: `python3 scripts/build_research_selection_scorecard.py`.
