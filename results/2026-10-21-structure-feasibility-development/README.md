# Ordered hardware descriptors: negative development ablation

The fixed descriptor bundle does **not** repair SHA256's feasibility failure. It delays the adaptive GP's +64-LUT optimum from query two (134.518 recorded target seconds) to query three (200.552 seconds), in all five dependent tie seeds. Its best verified speedup remains 1.021384665×. The cost-aware heuristic still finds this optimum in query one (67.471 seconds). Do not promote this bundle into the bounded-agent comparison.

The single predeclared experiment uses the frozen GP, kernel hyperparameters and acquisition unchanged. It appends 45 ordered operation-class/operand-role/immediate/width descriptors. Four preorder slots preserve order; an overflow counter records omitted nodes. Operation classes deliberately pool exact opcodes; the bundle is a limited descriptor test, not a complete graph encoding. Its additional standardized dimensions change isotropic kernel distances; the experiment does not isolate which component causes the negative result, and no retuning follows.

Existing zero-shot hardware predictions exactly reproduce the historical archives. Three targets × three caps × five seeds × six comparator/variant pairs yield 270 trajectories and 810 budget endpoints. The three budgets are dependent prefixes, not independent tests. All six source workloads are consumed development data; exact historical EDN/UD cohorts have 15 fitting rows, SHA256 21, with unchanged workload/family exclusions. Other earlier workloads lack the same archived GP campaign and are historical training data here. See [predeclaration](protocol.md), [complete frontier table](replay/README.md), [predictions](replay/predictions.json), [events and diagnostics](replay/report.json), and [source/input/cost bindings](replay/protocol.json).

At +64 LUT4, the zero-shot area-MAE changes are EDN 16.017→16.177, UD 12.718→14.218, SHA256 16.158→16.211 LUT4. False-feasible mean predictions remain 2/5 EDN, 4/4 UD and 3/6 SHA256 among known hardware outcomes. Unknown failed/censored outcomes are excluded from hardware scoring, never relabeled infeasible. Area Brier score changes EDN .4973→.2454, UD .4259→.4592, SHA .3075→.3013; these mixed secondary changes establish neither calibrated probabilities nor improved selection.

All zero-shot feasible-speedup/cost curves remain unchanged. Adaptive EDN/UD curves remain unchanged. SHA adaptive +32 has changed attempted-time prefixes but retains baseline speedup; its +64 query-two frontier worsens, and +128 remains unchanged. No new native jobs, target labels or LLM calls occur. Historical available-label costs, narrower fitting cohorts and setup provenance are distinct in the protocol. Recorded target timers retain their historical mixed scopes. Reported inference includes process/import warmup and is not a latency benchmark or complete search/lifetime timer. UD's unresolved infrastructure-censored attempt leaves a best-verified reference; regret to its unknown full pool is unresolved.

Run from the repository root with the pinned Python 3.12 environment:

```sh
/Users/jasonrivera/Documents/Codex/2026-10-19/clo/work/audit-venv/bin/python scripts/ablate_hardware_descriptors.py --output generated/structure-feasibility-new
/Users/jasonrivera/Documents/Codex/2026-10-19/clo/work/audit-venv/bin/python -m pytest tests/test_ordered_hardware_descriptors.py -q
```

Seven descriptor tests pass. A subsequent replay adds an assertion that every unchanged search curve reproduces archived choices, feasible speedup and target measurement cost (excluding fresh inference timers and report-only metadata). The exact original run script is preserved beside its outputs; it is bound by the original protocol hash. No frozen source module or historical result was modified. A fresh source/input context and separately frozen justified revision remain necessary before any prospective claim.
