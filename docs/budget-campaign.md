# Prospective multi-workload, equal-budget comparison

This experiment expands actual processor measurements and tests whether learned selection improves the best verified feasible speedup under the same budget. It preserves the earlier negative SLRE result. No model parameters are selected using the new target outcomes.

## Predeclared experiment

The primary endpoint is best verified feasible speedup after **three candidate measurements**, at **12 MHz** with at most **64 additional LUT4**. Secondary controls use +32 and +128 LUT4 and budgets one and two. Five seeds repeat model bootstraps and tie orders; the independent unit is the workload, not the seed. Each six-candidate pool is uniformly spaced over merit ranks among automatically extracted, executable, calibrated formulas. The unmodified baseline is always available. The planned complete pool oracle is qualified after collection: UD has one infrastructure-censored outcome, so its reported reference is only the best verified completed design.

## Completed result — October 21

**No learned policy beats the strongest heuristics at the primary endpoint.** All five learned policies tie calibrated latency on both workloads. This is a prospective negative result, not a model promotion. The [raw archive and derived tables](../results/2026-10-20-budget-campaign/README.md) reproduce all 900 policy/constraint/budget/seed endpoints without native evaluation.

| Workload | Baseline cycles | Best verified candidate | Optimized cycles | Speedup | Added LUT4 | Primary outcome |
| --- | ---: | --- | ---: | ---: | ---: | --- |
| EDN | 386,561,849 | candidate 00 | 386,394,809 | 1.000432304× | 32 | Merit, latency and all learned policies find this design on query one. |
| UD | 37,845,951 | candidate 00 | 37,690,761 | 1.004117455× | 70 | Exceeds primary +64 cap; all policies retain baseline. Feasible at predeclared +128 cap. |

At +128 LUT4 and three queries, original regression finds only 1.002584162× on UD; normalized XGBoost, ranking, both hybrid policies and the strongest heuristics find 1.004117455×. Normalization therefore fixes an observed regression error but does not establish an advantage over merit. At +64, the separate latency-plus-cost heuristic misses EDN's best feasible design, showing why the strongest comparator matters. Random search is worse on EDN on average.

Five EDN and four UD candidates pass upstream correctness, execution counts, stock/custom processor controls, integrated synthesis and all three routes. EDN 17 fails a recorded memory-write contract; UD 08 fails its upstream self-check. UD 10 stops during firmware preparation because the runner observes less than 2 GiB free disk space, before simulation or hardware results. It remains **unknown**, not incorrect or proven infeasible. All three failures consume one query and their elapsed time; none was retried. Thus 12 new attempts yield nine verified labels, bringing automatic totals to **27 labels, 30 attempts, 32 fully measured designs, 96 routes, five workloads**.

The frozen scorer's original `oracle`/`regret` names are preserved for exact replay. The derived report uses **best verified pool reference** and **gap to that reference**. For UD the reference is a lower bound on the full-pool optimum; its gap is a lower bound on full-pool regret. At +64 UD's five-of-five reference hits merely indicate baseline retention and are not discoveries. Results do not establish whether its unmeasured candidate is feasible.

Mean speedup MAE over the five dependent seeds falls from 0.005276072 to 0.000082889 on EDN (**98.43%**) and from 0.003629536 to 0.000326825 on UD (**91.00%**). These are secondary diagnostics over five and four verified candidates, excluding failures. Normalized nominal 90% interval coverage is only 36% and 65%, respectively; UD coverage declines from the original model's 70%. All nine new measured cycle reductions exactly equal calibrated latency estimates, extending that exact match to all 27 successful automatic labels. No cycle residual model is justified by these results.

New target attempts cost **904.226627 candidate wall-seconds**, including **50.196657 seconds** in failed attempts. Adding the nonoverlapping historical candidate costs gives **1,698.152954 candidate wall-seconds** for the 30 automatic attempts. Baseline, setup, calibration, inference and failed qualification scopes are disclosed separately, so this is not total project compute time. Seven failed qualification contexts use 64.979547 native command-seconds; three linker diagnostics add 0.768713 command-seconds. Faster failed attempts can lower a policy's charged time without improving its selected design.

## Demonstrated lowering fix and next experiment

EDN 17 removes original `%hi(a)`/`%lo(a)` source references and hardcodes the linked address. Linker garbage collection then drops the 400-byte array while the modified program still writes to its old address. Formula-level integer checks cannot catch this source/linker semantic error. The new `relocation_guard` rejects symbolic relocation and unsupported operand syntax from original marked assembly before future shortlisting. Its tests include the actual preserved EDN failure. Existing pools and successful labels remain unchanged; a conservative source-risk flag alone does not invalidate a recorded successful run.

