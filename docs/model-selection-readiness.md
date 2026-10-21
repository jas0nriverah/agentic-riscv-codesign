# Model improvement and research readiness — October 21, 2026

Implementation update: the proposed [four-tool host, remote provider and shareable demo](bounded-selection.md) now work with matched deterministic controls. Live LLM trials still need an API key. The [single descriptor ablation](../results/2026-10-21-structure-feasibility-development/README.md) is negative and is not promoted. Original arithmetic diagnostics below remain unchanged.

**ISAForge is aligned with the proposal, but the central agent and final instruction-set comparison are unfinished.** The next integration milestone should be a small bounded LLM selector, alongside one focused experiment on the demonstrated hardware-feasibility error. Keep whole-program performance under hardware and evaluation budgets as the endpoint. A new model architecture or another isolated area study would not resolve the current evidence gaps.

This review uses the preserved 33-label corpus and frozen EDN/UD/SHA256 predictions and paid-update logs. Its arithmetic factor ablations start no model fits, LLM calls or native measurements. All six workloads are consumed development data. This report does not replace the original prospective results or promote a new policy.

## What the evidence says

| Question | Finding | Consequence |
| --- | --- | --- |
| Is measured whole-program performance connected to the pipeline? | 33 verified candidates, six workloads, three separately preserved failures, 39 measured designs and 117 routes. | The engineering foundation works for the supported fixed-input domain. |
| Does the speedup model beat a strong baseline? | All 33 measured cycle reductions exactly match independently calibrated latency. Learned selection has not beaten the strongest heuristic. | Retain XGBoost as a measured comparator; another cycle residual model has no observed residual to learn. |
| What changes the SHA256 first choice? | Removing duration, duration variance or timing leaves the initial ordering unchanged for all three targets and all three area caps. Area feasibility does change the choice. | Repair the demonstrated feasibility representation before tuning duration or replacing the acquisition algorithm. |
| Is uncertainty reliable? | Nominal 90% normalized-XGBoost coverage is 36% EDN, 65% UD and 43.3% SHA256. A paid GP update produces a 33.5-standard-deviation area error. | Label spreads as uncalibrated; they cannot justify confident feasibility or deployment. |
| Does the dataset test the difficult cases? | All 33 successful candidates reduce cycles and fit the device; minimum routed Fmax is 59.308 MHz versus a 12 MHz constraint. | Area tradeoffs are tested. Successful slowdowns, timing-boundary and device-fit discrimination are not. |
| Is the original project complete? | The isolated bounded LLM comparison and jointly validated final one-to-three-instruction sets are missing. | Finish those connections before extending into new frameworks or model families. |

The [reproducible diagnostics](../results/2026-10-21-model-readiness-analysis/README.md) contain the exact candidate identities, source hashes, first-query rankings and observed paid updates. The [preserved SHA report](guarded-sha256.md) remains the authoritative prospective outcome.

## Why the current model loses measurements on SHA256

At +64 LUT4, candidate 00 offers 1.053940× cycle speedup but actually adds 68 LUT4. Candidate 22 offers 1.021385× at 50 LUT4 and is the best verified feasible design.

| Estimate before any target measurement | Candidate 00 | Candidate 22 |
| --- | ---: | ---: |
| GP predicted added LUT4 | 51.874 | 54.082 |
| GP standard deviation | 20.268 | 20.197 |
| GP probability of area ≤64 | 0.725 | 0.688 |
| Cost-aware heuristic estimate | 86.667 | 43.333 |
| Actual added LUT4, privileged scoring only | 68 | 50 |

The GP gives the higher-benefit infeasible candidate the larger feasibility probability, so it queries 00 first. After paying for 00, it predicts related candidate 11 at 67.994 ±0.526 LUT4 and chooses 22 second. Normalized XGBoost ranks by predicted speedup without an area-aware acquisition rule, so it queries 00 → 11 → 22. The simple cost-aware heuristic uses the historical 21.667 LUT/tree-operation estimate and finds 22 immediately.

An arithmetic diagnostic replacing only the area factor with actual measured feasibility changes SHA's first query to 22. This uses hidden labels and is deliberately **not a valid policy**. It locates a bottleneck; it does not establish a proposed improvement. We omit this counterfactual when hardware outcomes are missing rather than assigning failed or censored attempts invented area values.

