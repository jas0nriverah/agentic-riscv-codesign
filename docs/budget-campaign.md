# Prospective multi-workload, equal-budget comparison

This experiment expands actual processor measurements and tests whether learned selection improves the best verified feasible speedup under the same budget. It preserves the earlier negative SLRE result. No model parameters are selected using the new target outcomes.

## Predeclared experiment

The primary endpoint is best verified feasible speedup after **three candidate measurements**, at **12 MHz** with at most **64 additional LUT4**. Secondary controls use +32 and +128 LUT4 and budgets one and two. Five seeds repeat model bootstraps and tie orders; the independent unit is the workload, not the seed. Each six-candidate pool is uniformly spaced over merit ranks among automatically extracted, executable, calibrated formulas. The measured oracle covers only that pool, with the unmodified baseline always available.

All target pools and baseline measurements are authenticated together before model predictions are committed. The same 18 earlier automatic CRC32, aha-mont64 and SLRE outcomes are available to every policy. Exact/related operation-tree families are excluded from fitting for each target. No outcome from another new target enters training or adaptation. Only paid observations from the current target update an adaptive policy. Failures consume an evaluation and their actual elapsed time; they cannot supply a feasible implementation.

The seven qualification failures remain evidence: three programs exceeded the original 4,224-byte program partition; UD and SHA256 also exceeded 6,400 bytes; EDN fit but reached the simulator's 200-million-cycle cap. Exact-flag linker maps identified UD at 7,072 bytes, SHA256 at 7,472, and statemate at 6,420. The prelabel amendments qualify EDN with a 6,656-byte program limit and 1,408-byte stack. Statemate runs in this partition but yields only one eligible formula, so it fails the declared six-candidate pool requirement. UD is qualified separately with a 7,168-byte program limit and 896-byte stack. Both target contexts retain a 128-byte declared guard and an 800-million-cycle simulator ceiling. The compiler remains `-Os`/RV32I and the synthesized 8 KiB RAM/core/PCPI are unchanged. Every stack pointer and RAM write is observed, with deliberate guard violations and an unobserved baseline control. These establish bounds only for recorded inputs. UD retains its original software double helpers; its executed ISA remains RV32I. The extractor targets marked benchmark assembly and does not lower the linked software arithmetic helpers.

## Fixed policies and the demonstrated model problem

| Policy | Selection rule |
| --- | --- |
| Frequency | Descending observed baseline replacement count. |
| Merit | Descending removed instruction count. |
| Calibrated latency | Whole-program speedup reconstructed from independently measured instruction/PCPI latency and the baseline execution profile. |
| Latency plus cost heuristic | Historical median added LUT4 per operation, historical minimum routed Fmax, then analytic improvement per predicted LUT4. |
| Random | Seeded shuffled pool. |
| Original regression | Existing twenty-member bootstrap XGBoost predicting raw whole-program speedup. |
| Original ranking | Existing fixed grouped pairwise XGBoost ranking objective. |
| Normalized XGBoost | Predict measured saved cycles per candidate execution, then reconstruct whole-program speedup using the target's baseline cycles and exact execution count. |
| Hybrid GP, zero shot | Analytic speedup improvement × predicted feasibility × expected inverse measurement duration; hardware predictions use historical data only. |
| Hybrid GP, paid adaptation | The same rule, refitting hardware surrogates after successful paid target measurements. |

SLRE demonstrated a transfer failure: the original learned models ranked its optimum fifth. The normalized model addresses benefit scale directly, using structural features and signed measured cycle-savings labels. It retains the existing fixed twenty bootstraps, eighty trees, depth two and learning rate 0.05. The count comes from baseline timed-region occurrences, not from a measured custom implementation or startup/warmup execution. Negative savings remain negative. A one-cycle floor protects reconstruction numerically and any use is disclosed. This is one target transformation motivated by an observed failure, not a model-version search.

The hardware surrogate is justified by a separate development observation: at +64 LUT4, three historical aha candidates, three CRC candidates and two SLRE candidates are infeasible. The fastest unconstrained SLRE candidate costs +77 LUT4. Feasible design selection therefore requires cost information; area-prediction error is still only a secondary diagnostic.

Independent fixed Matérn-3/2 Gaussian processes predict integrated added LUT4, minimum routed Fmax and log measurement duration. Inputs and outputs are standardized, the kernel length scale is one, numerical noise is 1e-4 and there is no optimizer. Output scaling floors are 8 LUT4, 1 MHz and 0.25 log-seconds. These floors are not calibrated error bars. The acquisition uses positive improvement from the **calibrated analytic objective**, Gaussian area/timing probabilities, a shared smoothed device-fit rate and `exp(-mu_log_time + variance_log_time/2)`. Only hardware-infeasible successes have usable hardware labels; failed attempts remain charged without fabricated labels.

This adapts the independent feasibility factor in Gardner et al., *Bayesian Optimization with Inequality Constraints*, ICML 2014, §§3.1–3.2 ([primary paper](https://proceedings.mlr.press/v32/gardner14.pdf)), and expected inverse duration from Snoek et al., *Practical Bayesian Optimization of Machine Learning Algorithms*, NeurIPS 2012, §3.2 ([author version 2](https://arxiv.org/pdf/1206.2944v2)). It is **not** a reproduction of constrained expected improvement: the objective here is an analytic finite-pool anchor. Cost, timing and duration independence is approximate. Bootstrap spread and GP probabilities are evaluated descriptively, never presented as calibrated confidence.

## Evidence and costs

Each accepted candidate requires automatic lowering checks, independent integer/block checks, exact execution counts, the upstream benchmark self-check, stock firmware on the extended processor, rejection of custom firmware on the unextended processor, integrated synthesis and three routing seeds. Results are RTL simulation and FPGA synthesis/routing estimates, not board measurements.

All policy curves charge the same released raw observations. Historical training has **18 labels and 793.926327 candidate wall-seconds**, with setup and baseline work reported separately. That number excludes older failed qualification contexts and is not a complete project cost. New qualification failures and static linker diagnostics are also retained and charged separately. Command-time totals overlap evaluation wall-time totals and must not be added. Replay launches no native hardware jobs; it refits the frozen predictions and authenticates the raw evidence before scoring.

Whole-workload transfer, compiler/partition shifts, source-family exclusions, candidate-pool coverage, prediction errors, uncertainty coverage, feasible-oracle hits and actual selection time all remain visible. Single-candidate speedups do not establish the performance of a combined instruction set. The LLM selection agent and joint one-to-three-instruction validation remain subsequent milestones.
