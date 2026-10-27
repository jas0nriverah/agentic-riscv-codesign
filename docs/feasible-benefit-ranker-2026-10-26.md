# Decision-aware ranker diagnostic — October 26, 2026

This experiment asks whether the current pairwise ranker makes poor choices because it ranks performance benefit without accounting for integrated hardware feasibility. It trains an unchanged pairwise XGBoost model on a different, decision-aligned relevance label: measured whole-program cycle reduction for a candidate that meets the +64 LUT4 and 12 MHz constraints, and zero relevance for a measured infeasible candidate.

It uses the authenticated 122-label, 126-attempt corpus, whole-workload holdouts, and related operation-tree-family exclusions. Each held-out pool is ranked before revealing its outcomes. The three budgets charge failed attempts and their measured time exactly as in the frozen failure-aware screen. Comparisons reuse the exact `merit`, latency/cost heuristic, pairwise XGBoost, and factorized feasibility trajectories from that screen. This is consumed-data development, not independent confirmation.

| Queries | Feasible-benefit ranker regret | Merit regret | Pairwise XGBoost regret | Factorized feasibility regret |
|---:|---:|---:|---:|---:|
| 1 | 1.0988% | 1.1317% | 0.8417% | 0.7292% |
| 2 | 0.7349% | 0.4654% | 0.4385% | 0.5347% |
| 3 | 0.6689% | **0.0145%** | 0.0702% | 0.5275% |

At one query, the challenger's mean regret advantage over merit is only **0.0329 percentage points**; the 95% workload-bootstrap interval is **−1.0307 to +1.2206 pp** (4 wins, 3 ties, 5 losses). At three queries, merit has **0.6544 pp lower mean regret**; the challenger’s paired advantage over merit has a 95% interval of **−1.1954 to −0.1467 pp**. Five workloads favor merit, six tie, and one favors the challenger. The new ranker is also worse than the existing pairwise ranker at all three budgets. These outcomes do not support promoting the decision-aware relevance.

The result suggests that changing the ranking label alone does not solve the hardware-feasibility boundary problem. It may also discard useful ordering information by assigning all infeasible candidates the same relevance. That explanation is a hypothesis; this experiment does not isolate why the ranker loses.

The model takes an average **0.049 s per held-out workload fold** to fit and about **0.00022 s per target context** to score on this host. Mean charged hardware-evaluation time is 56.16, 112.40, and 169.96 seconds at budgets 1, 2, and 3. Model compute is recorded separately from the hardware-evaluation budget.

The current dataset is too small to make grouped conformal bounds a reliable next selection policy. There are fourteen workload groups, and the groups are selected, correlated engineering sources rather than an established exchangeable sample. Even ordinary split-conformal 95% calibration needs at least nineteen independent calibration groups; five calibration groups support only a coarse 80% order statistic. Existing hierarchical-conformal guarantees concern a random observation from a new group and do not by themselves establish coverage for ISAForge's selected candidate pools. Treat any group-residual bound on this corpus as exploratory, not a calibrated safety guarantee. Add fresh workloads and boundary-diverse hardware outcomes before estimating uncertainty or selecting another model family.

## Reproduction

With the pinned research dependencies installed, run:

```sh
python scripts/evaluate_feasible_benefit_ranker.py \
  --corpus results/2026-10-26-lift-selection-corpus/corpus.json \
  --baseline-screen results/2026-10-26-feasibility-model-screen \
  --output results/2026-10-26-feasible-benefit-ranker-screen
```

The [sealed report](../results/2026-10-26-feasible-benefit-ranker-screen/results.md) contains per-workload trajectories, training label audits, fit/inference timings, paired contrasts, protocol source hashes, and its artifact manifest. The [broader fixed feasibility screen](model-screen-2026-10-26.md) contains the matched controls and model-family results.
