# Ascon selector prelabel freeze — October 27, 2026

**Historical v1 package.** Preserve this zero-label package, but do not use it
to authorize candidate dispatch: its `AGENTS.md` and `README.md` bindings no
longer match the committed source state. The replacement is
[`Ascon selector preregistration v3`](ascon-selector-prereg-v3.md), with a new
output directory, a hash-bound preparation script, and a separate controller
release. The command block below is historical and now follows the current v3
default; it does not regenerate this original v1 package.

The existing ISAForge selector recipes are frozen on the accepted Ascon v1.3.0
public pool before any target candidate outcome was read. Reproduce with:

```sh
../work/audit-venv/bin/python scripts/prepare_ascon_selector_prereg.py freeze
../work/audit-venv/bin/python scripts/prepare_ascon_selector_prereg.py authenticate
```

The sealed package is in
[`results/2026-10-27-ascon-selector-prereg/`](../results/2026-10-27-ascon-selector-prereg/).
It contains the unchanged 12-candidate public pool, five fixed model seeds,
frequency, merit, calibrated-latency, timing/cost, random, XGBoost regression
and ranking, GP, feasible-benefit and factorized-feasibility controls, plus a
zero-label specification for a future current-chat LLM policy.

The family filter compares all 12 target formulas against every historical
formula. Seven distinct target operation-tree families exclude 32 related
historical rows, leaving **90 measured training labels across 14 historical
workload groups**. Historical cost accounting retains all 126 attempts,
including four failures. Ascon remains same-domain crypto transfer and cannot
serve as an independent workload-family confirmation.

Prelabel policies disagree, so a limited-budget experiment can distinguish
their decisions. At seed 0, frequency, merit, raw and normalized XGBoost, and
pairwise XGBoost rank `and(xori(in0,-1),in1)` first. Calibrated latency ranks
`add(slli(in0,31),srli(in1,1))` first; factorized feasibility ranks
`add(slli(in0,31),in1)` first at the +64 LUT4 cap. These are public
predictions, not measured outcomes or evidence of which design is best.

The prelabel package records **zero target labels read, zero target labels
observed, and zero candidate attempts**. It freezes known XGBoost recipes; it
does not add a model version or claim improved accuracy. The ranker emits an
ordering score, not a speedup estimate. Bootstrap spread remains uncalibrated.

## Next release gate

No native candidate evaluation is authorized yet. The campaign still needs a
separate Ascon-native controller that:

- runs in a fresh attempt root while preserving the baseline-only qualification;
- uses session-local handles bound to full immutable candidate IDs;
- charges an action before dispatch and never retries a failed/interrupted
  attempt;
- enforces the same +64 LUT4, 12 MHz, and three-attempt budget for every policy;
- seals the current-chat LLM decision prefix and matched control decisions
  before any oracle outcomes are exposed; and
- records candidate evaluation time, chat relay time, and fitting/inference
  time as separate costs.

The LLM policy must get the same public features, model predictions, constraints,
and paid observations as its controls. The current chat has broader conversation
context than an isolated provider run; its result must be labeled accordingly.
Only after this controller and its source-bound release are committed and pushed
before target labels may the native experiment proceed. If authorized later, the
full measured 12-candidate pool supports a separate oracle replay; any unresolved
reference attempt makes regret a lower bound.
