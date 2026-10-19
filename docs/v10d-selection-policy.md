# Measured implementation selection policy

This policy is defined after inspecting the complete V10d timing results. It is a deterministic development analysis of already measured alternatives, not a preregistered experiment, learned selector, held-out result or measurement-saving claim. It introduces no new RTL, synthesis, routing, target labels or fits. The original immutable timing evidence remains unchanged.

## Inputs and constraints

Authenticate the complete 32-formula, 64-arm, 192-route evidence through the frozen raw auditor. Retain original and CSD implementations of each same function, all three seeds, every resource count and every critical-path attribution. No comparison across different functions is a Pareto comparison of implementations.

Optional hard caps are `max_wrapped_lut4`, `max_carry`, `max_packed_lc`, `max_ff` and `min_fmax_mhz`. Count caps must be nonnegative integers; the frequency must be finite and nonnegative. Booleans, null values, duplicate keys, unknown constraints and nonfinite values are invalid. Omitted keys are unconstrained; zero MHz explicitly sets a zero threshold. Equality passes. Each selected alternative must satisfy every supplied constraint on every measured seed. There is no tolerance or violating fallback.

These are per-implementation harness budgets. They are not total-CPU budgets or sums over 32 simultaneous units. LUT4, carry, packed logic cells and flip-flops remain separate coordinates, even when the FPGA packs several resources into one physical cell. No arbitrary weighted sum or LUT-to-carry exchange rate is used.

## Choice rule

Keep both the complete and feasible Pareto fronts using each resource's maximum over seeds and the maximum observed period. A front member cannot be improved in one coordinate without worsening another among the measured alternatives. Identical alternatives both remain on the front.

Choose minimum worst observed period among feasible alternatives. Break exact ties by lower maximum LUT4, carry, packed logic cells, FF, then original before CSD. This declares a timing preference within the supplied budgets; it does not assert that timing is every user's objective. No feasible implementation yields an explicit null choice with reasons. Unknown path attribution remains unknown and refers to whole-harness timing, not an invented arithmetic-only delay.

## Complete comparison policies

The reproduction helper applies exactly three policies to all 32 functions:

1. **Unconstrained:** no supplied caps, with the stated worst-period objective.
2. **Common clock:** minimum Fmax of 12 MHz, the original routing constraint, with no resource cap. All routes already passed this threshold; no gain in the count of timing-feasible functions is expected or claimed.
3. **Original worst-case limits:** separately for each function, cap each resource at that original arm's largest observed count and require its lowest observed Fmax. Select among original and CSD with the same choice rule. This tests whether a rewrite fits within the original implementation's measured worst-case envelope. It is not a ban on every individual same-seed regression, because the envelope uses worst observations.

No policy is chosen as a winner after scoring. All alternatives, constraints, violations, front membership, chosen arms and no-choice outcomes are retained. The policy comparison uses postmeasurement information, including original resources, and cannot measure acquisition efficiency. The baseline policy is a transparent analysis, not a proposed universal deployment budget.

## Use and replay

```sh
python scripts/select_v10d_implementations.py \
  --root results/2026-10-15-v10d-timing \
  --budgets '{"min_fmax_mhz":12,"max_carry":32}' \
  --output generated/selection-example.json

python scripts/reproduce_v10d_selection.py \
  --root results/2026-10-15-v10d-timing \
  --output generated/reproduction/v10d-selection
```

The first command illustrates a user-specified 32-carry limit; it is not a research benchmark or recommended device budget. The second replays every declared policy and generates figures. Use a fresh output; `--skip-figures` avoids plotting dependencies. The selector and evidence replay need no native hardware tools. CPU integration, actual workload latency, power and energy require their own measurements.
