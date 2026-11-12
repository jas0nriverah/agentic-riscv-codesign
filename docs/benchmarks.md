# Benchmarks

## Measurement pipeline

**RV32 formula → original RTL → semantic checks → frozen prediction → Yosys iCE40 synthesis → error and budget comparison.**

| Target | Included | Not implied |
| --- | --- | --- |
| Isolated iCE40 LUT4 count | Original circuit's mapped lookup tables | CPU speed, ASIC area, power or whole-core LUT count |
| Semantic verification | Saved sampled/boundary RTL checks | Exhaustive formal proof |
| Model comparison | Same circuits, training data and synthesis labels within each study | Comparability across unrelated datasets |

A zero-LUT circuit can still use carry resources. Hardware integration results are reported separately in [the hardware track](../hw/README.md).

## Metrics

| Metric | Definition | Interpretation |
| --- | --- | --- |
| MAE | Mean `abs(predicted − measured)` over every circuit | Error in LUT4, including zeros |
| Positive-target MAPE | `100 × mean(abs(predicted − measured) / measured)` where measured > 0 | Per-circuit percentage error; small targets can dominate |
| Worst underprediction | Maximum `measured − predicted`, bounded below by zero | Largest area underestimate |
| False acceptance | Predicted ≤ budget, measured > budget | Circuit would exceed the budget |
| False rejection | Predicted > budget, measured ≤ budget | Feasible circuit is excluded |

Budget caps are **32, 64 and 128 LUT4**. Predicting 12 for a measured 10 gives 20% error; predicting 3 for a measured 1 gives 200%. Zero targets stay in MAE and are counted separately, never divided by zero.

## Evaluation panels

| Panel | Unique circuits | MAPE denominator | Primary comparison |
| --- | ---: | ---: | --- |
| Research baselines | 192 | 186 positive; 6 zero | Equal-stratum MAE across eight equally sized strata |
| Application transfer | 327 | 228 positive; 99 zero | Equal-family / eligible-program MAE |
| Arithmetic stress | 32 | 32 positive | Equal-template MAE across four equally sized templates |

Application transfer has **521 overlapping program/formula memberships**, five nonempty families and one empty recursion outcome. One zero-area factorial circuit carries one-fifth of the primary family mean. The input pool has disclosed historical overlap; this is not an untouched semantic holdout. The scoped policy on that panel is retrospective. Arithmetic stress uses prospective but related synthetic circuits.

## Baselines and evidence

| Comparison | Meaning |
| --- | --- |
| MasterRTL recipe adaptation | Our FPGA adaptation of [MasterRTL's method](https://arxiv.org/html/2311.08441v1); not its published ASIC accuracy |
| Dual-graph vs base | Same fitting data; mapping-related descriptors differ |
| Base vs coverage | Same estimator and representation; 48 training examples added |
| Later budget classifiers | Separate declared experiments; failed candidates remain unpromoted |

Do not combine these panels into one learning curve. [Results](../results/README.md) contain observation files and replay links. [Detailed historical protocol](https://github.com/jas0nriverah/agentic-riscv-codesign/blob/f8fa7b02ba56507f64893debece8d38db8aff642/docs/benchmarks.md).
