# Speedup-model analysis — October 20, 2026

> Historical checkpoint: the subsequent [prospective SLRE experiment](prospective-slre.md) completes the third-workload milestone and tests the fixed models. Preserve these original findings; use the current README and handoff for next work.

The current models are limited most by missing execution information and a very small, biased training corpus. Increasing tree count or trying another model family would not resolve either problem. A separately measured processor-latency baseline now explains **all twelve existing automatic candidates' cycle reductions exactly**, without fitting application speedup labels. It matches simple merit's one-measurement selection result. This is evidence for a stronger baseline and better model inputs; it is not evidence of improved ML generalization.

The original CRC32, automatic aha-mont64, automatic CRC32, and fixed ranking experiments remain unchanged. Three GPT-6.1-Sol subagents independently reviewed the ML diagnosis, calibration/evaluation code, and primary research. Their reviews identified integration and evidence-validation issues that were corrected before the new comparison. No model hyperparameter search or new XGBoost variant was conducted.

## What is actually learned

| Component | Target and training | Current limitation |
| --- | --- | --- |
| `SpeedupPredictor` | Twenty row-bootstrap XGBoost regressors, each 80 trees of depth two, predicting measured baseline cycles / modified-program cycles. Uses 35 structural/profile features. | Each transfer direction has five fitting candidates from one source workload after related-pattern exclusion. |
| `SpeedupRanker` | Fixed XGBoost pairwise ranking, with query groups defined by workload/build/input context. Relevance preserves measured speedup order and ties. | Five fitting candidates provide only eight or ten unequal pairs. Rank scores are not speedup or uncertainty estimates. |
| Historical area models | Isolated combinational LUT4 cost, on their separately preserved corpora. | They do not predict whole-program speedup or integrated processor feasibility and are not substitutes for the two models above. |

The application labels are RTL-simulated whole-benchmark cycles with verified outputs, plus integrated FPGA synthesis/routing. They are not instruction-count proxies or physical-board measurements. The legacy `measurement_source` string is accompanied by the more specific corpus `label_kind` and `measurement_detail`; use those fields when describing the evidence.

## Diagnosed failure mechanisms

**Training support is inadequate.** Twelve automatic candidates cover two workload groups. Eighteen of the 35 feature columns are constant. Among the varying columns, `size` equals `tree_op_count`, and `constant_count` equals `unique_constant_count` in this corpus. There are no exact duplicate full feature vectors, but this does not make the examples independent.

When predicting aha-mont64, every fitting CRC candidate has `runs=174080` and `places=1`. Every aha target has a different execution count and six to eleven locations. The model cannot learn an execution-frequency effect from that training set. Aha also introduces `or`, absent from its fitting data. In the reverse direction, CRC introduces `xor` and `andi`, and all target location counts lie below source support. Range checks are diagnostic flags, not calibrated probabilities of failure.

**Trees collapse important distinctions.** Across all five model seeds, CRC-trained regression produces only two distinct predictions for six aha candidates. Its splits use size, maximum constant, input count, and constant count; they never learn frequency or normalized execution exposure. For seed zero, the following four candidates receive the same 1.025363× prediction:

| Aha formula | Measured cycles saved per execution | Measured speedup |
| --- | ---: | ---: |
| `add(srli(in0,31),in1)` | 13 | 1.066244× |
| `add(in0,slli(in1,1))` | 4 | 1.017686× |
| `or(in0,slli(in1,1))` | 4 | 1.010537× |
| `or(srli(in0,31),in1)` | 13 | 1.035077× |

The existing features count shift operations, but do not encode the processor's shift steps. `max_abs_constant` also conflates masks such as 255 with shift amounts. `saved_percent` divides instruction savings by instruction count; it does not express saved processor cycles. Feature scaling alone cannot recover information missing from the representation or variation missing from training.

**The uncertainty intervals omit workload shift.** A bootstrap of five rows contains an expected 3.3616 distinct examples, and omits any particular example with probability 32.768%. Twenty resamples do not create twenty independent training workloads. Three aha labels lie outside the fitting speedup range, including its best candidate. The central 90% ensemble range has the following empirical coverage:

| Held-out development workload | Regression MAE, speedup ratio | Regression pair accuracy | Ranking pair accuracy | Ensemble coverage | Latency-baseline MAE |
| --- | ---: | ---: | ---: | ---: | ---: |
| aha-mont64 | 0.020262 | 70.00% | 70.00% | 26.67% | 0 |
| CRC32 | 0.006458 | 77.27% | 72.73% | 83.33% | 0 |

Learned diagnostics are means over the five fixed seeds, each evaluated on six candidates. These are two dependent development case studies, not thirty independent test programs. Prediction ties receive half credit in pair accuracy. The intervals describe model disagreement; neither their name nor their width establishes prediction coverage.

**The current task has little room to show a selection advantage.** Both pools were shortlisted by instruction-saving merit. All twelve candidates speed up their programs and satisfy +128 LUT4 and 12 MHz limits. Simple merit already reaches both pool optima with one query in every seed. A method cannot use fewer than one verified candidate measurement to match that result. The experiment does not test discovering candidates excluded by merit, rejecting slowdowns, or learning a tight feasibility boundary. The original hand-adapter CRC slowdown remains preserved; it must not be relabeled or merged as if it had the same lowering as the automatic result.

## Implemented improvement: execution-aware features and a strong baseline

The independent [processor calibration](../results/2026-10-20-latency-calibration/README.md) executes 222 fixed instruction/input cases, checks their values, and verifies that an unextended processor traps at the custom opcode. It measures launch-to-launch instruction spans using the existing pinned core and synchronous RAM. All cases support:

```text
ordinary integer ALU cost = 4 cycles
immediate shift cost(s)   = 4 + floor(s / 4) + (s mod 4) cycles
one-wait PCPI cost        = 5 cycles
```

