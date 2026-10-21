# Fresh-source model and data experiment

ISAForge now has **45 verified candidate labels across seven sources and eight contexts**, with all three earlier failed attempts retained. The new source is pinned BEEBS integer JPEG DCT; six sources are Embench. This extends the working RV32I/PicoRV32 pipeline without changing the original processor, input arithmetic, RAM capacity, extractor or lowering interface.

The [full twelve-policy report](../results/2026-10-21-jfdctint-report/results.md), [raw evidence](../results/2026-10-21-jfdctint-campaign/README.md), [prelabel checkpoint](../results/2026-10-21-jfdctint-preregistration/README.md) and [consumed dataset](../results/2026-10-21-seven-source-corpus/README.md) are complete. The source/model/baseline/prediction package was pushed at `a2004f9540a2355c7b2fec31cacfa8fe8f153bb4` before any candidate attempt. Native state was authenticated before/after fitting and again at release. Every learned policy fits the same 38 historical candidates across six source groups after family exclusions; all 39 earlier successful labels and all 42 earlier attempts remain charged.

## The one model change

The earlier utility model still spends queries on infeasible hardware, and its bootstrap ranges miss most measured zero utilities. All 39 prior cycle deltas already equal independently calibrated latency. The fixed new hypothesis therefore learns **hardware feasibility separately from benefit**:

```text
score = mean feasibility score × max(0, public estimated saved cycles / baseline cycles)
feasible = device fits AND added LUT4 ≤ cap AND minimum routed Fmax ≥ 12 MHz
```

`isaforge.feasibility_selection.FeasibilitySelectionPredictor` uses the same 31 structural columns, historical cap/area proxy and fixed 20-member/80-tree/depth2 ensemble settings. Each candidate bootstrap includes all three cap replicas at one-third weight. Its binary logistic target is conditional on successful verified execution; failures have unknown hardware labels and never train zeros. Single-class bootstrap members use explicit constant predictions. Portable JSON boosters and schemas verify source, settings, dependency and training-cohort hashes and reproduce weights exactly.

