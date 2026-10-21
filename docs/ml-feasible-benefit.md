# Improving the selection model

The owner's latest priority is **the learned model and measured dataset**. Demo, live LLM and presentation work are paused. Preserve their existing implementations and evidence; they are not the next assignment.

The observed model failure is concrete: an accurate unconstrained speedup ranking can spend its first measurements on instructions that exceed the area cap. The new fixed experiment tests whether conditioning a learned benefit model on that cap improves actual feasible selection. It does not start another isolated area-prediction study.

On six fresh SHA256 candidates, the new model reaches the best feasible design after **two measurements versus three** for the previous normalized XGBoost, across all five dependent seeds. The design executes in **25,466,830 versus 26,135,630 cycles**, a **1.026262× speedup**, with **43 added LUT4** and minimum routed Fmax **62.992 MHz**. Full-program correctness, processor controls and all three routes pass.

| Policy | First query attaining the +64-LUT4 optimum | Recorded target seconds to that query |
| --- | ---: | ---: |
| Cost-aware heuristic | 1 | 63.840 |
| New feasible-benefit XGBoost | 2 | 131.808 |
| Adaptive hardware GP | 2 | 131.808 |
| Previous normalized XGBoost | 3 | 201.231 |

At a budget of two, the previous model retains baseline; the new model obtains the optimum. At three, both models attain it and spend all three attempts. Earlier oracle attainment is **not** demonstrated automatic stopping or a complete-project latency saving. The strongest heuristic still wins. This is a targeted model improvement within a consumed source context.

## Model and training labels

`isaforge.feasible_benefit.FeasibleBenefitPredictor` reuses the existing 31 structural features and 20 candidate-bootstrap XGBoost regressors, each with 80 trees of depth2. Its one new feature is the area cap divided by a candidate area proxy: historical median integrated LUT4 per tree operation multiplied by that candidate's operation count. Only training hardware outcomes determine the proxy.

The supervised target is signed **measured saved cycles per executed replacement when the measured instruction is feasible**, and zero decision utility when its measured hardware is infeasible under the cap and 12 MHz clock. Unknown/failed attempts cannot train it. An infeasible zero utility is not a zero-speedup label. Feasible slowdowns remain signed negative labels. Final acceptance always retains the unmodified baseline if paid observations do not establish a feasible improvement.

Each bootstrap draw samples a measured candidate and includes all three cap contexts,32/64/128, at one-third weight each. Cap replicas are not independent measurements. Prediction multiplies utility by public replacement count divided by baseline cycles to rank feasible program savings. This is **decision utility, not predicted speedup, calibrated feasibility probability or confidence**. The original measured-speedup regressors and pairwise ranker remain separate unchanged comparators.

This is one combined target/context hypothesis, with the existing XGBoost settings fixed. It does not isolate the effect of the target transform from the added cap feature. No hyperparameter or feature sweep is justified by these results. Bootstrap disagreement remains uncalibrated; it is not promoted as repaired uncertainty estimation.

On the fresh pool, the nominal 90% bootstrap range covers the measured **utility** in only **16.7%** of cases at the primary cap, averaged over dependent seeds; coverage is 20% at +32 and 33.3% at +128. These are utility ranges, not speedup intervals, so they cannot be compared directly with the old speedup coverage. The first over-budget query also remains. Do not treat this model as a calibrated feasibility gate or uncertainty solution. The historical median area scale is fixed across ensemble members, so their spread also omits uncertainty in that shared scale.

## Evidence and limits

The [consumed-data development comparison](../results/2026-10-21-feasible-benefit-development/README.md) reproduces all 450 original comparator trajectories. At SHA256 +64 LUT4, the new model reaches the known feasible optimum in two queries instead of normalized XGBoost's three, across all five dependent seeds. The cost-aware heuristic still needs only one. One of five EDN +32 seeds regresses at query one and recovers at query two. Preserve both results.

The [fresh-candidate report](../results/2026-10-21-feasible-benefit-report/results.md) tests the frozen model on six previously unmeasured SHA256 formulas. The complete [preregistration](../results/2026-10-21-feasible-benefit-preregistration/README.md), all 100 exported JSON boosters, predictions and native baseline were committed and pushed at `25322573b86b933253f36a8316a18f7b1a058e67` before the first candidate attempt. Native state was authenticated both before and after fitting. All 27 non-SHA successful labels were available; related-family exclusions leave21 fitted candidates across five workloads. All six older SHA measurements are excluded from fitting but retained as consumed development cost.

The six old literal formulas were excluded before guarding, calibration and rank sampling from the remaining 50 legal formulas. Inputs, processor ISA, memory partition, correctness checks and native evaluator are unchanged. All six fresh candidates belong to the same four families present in the earlier SHA pool, although none reproduces an old SHA31-feature vector exactly. **This is not an unseen-workload or independent-family generalization result.** Five model/tie seeds, caps and budget prefixes do not create independent workload tests.

All eleven policies use the same public pool, historical data and area/timing limits. Frequency, merit, calibrated latency, historical latency/cost heuristic, random, raw/ranking/normalized XGBoost and zero-shot/adaptive hardware GP remain mandatory comparators. The complete manageable pool is measured for a separate oracle; selection sees only charged outcomes during cooperative replay. This is not a live adaptive native search. No LLM was called.

Historical training availability costs 1,698.153 recorded candidate seconds including three failures. All 36 consumed development attempts cost 2,100.614 seconds, including the old SHA labels. New candidate ledger walls, baseline/setup, overlapping command durations, calibration, model fitting/prediction and replay host time stay separate. Missing utility-trajectory inference fields must never be imputed as zero. The [expanded consumed corpus](../results/2026-10-21-model-training-corpus/README.md) retains source groups, context changes, signed performance, hardware/timing and failure classifications.

## Working commands

Use Python 3.12 and the pinned `requirements-speedup.txt` environment from the repository root:

```sh
make reproduce-feasible-benefit PYTHON=python
make feasible-benefit-report PYTHON=python
make export-model-corpus PYTHON=python
python -m isaforge.feasible_benefit_experiment predict \
  --root results/2026-10-21-disjoint-sha256-selection \
  --public results/2026-10-21-disjoint-sha256-selection/model/public.json \
  --seed 0 --area-cap 64 --output generated/feasible-benefit-predictions.json
```

Replay authenticates the prelabel Git bytes, native controls, measured cycles, netlist and routes, exactly refits all five original control packages and utility ensembles, and verifies all 495 policy endpoints. It launches no compiler, simulator or synthesis process. Inference loads portable JSON boosters and requires the recorded code/dependency versions. Prediction/report/export outputs require fresh paths.

For the earlier consumed-data model diagnosis, run `python scripts/evaluate_feasible_benefit.py --output generated/feasible-benefit-development-replay`. Do not overwrite its archived source snapshots or negative outcomes.

## Next blocker

More independent real workloads and candidate families are needed to evaluate transfer and source-level uncertainty calibration. [Preserved qualification diagnostics](../results/2026-10-21-model-data-qualification/README.md) show why sglib-combined, qrduino and minver do not fit the current unchanged8 KiB contract. Collecting six additional formulas does not solve source diversity. Qualify one fresh small integer source under a declared compatible compiler/input/memory context before tuning this model again.

All previously verified cycle changes match the independently calibrated latency baseline. Train a performance residual only if new measurements reveal systematic residual error. An LLM wrapper cannot fix missing model evidence. Joint instruction sets remain a later integrated experiment: implement and measure their combined execution, area and timing instead of adding single-instruction predictions.
