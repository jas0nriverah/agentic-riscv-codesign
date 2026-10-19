# Final independent policy test

Frozen 2026-10-13, after the prospective six-program evaluation and before
resource labels from the last five Embench programs were inspected.

The first transfer test improved novel-formula MAE with v2 but found that its
point-feasibility ranking lost to raw merit on SLRE. Retain that negative result.
The four candidate-bearing families from that test now serve as policy
calibration data; they are not an independent test of the revised policy.

The final untouched programs are cubic, picojpeg, qrduino, sglib-combined, and st.
Use every eligible max-four-operation candidate, unchanged compiler/RTL settings,
and the same frozen v1, resource baseline, and v2 artifacts. No refitting.

The revised policy uses the 90th-percentile order statistic of each calibration
program's maximum signed log overprediction among formulas absent from original
training. Each program has equal weight. With only four programs, this selects
the largest observed error. The discounted acquisition score is
`max(0, exp(log(1 + prediction) - margin) - 1)`. Rank by merit when this score is
within the cap; actual synthesis still determines final feasibility. This score
is not a revised point estimate and is excluded from prediction-error metrics.

An initial formula-weighted draft was replaced before final labels with the
program-weighted maximum because the decision endpoint is program-level and a
rare exclusion of the best candidate matters. Keep the draft in local audit
artifacts; do not select among policy variants using final test outcomes.

The fixed primary endpoint remains cap64/budget1; report the full32/64/128 by
1/3/5 grid, all original baselines, and descriptive whole-program intervals.
Report both the model's original301 training circuits and additional policy
calibration circuits in cost accounting. Novel final formulas exclude those in
both training and calibration data; report the count explicitly.

Four calibration programs cannot establish a distribution-free guarantee or
population-level superiority. The empirical margin is a cautious prioritization
rule, not a probability of feasibility. Even a tie or loss must be preserved.
