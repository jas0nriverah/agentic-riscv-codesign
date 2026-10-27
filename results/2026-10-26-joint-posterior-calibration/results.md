# Fixed-joint posterior calibration diagnostic — October 26, 2026

**Exploratory retrospective diagnostic only.** The fixed-joint Gaussian update implementation and paid-observation semantics remain unchanged. This checks the existing model’s predictive uncertainty under 14 whole-workload/family-held-out folds on the consumed 122-success corpus. It does not tune or select a model and is not confirmatory.

Input corpus SHA-256: `901413111da94933a1c14f0e758c1cf96f959bde44325e79ded6e47c4b8743ef`. Source contract SHA-256: `128c67471373ce2b8d23ffa762e96c03183cd787ee12aeeacd5c4f3842ef1af2`. No target outcomes were used during fitting; no native jobs or new measurements were run. Four failed attempts stayed without numerical labels.

| Output | Scored labels | Median |z| | Standardized RMSE | 50% / 80% / 95% interval coverage | Feasibility Brier | Training-only prior Brier |
|---|---:|---:|---:|---:|---:|---:|
| area_delta_lut4 | 122 | 0.660 | 1.035 | 0.549 / 0.779 / 0.926 | — | — |
| routed_fmax_min_mhz | 122 | 0.657 | 1.061 | 0.533 / 0.770 / 0.926 | — | — |
| log_measurement_seconds | 122 | 0.715 | 1.690 | 0.418 / 0.836 / 0.918 | — | — |
| hardware_feasibility | 122 | — | — | — | 0.2564 | 0.4497 |

The model’s standardized residual correlations were area/Fmax `0.082`, area/log-time `0.088`, and Fmax/log-time `0.027`. They are descriptive, based on 122 selected engineering-corpus points; they do not establish cross-output independence.

The feasibility Brier score uses `P(area ≤ +64 LUT4) × P(min Fmax ≥ 12 MHz) × P(device fit)` from independent Gaussian heads and the training-only Beta rate. The comparator is only the constant device-fit prior, so this is not a comparison against frequency, merit, XGBoost, or an oracle.

The clearest calibration concern is log evaluation time: its standardized RMSE exceeds one and its 50% coverage is below nominal. Area and Fmax intervals are closer to nominal in this retrospective sample. These findings justify treating fixed GP uncertainty as provisional; they do not justify changing alpha or claiming improved selection. A future noise-policy change needs a fresh, predeclared held-out measurement cohort and a matched myopic control.

Limitations: labels are consumed development data; failures are unscored unknowns; candidate queries are not selection-conditioned; workload groups are not exchangeable; and this audit does not test prospective acquisition or best verified feasible speedup.
