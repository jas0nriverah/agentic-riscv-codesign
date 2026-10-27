# Joint-posterior calibration report correction — October 27, 2026

This append-only correction preserves the original files in
[`results/2026-10-26-joint-posterior-calibration/`](../results/2026-10-26-joint-posterior-calibration/).
It does not change the original diagnostic values or the fitted model.

Two reporting fields in that retrospective report are inaccurate:

- `protocol.json` records `model_fits: 0`, but the report records `fit_calls: 14`
  and `scripts/audit_joint_posterior_calibration.py` fits once for each of the
  fourteen held-out workload folds. The actual fit count is fourteen.
- `results.md` calls the output cross-correlations “standardized residual”
  correlations. The implementation correlates raw prediction residuals
  (`observed - predicted_mean`), so they should be described as raw residual
  correlations.

The original audit scores every candidate from the zero-observation posterior;
it never calls `JointHardwarePosterior.condition()`. Its interval-coverage
results therefore do not validate calibration after paid updates. The separate
[paid-prefix diagnostic](../results/2026-10-27-joint-paid-prefix-calibration-r2/results.md)
adds a retrospective candidate-ID-ordered prequential check. It is development
evidence only and is not a selection-conditioned or prospective experiment.
