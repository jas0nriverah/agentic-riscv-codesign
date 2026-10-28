# ISAForge — 11-slide, seven-minute script

Total scheduled time: 420 seconds. Sources and Q&A material are not part of the spoken script.

## 1. ISAForge (25 seconds)

ISAForge asks whether learned predictions and an AI selection agent can find better RISC-V custom instructions with fewer expensive evaluations. We optimize verified whole-program performance under hardware constraints. Our contribution is the connection from real programs to measured labels to budgeted selection. Today we have a working pipeline, measured data, and preliminary comparisons—not yet a consistent machine-learning win.

### Sources / Q&A

Scope: README.md; docs/research-foundation.md. Guarded AI-track results are separate from other hardware contexts in the team report.

## 2. Research foundations (30 seconds)

We build on established methods rather than inventing another enumerator. Atasu provides the dataflow and architectural constraints for legal instruction candidates. CIDRE emphasizes that benefits depend on the processor and its timing. AutoTVM motivates ranking alternatives using measured performance. Constrained Bayesian optimization motivates measuring promising candidates while accounting for feasibility. ISAForge tests this combination on whole-program PicoRV32 outcomes; we do not claim to reproduce these complete systems.

### Sources / Q&A

Atasu, Pozzi & Ienne. Automatic Application-Specific Instruction-Set Extensions Under Microarchitectural Constraints. DAC 2003, 256–261. DOI 10.1145/775832.775897; methods §§4–7.
Rezunov et al. Automatic Microarchitecture-Aware Custom Instruction Design for RISC-V Processors. ICCAD 2025. DOI 10.1109/ICCAD66269.2025.11240781; arxiv.org/html/2509.15782v2, §§II–IV.
Chen et al. Learning to Optimize Tensor Programs. NeurIPS 2018. arxiv.org/pdf/1805.08166v4, §§3–4, Algorithm 1.
Gardner et al. Bayesian Optimization with Inequality Constraints. ICML 2014, PMLR32(2):937–945. https://proceedings.mlr.press/v32/gardner14.pdf, §§3.1–3.2.
Repository method reviews: docs/research-foundation.md; docs/selection-methods-review.md.

## 3. Timeline and team contributions (20 seconds)

We started by collecting real benchmark traces and synthesizing isolated circuits for a hardware-cost model. Next we connected candidates to whole-program execution on PicoRV32, expanded the dataset, and tested selection policies. Two project chats record about forty-six hours of turn duration, including waits and interruptions, not training time. Team roles are provisional and need confirmation.

### Sources / Q&A

Dated results directories October19–27; git history; docs/original-project-proposal.txt; supplied AgenticRiscPredictor.pdf. Codex history snapshot: two project chats record 15.82 and 29.97 hours of ended turn duration, approximately 45.8 hours combined, including tool waits and interruptions. The earlier 15.82 hours includes 4.51 hours across two interrupted turns. 72 distinct directly spawned subagent threads; activity is not training time or a research outcome. See codex-history-and-baseline.md. Team must confirm roles and aliases; Git alone cannot measure contribution shares.

## 4. From workload to verified improvement (35 seconds)

We wrote scripts that compile and profile workloads, extract legal candidates, and lower them to custom instructions. The evaluator executes each modified program with Verilator and checks correctness; Yosys and nextpnr measure integrated area and timing. The unmodified CRC32 reference took 32.39 million simulated cycles. The best candidate took 30.82 million, a 1.051 times common-clock speedup. These are simulation and FPGA tool results, not physical-chip stopwatch measurements.

### Sources / Q&A

src/candidates.py extracts legal candidates; isaforge/workload_experiment.py orchestrates workload preparation and collection; isaforge/codesign.py implements ProcessorEvaluator; Verilator simulates, Yosys synthesizes, nextpnr routes. docs/codesign-loop.md; results/2026-10-19-codesign/independent-audit.json. Embench CRC32,170 benchmark repetitions; startup, independent checksum, warm-up and serial reporting excluded from counter window. Same RV32I PicoRV32, 8KiB RAM and 12MHz target. Baseline 32,387,382 cycles,1653 LUT4; index_offset 30,820,662 cycles,1684 LUT4 (+31), 1.050833x. Both correctness checked; same-clock speedup, not measured board runtime. Baseline synth/routing Fmax 68.49–77.16 MHz. Distinguish this unmodified reference from heuristic selection baselines.