The calibration used eight serial native commands, 5.095776 command-seconds, two RTL simulator runs, and zero synthesis runs. It collected no new application candidate labels. The generic PicoRV32 documentation is not a substitute for this measurement: memory-interface and shifter settings affect observed costs. [Pinned processor documentation](https://raw.githubusercontent.com/YosysHQ/picorv32/ef203c2b0a3fb793280f5114941416c425c5b461/README.md).

For each legally lowered occurrence, the new estimator sums the costs of its distinct original instructions, subtracts the PCPI cost, and weights the difference by its baseline execution count. It then divides by measured baseline cycles to form a normalized benefit and converts that to a speedup estimate. This follows the established software-minus-hardware latency merit described in CIDRE §II-D; it does not reproduce CIDRE's complete selection or microarchitecture framework. [CIDRE methods](https://arxiv.org/html/2509.15782v2#S2.SS4).

[The implementation](../isaforge/latency_features.py) exports baseline cycles/instructions/CPI, normalized replacement frequency, actual occurrence sizes, dynamic software/PCPI/shift costs, and estimated cycle reduction/speedup. It counts actual DAG instructions rather than repeated expression-tree nodes, rejects overlapping occurrences and impossible dynamic counts, and rejects uncalibrated operations such as variable shifts. These features are available for the next fixed ML experiment; they have **not** been added silently to the historical 35-feature models.

| Automatic pool | Candidate | Measured cycles saved | Calibrated estimate | Measured speedup |
| --- | --- | ---: | ---: | ---: |
| aha-mont64 | 00 | 5,360,256 | 5,360,256 | 1.094120× |
| aha-mont64 | 01 | 2,923,776 | 2,923,776 | 1.049232× |
| aha-mont64 | 02 | 3,871,296 | 3,871,296 | 1.066244× |
| aha-mont64 | 03 | 1,082,880 | 1,082,880 | 1.017686× |
| aha-mont64 | 04 | 649,728 | 649,728 | 1.010537× |
| aha-mont64 | 05 | 2,111,616 | 2,111,616 | 1.035077× |
| CRC32 | 00 | 1,566,720 | 1,566,720 | 1.050833× |
| CRC32 | 01 | 1,566,720 | 1,566,720 | 1.050833× |
| CRC32 | 02 | 870,400 | 870,400 | 1.027617× |
| CRC32 | 03 | 522,240 | 522,240 | 1.016389× |
| CRC32 | 04 | 870,400 | 870,400 | 1.027617× |
| CRC32 | 05 | 870,400 | 870,400 | 1.027617× |

The latency policy adds 60 budget/seed outcomes to the existing 420: two pools × five seeds × six budget prefixes. At budget one, calibrated latency and simple merit find the oracle in **5/5 seeds on both workloads**. Existing regression/ranking each achieve 3/5 on aha and 5/5 on CRC. At budget three, all learned policies reach both optima; random remains worse. Thus the new feature information fixes explanatory and ranking deficiencies of the current predictions, while **selection improvement over simple merit and learned-model improvement remain unestablished**.

Exact agreement is limited to these consumed programs, fixed inputs, lowering, memory system and PCPI protocol. The analytic structure was investigated after observing their results; the independent microbenchmark prevents fitting its latency constants to application labels, but does not turn this comparison into an untouched test. Relocation, changed instruction context, variable shifts and different interfaces can invalidate the additive operation-cost assumption. Adding estimates across different candidate instruction sets remains prohibited. Final correctness, whole-program cycles, area and timing must still be measured.

This comparison adds an architectural baseline; it is not a matched feature ablation of XGBoost. The existing learned predictions remain frozen. The next prospective ablation must make the new public features and calibration evidence available equally to the compared policies.

## Improvements worth testing next

1. **Collect independent, less selectively sampled outcomes.** First unblock the third workload through the checked memory/runtime work in the [handoff](HANDOFF.md). Freeze a manageable legal pool spanning sizes, frequencies and operation families before measuring candidate outcomes; include lower-merit patterns. Expanding the remaining CRC/aha candidates improves within-workload coverage but does not create new workload groups. Then grow to several independent programs and source families, with separate development and final held-out workloads.
2. **Run one fixed feature ablation.** Keep the current regression/ranking settings as controls. Compare adding the new execution-aware inputs with the independent analytic baseline, frequency, merit and random. Freeze predictions before target labels; report budgets one through three first, then adaptation. Adding features does not itself give trees reliable extrapolation beyond their training support.
3. **Learn residuals only when they exist.** A candidate target is normalized measured cycle savings minus normalized analytic savings. Predicting a correction to a physical baseline could transfer better than raw speedup, but that is a hypothesis. Current twelve residuals are exactly zero, so fitting a residual learner now has no demonstrated purpose. Require repeatable, feature-dependent analytic errors on independent development workloads and better held-out selection regret before promoting it.
4. **Evaluate uncertainty at the workload level.** Keep support diagnostics visible. Once there are enough independent groups, evaluate empirical interval coverage, width, and misses of the best candidate on untouched workloads. Do not apply a conformal guarantee merely because a residual quantile can be computed. Compare a fixed uncertainty/diversity acquisition rule against mean-only selection, random and calibrated merit under identical paid adaptation budgets.
5. **Test real hardware constraints.** Current all-feasible pools cannot validate feasibility prediction. Predeclare realistic area/timing limits in future experiments and report Pareto tradeoffs. For example, CRC candidates 00 and 01 have equal speedup but add 69 and 31 LUT4 respectively. That difference matters under tighter limits; it is not grounds for another isolated LUT study. Integrated cost prediction earns priority when it improves actual constrained selection.

Keep XGBoost until this evidence shows a reason to change it. No GNN, RTL-rewriting agent, or unrelated model architecture is indicated. The eventual LLM selection agent should use the same bounded information and evaluation tools, after the non-agent comparison and isolation are sound.

## Additional primary research and precise implications

- **Venkataraman, Yang, Franklin, Recht and Stoica. “Ernest: Efficient Performance Prediction for Large-Scale Advanced Analytics.” NSDI 2016, pp. 363–378.** §§3.1–3.4 construct a small mechanistic basis, select measurements with cost-constrained experiment design, and diagnose model inadequacy. This supports interpretable latency/profile features and explicit mismatch checks. Job-specific coefficients and its experiment-design objective do not establish zero-shot instruction-selection performance or make a diversity heuristic an Ernest reproduction. [Primary proceedings PDF](https://www.usenix.org/system/files/conference/nsdi16/nsdi16-paper-venkataraman.pdf).
- **Renda, Chen, Mendis and Carbin. “DiffTune: Optimizing CPU Simulator Parameters with Learned Differentiable Surrogates.” MICRO 2020.** §I and §VI of the linked 14-page author manuscript distinguish measured instruction behavior from simulator parameters; fitted parameters can compensate for model omissions without retaining physical meaning. This supports independently checked calibration plus whole-program validation. Its x86 simulator/surrogate method is not being implemented, and its scale does not justify fitting a residual model from five rows. [Primary author manuscript](https://adapt.cs.illinois.edu/papers/difftune.pdf), [author-submitted bibliographic record](https://arxiv.org/abs/2010.04017).
- **Barber, Candès, Ramdas and Tibshirani. “Conformal Prediction Beyond Exchangeability.” Annals of Statistics 51(2), 816–845, 2023, DOI 10.1214/23-AOS2276.** §§3–5, especially §5.3, of the linked 62-page author manuscript bound coverage loss using distribution discrepancies and weighting. Under substantial workload shift those bounds can be uninformative; downweighting data also reduces effective calibration size. We therefore retain empirical coverage diagnostics rather than asserting calibrated uncertainty from feature similarity or bootstrap spread. [Primary author manuscript, including supplement](https://www.stat.cmu.edu/~ryantibs/papers/nexcp.pdf). These section numbers refer to that manuscript, not the publisher's differently paginated version.

The [earlier primary-method review](selection-methods-review.md) already covers AutoTVM's measured ranking, SMAC, RGPE, Ithemal and covariate-shift conformal prediction. None establishes that our present models outperform merit. The exact Sun 2004 and Hussein 2026 methods remain unresolved access gaps.

## Evaluation and integration issues to retain

- Report historical candidate-label cost, baseline/discovery setup, native command time, candidate wall time and inference separately. The old pilot's `total_*` fields include candidate measurements and inference but exclude separately recorded baseline/discovery setup. They are not complete project costs. Heuristics do not intrinsically require historical training labels; the new latency baseline has its separate one-time 5.095776-second calibration cost. Do not sum overlapping timers.
- The current automatic corpus binds compiler flags in each experiment plan, but its processor identity omits the complete flag list. A future `-Os` or memory-partition context must have explicit compatibility handling before pooling it with `-O2`; a shared compiler binary is insufficient.
- Whole-workload and operation-tree exclusions are useful but not universal semantic independence checks. Related source programs, alternative encodings and shared subgraphs still need explicit scrutiny.
- The frozen primary `TransferTools` is constructed with complete target rows even though its public listing filters fields. Current cooperative policies do not exploit that access, but it must not be exposed to an LLM. The new latency replay sanitizes its public rows; external-agent execution still needs an isolated measurement boundary.

## Reproduce and inspect

With the pinned Python 3.12 environment and [requirements](../requirements-speedup.txt):

```sh
make reproduce-model-analysis
make test
make reproduce
make reproduce-speedup
make reproduce-selection-research
```

The first command authenticates both new manifests, rechecks the 222 raw calibration cases, recomputes feature-support/tree/uncertainty diagnostics, and verifies 420 preserved plus 60 new policy outcomes without new native measurements. Its wrapper uses canonical JSON comparison to handle a tuple/list round-trip defect in the frozen analyzer's direct `verify` command; no scientific fields are ignored, and the original source is preserved. Only measured analysis wall time is excluded from exact replay.

All research replays and the 49 targeted tests pass, including all 27 new tests. Both full-suite runs have 2,550 passing tests, 179 passing subtests, and one unresolved failure in the unchanged legacy subprocess-cleanup test: macOS denies a process-group signal after the producer encounters a broken pipe. Its exact cause remains unresolved. The full suite is therefore not green; both failure logs and raw journals are retained.

Raw [calibration evidence](../results/2026-10-20-latency-calibration/README.md), [analysis artifacts](../results/2026-10-20-model-analysis/README.md), and the [validation record](../results/2026-10-20-model-analysis-validation/README.md) distinguish completed work from the next prospective experiment. The next engineering blocker remains a third independent workload with validated memory/runtime support.
