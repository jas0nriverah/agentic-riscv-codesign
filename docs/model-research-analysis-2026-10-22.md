# ISAForge model diagnosis and research decisions — October 22, 2026

## Conclusion and evidence boundary

ISAForge has a working measured optimization pipeline and limited evidence that learned selection can beat merit. It does **not** yet have a consistently better selector or calibrated uncertainty on unseen workloads. The most useful improvements are specific: align acquisition with the declared budget, distinguish semantically different hardware in the features, and test transfer on additional independent workloads with useful optimization opportunities. A larger model is not the first missing connection.

This analysis adds a reproducible [quantitative diagnosis](../results/2026-10-22-model-research-diagnosis/README.md), [hardware-method review](research-notes-hardware-2026-10-22.md), [acquisition/transfer review](research-notes-acquisition-2026-10-22.md), and [current tabular/reliability review](research-notes-reliability-2026-10-22.md). It uses primary method sections, exact versions and explicit access gaps. There are no new fitted scientific models, native measurements or policy trajectories. All eleven existing source workloads are consumed development data; the cached counterfactual below is not a new held-out result.

The [proposal](original-project-proposal.txt) and [scope contract](../README.md) still govern the work: select legal custom instructions to improve measured whole-program execution under hardware and evaluation constraints. Preserve CRC32, aha-mont64, negative results and every earlier freeze. RTL implements and measures instructions; an RTL-rewriting agent is outside scope. Cloud/API/demo/live-LLM work remains paused.

## What the current models actually learn

The automatic corpus contains **87 verified candidate labels, three preserved failed attempts, eleven sources and twelve contexts**. Six sources are Embench and five are BEEBS. There are 99 completed integrated processor designs and 297 routing results including baselines. The three failed attempts comprise two known validation failures and one infrastructure-censored unknown outcome. None should be filled with an invented speedup or area label.

| Existing component | Target and information | Consequence for improvement |
| --- | --- | --- |
| Raw XGBoost regression | Real baseline/modified whole-program speedup | A real performance model, not an isolated LUT model; transfer remains weak. |
| Normalized XGBoost | Measured cycles saved per executed replacement; reconstructed whole-program speedup | Removes large differences in workload execution counts. Its improvement is useful but does not establish selection superiority. |
| XGBoost pairwise ranking | Relative measured speedup within a benchmark context | It does not learn an area-constrained order merely by learning the speedup order. |
| Budget-conditioned utility XGBoost | Feasible benefit at a supplied hardware budget | Existing direct decision hypothesis; preserve both its SHA improvement and other losses. |
| Factorized XGBoost classifier | Feasibility score, multiplied by calibrated analytic benefit | Existing hardware-decision hypothesis; bootstrap disagreement is not calibrated confidence. |
| Zero-shot/adaptive GP selection | Independent integrated-area, routed-Fmax and log-measurement-duration predictions; analytic benefit | This selector does **not** learn program speedup. Only paid target measurements update the adaptive hardware model. |
| Calibrated latency | Lowered instructions, dynamic occurrences and independently measured PicoRV32 instruction/PCPI costs | Exact on all 87 observed cycle changes; it is a required strong control. |

All 87 cycle differences equal the independently calibrated latency estimate. Under this restricted fixed-latency PCPI pipeline, we currently have no observed residual benefit for another learner to explain. This is not proof for arbitrary workloads, different microarchitectures, input-dependent behavior or instruction combinations. Retain real execution labels and their verifier; do not manufacture a harder prediction problem by hiding valid public profile information from only the heuristics.

The present ML opportunity is predominantly **predicting whether the promising instruction fits the hardware budget and choosing which uncertain outcome to purchase**. That remains inside the research objective. A claim of learned speedup generalization must separately beat the analytical baseline on cases where it has an actual error.

## What improved, and what regressed

The earlier [three-source blind campaign](blind-source-campaign.md) produced a real but narrow win: at +64 LUT4 and three queries, both frozen GP controls found all three pool optima, with **1.602185%** source-macro cycle reduction versus **1.144539%** for merit. This is three independent source tests, not 15 independent seeds or a total-cost saving after collecting training data.

The later [expanded-history comparison](ml-live-adaptation.md) is a consumed-data development experiment. It changes historical training availability while holding targets/settings fixed. Its primary endpoint is source-macro cycle reduction on the same compression, DES and MD5 targets, at +64 LUT4, 12 MHz and three attempts:

| Policy | Earlier history | Expanded history |
| --- | ---: | ---: |
| Frequency | 1.010363% | 1.010363% |
| Merit / calibrated latency | 1.144539% | 1.144539% |
| Random | 0.595405% | 0.595405% |
| Latency/area-cost heuristic | 0.705266% | 0.705266% |
| Raw XGBoost | 0.766274% | 1.602185% |
| Normalized XGBoost | 1.449636% | 1.602185% |
| Pairwise ranking | 1.149319% | 0.652616% |
| Zero-shot GP | 1.602185% | 1.144539% |
| Adaptive GP | 1.602185% | 0.839441% |
| Utility XGBoost | 0.602929% | 0.602929% |
| Factorized feasibility | 0.719365% | 0.748475% |

More data helps some models and hurts others. Do not promote the best development row after seeing the table. The DCT development control and all one/two-query/cap results remain in the sealed report. In particular, the tight-area DCT failure persists.

The latest fresh-source [Expint experiment](../results/2026-10-22-live-gp-report/results.md) is a working live feedback loop, with the actual GP querying **03 → 00 → 01** before the oracle-only remainder. It reaches the optimum on query two; merit and normalized XGBoost need one. The best design saves only **11 / 31,843 cycles = 0.034544484%**, at +17 LUT4. Each candidate executes once. This source verifies integration and exposes a decision failure; its small opportunity cannot support a compelling application-performance headline.

## Diagnosed failure 1: the representation merges different hardware

The 31 hardware features have 79 unique vectors among 87 rows. One exact same-context collision involves different NDES formulas:

| Formula | Measured added LUT4 | Measured cycles saved | +64 feasible? |
| --- | ---: | ---: | --- |
| `add(in0,slli(in1,2))` | 70 | 3,280 | No |
| `slli(add(in0,in1),2)` | 40 | 720 | Yes |

The formulas have the same operation histogram and depth but different operation order. No learner receiving that identical hardware vector can distinguish them. The full 35 profile/structural features used by raw regression/ranking are unique across the corpus; this particular exact collision should not be attributed to every model.

Expint candidate03, `add(in0,slli(in1,3))`, demonstrates the consequence. Its frozen GP predicts **40.002 added LUT4 with model standard deviation 0.214**, while actual integrated synthesis gives **71**. This is not a calibrated confidence interval. Its nearest retained training vector is the reordered 40-LUT NDES expression above. The standardized distance is **2.699e−9**: only constant magnitude differs, 3 versus 2, and its historical standard deviation is **370,562,752.59**. Operator-order information is absent and this raw-constant scale nearly erases the remaining difference. Correct related-family exclusion removes the same-order NDES example; retaining it would weaken the test rather than fix the representation.

