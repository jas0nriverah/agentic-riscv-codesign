# Improvement analysis — October 21, 2026

The next useful improvement is safer, auditable collection followed by fresh workload coverage. The current measurements do not justify another performance-model version or a claim that learned selection beats the strongest heuristics. This analysis uses preserved evidence; the new guarded collection has not yet established a native result here.

## What the existing experiment establishes

The [expanded corpus](../results/2026-10-21-expanded-corpus/corpus.json) contains 27 verified automatic labels: six each from CRC32, aha-mont64 and SLRE, five from EDN and four from UD. Three further attempts have no verified speedup label. The five source workloads are consumed development data, with different compiler and memory contexts; 27 rows are not 27 independent generalization tests. The older source-adapter CRC32 study is separate.

The [frozen EDN/UD protocol](../results/2026-10-20-budget-campaign/selection/cohort.json) declares ten policies, budgets 1–3, added-LUT4 caps 32/64/128 and a common 12 MHz clock. Its primary endpoint is budget three at +64 LUT4. Both targets use the same 18 historical labels, with 15 fitting rows each after related-family exclusion. Predictions preceded target measurements. The 900 policy/cap/budget/seed endpoints comprise two independent source workloads and five dependent seed repetitions, not 900 independent trials.

At the primary endpoint:

- EDN's best verified speedup is **1.0004323039443317×**, at +32 LUT4. Frequency, merit, calibrated latency and all five learned policies find it on query one. There is no learned selection win.
- Every completed UD candidate costs +65 to +72 LUT4. All policies retain baseline at +64; their reference hits do not demonstrate discovery of an improving feasible candidate.
- At the predeclared secondary +128 cap, normalized XGBoost improves the original regressor's budget-three choice from **1.0025841623021774×** to **1.0041174546727778×**, but only matches merit, latency and ranking.

These values and query histories are in the frozen [EDN report](../results/2026-10-20-budget-campaign/selection/embench-edn/report.json) and [UD report](../results/2026-10-20-budget-campaign/selection/embench-ud/report.json). The calibrated latency rule exactly explains every successful cycle delta across all 27 labels. A cycle-residual model currently has no demonstrated error to learn.

## Collection correctness and provenance come first

The [failure interpretation](../results/2026-10-21-expanded-corpus/failed-attempt-interpretation.json) distinguishes three outcomes:

- EDN candidate 17 violates the recorded memory contract. Removing `%hi(a)`/`%lo(a)` references lets linker garbage collection discard a 400-byte array while a decoded literal old address survives. Its first invalid write is address 5956; this is not a stack-overflow diagnosis.
- UD candidate 08 completes its recorded execution but fails the upstream self-check.
- UD candidate 10 stops during firmware preparation for low free disk space. Its 31.322582 seconds and query remain charged. No simulation, netlist or routes establish correctness, performance or feasibility.

The [source diagnosis](../results/2026-10-21-expanded-corpus/source-relocation-diagnosis.json) flags both recorded correctness failures and the censored UD candidate. It also flags a successful historical SLRE candidate: source risk is a conservative rejection rule for future pools, not permission to relabel an observed success.

The original collection interfaces expose several engineering gaps. The base evaluator authenticates source hashes but does not enforce a specialized `required_entrypoint`; opening a specialized root through an older evaluator can bypass its intended checks. The inherited collector stops on the first exception, and its measurement method can create a second attempt after a failure. A hard interruption can leave a directory without a terminal result. Native preflight failures can occur before a command receipt exists, so receipt count alone cannot account for paid attempts. See [the frozen base evaluator](../isaforge/workload_experiment.py) and [native runner](../isaforge/codesign.py).

The following fixes are **implemented in new modules, with focused tests**, while historical sources and pools remain unchanged:

- [The relocation guard](../isaforge/relocation_guard.py) checks original removed source statements. [The guarded evaluator](../isaforge/guarded_workload.py) filters the full executable list before calibration filtering and stratification, binds guard/runtime/auditor sources, and rederives guarded discovery on cache access. This explicitly replaces the captured `partition.EXTRACT` path; changing `lowering.extract` alone would not reach that alias.
- The new plan has an incompatible one-attempt budget marker, so historical runners reject it. The guarded runner checks the declared runtime and source/input identities. Existing raw ISA, lowering, full-program self-check, PCPI counts, stock/custom controls, memory guards, netlists and three-route checks remain required.
- [Persistent attempt accounting](../isaforge/guarded_attempts.py) records a charge before candidate work, preserves terminal failures, refuses implicit retries and stops collection on unresolved interruption. Successful cached results retain authenticated evidence. Baseline setup remains outside candidate duration.
- [The new evidence auditor](../isaforge/guarded_evidence.py) independently recounts baseline and successful raw measurements, authenticates receipt prefixes/spans and ledger artifacts, and supports partial archives. Unknown interrupted wall time remains nullable; malformed partial simulator output is preserved as unknown. Recorded wall time and overlapping native-command time remain distinct.

**Pending acceptance:** a fresh, source-bound development pool must execute through this complete path and replay from its archive. Passing unit fixtures alone does not establish processor correctness, close the old failures, or produce a fresh held-out result. A copied or filtered old pool is insufficient.

## Prediction accuracy, uncertainty and acquisition are different outcomes

Across dependent seeds, normalized XGBoost reduces mean speedup MAE versus raw regression by **98.43% on EDN** and **91.00% on UD**. Yet its nominal 90% interval coverage is only **36% / 65%**. Raw coverage is **0% / 70%**, so normalization worsens UD coverage while improving its predictions. These are successful-outcome diagnostics, excluding failed/censored attempts; they do not establish calibrated confidence. Exact per-seed values are under `diagnostics` in the frozen target reports.

