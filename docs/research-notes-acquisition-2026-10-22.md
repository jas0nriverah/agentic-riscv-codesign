# Acquisition and transfer methods — October 22, 2026

This is a selective primary-method review and a proposed next decision experiment, not a model implementation or a new result. It follows the [current scope](../README.md), [handoff](HANDOFF.md), [research foundation](research-foundation.md), and [live-adaptation result](ml-live-adaptation.md). No model fitting, native measurements, or frozen-source edits were performed for this review.

## Decision supported by the present evidence

The smallest useful next hypothesis is **whether multiplying acquisition by predicted inverse duration hurts the three-query endpoint**. Keep the existing hardware GP, features, training exclusions, adaptive updates, and every existing policy fixed. Compare one duration-free acquisition against the existing cost-aware acquisition on consumed development sources before freezing a new source test. This isolates a decision rule from a representation/model change. It is a proposed test; it is not established that removing duration improves selection.

All 87 verified cycle reductions currently agree with calibrated latency. The expensive unknowns are hardware feasibility and evaluation cost, with source transfer errors. The latest expanded-history study regresses both GP policies and ranking, while expint's optimum is found at query two by GP and query one by merit. These observations do not establish that exploration caused the first infeasible query: incorrect area beliefs, the duration multiplier, and posterior update behavior are competing explanations.

The runtime inspected was `isaforge/budgeted_selection.py`, especially `HardwareSurrogate.fit`, `hybrid_score`, and `search`. It uses standardized structural features, fixed isotropic Matérn-3/2 GPs with `alpha=1e-4`, independent area/timing/log-duration outputs, and a common smoothed device-fit rate. Its acquisition is positive analytic speedup improvement times independent area/timing probabilities, device-fit rate, and expected inverse duration. The common device-fit rate does not distinguish candidates. No successful example currently supplies a timing/device-fit failure boundary. These probabilities remain model beliefs, not calibrated confidence.

### Count budget and time budget are different decisions

Our derivation: write `b(x)` for known benefit, `v` for the best verified feasible benefit, and `F(x)` for successful verification plus hardware feasibility. With **one query remaining**, maximizing expected terminal verified improvement gives

`a_count(x) = max(b(x) - v, 0) * P(F(x) | paid data)`.

This statement assumes benefit really is known and the verification/feasibility probability is the appropriate joint probability. Independent marginal probabilities are an additional modeling assumption. For future workloads the analytic benefit still requires measured validation; 87 agreements do not prove universal exactness.

Utility units also matter: for the primary cycle-reduction endpoint, use `b(x) = 1 - 1/speedup(x)`. Expected speedup and expected cycle reduction need not rank uncertain-feasibility queries identically. The narrowly isolated **duration-removal ablation** proposed here retains the existing speedup gain; it therefore tests that one factor rather than claiming exact Bayesian optimality for the primary cycle-reduction metric. Changing both gain units and duration would be a broader acquisition change and must be identified as such before testing.

The current extra factor `E[1/T]` changes the objective. In its log-normal model it is `exp(-mu_logT + variance_logT/2)`: holding median duration fixed, more duration uncertainty increases this factor. That is arithmetic, not evidence that uncertain commands finish sooner. Retain this policy as the established cost-aware control. Report actual cost for a count-aligned policy as well; a count win need not be a time win. A genuine remaining-time-budget policy would model the probability and utility of completing later queries before a deadline, rather than assume this product solves the finite-horizon problem.

## Six method families worth distinguishing

The descriptions below are based on method sections of the linked primary versions. Adaptation judgments are ours. They are deliberately narrower than a model-version survey.

### 1. Two-step constrained lookahead: closest match to verified terminal utility

