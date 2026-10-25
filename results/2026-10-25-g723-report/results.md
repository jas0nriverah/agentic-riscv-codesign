# Original-input g723 seventeen-policy comparison

Known calibrated-benefit assumption: 0 unique successful candidate violations; violated=False. Every actual label and residual is retained in summary.json.

One fresh source; five dependent seeds. No significance, calibration or superiority claim.

| Policy | Queries | Cycle reduction % | Regret % | Verified reference hits /5 |
| --- | ---: | ---: | ---: | ---: |
| frequency | 1 | 4.223235288 | 0.000000000 | 5 |
| frequency | 2 | 4.223235288 | 0.000000000 | 5 |
| frequency | 3 | 4.223235288 | 0.000000000 | 5 |
| merit | 1 | 4.223235288 | 0.000000000 | 5 |
| merit | 2 | 4.223235288 | 0.000000000 | 5 |
| merit | 3 | 4.223235288 | 0.000000000 | 5 |
| calibrated_latency | 1 | 4.223235288 | 0.000000000 | 5 |
| calibrated_latency | 2 | 4.223235288 | 0.000000000 | 5 |
| calibrated_latency | 3 | 4.223235288 | 0.000000000 | 5 |
| latency_cost_heuristic | 1 | 4.223235288 | 0.000000000 | 5 |
| latency_cost_heuristic | 2 | 4.223235288 | 0.000000000 | 5 |
| latency_cost_heuristic | 3 | 4.223235288 | 0.000000000 | 5 |
| random | 1 | 0.133996363 | 4.089238924 | 0 |
| random | 2 | 0.159709793 | 4.063525494 | 0 |
| random | 3 | 1.000296836 | 3.222938452 | 1 |
| raw_regression | 1 | 4.223235288 | 0.000000000 | 5 |
| raw_regression | 2 | 4.223235288 | 0.000000000 | 5 |
| raw_regression | 3 | 4.223235288 | 0.000000000 | 5 |
| ranking | 1 | 4.223235288 | 0.000000000 | 5 |
| ranking | 2 | 4.223235288 | 0.000000000 | 5 |
| ranking | 3 | 4.223235288 | 0.000000000 | 5 |
| normalized_xgb | 1 | 4.223235288 | 0.000000000 | 5 |
| normalized_xgb | 2 | 4.223235288 | 0.000000000 | 5 |
| normalized_xgb | 3 | 4.223235288 | 0.000000000 | 5 |
| hybrid_gp_zero_shot | 1 | 4.223235288 | 0.000000000 | 5 |
| hybrid_gp_zero_shot | 2 | 4.223235288 | 0.000000000 | 5 |
| hybrid_gp_zero_shot | 3 | 4.223235288 | 0.000000000 | 5 |
| hybrid_gp_adapt | 1 | 4.223235288 | 0.000000000 | 5 |
| hybrid_gp_adapt | 2 | 4.223235288 | 0.000000000 | 5 |
| hybrid_gp_adapt | 3 | 4.223235288 | 0.000000000 | 5 |
| feasible_benefit_xgb | 1 | 4.223235288 | 0.000000000 | 5 |
| feasible_benefit_xgb | 2 | 4.223235288 | 0.000000000 | 5 |
| feasible_benefit_xgb | 3 | 4.223235288 | 0.000000000 | 5 |
| factorized_feasibility_xgb | 1 | 4.223235288 | 0.000000000 | 5 |
| factorized_feasibility_xgb | 2 | 4.223235288 | 0.000000000 | 5 |
| factorized_feasibility_xgb | 3 | 4.223235288 | 0.000000000 | 5 |
| hybrid_gp_adapt_count | 1 | 4.223235288 | 0.000000000 | 5 |
| hybrid_gp_adapt_count | 2 | 4.223235288 | 0.000000000 | 5 |
| hybrid_gp_adapt_count | 3 | 4.223235288 | 0.000000000 | 5 |
| hybrid_gp_adapt_count_semantic | 1 | 4.223235288 | 0.000000000 | 5 |
| hybrid_gp_adapt_count_semantic | 2 | 4.223235288 | 0.000000000 | 5 |
| hybrid_gp_adapt_count_semantic | 3 | 4.223235288 | 0.000000000 | 5 |
| fixed_joint_myopic | 1 | 4.223235288 | 0.000000000 | 5 |
| fixed_joint_myopic | 2 | 4.223235288 | 0.000000000 | 5 |
| fixed_joint_myopic | 3 | 4.223235288 | 0.000000000 | 5 |
| fixed_joint_lookahead | 1 | 1.884174848 | 2.339060440 | 2 |
| fixed_joint_lookahead | 2 | 3.443548474 | 0.779686813 | 4 |
| fixed_joint_lookahead | 3 | 4.223235288 | 0.000000000 | 5 |
| fixed_joint_heuristic_fallback | 1 | 4.223235288 | 0.000000000 | 5 |
| fixed_joint_heuristic_fallback | 2 | 4.223235288 | 0.000000000 | 5 |
| fixed_joint_heuristic_fallback | 3 | 4.223235288 | 0.000000000 | 5 |

Primary endpoint: +64 LUT4, planned B3 terminal. B3 prefixes remain separate from independently executed finite B1/B2/B3 terminal horizons in endpoints.csv. All old fourteen controls are preserved.

Native pool: 12 charged attempts, 11 successes; 729.893610 ledger seconds. History: 99 successes +3 failures /102 charged attempts.

Qualification contributes one baseline integrated design and three routes, separately from the99label training corpus and candidate attempts. Other-policy cost curves are charged replay accounting. Ledger, native command, CLI, observer, fitting and inference timers have overlapping scopes. UTC and monotonic observations remain separate.

- One fresh source and five dependent seeds do not establish broad generalization, significance, calibration or model superiority.
- All fourteen previous controls remain fixed and share identical source/family-excluded fitting rows with the three finite controls.
- Only fixed_joint_lookahead seed0/+64/planned B3 dispatches live native jobs; all other policies use charged cooperative replay.
- Finite B1/B2/B3 are independently executed horizons; B3 prefixes are labeled separately.
- Known calibrated benefit, independent hardware GPs, assumed Gaussian observation noise and a common Beta device-fit model are assumptions.
- Fixed initial preprocessing and noisy conditioning differ from the old dynamic semantic refit; two-step receding horizon is an approximation.
- Correctness/infrastructure failure probabilities are unmodeled; failed attempts are charged and never Gaussian labels.
- Original256 A-law samples and checksum24284 are retained; fixed-input checks do not prove arbitrary-input correctness.
- All102 historical attempts and every new attempt remain charged; ledger/native/CLI/observer/model timer scopes overlap and cannot be added.
- Initial fitting and repeated authentication refits have distinct host scopes; neither is free total-model cost.
- A cooperative callback is not an OS sandbox; outcome access is restricted to the current paid query.
- UTC/monotonic observations remain distinct; no uninterrupted calendar-wall-time saving is established.
- The paired collection timer begins after initial authentication/release checks; Python startup and initial checks are excluded. Candidate CLI timers include their dispatch checks.
- A pool reference is complete only without infrastructure-censored outcomes; baseline is always available.
- Single instructions only; joint instruction sets require joint execution and synthesis.