## 5. Dataset: measured programs, not synthetic labels (40 seconds)

Our first hardware-cost study grew from 301 to 713 distinct synthesized formulas across benchmark collections. Those isolated LUT labels are separate from the current whole-program dataset: 122 candidate-program measurements across fourteen workload groups, plus four charged failures. The chart shows its three benchmark suites. We hold out entire workloads. Our thirteen-policy screen includes 2,925 replays of existing measurements, not new hardware runs.

### Sources / Q&A

Earlier area study: initial 301 formulas, later three collections 1,098 program/formula rows and 713 distinct formulas from 17 candidate-bearing programs; isolated LUT4 labels, not processor cycles. The frozen original-301 model evaluated 331 novel final formulas: structural linear 23.154 LUT4 MAE versus original XGBoost 87.595. Later all-713 deployment refit lacks a fresh independent test. See results/2026-10-13-prospective/README.md and docs/methodology-history.md. Current dataset: submissions/midterm-2026-10-28/dataset/; results/2026-10-27-final-selection-scorecard/scorecard.json. 15 build/input contexts;12 complete measured-pool oracles,2 censored. Embench39 labels/6 groups; BEEBS48/5; TACLeBench35/3. Original teammate hardware-branch data uses a distinct context and is not silently merged.

## 6. The ML model: shallow boosted-tree ranking (40 seconds)

Our main challenger is XGBoost pairwise ranking, not a neural network. Thirty-five premeasurement features describe each candidate. We use measured speedup to order pairs within a workload, then fit eighty shallow trees. The output is a relative ranking, not a speedup or confidence probability. We tried eight learned policies in the final screen and five controls. Separate experiments tested Gaussian-process active learning. We assess selection quality, not just prediction error.

### Sources / Q&A

isaforge/ranking.py: XGBRanker rank:pairwise;80 estimators,max_depth2,learning_rate0.05,min_child_weight1,reg_lambda1,subsample1,colsample_bytree1,hist,n_jobs1. isaforge/features.py:35 features. Relevance preserves ties within context. Measured target outcomes excluded from input features.

## 7. Explainability and uncertainty (40 seconds)

Tree contributions show what drives the ranking: estimated instruction savings alone accounts for about forty-seven percent of normalized attribution. This describes the model’s behavior; it is not a causal explanation. A useful failure case is bitcount’s top-ranked candidate: it passes correctness and speeds up execution, but adds sixty-five LUT4 cells, exceeding the cap by one. Uncertainty should help us choose what to measure next. Ensemble disagreement and Gaussian-process estimates are available, but they are not yet calibrated confidence, and the ranker itself does not provide a confidence interval.

### Sources / Q&A

results/2026-10-27-ranker-explainability/explanation.json; global_feature_contributions.csv. Normalized absolute additive tree contributions macro-averaged over14 held-out workloads; profile opportunity features account for66.39%. Local add(in0,andi(in1,15)) rank1/12;1.008782x,+65LUT4,61.82MHz. Uncertainty calibration remains unproved.

## 8. The LLM agent: choose, measure, respond (45 seconds)

The LLM selector uses controlled tools to inspect candidates, query predictions, request a bounded measurement, and return a validated selection. Paid outcomes feed its next decision, and failed requests consume budget. This is an actual agentic loop, separate from the coding assistants used for implementation, debugging, and analysis. The Ascon pilot measured three correct candidates; the best feasible one achieved about 1.024 times cycle speedup. But nine candidates remain unmeasured and there are no matched controls. A status-handling bug prevented live GP updates; the fix was verified afterward. We also have not implemented dynamic routing between language models.

### Sources / Q&A

