# V9 consumed-cohort adaptation evidence

This is the fixed budget1/3/5 residual-correction development experiment on already consumed V8 application data. It does not refit a model, collect hardware labels, change query policy, or independently confirm transfer. The [results note](../../docs/v9-adaptation-results.md) explains the effect and limitations; the [frozen protocol](../../docs/v9-budgeted-adaptation-protocol.md) specifies the experiment.

At the primary three-query prefix, frozen/local/global equal-family MAEs are **3.345004634 / 3.279959536 / 3.659587363 LUT4**. Local minus frozen is **−0.065045098 LUT4**, a 1.94% reduction. The same 138 unqueried program/formula rows are scored for every adapter. FFT contributes only three zero targets, and one zero target at budget5. Isqrt remains secondary and is exhausted after two queries. The largest constant-multiply errors are unchanged.

| Artifact | Purpose |
| --- | --- |
| [prepared-attempt-0000/preparation.json](prepared-attempt-0000/preparation.json) | Immutable input/source/protocol bindings; written before its payload; no application labels or evaluation read |
| [prepared-attempt-0000/public-prepared.json](prepared-attempt-0000/public-prepared.json) | Whitelisted public candidates, original points, strict mapping217 selections, 146×300 leaf IDs, same-tree kernel, transitive identity ledger, fixed query schedules and all prefix exclusions |
| [parent-evaluation-release.json](parent-evaluation-release.json) | Parent release bound to the reviewed preparation and payload |
| [evaluation-attempt-0000/evaluation-start.json](evaluation-attempt-0000/evaluation-start.json) | Immutable evaluation source/input/release bindings |
| [evaluation-attempt-0000/unqueried-forecasts.json](evaluation-attempt-0000/unqueried-forecasts.json) | Sequential charged query log and all unqueried forecasts; saved before scoring |
| [evaluation-attempt-0000/evaluation.json](evaluation-attempt-0000/evaluation.json) | Three adapters, every family/budget, exact denominators, program metrics and complete-family guards |
| [evaluation-attempt-0000/completion.json](evaluation-attempt-0000/completion.json) | Completion and unchanged input/source hashes |
| [independent-audit/evaluation-audit.json](independent-audit/evaluation-audit.json) | Independent exact arithmetic check of 415 forecasts, all reported metrics, kernel/schedules and completion bindings; primary query contributions retained |
| [independent-audit/audit_v9_evaluation.py](independent-audit/audit_v9_evaluation.py) | Audit source; imports neither V9 implementation nor evaluator |

Preparation and evaluation paths are immutable. Failed or incomplete attempts must remain visible; use fresh output paths for replays. The source-bound preparation must not be edited to accommodate a later source/protocol revision.

To replay the same released evaluation in the pinned project Python environment, use the preserved preparation and release, writing to a fresh destination:

```sh
.venv/bin/python scripts/develop_v9_adaptation.py evaluate \
  --prepared results/2026-10-15-v9-adaptation-development/prepared-attempt-0000 \
  --review results/2026-10-15-v9-adaptation-development/parent-evaluation-release.json \
  --output generated/v9-adaptation-replay
```

This reuses consumed labels through the same sequential broker and recomputes only the declared correction and scoring arithmetic. The preparation loader authenticates the original public inputs, artifacts, protocol and implementation before target access. Real input-only preparation can be repeated with `prepare --root results/2026-10-15-v8-application-transfer --output FRESH_DIRECTORY`; a newly timestamped preparation requires its own bound review/release before evaluation.

The [plot helper](../../scripts/plot_v9_adaptation.py) reads completed scores and public denominators without recomputing predictions:

```sh
.venv/bin/python scripts/plot_v9_adaptation.py \
  --root results/2026-10-15-v9-adaptation-development \
  --output generated/v9-adaptation-figures
```

Published [figures](../../docs/figures/v9-adaptation/figure-manifest.json) include PNG, SVG, PDF, caption, numeric data and source/input/output hashes. Unqueried sets change across budgets; within-budget adapter comparisons use identical cases. There are no population confidence intervals, calibrated upper bounds or instruction-selection/CPU-performance claims.
