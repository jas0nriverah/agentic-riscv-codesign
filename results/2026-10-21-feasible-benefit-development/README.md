# Budget-conditioned feasible-benefit XGBoost

The model improves one demonstrated development decision: at **SHA256 +64 LUT4**, all five dependent seeds reach the best verified feasible 1.021384665× design after **two queries / 134.518 recorded target seconds**, versus **three queries / 200.552 seconds** for the existing normalized-speedup XGBoost. It avoids the second wasted measurement by choosing candidate22 before over-cap candidate11. The first query is still over-cap candidate00. It matches the adaptive hardware GP and still loses to the historical cost heuristic, which finds the optimum after one query /67.471 seconds. This is a consumed-data development improvement over one existing ML comparator, not generalization or superiority over the strongest baseline.

This is an actual new learned decision model, preserving the measured-speedup predictor separately. It uses the same31 structural columns and20-bootstrap,80-tree,depth2 XGBoost settings. Its one added context scalar is area cap divided by the historical median LUT4-per-operation proxy cost for that candidate. The response is signed measured saved cycles per replacement when measured hardware is feasible under the given cap/12MHz constraint, otherwise zero decision utility. Hardware-infeasible zero utility is not relabeled speedup or a failed-performance label. Each candidate bootstrap draw expands all three cap contexts with one-third weight; there remain15/15/21 measured fitting candidates for EDN/UD/SHA256, not45/45/63 independent observations. Failed/censored attempts have unknown utility and cannot train the model.

Predicted utility times public replacements divided by public baseline cycles ranks expected feasible whole-program savings. The output is **not a speedup prediction or calibrated feasibility probability**. The zero-shot ranking is fixed throughout an episode; final acceptance uses actual paid verified outcomes. Baseline is retained if no paid feasible improvement exists. No policy receives unpaid target outcomes.

Negative and limiting results remain visible:

- EDN +64/+128 and UD +64/+128 produce the same feasible-speedup curves as normalized XGBoost. SHA256 +128 already reaches the fastest feasible design in one query; the new model does not improve that outcome.
- At EDN +32, one of five seeds selects the second-best design first: mean query-one speedup1.000417168× versus normalized XGBoost's1.000432304×. It recovers by query two; its mean three-query recorded target time increases from405.370 to407.161 seconds.
- At UD +32/+64 and SHA256 +32, no verified improving feasible candidate exists in the fixed measured reference. The model still spends its full declared query allowance. UD's unresolved infrastructure-censored attempt means its full-pool optimum is unknown.
- At +64, seed-zero predictions assign positive utility to all known hardware-infeasible candidates:2 EDN,4 UD and3 SHA256. Its useful SHA reordering does not establish calibrated feasibility or remove the first wasted query. Bootstrap spreads remain uncalibrated.

The [predeclaration](protocol.md) fixes one model before fitting. [Predictions](replay/predictions.json) were sealed before opening target scoring reports. [Protocol/source/input bindings](replay/protocol.json) retain runtime versions, exact workload/family-excluded cohorts, historical available-attempt/setup costs and architectural contexts. Exact authoring sources are preserved under `replay/sources/`. [Report](replay/report.json) contains495 trajectories and1,485 budget endpoints across three targets, three caps, five dependent seeds and all11 policies. All450 unchanged comparator trajectories reproduce their historical choices, speedups and target costs exactly. [The compact +64 table](replay/README.md) includes every comparator; full caps, negative outcomes, utility diagnostics and regret are in the JSON.

No native jobs, new measurements or LLM calls were run. All six workloads are consumed development data; the other three workloads supply historical training context here. Repeated seeds/caps/budget prefixes are not independent tests. UD gaps use its best-verified reference and are lower bounds on regret to its unknown full pool. Target times are archived record/ledger costs with mixed scopes; historical attempt costs, baseline/setup and inference remain separate. [Fit/inference host times](replay/fitting.json) are about0.05 seconds per seed after first-import warmup of about0.50 seconds; this is not a complete search lifetime timer.

From the repository root, using the pinned runtime:

```sh
/Users/jasonrivera/Documents/Codex/2026-10-19/clo/work/audit-venv/bin/python scripts/evaluate_feasible_benefit.py --output generated/feasible-benefit-new
/Users/jasonrivera/Documents/Codex/2026-10-19/clo/work/audit-venv/bin/python -m pytest tests/test_feasible_benefit.py -q
```

All14 focused tests pass, including signed utility/failure separation, hardware-boundary conditions, candidate-level bootstrap weights, repeatable fits, public-only prediction inputs, constant fallback and charged measured acceptance. Full project tests and historical reproduction are coordinated by the parent task. Fresh source/input evidence under a protocol frozen before target measurements is still required to assess transfer.

Reusable API for a fresh frozen pool:

```python
from isaforge.feasible_benefit import FeasibleBenefitPredictor, search
model = FeasibleBenefitPredictor(seed=0).fit(successful_historical_rows)
predictions = model.predict(strict_public_rows, area_cap=64)
# Seal these public-only predictions before measuring any fresh target candidate.
result = search(strict_public_rows, charged_measurement_provider,
                area_cap=64, seed=0, budget=3, predictions=predictions)
```