The cost heuristic is not universally best. On EDN its 23-LUT/operation estimate places the actual +32-LUT optimum above the +64 cap, and it misses the optimum through three queries. Calibrated latency and the GP find that optimum immediately. Any revision must retain both comparators and show every workload rather than optimizing the SHA example alone.

Keep prediction and acquisition effects distinct. SHA's 00 → 11 → 22 ordering is the correct unconstrained measured speedup order; it is inefficient under the area constraint. Adding a shared feasibility-aware acquisition could improve a regressor's decisions without improving its predictions. An eventual learned-benefit comparison should hold hardware estimates and acquisition fixed when swapping normalized XGBoost for analytic benefit. Likewise an agent-only comparison must hold the numeric models and public information fixed. Do not attribute a richer policy or extra inputs to a better regressor or LLM.

## The smallest justified model experiment

The hardware GP uses 31 structural columns: operation counts and a few scalar tree summaries. Thirteen columns are constant in the 33-row corpus. It omits parent–child operator order, immediate role/sign and workload execution context. Standardizing one maximum-absolute-constant field also makes small immediate differences nearly invisible when historical constants span a much wider range.

Two examples show the risk:

- EDN `addi(slli(in0,1),-2)` costs 65 LUT4 but is predicted at 59.999940 ±0.262549. Its near-neighbor `slli(addi(in0,1),4)` costs 60. The prediction crosses the +64 boundary. This candidate's tiny benefit does not explain an initial optimum miss; it is a genuine constraint-confidence failure.
- After two paid SHA observations, candidate 33 is predicted at 50.013610 ±0.327806 but costs 61. The error is 33.514877 predicted standard deviations. Both prediction and truth fit +64, so this striking miscalibration does not itself change that endpoint's feasibility.

The setting called an 8-LUT floor is an **output-standardization floor**, not a lower bound on predictive uncertainty. Do not assume the returned standard deviation is at least eight. Exact different-formula descriptor collisions in this corpus happen to have equal measured area; the harmful evidence concerns near-neighbor transfer rather than conflicting labels at an identical vector.

Run one declared development ablation: existing features versus a compact ordered-structure/immediate bundle, keeping the fixed GP, latency anchor and acquisition rule. Candidate descriptors should include root/operator relationships, operand position, signed per-operation immediates, shift amounts and a few bounded RV32 bit-pattern summaries. Use the existing parser and validate their meaning against emitted RTL. Avoid full formula IDs, huge one-hot vocabularies or a neural representation with 33 labels.

SHA22/33 make this concrete: both are `add(in0,slli(in1,k))`, but shifting by 21 versus 14 changes measured added area from 50 to 61 LUT4. Effective operand/arithmetic width after a fixed shift is a plausible low-cost descriptor. Normalize shift amounts within their RV32 range instead of hiding them in a single field shared with large address-like constants. This is a feature hypothesis to test, not an asserted synthesis-cost formula.

Hold out whole workloads and related formula families; report the remaining fitting groups after exclusions. Judge best verified feasible speedup at each budget, false-feasible/missed-optimum queries, actual time and uncertainty failures. Area MAE is secondary. Test an uncertainty correction separately so an apparent gain can be attributed. Fit discrepancy estimates only on training/development folds. If the feature bundle does not improve decisions, preserve the negative result and keep the current baseline.

Every baseline core in this corpus is 1,653 LUT4, so dividing increments by baseline area supplies no missing distinction. More trees, more ensemble members, a GNN, another ranker or another speedup-target transform do not repair an omitted operation relationship.

## Measurement cost and acquisition

The duration model sees structural instruction features but not workload runtime. The same literal formula has the same +70 LUT4 and 61.8544 MHz result in CRC32 and EDN, yet measurement durations are about 45.453 versus 130.047 seconds. EDN predictions of roughly 41–47 seconds substantially understate its 124–140-second successful evaluations.