Reuse established semantic analysis, not an arbitrary new graph model. The existing formula-only `structural_features_v3.feature_dict` already distinguishes the NDES pair using order, carry and demanded-bit descriptors. Expint00 also simplifies over the complete u32 domain to `x == 0 ? 1000 : 2`, while Expint07 is `4-x mod 2^32`. Syntactic operation count misses that distinction. Conservative known/demanded-bit analysis has a primary precedent in [BitValue](https://www.cs.cmu.edu/~seth/papers/budiu-tr00.pdf); recent [ISAMORE](https://uv-xiao.github.io/assets/pdf/isamore_asplos26.pdf) uses semantic equivalence and reusable patterns rather than demonstrating learned integrated-LUT features.

However, the existing v3 representation gives identical vectors to two DCT constant expressions whose integrated additions are 33 and 15 LUT4. Original DCT hardware vectors differ in constant magnitude; their cached classifier outputs are identical. This is fitted-score equivalence, not another exact original-feature collision. Also preserve the earlier **negative 45-descriptor experiment**, which moved adaptive SHA optimum attainment from query two to three. Separating a motivating pair is a necessary diagnostic, not proof of useful cost prediction. Do not promote the entire descriptor bundle or introduce synthetic area-training labels.

## Diagnosed failure 2: acquisition mixes count and time objectives

The existing GP score is approximately:

```text
positive analytic speedup improvement
  × P(area within cap) × P(clock feasible) × common device-fit rate
  × E[1 / measurement duration]
```

The primary endpoint gives each policy the same **number of charged attempts**, so the duration multiplier can sacrifice that endpoint for a different preference. In every cached decomposition the clock factor is numerically 1; the device-fit rate is common within a pool. Area probability and the duration factor drive the relevant hardware ranking.

We exactly reproduce all **270 archived first choices** from cached predictions: two GP policies, nine source/cohort cases, three caps and five dependent seeds. The policies share their initial prediction, so there are 135 distinct initial cases. Removing **only** the inverse-duration factor changes 20 choices: 15 almost-tied old-AHA choices with equal actual benefit, and five Expint +64 choices. Measured first-query outcomes improve in **5**, worsen in **0**, and tie in **130**. All improvements are dependent repetitions of one fresh-source failure.

For Expint +64, the existing score chooses the infeasible +71-LUT formula. The unchanged predicted benefit and feasibility factors, without inverse duration, choose the measured +17-LUT optimum. This justifies an ablation; it does not establish a full-trajectory improvement, a new blind win, a calibrated posterior or a time saving. It also does not explain the entire expanded-history three-query GP regression.

For one query remaining, known benefit `b`, verified incumbent `v` and true joint feasibility event `F`, our terminal-utility derivation is `max(b-v,0) × P(F | paid observations)`. For the primary cycle-reduction metric, `b = 1 - 1/speedup`. The proposed single-factor ablation deliberately retains the frozen **speedup** gain, so it is not claimed to be the exactly optimal cycle-utility policy. Changing the benefit units is a separate experiment. A deadline policy also needs remaining-time/completion reasoning; inverse-time weighting alone is not an optimal finite-budget planner.

## Diagnosed failure 3: eleven sources are not a broad hardware dataset

- **Constraint diversity:** 12/87, 44/87 and 87/87 verified designs satisfy +32/+64/+128 LUT4 respectively. All 87 fit the device and clear 12 MHz; minimum routed Fmax ranges from 59.133 to 73.411 MHz. Timing and device-capacity failure boundaries are unobserved. Extra cap replicas do not create new physical measurements.
- **Group imbalance:** four sources supply 48/87 candidate rows. Three twelve-candidate contexts supply 198/319 possible within-context pairs. Candidate-row bootstrapping does not represent eleven independent source draws. Source-balanced fitting is a testable hypothesis, not a demonstrated alias or transfer fix.
- **Ranking mismatch:** there are 294 unequal-performance pairs and 25 ties across the twelve contexts. At +64, 78 potential pairs prefer a faster but infeasible instruction over a slower feasible one. A pure speedup ranker is rewarded for that order; adding more such pairs does not teach hardware feasibility. Pairs share rows and are not 294 independent samples.
- **Pool coverage:** pools contain 6 or 12 selected formulas. For MD5, 12 of 297 eligible formulas were measured; DCT has 6 of 29. Later shortlists span instruction-saving ranks rather than being a simple top-K list, but they are still merit-stratified convenience subsets. The oracle is a **declared-pool oracle**, not the best instruction in the complete source program. UD additionally retains an unresolved censored pool member.
- **Reliability:** Expint's wrong, narrow posterior is direct evidence against interpreting GP standard deviation as calibrated uncertainty. Earlier bootstrap coverage and Brier negatives remain. A row-bootstrap or conformal wrapper cannot establish unseen-source coverage merely by being added to the pipeline.

The next data increment should add independent sources and actual decision difficulty, rather than repeatedly sample nearly equivalent formulas. Predeclare a fixed qualification order and label-free useful-headroom criterion from supported instructions/profiled occurrences, plus a manageable legal-pool requirement. Retain every rejected qualification. This defines an opportunity-rich supported population; it must not become post-label workload shopping. Include enough candidates around the fixed area boundary where possible, without using hidden target synthesis labels to choose them. Do not manufacture failures by silently raising the timing target or changing the ISA.

## What current research changes about the plan

The [hardware review](research-notes-hardware-2026-10-22.md) distinguishes modeled performance, datapath area and integrated processor outcomes. [CIDRE, ICCAD 2025](https://arxiv.org/html/2509.15782v2), is the most relevant synthesis/timing-aware selection precedent; a faithful PicoRV32 adaptation still needs our latency/interface constraints and integrated measurements. Our simple merit is not its full reproduction. [CIExplorer, ICS 2025](https://hpcrl.github.io/ICS2025-webpage/program/Proceedings_ICS25/ics25-61.pdf), does not justify an out-of-order performance model for the present in-order pipeline. New extraction or RTL frameworks are not the missing connection.

For search, [constrained two-step lookahead, NeurIPS 2021](https://papers.nips.cc/paper_files/paper/2021/file/685217557383cd194b4f10ae4b39eebf-Paper.pdf), is a plausible later comparator because the endpoint is a verified result. It needs joint posterior covariance, not independent candidate fantasies. Constrained KG can recommend unmeasured designs; recent [decoupled KG](https://arxiv.org/html/2512.17569v1) assumes separately purchasable observations. Neither can be copied without matching our final-verification and coupled-attempt contract. RGPE is relevant to negative transfer, but its paid-target initialization and inability to correct absolute area offsets by ranking alone limit its immediate value. Detailed assumptions are in the [acquisition notes](research-notes-acquisition-2026-10-22.md).

Recent tabular-model results do not establish that switching from XGBoost to a foundation model fixes these failures. [Beyond IID, June 2026 preprint](https://arxiv.org/html/2606.30410v1), reinforces grouped inner and outer evaluation. [TabReliBench, October 2026 preprint](https://arxiv.org/html/2610.13654v1), separates accuracy, distribution quality and subgroup reliability. These are useful evaluation lessons, not ISAForge performance evidence. The exact Sun TCAD 2004 and Hussein TACO 2026 full-method access gaps remain explicitly unresolved; related versions have not been silently substituted.

## Next experiment and acceptance criteria

**First: one acquisition ablation, with no new model architecture.** Preserve all twelve controls, exact fitting cohorts/family exclusions, hardware context, existing benefit units, posterior settings, paid updates, ties and budgets. Remove only inverse-duration weighting in one new adapter; do not edit hash-bound runtime. Replay full trajectories on consumed sources, keeping old and expanded history separate. This is the next engineering experiment, **not completed by the present first-query arithmetic**.

**Then: freeze a three-source untouched pilot.** Use the same declared +64-LUT4/12-MHz/three-attempt endpoint and one/two-query curves; retain +32/+128 controls. Declare the qualification order and numerical useful-opportunity/pool criteria before qualifying new independent supported sources. If fewer than three qualify, preserve the rejections and report that blocker rather than silently lowering the gate. Freeze the complete package before labels, collect the primary live trace before oracle-only measurements, and never train one target on another's outcomes. Three fresh sources remain a descriptive pilot, not a powered field-wide superiority claim.

**Next, only if the error persists: one semantic representation hypothesis.** Reuse a small, declared formula-only block that addresses the demonstrated operation-order/bit-demand alias. Keep acquisition and learner fixed so the cause remains identifiable. Include the negative DCT and earlier descriptor results in development checks; do not sweep bundles and report the winning one as a fresh test. Source offsets, robust constant scaling or source weighting each require their own evidence before being combined with this change.

Report source-macro best **verified feasible** cycle reduction and oracle regret at each paid query, oracle-gain fraction where positive, failed/infeasible-query rate, and queries to a predeclared fraction of oracle benefit. Also retain source-level uncertainty diagnostics and widths near the area cap. Report target cost, historical training attempts/time, qualification/baseline setup, fit/inference and oracle-reference costs separately; preserve raw timer scopes and existing clock qualifications. Repeated seeds/caps do not increase the independent source count. No automatic stopping or total-cost win follows from finding the optimum before the end of a fixed run.

Only after this evidence should a finite-pool lookahead method or an LLM selection agent become a new comparison. The later one-to-three-instruction endpoint requires joint lowering, execution and synthesis, with overlap/compatibility handled explicitly. Individual speedups and area increments cannot be added. That is a meaningful extension of the present known-single-instruction-benefit setting, not permission for another disconnected framework.

## Reproduce this analysis

```sh
# Python 3.12 with requirements-speedup.txt; OUTPUT must be fresh.
python scripts/diagnose_current_models.py --output generated/reproduction/model-research-diagnosis
python -m pytest -q tests/test_current_model_diagnosis.py
```

The diagnosis authenticates inputs and existing prediction arithmetic. It does not refit the reviewed models, run synthesis or produce a new selection trajectory. [Validation logs](../results/2026-10-22-model-research-validation/README.md) distinguish this analysis from historical regression tests. The next blocker is a complete isolated acquisition replay followed by genuinely untouched, useful-headroom source evidence; it is not another model version or deployment wrapper.
