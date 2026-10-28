# AI track: report inserts and presentation notes

Prepared at the owner's requested October 27 stopping point. These inserts describe the guarded ISAForge experiments. They must be labeled separately from the team's earlier RV32IM/Spike and ten-route hardware results. The supplied PDF and existing slide files have not been overwritten.

## Suggested Section 2.3 — Applying AI to Choose Candidates

We evaluate whether learned instruction selection can find better verified designs within a small hardware-evaluation budget. Each candidate is represented by features available before measuring its implementation: operation counts, expression depth, input and constant counts, execution frequency, occurrence locations, and projected instruction savings. Measured outcomes are kept separate from model inputs. The historical guarded corpus contains 122 successful whole-program speedup labels and four charged failed attempts across 14 workload groups and 15 build/input contexts.

We implemented XGBoost speedup regression and pairwise learning-to-rank, together with hardware-feasibility predictors and Gaussian-process acquisition policies. The pairwise challenger uses 80 depth-two boosted trees with learning rate 0.05 and the `rank:pairwise` objective. Training relevance is derived from measured speedup order within each workload/build/input context; its output is a ranking score, not a speedup estimate or confidence interval. Whole workloads are held out during evaluation, and related operation-tree families are excluded from the training fold. Repeated seeds are aggregated within workloads rather than counted as independent samples.

Selection methods receive the same budget of one, two, or three attempted evaluations. A design counts as an improvement only after passing correctness and the declared area and timing constraints: at most 64 added LUT4 cells and a 12 MHz timing floor in this guarded comparison. We report the best verified feasible cycle reduction, regret relative to a fully measured feasible-pool oracle where available, and evaluation count and time. Historical training measurements must be accounted for separately from target evaluation cost. The scorecard records target times and available host timing examples; isolated fit/inference timing for the exact pairwise policy still needs prospective measurement. Failed attempts consume the budget; incomplete pools do not provide complete oracles.

An LLM tool interface allows a selector to inspect candidates, query model predictions, request bounded measurements, and return a validated selection. This creates an agentic decision loop in which the language model can respond to revealed outcomes. It is distinct from the coding assistants used to develop and test the system. The current chat model has exercised this interface in a consumed-data replay and a separate three-measurement Ascon session. Dynamic routing between LLMs is not implemented. Adaptive model refitting and fixed Gaussian conditioning are separately named policies with different update semantics; their uncertainty remains empirically provisional.

## Suggested Section 3.3 — Analyzing the AI-Guided Selection

The current results do not establish ML superiority over the strongest heuristic. In the retrospective whole-workload-holdout screen, pairwise XGBoost has lower mean oracle regret than merit at budgets one and two, but the paired workload confidence intervals include zero. Merit performs better at budget three. Twelve workload groups have complete pool oracles; regret excludes the two censored groups. These workloads have informed development, so this comparison does not establish prospective generalization.

| Attempt budget | Merit regret | Pairwise XGBoost regret | Interpretation |
| --- | ---: | ---: | --- |
| 1 | 1.132% | 0.842% | Ranker point estimate better; paired interval includes zero |
| 2 | 0.465% | 0.439% | Small ranker advantage; paired interval includes zero |
| 3 | 0.015% | 0.070% | Merit point estimate better |

All 122 historical cycle-speedup labels equal independently calibrated PicoRV32 latency predictions. Thus the present evidence does not show a residual speedup relationship that requires ML. The remaining learned decision chiefly concerns hardware feasibility and ordering useful evaluations. Timing is not a tight boundary in this cohort: the minimum routed Fmax among selected feasible winners is 59.13 MHz, well above the 12 MHz floor. The results therefore test area-sensitive selection more strongly than timing-sensitive selection.