There is also a target-definition mismatch: older rows use narrower measurement-record timers, whereas SHA's `measurement_seconds` uses the attempt ledger including validation. SHA totals 251.904 record seconds versus 402.461 ledger seconds. Define a consistent derived training timer and preserve original scopes before adding baseline runtime, tool/build settings and validation context. Instrument full outer search time; it cannot be reconstructed as the sum of overlapping command timers. This matters to the research endpoint even though the frozen first-choice ablations show that duration did not cause the current initial ranking errors.

The current acquisition multiplies analytic gain by approximate feasibility and expected inverse duration. It is greedy gain per modeled cost, without an explicit value-of-information term. Paid observations can nevertheless help through shared hardware predictions. Larger log-duration variance increases expected inverse duration; it is not improvement divided by expected duration. Keep a no-duration control when testing changes.

Fixed-budget searches can spend after reaching the pool optimum. On SHA +64, adaptive GP's third query consumes another 66.034 seconds with acquisition approximately 2.3e−18. Some other recorded acquisitions are exactly zero. A future stop-enabled comparison should distinguish exhausted positive analytic benefit from a tiny score caused by uncalibrated feasibility. A vanishing probability is not a proof that an unmeasured instruction is infeasible. Preserve the original fixed-budget comparison and freeze any new stopping rule before prospective evaluation.

## Would an LLM agent make this better?

**Yes for completing and testing the intended system; performance improvement remains a hypothesis.** An agent could interpret formula structure, question unsupported predictions, decide which measurement could change the final choice, react to failures and choose when to stop. It cannot repair numerical calibration merely by explaining it, and every inferred hardware claim still needs measured verification.

SHA's primary optimum is already verified by the heuristic in one query. There is no query-count headroom to beat that result with another verified improving design. Use SHA as a tool/ledger regression test, alongside harder consumed cases; do not make it the sole proof that an LLM helps. An agent tying a heuristic while adding inference cost is a valid negative outcome.

Use one agent and four narrow tools over the existing pipeline:

| Tool | Contract |
| --- | --- |
| `list_candidates` | Frozen IDs, formulas, public features/profile, supported context, constraints and remaining budget. |
| `predict` | Existing learned/analytic predictions, heuristic ordering, support diagnostics and an explicit uncalibrated-uncertainty flag. |
| `measure` | One charged attempt for a permitted candidate; returns only that observation or its classified failure and cost. |
| `finalize` | Baseline or an already measured, verified feasible choice; deterministic host acceptance. |

The agent must have no filesystem, shell, raw reports or oracle access. The evaluator owns hidden labels, charging, concurrency and numerical acceptance. A hosted model given only these four tools needs a thin dispatcher, not another orchestration framework. Budget validity must hold for malformed or repeated requests, exhausted limits, failed attempts and early termination. Preserve a short decision summary and action trace; do not require hidden chain-of-thought.

Freeze one prompt/model/tool schema, examples excluding the target group/family, model-call/token limits and five trajectories. First use consumed-data replay to test the interface. Compare agent and non-agent policies with the same public descriptors and historical data. Include unchanged cold-start baselines and a separately named matched-start experiment, charging the same heuristic warm-start query to both agent and GP. A matched start isolates later adaptation; it does not test first-choice quality. Score all trajectories, failures, query count, measured/replayed evaluation costs, actual inference/search time and model cost. Fresh cache-backed replay is not fresh hardware evaluation.

If the agent gets structural context unavailable to a baseline, add that context to a deterministic or GP comparator as well. Otherwise the experiment confounds a richer input with the LLM decision layer. Stopping gains also need a stop-enabled non-agent comparator. Report five trajectories as stochastic repetitions of a workload, not five independent generalization tests.

## Dataset and research contract

Six source groups are useful engineering evidence but too few to claim broad calibrated transfer. Only four of the eight originally named programs have accepted automatic labels: CRC32, aha-mont64, EDN and SHA256. SLRE and UD supply the other two groups. The smaller supported RV32I/PicoRV32 scope is an accepted implementation choice, not a requirement to restart Spike/VexRiscv integration. Memory qualification limits support; do not silently shrink a benchmark or discard its self-check.

All current successful examples fit the device and have minimum routed Fmax far above 12 MHz. Pools are merit-conditioned shortlists; SHA's measured reference covers six of 56 eligible formulas. Candidate count, routing seeds and 450/900 endpoints do not create additional independent source workloads. Future data should expose genuine feasible-design tradeoffs, input sensitivity, near-boundary hardware and joint-set interactions. Do not manufacture a harder objective simply to obtain an ML win. Report where analytic latency and heuristics suffice.

