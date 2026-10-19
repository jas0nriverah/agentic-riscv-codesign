# V9 development direction: fill composition gaps before adding features

Status: read-only diagnosis and a proposed experiment. **No new fit or hardware
measurement has run.** V8 is consumed development evidence; its frozen transfer
result and artifacts remain unchanged. The separate
[paid adaptation study](v9-budgeted-adaptation-protocol.md) asks whether a small
number of revealed target residuals improves the remaining predictions. This
proposal instead tests the original training coverage.

The [current literature notes](research-update-2026-10-15.md), including their
[MARU source paper](https://lca.ece.utexas.edu/pubs/kholay_arc26.pdf), motivate
keeping data coverage and explicitly paid adaptation distinct from untouched
transfer. This diagnosis supplies local evidence for the coverage question; it
does not compare our LUT target or scores with MARU's target.

## What the frozen evidence shows

The original 1,665 rows contain 72 low-multiply nodes but only **26 constant-low-
multiply rows**. Seven of those have zero measured area; ten use zero, one,
minus one or a power of two. High multiplication has 116 nodes in 115 rows.
There are only two direct full-width constant products, constants **84** and
**1,103,515,245**, with targets 153 and 574 LUT4. One training row adds a variable
after the latter product, targeting 635 LUT4. None uses 54, 2025 or 3456, the
constants in V8's six concentrated-error rows.

After folding constant-only subexpressions, aliasing immediate operations and
ignoring constant values/input identities, coverage is:

| Consumed V8 context | V8 rows examined | Matching original training shapes |
| --- | ---: | ---: |
| Direct constant product | 3 | 2 for each |
| Variable add after constant product | 1 | 1 |
| Two-input subtraction before constant product | 1 | 0 |
| Masked subtraction before constant product | 1 | 0 |
| Signed-shift sum minus an input sign | 1 | 0 |

The last shape is `sub(srai(add(in0,in1),5),srai(in1,31))`, true area **56 LUT4**.
There are 300 training rows containing signed right shift, but none with that
four-operation composition. Shape matches diagnose coverage; they do not prove
functional equivalence.

The seven cases have **no exact training-vector collision** in any of the five
ExtraTrees views, even after sklearn's float32 input conversion. All mapping217
coordinates fall inside their individual training ranges. For mapping, original
legacy, rewritten legacy and dual graph, every reached query leaf has one
distinct training target. Large errors therefore do not come from averaging
conflicting targets inside a leaf.

They come from averaging predictions across trees routed to different contexts.
For `mul(sub(in0,in1),54)`, true area 201, mapping predicts 301.22; 30% of its
training influence comes from a shifted negative-constant product targeting 253,
with another 16% and 14% from variable products targeting 314 and 340. Rewritten
legacy still gives that shifted negative-constant example 38.33% influence and
predicts 286.77. The original syntax uses decoded constant expressions; the
quoted formulas here abbreviate constant-only subtrees.

For the true-326 `mul(in0,2025)` case, SOG predicts 62.61. A masked high-product
training row targeting 48 contributes **63%** of its influence; another
high-product row contributes 17%. The nearest SOG example has analytical area
1272 and XOR count 402, versus 1261 and 403 for the query, despite their very
different mapped LUT costs. This supports a local representation limitation,
without implying an exact feature collision.

The true-56 cap case has mapping median tree prediction 64 and mean **64.7767**;
174/300 tree predictions are at or below 64. Original and rewritten legacy means
are 63.11 and 62.2867. This explains a sensitive acquisition decision; tree votes
are not calibrated feasibility probabilities. Merit alone already attains the
cap64/budget1 oracle on V8, so repairing this miss cannot demonstrate an added
selection benefit over merit on this pool.

## Proposed small experiment

Keep **mapping217 and the fixed ET300 recipe**. Propose one complete, input-
sealed development batch of at most **48 original circuits**, followed by one
augmented fit against the existing frozen baseline:

1. **32 constant-product contexts:** take constants `{11,85,341,511}` times
   `{1,4}` and cross those eight constants with direct product, variable add
   after product, two-input subtraction before product, and masked subtraction
   before product. This varies positive-constant density, trailing zeros and the
   missing composition contexts. Every constant fits `addi(0,K)`'s signed
   12-bit immediate, with maximum 2044, preserving the proposed operation counts.
2. **16 signed-shift contexts:** use `sub(srai(add(in0,in1),k),srai(in1,31))`
   and its inner-`sub` variant for `k={1,2,3,4,8,12,24,30}`.

The [exact proposal](../results/2026-10-15-development-diagnosis/proposed-experiment-inputs.json)
contains no exact original-formula match in the inspected original 1,665 or V8
pool. Before any release, check the complete older consumed ledger and physical
RTL/tool identities, then seal the full pool and recipe. Measure every admitted
original once; no outcome-dependent replacements. These constants and contexts
are training cases, not independent application units.

Compare the one augmented forest with the frozen mapping model on all consumed
V8 rows, the six constant-product errors, signed-shift errors, cap32/64/128
false accepts/rejects, and original-support regression checks. Keep parameters,
weights and zero handling fixed. If unchanged features improve after coverage
augmentation, that identifies an actionable data bottleneck. Otherwise inspect
the newly measured context matrix before choosing a narrowly defined cost
interaction or learner change. The existing legacy features already encode
constant counts/popcounts/signed digits and are used in tree paths; another
119-column block is not the next supported experiment.

Any improvement remains a development result. A selected method needs a later
freeze and newly reserved application families for a transfer claim.

Evidence and replay: [retained package](../results/2026-10-15-development-diagnosis/README.md),
[human report](../results/2026-10-15-development-diagnosis/report.txt),
[slim diagnostic](../results/2026-10-15-development-diagnosis/diagnosis-summary.json),
and the complete compressed 10,500-leaf trace in that package.