The hardware GP has a concrete representation problem. EDN candidate 14, `addi(slli(in0,1),-2)`, actually costs **+65 LUT4**. Its seed-zero prediction is **59.999940 ± 0.262549 LUT4**, yielding an area probability of 1.0 at the +64 threshold numerically. Its closest historical standardized descriptor is `slli(addi(in0,1),4)`, measured at +60 LUT4, at distance **0.0039907988**. Count-based descriptors omit operation order and immediate placement/sign; the differing maximum absolute constant contributes little after scaling. Descriptor proximity does not establish hardware equivalence.

The historical row and target predictions are directly available in [EDN history](../results/2026-10-20-budget-campaign/selection/embench-edn/history.json) and [frozen predictions](../results/2026-10-20-budget-campaign/selection/embench-edn/predictions.json); the representation and fixed kernel are in [budgeted_selection.py](../isaforge/budgeted_selection.py). The +64 feasibility Brier errors are **0.477994 on EDN** and **0.377283 on UD**, reported as uncalibrated diagnostics. The common device-fit factor is also not candidate-specific evidence.

The duration GP predicts EDN median durations of approximately **41.2–46.9 seconds**, against **123.9–139.6 seconds** for successful measured attempts. Its inputs omit baseline workload runtime. Consequently, predicted evaluation efficiency needs its own validation; structural similarity cannot substitute for execution-cost context.

Paid GP updates exist, but these pools do not demonstrate useful active learning. For both hybrid policies, seed-zero EDN queries two and three at +64 have acquisition value **exactly zero**, followed by analytic-speedup tie-breaking. They consume **265.787507 additional seconds** after the first query already finds the best verified design. UD at +128 similarly spends **96.038852 seconds** after its first-query optimum. These are valid fixed-budget replay results, not evidence that later uncertainty-driven queries improve selection. Future online experiments should predeclare whether to stop when no positive acquisition remains; changing that rule now cannot retroactively improve the frozen comparison.

## Why the present constraints give limited discrimination

The new area caps create real exclusions, but EDN's highest-benefit candidate is already feasible and UD's completed candidates all fall above the primary cap. Thus the primary comparison is one easy successful ranking plus one baseline-retention case. Every successful new design clears 12 MHz; the lowest recorded minimum routed Fmax is **61.854397 MHz**. These outcomes do not test selection near a timing boundary. The [verified-label table](../results/2026-10-21-expanded-corpus/verified-labels.csv) retains exact costs and timing.

UD's best-verified reference is a lower bound on its unresolved frozen-pool optimum because candidate 10 is infrastructure-censored. Reference gaps are therefore lower bounds on true full-pool regret. [The qualified report](../results/2026-10-20-budget-campaign/report/results.md) preserves this distinction; the original scorer's `oracle`/`regret` field names remain unchanged. No synthetic value should fill the missing label.

The reviewed [primary-method foundation](research-foundation.md) already motivates constrained latency merit, integrated hardware measurement, feasibility-aware acquisition and evaluation-cost accounting. The [method extension](selection-methods-review.md) emphasizes grouped transfer, representation, support and independent calibration. The present hybrid multiplies deterministic analytic improvement by approximate independent constraint probabilities and expected inverse duration; it is an adaptation, not a complete constrained-EI reproduction. Two inaccessible full-method reviews remain unresolved. Neither the existence of ML nor this negative comparison establishes novelty.

## Bounded next steps

1. **Finish the guarded engineering validation.** Freeze source bindings, original-source guard decisions, safe calibrated pool, partition, inputs, attempt limit and hardware constraints before new candidate measurements. Require all raw correctness controls and portable replay. Report every attempt and failure; do not use this consumed-workload validation as unseen-workload ML evidence.
2. **Qualify an independent SHA256 source pool before labels.** The preserved [link diagnostic](../results/2026-10-20-budget-campaign/diagnostic-costs.json) records program/data/BSS end 7472 bytes. A predeclared 7488-byte program limit and 7616-byte stack floor would leave a 128-byte guard and 576-byte stack in the unchanged 8 KiB RAM. Fit, complete fixed-input self-check, runtime ceiling, observed stack bound, and a sufficiently large guarded/calibrated pool are still unproven. Preserve a qualification failure instead of changing these limits after candidate outcomes. Retain the complete 32-byte SHA256 digest check.
3. **Freeze a meaningful selection test only after qualification.** Keep current models fixed, hold out the entire source workload and related candidate families, and use equal information and query/time accounting. Predeclare the primary cap and budget; do not choose a threshold after seeing new hardware labels. Keep infrastructure censoring explicit.
4. **Use consumed data for diagnosis before another model.** Investigate operation-order/immediate descriptors, workload duration context and uncertainty support with fixed ablations. A later revision needs fresh grouped validation and measured selection value. Do not fit a latency residual while the calibrated rule remains exact.
5. **Connect later system stages after this foundation.** A bounded LLM selector still needs actual label isolation; cooperative Python replay is not a security boundary. One-to-three-instruction sets need joint lowering, execution and synthesis, since individual benefits and area increments are not additive.

The existing [final validation record](../results/2026-10-21-budget-final-validation/README.md) also retains the unresolved legacy process-cleanup EPERM failure. New focused tests and successful replays must not be described as fixing that unrelated failure.