The consumed EDN chat-agent replay matched the measured-pool oracle after one valid request and one charged invalid request. Ordinary policies also reach that oracle at the same two-attempt budget. In the separate Ascon session, all three measured candidates passed correctness. The best measured feasible candidate achieved 1.023731x same-clock cycle speedup, added 42 LUT4 cells, and reached a minimum routed 64.620 MHz. Nine of twelve candidates remain unmeasured, there is no matched-policy comparison, and Ascon overlaps existing cryptographic families. A status-handling defect prevented adaptive GP updates during the live session; the corrected source passes regression checks, but its post-hoc replay does not establish live adaptation. Neither pilot demonstrates an LLM advantage.

The next research milestone is a frozen, equal-information and equal-budget comparison on untouched supported workloads, followed by jointly implementing and measuring the selected one-to-three-instruction set. Negative outcomes and qualification rejections remain part of the result.

## Seven-minute presentation allocation

| Time | Topic | Essential point |
| --- | --- | --- |
| 0:00–0:45 | Problem and research question | Hardware measurements are expensive; can learned selection find feasible improvements sooner? |
| 0:45–1:45 | Candidate extraction | Real workloads, dataflow legality, two inputs/one output, executable rewrites |
| 1:45–2:45 | Hardware evaluation | Correctness, whole-program cycles, integrated area, routed timing; distinguish hardware contexts |
| 2:45–3:45 | AI methodology | Boosted trees, workload holdouts, family exclusions, bounded agent tools |
| 3:45–5:00 | Matched-budget results | Show regret curves and uncertainty; ranker B1/B2 point estimates versus merit B3 |
| 5:00–5:45 | Agentic loop and limitations | Describe actual tool/measurement feedback; disclose incomplete oracle and paid-update defect |
| 5:45–6:30 | Timeline and contributions | Attribute roles using the team's confirmed matrix; distinguish coding AI from selector AI |
| 6:30–7:00 | Next milestone | Untouched-workload comparison and measured joint instruction set |

## Four-minute Q&A preparation

- **Why XGBoost rather than a neural network?** The data are small and tabular. Shallow boosted trees are a bounded challenger; we have not shown that additional model capacity improves selection.
- **Did ML win?** No overall advantage is established. Early-budget point estimates favor the ranker, intervals overlap zero, and merit is stronger at three attempts.
- **How did you use AI?** A learned ranker/predictor supports candidate evaluation, and an LLM exercised bounded selection tools. Separately, AI coding agents helped implement and test the research pipeline. We do not claim dynamic model routing or successful live GP adaptation in the Ascon run.
- **How is this explainable?** Show the input candidate formula and premeasurement features, the ranker's relative score, applicable area/timing constraints, and the logged query/outcome/selection sequence. Feature importance alone is not a causal explanation; rank scores are not probabilities.
- **What makes comparisons fair?** Same candidate pool, available information, evaluation budget, feasibility constraints, and charged failures; complete-oracle regret only where all candidate outcomes exist. Fresh confirmation remains unfinished.
- **Are these real hardware speedups?** Cycles come from modified-program RTL simulation; area and timing come from integrated FPGA synthesis/routing. Current cycle-speedup ratios assume a common operating clock. They are not physical-chip runtime measurements or automatic Fmax-adjusted speedups.
- **What remains incomplete?** An independent prospective cohort, calibrated uncertainty, a fair LLM-versus-non-agent comparison, and jointly verified final instruction combinations.

## Evidence to open before presenting

- [Selection scorecard and plot files](../../results/2026-10-27-final-selection-scorecard/README.md): primary ML-versus-merit figures and exact denominators.
- [Report alignment](../../docs/midterm-report-alignment.md): current report gaps and hardware-context differences.
- [Ascon paid-update semantics](../../docs/paid-update-semantics.md): actual agent measurements and the live-update limitation.
- [Ranker implementation](../../isaforge/ranking.py) and [feature definitions](../../isaforge/features.py): model architecture and permitted inputs.
- [Countnegative rejection](../../results/2026-10-27-countnegative-discovery-diagnosis/README.md): a preserved negative qualification, not a model result.

Before Canvas submission, insert the AI sections into the team's current report, fill the major/email placeholders, confirm contribution attribution, and rehearse to seven minutes. No Canvas submission has been made.