The decision rule adapts the objective/constraint separation in [Gardner et al.,2014,§§3.1–3.2](https://proceedings.mlr.press/v32/gardner14.pdf). It does not reproduce constrained expected improvement or introduce a GP objective posterior. [XGBoost's binary logistic objective](https://xgboost.readthedocs.io/en/stable/parameter.html) supplies the classifier; the runtime remains pinned to 3.4.1. No hyperparameter, feature, confidence threshold or stopping-rule search was performed. The combined target/objective change is not an isolated causal ablation.

These scores are **uncalibrated**. Bootstrap spread is estimator disagreement, not a confidence or predictive interval. Prediction accepts only strict public inputs; paid measured correctness, cycles, area and timing decide final acceptance. Existing measured-speedup regressors, ranking and adaptive GP stay separate unchanged controls. The new policy is static zero-shot selection, not active learning.

## Actual fresh-source result

The exact upstream BEEBS source, original input and all 64 golden coefficient checks are preserved. Only an external no-op `warm_caches` adapter supplies the missing harness ABI. Compiler ISA is RV32I with counters/ILP32; PCPI is two inputs/one output. Original 8 KiB RAM, 12 MHz iCE40HX8K CT256, routes 1/2/3, serial native attempts and build workers 2 remain fixed. The declared partition reserves 3,072 bytes for program, 128 guard and 4,992 stack; baseline observed 304 bytes of stack use for the recorded input.

The baseline executes 117,522 cycles. All six automatically extracted candidates from 29 eligible formulas pass lowering, full verifier, stock/custom controls, execution-count checks, integrated synthesis and three routes. Candidate00 executes 116,946 cycles (**1.004925×**, 0.4901% fewer cycles), adds 61 LUT4 and has minimum routed Fmax 70.912 MHz. All six measured cycle deltas equal the public analytic estimate; all45 successful labels still have zero cycle residual.

| Declared cap | Result and limitation |
| --- | --- |
| +64 LUT4, primary | New model finds the optimum on query1 in all five dependent seeds, tying frequency, merit and earlier learned models. The cost heuristic misses it through query3. No advantage over the strongest heuristic or earlier model. |
| +32 LUT4, control | Candidate 17 is the sole feasible instruction,1.000409× at +15 LUT4. New model misses it through query3 in all five seeds; frequency finds it in four. Preserve this negative result. |
| +128 LUT4, control | Candidate00 is also the optimum. No broad learned-selection advantage is established. |

The oracle covers the declared six-candidate subset, not all 29 formulas. All twelve policies share history, public information, caps and attempt budgets 1/2/3. There are 180 trajectories / 540 endpoints. Outcomes reach policies only after charged queries in cooperative replay; this is not live adaptive native search. Three-query runs still spend three attempts after finding an optimum. Single-instruction results cannot be summed into a final set.

## Reliability and development evidence

The [fixed retrospective source diagnosis](../results/2026-10-21-factorized-development/report.json) holds out entire sources, including both SHA contexts together, and removes their formula families before fitting. It compares the new classifier, existing independent hardware GPs and the training feasibility rate. At +64, source-macro Brier is 0.310182 for XGBoost, 0.319040 for GP and 0.261751 for the simple prior. The prior also wins at the other two caps. The new model does not repair uncertainty.

Against the cost heuristic alone, retrospective +64 three-query source-macro speedup improves 1.014623×→1.028345× and gap to best-verified reference drops 0.013723 → 0. This is consumed-data development evidence and a limited comparator subset, not proof of superiority over frequency/merit. UD's unresolved infrastructure result still censors its full-pool reference. All source/cap outcomes, misses, inference times and zero observed cap-monotonicity violations remain in the report; no diagnostic chose model settings.

Fresh-source+64 Brier is 0.213194 versus existing GP 0.211783. All successful designs fit the device and easily meet12MHz, so these observations mostly discriminate area feasibility. Timing-boundary generalization is untested. The short DCT input and six-candidate pool offer limited absolute gain and selection difficulty. More independent sources and constraint-diverse labels are the next bottleneck; another variant tuned on these outcomes is not justified.

## Commands, costs and next work

Use Python 3.12 and `requirements-speedup.txt`:

```sh
make reproduce-jfdctint PYTHON=python
make jfdctint-report PYTHON=python
make export-seven-source-corpus PYTHON=python
make diagnose-factorized-selection PYTHON=python
python -m isaforge.factorized_selection_experiment predict \
  --root results/2026-10-21-jfdctint-selection \
  --public results/2026-10-21-jfdctint-selection/controls11/model/public.json \
  --seed 0 --area-cap 64 --output generated/jfdctint-predictions.json
```

Derived outputs require fresh paths; override the Makefile output variables on another run. Prediction reads zero target labels. Reproduction verifies raw evidence, complete committed manifest, release-before-attempt chronology, exact control/utility/classifier refits and every endpoint, with zero native jobs. The retrospective diagnostic records an absolute corpus path in its protocol; its exact report replay currently assumes the recorded checkout path. That metadata limitation is separate from portable JSON model loading and the main native-evidence replay.

Historical 42 attempts cost 2,497.368142 recorded seconds. Six new attempts add 250.772492 ledger seconds / 262.986905 CLI-operation seconds. The baseline ledger is 27.569974 s; 133 native commands total 266.639223 s across setup, baseline and candidates. These scopes overlap. Complete subprocess walls, qualifier/link failure costs and narrow measurement records remain separately archived. Legacy control-curve history timers sum successful rows only; use the outer `cost_provenance.historical_training_available` for complete historical charges including failures. Model fitting and prediction costs are explicit; there is no demonstrated end-to-end search-time win.

Continue data collection with a new independent small integer source under a frozen protocol. Retain both the fixed factorized model and all stronger controls; do not promote it as the winner. Add source-held-out calibration only when enough independent workloads support evaluation. Jointly selected one-to-three-instruction sets remain later integration work. Demo/live LLM and RTL-rewriting work remain out of the current assignment. Preserve [qualification rejections](../results/2026-10-21-jfdctint-qualification/README.md), [validation](../results/2026-10-21-factorized-validation/README.md), every historical experiment and all negative results.