**Yunxiang Zhang, Xiangyu Zhang, Peter Frazier. _Constrained Two-step Look-Ahead Bayesian Optimization_. NeurIPS 2021.** Read the [published paper](https://papers.nips.cc/paper_files/paper/2021/file/685217557383cd194b4f10ae4b39eebf-Paper.pdf), §§2.3, 3–4 and 5.1. The arXiv title differs; this citation identifies the proceedings version.

2-OPT-C chooses the first evaluation for the expected best **observed feasible** result after one further adaptive evaluation. Independent objective/constraint GPs and correlated beliefs across candidate locations allow an infeasible measurement to improve the next choice. The paper develops likelihood-ratio gradient estimation for continuous acquisition optimization; its experiments fit GP hyperparameters. Neither that optimizer nor those fits are required by our tiny finite pool.

**Adaptation:** enumerate the remaining six/twelve candidates, fantasize jointly correlated constraint values, update the posterior, and maximize the expected terminal verified incumbent. Use deterministic analytic benefit rather than an objective GP. Two-step lookahead is exact only for two remaining queries under its assumed probabilistic model; using it with three remaining is a receding-horizon approximation. Freeze fantasy draws/count, ties, numerical integration, and overhead accounting. A poor transfer posterior can make this confidently wrong. Defer until the simpler count-alignment test identifies a remaining exploration problem.

### 2. Constrained knowledge gradient: valuable constraint information, different final recommendation

**Juan Ungredda, Juergen Branke. _Bayesian Optimisation for Constrained Problems_. ACM TOMACS 34(2), article 9, 2024, DOI [10.1145/3641544](https://doi.org/10.1145/3641544).** Read [the author's accepted manuscript](https://wrap.warwick.ac.uk/id/eprint/182775/1/WRAP-Bayesian-optimisation-constrained-problems-24.pdf), §§4.1–4.6 and 5. Its repository cover identifies it as an accepted manuscript; the embedded 2021/template bibliographic footer is not the published citation. [Repository metadata](https://wrap.warwick.ac.uk/id/eprint/182775/) establishes the journal version.

cKG values an observation through its effect on the posterior-best objective weighted by feasibility. This can reward learning a constraint even where immediate feasible improvement is unlikely. Its usual recommendation may be unmeasured. Crucially, §5 addresses a decision maker requiring a sampled feasible solution: it suggests cKG for the first `B-1` iterations, then noisy EI (ordinary constrained EI without noise) on the last. The finite-space consistency result is an infinite-budget result.

**Adaptation judgment:** its distinction between learning and final verification is useful. It is less directly matched than 2-OPT-C to a three-query best-verified endpoint, and its consistency theorem supplies no three-query guarantee. Do not compare its unmeasured recommendation with our measured winner.

### 3. Decoupled cKG: recent, but requires a different purchasing interface

**Xietao Wang Lin, Juan Ungredda, Max Butler, James Town, Alma Rahat, Hemant Singh, Juergen Branke. _Bayesian Optimisation: Which Constraints Matter?_ [arXiv:2512.17569v1](https://arxiv.org/html/2512.17569v1), December 19, 2025.** Read §§2.2–2.4, 3.1–3.3, Algorithm 1 and §§4.1–4.3. This is the identified preprint, not an asserted accepted journal/conference version.

dcKG selects both a design and an individually purchasable objective/constraint observation, divided by that function's cost. A coupled alternative prevents the pathology in which no individual observation appears worthwhile. cEI+ chooses the design by constrained EI and the function by dcKG. The experiments start with six fully coupled designs and use a 150-coupled-evaluation-equivalent budget.

**Adaptation judgment:** our one charged integrated attempt presently yields correctness, area and routed timing together. It cannot save cost by simply skipping a constraint in the score. A later staged verifier/synthesis/router interface could make decoupling meaningful, but must predeclare stage costs, partial-observation semantics, failures, and the full final verification requirement. The paper does not demonstrate its advantage under our one-to-three-query conditions. No new decoupled infrastructure is justified for the immediate experiment.

### 4. RGPE: negative-transfer protection has a paid-target-information requirement

**Matthias Feurer, Benjamin Letham, Eytan Bakshy. _Scalable Meta-Learning for Bayesian Optimization using Ranking-Weighted Gaussian Process Ensembles_. AutoML Workshop at ICML 2018.** Read [the author-hosted expanded workshop manuscript](https://ml.informatik.uni-freiburg.de/wp-content/uploads/papers/18-AUTOML-RGPE.pdf), §§3.1–3.2 and experimental setup. This is a workshop paper, not main-track ICML proceedings; it is distinct from the nine-page preprint reviewed previously.

RGPE keeps separate source GPs, samples pairwise ranking losses on paid target observations, and weights each model by its probability of minimum loss. The target model uses leave-one-out predictions. Poor source models are discarded relative to the target's sampled loss to prevent weight dilution. Ranking requires more than one target observation; the experiments initialize with three random target evaluations.

**Adaptation judgment:** valuable protection against blindly pooling unrelated sources, but it cannot identify source relevance before query one. With only three queries its published initialization consumes the whole budget. Furthermore, correct ranking of area does not imply correct feasibility at an absolute +64-LUT threshold: a source-dependent offset can preserve ranks while missing every boundary decision. Different source candidate domains need a justified shared representation. Keep source-group diagnostics and target-only/prior controls; do not promise automatic negative-transfer immunity from ranking weights.

### 5. CMES-IBO: finite-pool information acquisition, with a different reward

**Shion Takeno, Tomoyuki Tamura, Kazuki Shitara, Masayuki Karasuyama. _Sequential- and Parallel- Constrained Max-value Entropy Search via Information Lower Bound_. ICML 2022, PMLR 162:20960–20986.** Read [the published paper](https://proceedings.mlr.press/v162/takeno22a/takeno22a.pdf), §§2, 3.1–3.3 and Appendix A.

CMES-IBO seeks information about the constrained optimal value using a computable mutual-information lower bound. It explicitly represents the possibility of no feasible point. The main model uses independent GPs and Gaussian observation noise; the acquisition uses noiseless latent outputs for tractability. For a moderately sized finite pool, the paper samples the optimum from joint predictive distributions directly, avoiding continuous random-feature optimization.

**Adaptation judgment:** this provides a clean finite-pool constraint-information comparator, but information gained is not expected best verified benefit after three attempts. Our deterministic objective also changes the optimal-value distribution; its continuous-objective formulas should not be copied by substituting a zero-variance objective without a derivation. Baseline fallback removes the practical empty-feasible-set problem. Prefer count EI, then terminal-utility lookahead, before adding an entropy-search control.

### 6. SAASBO: feature relevance, not a transfer or calibration cure

**David Eriksson, Martin Jankowiak. _High-Dimensional Bayesian Optimization with Sparse Axis-Aligned Subspaces_. UAI 2021, PMLR 161:493–503.** Read [the published paper](https://proceedings.mlr.press/v161/eriksson21a/eriksson21a.pdf), §§4.1–4.3 and Algorithm 1.

SAASBO places global/local half-Cauchy shrinkage priors on inverse squared kernel length scales, favoring a small number of active input dimensions. Its acquisition integrates over hyperparameter samples obtained with NUTS. This is an explicit sparsity assumption, not evidence that arbitrary structural descriptors transfer between workloads.

**Adaptation judgment:** potentially useful if source-held-out diagnosis shows irrelevant feature dimensions are the error mechanism. It adds inference machinery and prior choices without resolving source offsets, known-objective acquisition, or workload-shift calibration. It is a poor first response to the present failures. Do not begin a kernel/feature/prior sweep on eleven consumed sources.

## Current-access limits

The two suggested OpenReview MTPFN endpoints, [Ge3wbgb2Vi attachment](https://openreview.net/attachment?id=Ge3wbgb2Vi&name=pdf) and [iwqJLEPgvF PDF](https://openreview.net/pdf?id=iwqJLEPgvF), returned browser-verification pages on direct retrieval in this review. Search-indexed first-page text for the former identifies a third SPIGM Workshop at NeurIPS 2025 manuscript, while secondary listings mix 2025 and 2026 titles/status. This is insufficient to assert an accepted ICLR 2026 version or a full method review. Their architecture is not an immediate recommendation. Recent publication dates do not replace method/assumption access.

The [hierarchical-data primary manuscript](https://arxiv.org/html/2306.06342v4), Lee, Barber and Willett, _Distribution-free inference with hierarchical data_, v4 August 2, 2025, §2.2 Theorem 1, was also checked: its marginal coverage premise is hierarchical exchangeability. Neither candidate-row bootstrap nor adding a conformal wrapper proves this premise under a new workload distribution and adaptive query selection. Eleven sources are the relevant scale for source-level reliability, not 87 independently exchangeable rows or repeated policy seeds. A separate current-reliability review covers this in more detail.

## A bounded development-to-test protocol

1. **One immediate change:** remove only the inverse-duration factor, retaining the identical speedup gain, hardware surrogate and paid adaptation. Preserve all twelve existing policies, primary +64 LUT4/12 MHz/three queries, and one/two-query curves plus +32/+128 controls. Do not jointly alter feature scaling, kernel, source weighting and acquisition.
2. **Whole-source development:** use consumed sources only; keep every context of a source together and apply the exact/related-tree-family exclusions before fitting. Equalize admissible rows across learned controls. Inspect old-versus-expanded-cohort changes separately so a benefit from less history is not presented as an acquisition benefit. Seal all label-free predictions before scoring. Diagnose area residual bias, feasibility discrimination near caps, per-source calibration, changes in the chosen score factors, and outcomes after each paid update. A successful infeasible native evaluation teaches area/timing; an infrastructure failure is an unknown outcome, not a negative feasibility label.
3. **Then one untouched-source freeze:** require meaningful public benefit and enough legal candidates using label-free qualification criteria declared in advance. Freeze pools, cohorts, runtime, predictions, acquisition, ties and budgets together before labels; no target sources train each other. Charge every attempt. Collect the declared primary live trace before oracle-only outcomes. A prospective source is not interchangeable with a fresh candidate from a consumed source.
4. **Measure decisions and full costs:** source-macro best verified cycle reduction and measured-pool regret at query three are primary; query-one/two outcomes expose first-query errors. Retain all policy wins/ties/losses. Charge historical labels/attempts and their measured time once globally, including paid failures and excluded-but-collected history; separate qualification/baseline setup, target measurement, refits/inference and oracle-reference collection. Preserve raw paired timers and earlier clock qualifications. Repeated seeds and caps are dependent endpoints. An earlier optimum reached inside a fixed three-query run is not automatic stopping or a total-cost saving.

If this isolated acquisition test fails, the next supported hypothesis should follow its error decomposition. Consistent source-dependent area offsets motivate a narrowly defined transfer/representation correction; otherwise a frozen two-step finite-pool policy is the closest established exploration extension. Neither requires another speedup predictor while the calibrated benefit residual remains zero. Do not implement all six reviewed methods as a sweep.

Implementation reuse: existing `hybrid_score` exposes the factor decomposition, `search` supplies the charged provider and incumbent, and the current grouped experiment wrappers supply exclusions and prediction sealing. Preserve their frozen bytes. A new lookahead adapter would need **joint** posterior covariance across pool candidates, available from each fitted sklearn GP with `return_cov=True` and the existing output scales; current public `HardwareSurrogate.predict` supplies only marginal standard deviations. Independent per-candidate fantasies would discard the constraint-information mechanism being tested. Native dispatch, release gates, partial audits and one-attempt semantics can remain in the existing live controller.