Agent protocol and logs: results/2026-10-27-codex-chat-agent-edn-b64-s0/; Ascon results and docs/HANDOFF.md. EDN consumed replay:2 charged attempts including1 invalid ID, matched oracle and ordinary policies. Ascon C01:1.019698x,+73LUT4,62.992MHz; C06:1.017027x,+41LUT4,67.069MHz; C02:1.023731x,+42LUT4,64.620MHz.3/12 measured; correctness passed for all3. No claim of agent superiority or successful live GP refitting.

## 9. Baselines and a fair measurement budget (35 seconds)

The unmodified program gives the performance reference. A different kind of baseline is a selection policy: frequency counts occurrences, while merit estimates operations eliminated times executions. We compare these with latency-aware heuristics, random search, and learned policies. Every method gets the same pool and one, two, or three charged attempts; unqueried results remain hidden. The measured oracle knows all outcomes and gives a retrospective ceiling, not a deployable policy. Historical training cost is tracked separately.

### Sources / Q&A

Protocol: docs/research-foundation.md; scorecard.json. Simple merit uses projected instruction savings; do not label it a CIDRE reproduction. Primary endpoint best verified feasible cycle reduction; regret only for complete pools. Track target evaluations and elapsed time, historical training cost, fit/inference and agent costs separately. Exact isolated ranker fit/inference timing remains incomplete.

## 10. Results: early gains, no consistent ML win (75 seconds)

Here is the main selection result. The vertical axis is mean cycle-reduction regret relative to the best measured feasible candidate in each complete pool; lower is better. At one attempt, merit has 1.132 percent regret and the ranker has 0.842 percent. At two attempts they are almost tied. At three attempts, merit is better. The paired workload confidence intervals include zero for the early-budget advantages, so we cannot claim consistent superiority. Twelve workload groups have complete pool oracles; two incomplete groups are excluded from this regret calculation. The 2,925 policy-budget replays are dependent analyses of the existing measurements, not new hardware experiments. There is also an important diagnosis: all 122 historical cycle-speedup labels match the independently calibrated processor-latency calculation. This dataset therefore does not demonstrate a residual speedup relationship requiring machine learning. Our remaining challenge is learning which useful designs will be hardware-feasible and worth measuring. A previous three-source blind campaign favored both GP policies over merit at three attempts, but a later bitcount test favored the latency-cost heuristic. Those mixed results do not establish a general advantage. The Ascon pilot has no matched controls.

### Sources / Q&A

results/2026-10-27-final-selection-scorecard/scorecard.json. Paired difference = merit regret minus ranker regret (percentage points): B1 +0.290 [−0.065,+0.849]; B2 +0.027 [−0.097,+0.177]; B3 −0.056 [−0.167,0.000]. Workload bootstrap;12 complete pools.14-group cycle-reduction means merit1.086/1.657/2.043%;ranker1.334/1.680/1.996%. Earlier frozen three-source campaign: GP 1.602185% mean cycle reduction vs merit 1.144539% at B3; only three sources and cooperative replay, no total-cost win established. Later bitcount B3 latency-cost heuristic found 0.174118% improvement while both GP policies returned baseline. docs/blind-source-campaign.md; results/2026-10-22-bitcount-report/results.md. Timing floor weakly tested:minimum selected feasible Fmax59.13MHz vs12MHz. Target mean eval time merit55.67/114.24/169.76s;ranker56.29/115.69/171.46s. No total-cost advantage established.

## 11. Next milestone: an independent selection test (35 seconds)

We now have an end-to-end research system: real workloads, executable custom instructions, measured outcomes, learned ranking, and bounded agent tools. The next step is to freeze the policies before observing new workload results, then compare the agent and non-agent methods under identical budgets. We need better workload diversity and validated uncertainty before adding model complexity. Finally, we must implement and measure the selected one-to-three-instruction combination together. Individual speedups cannot be added. A reproducible heuristic win is still a useful scientific result.

### Sources / Q&A

docs/HANDOFF.md; docs/ACTIVE_GOAL.md. Research paused at presentation checkpoint; no new collection implied by this deck. Next experiments require frozen controllers/policies, legal lowering and blind measurement contracts. Keep the original CRC32 and aha-mont64 experiments and all negative outcomes. No RTL-rewriting optimization agent.