The final selected one-to-three-instruction set remains a missing stage. Reuse the teammate slot/overlap components already reviewed, adapt them to the guarded RV32I context, and measure the combined program and hardware. Shared resources and overlapping rewrites invalidate additive speedup/area assumptions. Keep the teammate RV32IM/external-memory summaries separate until their evidence and context satisfy an explicit import contract.

| Original proposal deliverable | Current assessment |
| --- | --- |
| Real workloads → candidates → implementation → measured performance/area/timing | Working for supported individual instructions; 33 candidates exceed the approximate 25 full-processor checks. |
| Diverse dataset and unseen-workload prediction | Partial: six consumed groups, small selected pools, explicit compiler/partition shifts; eight-program leave-one-out experiment remains incomplete. |
| Predictor with confidence estimates | Implemented; confidence accuracy is assessed negatively and remains unresolved. |
| Frequency/merit/random/active learning/measured reference | Working for declared individual pools; no learned superiority and one older censored full-pool reference. |
| Bounded LLM selector compared with non-agent acquisition | Missing; next integration milestone. |
| Agent-selected final two/three instructions jointly verified | Missing in the guarded current context; reusable teammate components exist. |
| Final reproducible optimizer/report | Strong component evidence; the complete agent/set connection is unfinished. |

The proposal explicitly permits a finding that simpler selection is sufficient. Success requires a controlled, verified comparison, not an LLM or ML victory.

## Established methods and limits

The [focused methods notes](../results/2026-10-21-model-readiness-analysis/primary-methods.md) record exact versions, sections and adaptation assumptions. Gardner 2014 supports independent feasibility-weighted acquisition; Snoek 2012 supports expected inverse evaluation duration. AutoTVM motivates structural/context-aware representations, without establishing transfer to integrated processor area. None requires a new algorithm framework here.

ReAct §2 supplies the observation/action-loop precedent. LLAMBO §§2.2, 4 and 6–8 studies language-assisted Bayesian optimization for hyperparameter tuning and acknowledges increased inference cost. They motivate a bounded experiment; their results do not demonstrate ISAForge gains. [ReAct, ICLR 2023](https://arxiv.org/pdf/2210.03629v3), [LLAMBO, ICLR 2024](https://proceedings.iclr.cc/paper_files/paper/2024/file/84b8d9fcb4e262fcd429544697e1e720-Paper-Conference.pdf).

Do not promise 90% distribution-free confidence from six workload groups. CQR needs an untouched exchangeable calibration design. In Lee–Barber–Willett's hierarchical split construction, Eq. (6) assigns mass `1/(K_cal+1)` to infinity; at most six calibration groups leave finite mass ≤6/7<0.9. That particular 90% construction is vacuous here, even before reserving groups for fitting. Nine calibration groups only permit a finite threshold; they do not guarantee useful intervals or valid sampling assumptions. This is method-specific, not an impossibility claim for all Bayesian intervals. [Primary hierarchical-conformal paper, §2.2, Eq. (6), Theorem 1](https://arxiv.org/pdf/2306.06342v1).

## Recommended milestone order

1. **Expose the current decision evidence and finish a thin bounded-agent development pilot.** Keep current frozen predictors and all strong baselines. Enforce the tool/label/budget contract before any LLM comparison. This advances a missing proposal deliverable without waiting for another model series.
2. **Run one structure-aware feasibility ablation and a separate uncertainty diagnostic.** Use consumed grouped data first; change only demonstrated weaknesses. Promotion requires a better verified feasible frontier, not a lower error number. Repair duration scope and outer-time accounting before time-efficiency claims.
3. **Freeze and test on genuinely fresh source/input evidence with explicit scope.** Keep all family/context exclusions and historical costs. Report development versus prospective results plainly and retain null findings.
4. **Jointly build and measure final compatible instructions.** Reuse the teammate implementation components, include baseline fallback, and complete the optimized software/hardware report. The final agent comparison still needs this connection.

No new production model, LLM advantage, formal calibration, arbitrary-program support or novelty is claimed by this analysis.
