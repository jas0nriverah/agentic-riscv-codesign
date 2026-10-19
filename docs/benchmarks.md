# Benchmarks and evaluation

## What is being predicted?

The target is **isolated original-RTL iCE40 LUT4 count**, measured with the frozen Yosys synthesis flow after RTL checks. It is not CPU cycles, ASIC gate area, power, or the LUT count of an entire processor. A zero LUT4 count can still use carry resources.

The pipeline is: extract or generate a candidate → generate RTL → verify integer semantics → freeze model predictions → synthesize original RTL → compare predictions with measured counts. The completed studies retain sampled/boundary checks, raw netlists and hashes in the [research archive](https://github.com/jas0nriverah/agentic-riscv-codesign/tree/b64716a2b94b332fdbced677869620bb949c073d). Sampled checks are not exhaustive formal proofs.

## Model comparisons

[MasterRTL](https://arxiv.org/html/2311.08441v1) motivates the bit-level simple operator graph and a lightweight resource estimator. We implement a recipe adaptation for FPGA LUT4 labels, alongside a tuned SOG model and graph-feature controls. The paper's original ASIC results use a different target, dataset and tool flow. Our matched comparison is between implementations trained and evaluated on our circuits; it is not a reproduction of the paper's published accuracy.

The research-baseline panel holds fitting data and target circuits fixed. Our representation extends the dual-graph control with 23 mapping-related descriptors. The coverage study instead changes training data, adding 48 measured examples while holding estimator settings and representation fixed.

## Evaluation sets

| Set | Unique circuits | Source / purpose | Primary endpoint |
| --- | ---: | --- | --- |
| Research baselines | 192 | Eight synthetic structural strata; compare representations and baseline recipes | Equal-stratum MAE |
| Application transfer | 327 | Five nonempty program families; six retained outcomes, including empty recursion | Equal-family / eligible-program MAE |
| Arithmetic stress | 32 | Four fixed arithmetic templates, eight parameters each | Equal-template MAE |

The 192- and 32-case groups are equally sized, so their primary MAE equals circuit-pooled MAE. Application families differ in size and share formulas. Its 521 program/formula memberships give a different weighting from its 327 unique physical circuits. The family-macro endpoint gives each eligible family equal weight; a single zero-area factorial circuit carries one-fifth of that mean. The empty recursion outcome has no defined error. Input overlap with earlier evidence is retained in the archive, so this is not a fully untouched semantic holdout.

Each saved observation includes the original formula, measured target and every retained comparator prediction. All original circuits and zero targets remain. The 32-case input draft had one disclosed pre-freeze template amendment after detecting old formulas; none were replaced after prediction/label release. The application scoped-policy result is retrospective. The arithmetic panel is prospective but related synthetic coverage, not new application-family transfer.

## MAPE and other metrics

For positive measured targets y:

$$\operatorname{MAPE}=\frac{100}{N_+}\sum_{i:y_i>0}\frac{|\hat y_i-y_i|}{y_i}.$$

This is the mean of each circuit's percentage error, not total error divided by total area. It compares predictions with measured synthesis labels, not with another model's output. Zero targets are excluded only from MAPE and counted explicitly; MAE includes every circuit. Tiny circuits can dominate MAPE even when their absolute errors are small.

We also report MAE in LUT4, zero-target MAE, maximum underprediction and fixed-budget mistakes. A false accept predicts a circuit at or below a cap when its measured count exceeds it. A false reject excludes a measured-feasible circuit. Caps are 32, 64 and 128 LUT4. No observed errors on a small panel do not establish a safety guarantee.

The default summaries use unique-circuit weighting and additionally retain each study's primary grouped endpoint. Do not compare percentages across different test sets as a learning curve. [Measured results](../results/README.md).
