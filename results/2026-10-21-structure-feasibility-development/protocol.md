# Consumed-data descriptor development protocol

Declared before this experiment's fits/scoring. All six workloads are consumed development data. This is one bundle ablation, not a new model release or prospective test.

Hypothesis: ordered operation classes, ordered operand roles, immediate bit patterns and conservative effective output width can reduce falsely feasible area predictions and wasted queries, particularly SHA256's demonstrated +64-LUT failure. Negative outcomes remain reported.

Compare unchanged HardwareSurrogate structural matrix against the same matrix plus four preorder operation slots. Each slot has six one-hot operator classes (arithmetic, logic, left shift, logical right shift, arithmetic right shift, other), ordered operand kinds, immediate signed-log magnitude/popcount, and conservative unsigned output-width upper bound. One overflow count preserves omitted-node information. No feature tuning, sweep, kernel/acquisition/target change or new hardware jobs.

Use exactly frozen history/public cohorts and related-family exclusions from EDN, UD and SHA256; verify unchanged zero-shot predictions against archives. These histories are earlier workload-held-out cohorts, not leave-one-row-out splits. Report postfilter groups. No other workload has the same archived GP campaign; six-workload corpus is already consumed, not a new holdout.

Both zero-shot and paid-success adaptation use the existing GP, GP_SETTINGS and hybrid_score. Caps 32/64/128 LUT4, 12MHz, budgets 1/2/3, tie seeds 0..4. Failures consume query/time, never hardware labels. Score best verified feasible speedup, gaps to best verified reference (UD censored), area MAE, false-feasible mean predictions, area probability Brier score, and actual recorded target time. Include fixed latency and cost-aware heuristic comparators. Historical training cost, baseline/setup provenance and inference are reported separately; mixed timer scopes prohibit lifetime-time claims. No uncertainty correction or calibration claim.

Implementation uses process-local scoped replacement of only the matrix function called by the unchanged GP. Each model fit/predict and adaptive search completes inside that context; original source bytes remain unchanged. Run the script as a standalone process, not as a concurrent in-process service. Predictions and protocol/source hashes are sealed before scoring within the run. One output directory only; replay into a fresh directory is permitted with identical protocol.
