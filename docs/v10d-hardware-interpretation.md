# V10d interpretation: LUT wins, mixed carry tradeoffs, unchanged model targets

The completed [paired summary](../results/2026-10-15-v10d-csd-hardware/measurements/attempt-0000/summary.json)
shows a useful hardware implementation improvement on this fixed development
cohort. CSD lowers LUT4 in **31/32 pairs**, ties one and worsens none: mean
`CSD − original` is **−88.5625 LUT4**, median **−39.5**, range **−272 to 0**.
Read-only recomputation from all 64 arm metrics matches the summary. All 32
fresh original LUT4 and carry counts exactly reproduce the consumed V9 values,
with matching original RTL/tool identities. The
[completion](../results/2026-10-15-v10d-csd-hardware/measurements/completion.json)
records 64 successful frontends, 32 universal actual-RTL algebra proofs, 64
fresh mapped arms and no failures or model fits.

## Pareto dominance holds for 20 pairs, not all 32

Here, CSD dominates its **matched original implementation** when it uses no
more LUT4 or carry cells and strictly fewer of at least one. Resource comparisons
between different functions are not a global Pareto frontier.

| Paired resource outcome | Cases |
| --- | ---: |
| Fewer LUT4 and fewer carry cells | 12 |
| Fewer LUT4, equal carry | 7 |
| Equal LUT4, fewer carry | 1 |
| Fewer LUT4, **more carry** | 12 |
| Original dominates CSD / both counts tie | 0 / 0 |

The 12 tradeoffs are direct, subtraction-before and masked-subtraction-before
contexts for constants **11, 44, 511 and 2044**. Carry increases by one for
11/44 and three for 511/2044. For example, direct 511 changes
**299 → 62 LUT4**, but **27 → 30 carry cells**. The lone LUT tie,
`add(mul(in0,addi(0,44)),in1)`, retains 141 LUT4 while carry falls **56 → 28**;
it is still Pareto-improved in this two-resource comparison.

Carry falls in 13 cases, ties seven and rises in 12. Its mean delta is −2.96875,
median zero. Summed across these separately measured circuits, LUT4 changes
7,817 → 4,983 and carry 1,453 → 1,358. These totals are descriptive; they are
not the area of an integrated design, and LUT/carry counts have no established
exchange rate. A blanket “smaller in every resource” claim would be incorrect.

Constants 511 and 2044 contribute **70.40%** of total LUT savings. The remaining
24 pairs still average **34.9583 fewer LUT4**, so the effect is not solely those
two constants. This deliberately chosen eight-constant/four-context cohort
does not establish an average gain on new programs or coefficients.

## Keep physical implementation and prediction targets separate

**Do not relabel existing original-RTL training or evaluation rows.** Their
targets describe the original emitted implementation, whose fresh controls
reproduce exactly. Functional equivalence does not make physical resource
counts interchangeable. The old model's prediction of original 511 area must
still be evaluated against 299 LUT4, not the rewritten implementation's 62.

Direct 511 and 2044 newly meet a LUT-only cap64 after rewriting; this is a new
physical feasibility result, not a correction to historical predictor false
accepts/rejects. Carry and timing constraints remain separate. If a future
deployment maps rewritten RTL, define a new target lineage keyed by formula,
rewrite policy, exact RTL, emitter and synthesis/tool configuration. Preserve
both measured arms and their pairing. A predictor for that implementation
needs separately frozen training/evaluation; V10d did not improve or refit the
original-RTL predictor.

## Focused next priorities

1. **Measure implementation timing before adopting CSD universally.** The
   existing [registered timing protocol](v10-timing-direction.md) is the next
   bounded hardware comparison: retain all 32 pairs, including the 12 carry
   tradeoffs and the LUT tie, with common boundaries and paired routing seeds.
   Report harness-limited paths and failures. Fewer LUTs, more/fewer carry cells
   and fewer source operators do not establish clock speed, CPU latency or power.
2. **Keep the original-area model work focused on its actual errors.** The
   [V9 coverage result](v9-coverage-results.md) improved mean error but retained
   cap mistakes: its six consumed-V6 cap64 false accepts are comparator,
   parallel-branch and shift cases; its six cap128 false rejects are arithmetic
   chains. Track those boundary errors alongside constant-product tails in any
   next fixed comparison. CSD labels would change the task rather than repair
   those errors; another broad feature block is not justified by V10d.
3. **Consider further adder-graph optimization only as a separate experiment.**
   First assess routed/resource tradeoffs. Then freeze one bounded alternative
   and the same proof obligations before new measurements. CSD is a successful
   baseline here, not a demonstrated global optimum. Any revised hardware or
   model method needs newly reserved sources for a transfer claim.

The universal proof concerns accepted parsed original/CSD RTL. Mapped
verification remains sampled at 2,148 vectors per arm. No CPU integration,
timing, power, ASIC-area or independent-generalization result follows from
this area study. This interpretation introduces no new native run or label.

[Research rationale for the timing and model follow-ups](v10d-research-direction.md) connects these choices to the primary constant-multiplication literature.