The source-only diagnostic flags one frozen SLRE formula, one EDN formula and two UD formulas; CRC32 and aha pools have none. The guarded complete executable lists retain 14 EDN formulas and eight UD formulas before the existing calibration filter. The next integration is to wrap the current extractor with this guard **before** the existing stratifier, bind its source in a fresh plan and test on a new independent workload/input pool. No new enumeration algorithm is needed. These consumed targets may train future hardware-feasibility acquisition, but cannot be reused as untouched test data. Further model tuning should be driven by verified feasible-design decisions, not a target MAE headline.

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

The complete prelabel checkpoint was pushed at [`993d5d95ad7edb2539782f49151419f479836969`](https://github.com/jas0nriverah/agentic-riscv-codesign/commit/993d5d95ad7edb2539782f49151419f479836969). Its [preregistration](../results/2026-10-20-budget-preregistration/README.md) binds every prediction, both accepted baselines, seven qualification failures and three static linker diagnostics. Each target fits 15 of the 18 historical candidates after excluding three related families. EDN's six candidates cover ranks 0, 3, 6, 9, 12 and 15 of 16 eligible formulas; UD covers ranks 0, 2, 4, 6, 8 and 10 of 11. Full-run observed stack use is 1,040 bytes for EDN and 592 bytes for UD, leaving 368 and 304 bytes of stack headroom respectively.

All policy curves charge the same released raw observations. Historical training has **18 labels and 793.926327 candidate wall-seconds**, with setup and baseline work reported separately. That number excludes older failed qualification contexts and is not a complete project cost. New qualification failures and static linker diagnostics are also retained and charged separately. Command-time totals overlap evaluation wall-time totals and must not be added. Replay launches no native hardware jobs; it refits the frozen predictions and authenticates the raw evidence before scoring.

Whole-workload transfer, compiler/partition shifts, source-family exclusions, candidate-pool coverage, prediction errors, uncertainty coverage, feasible-oracle hits and actual selection time all remain visible. Single-candidate speedups do not establish the performance of a combined instruction set. The LLM selection agent and joint one-to-three-instruction validation remain subsequent milestones.

## Working commands

Use Python 3.12 and `requirements-speedup.txt`. Reproduce the completed campaign without native tools with:

```sh
make reproduce-budget-campaign PYTHON=python
make campaign-report PYTHON=python
# Open generated/reproduction/budget-campaign-report/results.md or selection.png.
```

The actual collection used these roots, with preparation and baseline qualification completed before the prelabel commit:

```sh
python -m isaforge.extended_workload prepare \
  --reference-root generated/codesign-crc32-2026-10-19-r1 \
  --root generated/extended-edn-2026-10-20 --workload edn
python -m isaforge.extended_workload discover --root generated/extended-edn-2026-10-20
python -m isaforge.extended_workload baseline --root generated/extended-edn-2026-10-20
python -m isaforge.qualified_workload prepare \
  --reference-root generated/codesign-crc32-2026-10-19-r1 \
  --root generated/qualified-ud-2026-10-20 --workload ud
python -m isaforge.qualified_workload discover --root generated/qualified-ud-2026-10-20
python -m isaforge.qualified_workload baseline --root generated/qualified-ud-2026-10-20
python -m isaforge.campaign_evidence freeze \
  --root generated/budget-selection-2026-10-20 \
  --target-root generated/extended-edn-2026-10-20 \
  --target-root generated/qualified-ud-2026-10-20
# The complete cohort and sources were committed and pushed here.
python -m isaforge.extended_workload collect --root generated/extended-edn-2026-10-20
python -m isaforge.qualified_workload collect --root generated/qualified-ud-2026-10-20
python -m isaforge.campaign_evidence evaluate \
  --root generated/budget-selection-2026-10-20 \
  --target-root generated/extended-edn-2026-10-20 \
  --target-root generated/qualified-ud-2026-10-20
```

The EDN collection stopped on its last candidate's guard failure. UD collection stopped at candidate 08's self-check failure; the remaining candidate 10 received its first and only attempt with `qualified_workload.Evaluator(root).measure('candidate_10')`, with the evaluator's runner lock closed in `finally`. There was no retry, amended pool or postlabel model change. The campaign evidence wrapper validates successful and failed attempts even when the legacy complete-pool report is absent.

Use fresh roots for recollection. The pinned reference toolchain and benchmark sources must be available for native jobs; archive replay does not require them. Historical and new contexts remain distinct. The existing SQLite demo retains its frozen three-workload snapshot; the [consumed-corpus export](../results/2026-10-21-expanded-corpus/README.md) supplies consistent expanded rows for subsequent experiments. The tested relocation guard is not yet wired into the frozen collection entrypoints; invoking those historical commands does not apply the new filter.
