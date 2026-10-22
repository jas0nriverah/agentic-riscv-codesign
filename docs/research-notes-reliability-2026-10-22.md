# Current tabular learning, grouped evaluation and reliability

Reviewed October 22, 2026. These primary-method notes supplement the [model diagnosis](model-research-analysis-2026-10-22.md), [hardware](research-notes-hardware-2026-10-22.md) and [acquisition](research-notes-acquisition-2026-10-22.md) reviews. No ISAForge model was fitted or replaced. Recent preprints are identified as preprints; their results are not ISAForge experiments.

## Tabular foundation models are a possible future comparator

**Hollmann, Müller, Purucker et al., _Accurate predictions on small data with a tabular foundation model_, Nature 637, 319–326, January 8, 2025, DOI 10.1038/s41586-024-08328-6.** Primary [article and methods](https://www.nature.com/articles/s41586-024-08328-6), particularly inference details; [primary PDF](https://www.nature.com/articles/s41586-024-08328-6.pdf). TabPFN uses synthetic-task pretraining and in-context prediction; its ensemble uses preprocessing and feature permutations. This is evidence for a useful small-tabular comparator, not proof that its prior matches integrated FPGA hardware costs. An indistinguishable input representation and a mismatched decision objective remain problems regardless of predictor. Do not claim that the 2025 model is the latest version or start a foundation-model sweep to avoid the diagnosed failures.

## Current evidence favors testing the actual group shift

**Purucker, Tschalzev, Erickson et al., _Beyond IID: How General Are Tabular Foundation Models, Really?_, arXiv:2606.30410v1, June 29, 2026, preprint.** Read [§5, §6 and Appendices F.2/F.4/F.5](https://arxiv.org/html/2606.30410v1). BeyondArena curates 142 datasets and compares eleven models across IID, temporal and grouped settings. It uses group-preserving outer tests and inner validation for grouped tasks; its IID-split ablations change difficulty and rankings. Traditional-model tuning and default foundation-model inference use different protocols, and its aggregate results are not a matched three-evaluation search comparison.

**ISAForge implication:** use source workloads, including all compiler/input contexts, as the unit in both development validation and untouched tests. Related-formula exclusions remain an additional requirement. Eleven sources, several different contexts and 87 candidate rows do not establish the regime where another model family will win. This paper evaluates point-prediction/ranking metrics rather than proving our feasibility probabilities calibrated.

## Accuracy, proper score and reliable uncertainty are different endpoints

**Zhao, Guo, Tan and Zhang, _TabReliBench: Evaluating Tabular Foundation Models Beyond Predictive Accuracy_, arXiv:2610.13654v1, October 9, 2026, preprint.** Read [§§2–5 and Appendix B.1.2](https://arxiv.org/html/2610.13654v1). The benchmark has 160 classification and 81 regression datasets, with five random train/test repetitions and dataset-level analysis. It separately measures predictive accuracy, proper scoring rules, marginal/subgroup calibration and interval efficiency. Its ensemble-size ablation finds metric-dependent gains; better point predictions do not ensure better calibration. Its random within-dataset split protocol is not a substitute for workload holdouts.

**ISAForge implication:** retain source-level feasibility Brier diagnostics alongside constraint-boundary mistakes, interval widths and verified-selection regret. Never use low MAE or a larger ensemble as evidence of safe area-budget decisions. Dataset-level findings motivate our evaluation design; they do not establish our confidence bounds or rank current ISAForge learners.

## Hierarchical conformal prediction has nontrivial assumptions and data needs

**Lee, Foygel Barber and Willett, _Distribution-free inference with hierarchical data_, arXiv:2306.06342v4, August 2, 2025.** Read [§2.2, Theorem 1 and construction](https://arxiv.org/html/2306.06342v4). The method splits groups, gives each calibration group equal mass regardless of row count, and includes an infinity atom for a new group. Coverage relies on hierarchical exchangeability. At a 90% nominal level, only five calibration groups leave an infinity mass of 1/6, so the usual quantile construction can produce an infinite interval.

**ISAForge implication:** the 87 candidates are not 87 independent calibration workloads. A useful finite source-level interval may require substantially more independent groups. Convenience-sampled workloads, selected candidate pools and adaptively purchased outcomes require care; the theorem does not automatically cover their shift. A row bootstrap or unqualified conformal wrapper would overstate what the current data supports.

## Practical decision

Keep existing XGBoost and GP controls. First test the isolated acquisition failure, then a narrow established semantic representation if needed. Add group-held-out reliability evidence and independent source diversity. A new tabular model becomes worth testing only after the current representation/decision bottleneck is addressed and there is a predeclared source-held-out comparison; no architecture change or calibration guarantee is implemented by this review.
