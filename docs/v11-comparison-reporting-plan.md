# V11 frozen-model comparison: prospective reporting plan

This reporting plan is recorded after input collection and before new feature extraction, predictions or target measurements. It complements the adopted [V11b-E1 protocol](v11b-transfer-protocol.md); it changes neither the models, pool, endpoint nor acquisition policy. Independent input replay is still pending. The [collection snapshot](../results/2026-10-16-v11c-dtc-recovery/README.md) contains 327 unique originals across 521 program/formula memberships, six complete outcomes and five nonempty families.

## Admission and accounting

Require a complete independent input audit, all-original feature and prediction freezes for the exact uncalibrated V6/V9 artifacts, a separate prospective target release, and independently authenticated original-RTL measurements for every unique original. No partial pool supplies the primary score. Report any failed stages and retain their evidence. Do not substitute familiar labels, rank candidates to reduce the pool, refit a model or select a threshold from this panel.

Canonical originals are deduplicated globally for physical jobs, with every cross-program membership retained in scoring. Accepted-identity components and training overlap are diagnostic strata, never exclusion rules. Recursion remains an explicit empty outcome with unavailable error, not zero error. The original all-program endpoint remains undefined; factorial receives the recurrence-family weight only under the named E1 amendment.

## Primary and descriptive comparisons

Use the existing `scripts/score_v11_transfer.py` implementation without changing its endpoint or arithmetic after labels. The primary is equal-five-family/equal-eligible-program MAE in LUT4. Report V6, V9 and V9-minus-V6; a negative difference favors V9. Keep all five family scores and all six program outcomes visible.

Report membership-pooled MAE, signed bias, RMSLE, absolute-error P90/P95/P99, maximum absolute error and maximum underprediction. True-zero labels remain in MAE and feasibility decisions; report their count and MAE explicitly. Percentage error must not replace the primary or conceal zeros. Distinguish the 327 physical targets from the 521 memberships whenever pooling.

For caps 32, 64 and 128 LUT4, show false-accept and false-reject counts alongside total, truly feasible and predicted-feasible denominators. A lower mean error does not establish safer feasibility decisions or a better instruction selector. Neither a point predictor nor these descriptive counts establishes a calibrated safety guarantee.

As an explicitly secondary sensitivity diagnostic, show the five leave-one-family-out primary differences, recomputing equal weights over the four retained families. Preserve every omission result. These are sensitivity values, not a confidence interval or five independent replications. Shared formulas, helpers and source ancestry preclude treating all memberships as independent draws. No population-level significance or state-of-the-art claim follows from this deliberately chosen panel.

## Figures and reusable data

Generate figures from authenticated saved scores and points, never manually transcribed rounded values. Export editable SVG, publication PDF and PNG together with full-precision source data and SHA256 manifests.

1. **Primary and family errors:** V6/V9 paired MAE for the amended primary and all five families, with each family's eligible-program and membership counts. Mark the empty recursion outcome in the caption.
2. **Measured versus predicted area:** separate V6/V9 panels on identical scales, every global original once, the identity line, and all outliers retained. Use a clearly labeled zero-preserving scale if needed; do not silently clip points. This panel uses unique originals, not membership weights.
3. **Tails and hardware-budget mistakes:** P90/P95/P99 and worst underprediction plus all three fixed-cap error counts. Label denominators and weighting explicitly. These are isolated-circuit resource decisions, not CPU timing measurements.
4. **Sensitivity and overlap:** all five omission results, and canonical/direct/component familiarity counts against the pre-reservation reference and each model's training set. Where secondary errors are split by familiarity, retain both strata and all their denominators; an empty stratum is unavailable.

The caption must identify frozen V6/V9, the E1 amendment, label technology (original RTL mapped to iCE40 LUT4), shared-membership handling, exposed inputs and withheld-label chronology. Scores from V6, V8, V9, V13 and V14 belong to different experiment populations and must not be joined into a single accuracy trend.

## Scope of the conclusion

Report whether targeted training coverage improved this fixed reserved-source panel, including regressions. Keep any promotion decision separate from the primary arithmetic. Processor cycles, integrated FPGA resources and routed timing retain their existing independent evidence; power and energy remain unmeasured. This area-regression experiment does not establish a new CPU speedup or a learned acquisition advantage.
