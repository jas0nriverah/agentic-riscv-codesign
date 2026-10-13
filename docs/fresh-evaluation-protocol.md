# Prospective transfer and processor evaluation

Protocol frozen on 2026-10-13 before fresh synthesis labels were inspected.
The original eight-program pilot is development data for this second stage.
Neither retesting those programs nor tuning to their prior errors is a new
unbiased test. Preserve the original model and all failed comparisons.

## Fresh transfer test

- Training: the fixed 339 rows / 301 formulas in `results/2026-10-13/dataset.json`.
- Fresh programs, selected before label collection: `statemate`, `nsichneu`,
  `minver`, `nbody`, `slre`, and `ud` from the same pinned Embench revision.
- Same RV32IM compiler settings, input workload, extractor limit of four
  operations, RTL verifier, and Yosys mapping as the original pilot.
- Evaluate frozen v1 XGBoost, an extrapolating structural-cost linear baseline,
  and v2 structural-cost-plus-residual model. V2 configurations are developed
  only on the original corpus. Record each artifact hash before fresh inference.
- Inference receives only formula and identity fields. Save all predictions,
  model-load latency and warm batch latency, rather than only aggregate scores.
- Report all rows and the subset of formulas absent from original training;
  report nonzero-resource subsets, benchmark-specific metrics, and distinct
  formula metrics. The novel-formula subset is primary for transfer accuracy.
- Primary accuracy measure: MAE in LUT4 on distinct novel formulas; also RMSLE,
  Spearman, and macro average of benchmark MAEs. Large control-flow benchmarks
  must not hide failures on smaller programs.
- No model retraining after seeing fresh labels for this frozen comparison.
  Any subsequent revision uses these programs as development data and needs
  another independent test set before claiming confirmed improvement.

## Decision comparison

The decision remains one candidate per program under an isolated LUT4 cap.
Primary decision endpoint: mean per-program fraction of oracle instruction
savings retained at **64 LUT4 and one new candidate measurement**. The complete
fixed sensitivity grid is caps 32/64/128 and budgets 1/3/5.

Compare frequency, raw instruction-saving merit, merit divided by formula
operation count, seeded random order, and feasibility-first merit ranking from
each frozen model. Use 100 random seeds (0–99). Deterministic policies run once;
random results are averaged within each program before comparing programs.
All policies receive the same candidate pool and public occurrence metadata.
Labels are revealed only for attempted measurements; the exhaustive oracle is
retrospective. Historical training synthesis costs are reported separately.

Report feasibility failures, regret, candidate evaluations, and paired program
results. Bootstrap 95% intervals resample whole programs (seed 20261013, 10,000
resamples); six programs are a small convenience sample, so these intervals are
descriptive and do not establish population-wide superiority. Do not treat
candidates, seeds, or multiple caps as independent workloads.

## Processor experiment

Pin an open processor revision and identical parameters, firmware harness,
memory latency, and measurement markers across baseline and custom variants.
Check numerical outputs for every run. Measure cycles in RTL simulation and
whole-core mapped resources, including decoder/handshake overhead. Test more
than one loop length and a zero-work control. Record the custom-instruction
latency and whether memory and counters are inside the measurement window.

A recurrence microbenchmark validates integration and cycle impact only. It is
not a full Embench application result. Without place-and-route timing, cycle
ratios are not demonstrated wall-clock speedup. Include a same-extended-core
baseline to distinguish instruction substitution from changing core settings.

## Relationship to published work

[CIDRE](https://arxiv.org/abs/2509.15782) studies microarchitecture-aware instruction
selection and complete processor implementations. [ARISE](https://arxiv.org/abs/2508.07725)
studies automated extraction and code/instruction-count goals. Our simple merit
policies represent common heuristic ideas, not reproductions of either tool.
A claim of outperforming a named system requires its actual method or a verified
reimplementation on matched workloads, candidate space, processor, constraints,
and cost accounting. Cross-paper headline numbers cannot establish that claim.
The immediate research hypothesis is improved measurement efficiency, followed
by verified architectural benefit; superiority remains an experimental question.
