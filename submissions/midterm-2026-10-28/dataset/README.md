# ISAForge midterm dataset bundle

Release date: October 27, 2026. This bundle accompanies the ECE 4803 midterm report and slides. It is a frozen export of the consumed development evidence, not a prospective holdout.

## Contents

- `verified_candidate_labels.csv`: 122 successfully measured candidate labels across 14 workload groups and 15 contexts. Each row is a candidate/program measurement, not an independent workload.
- `failed_attempts.csv`: 4 charged failures retained separately from successful labels. They consume evaluation budget and do not receive fabricated speedup values.
- `policy_metrics.csv`: budget-level whole-workload-holdout policy outcomes, regret, confidence intervals, feasibility and evaluation-time summaries.
- `workload_level_metrics.csv`: per-workload policy summaries used for paired comparisons.
- `selected_hardware_metrics.csv`: measured area and minimum routed Fmax for selected feasible designs.
- `paired_regret_vs_merit.csv`: paired workload regret differences and bootstrap intervals for XGBoost ranking against merit.
- `global_feature_contributions.csv` and `local_candidate_contributions.csv`: descriptive XGBoost additive feature contributions; not causal effects.
- `codex_chat_selector_pilot.csv`: the one-episode active-chat LLM selector replay. One valid measurement selected the measured-pool oracle; a malformed ID charged a second attempt. It created no new hardware labels.
- `codex_chat_selector_control_comparison.csv`: frequency, merit, random, XGBoost, and GP controls at the chat episode's actual two charged attempts.
- `figures/`: PNG exports of the paired-regret and global-explainability plots used in the report.

## Important fields

In `verified_candidate_labels.csv`, `benchmark` identifies a workload context; `candidate_id` and `formula` identify the custom instruction; `speedup` is baseline cycles divided by candidate cycles; `baseline_cycles` and `candidate_cycles` are whole-program execution counts; `area_delta_lut4` is additional integrated LUT4 area; `routed_fmax_min_mhz` is the minimum across the recorded routing seeds; `correctness_verified`, `device_fits`, and `timing_feasible` are measured/validated gates. The nested `latency_features` JSON column contains profile-derived candidate opportunity estimates. Do not treat those features as independent measurement labels.

The corpus comprises Embench (39 labels, 6 workload groups), BEEBS (48, 5), and TACLeBench (35, 3). Twelve groups have complete measured candidate-pool oracles; two are censored. All 122 speedup labels equal the independent calibrated-latency estimates exactly, so the current cohort mainly tests ranking and hardware feasibility; it does not establish that XGBoost learned residual program-level speedup. The 2,925 policy-budget replays are dependent retrospective evaluations and add no hardware measurements.

## Model and interpretation limits

The pairwise XGBoost ranker is the single ML challenger selected for a future frozen prospective test; merit remains the operational fallback. Pairwise mean oracle regret is 0.842%, 0.439%, and 0.070% at budgets 1, 2, and 3. Merit regret is 1.132%, 0.465%, and 0.015%. Paired intervals include zero at budgets 1 and 2; at budget 3 the point estimate favors merit. No ML superiority is established.

Global ranker feature attribution assigns 66.39% of normalized contribution to profile-derived opportunity proxies, led by `saved_percent` (47.10%). Attribution explains this fitted model's ranking behavior; it is not causal and does not mean the model predicts speedup. The local bitcount example is an intentionally constrained case: the top-ranked candidate measures 1.008782x and passes correctness, but adds 65 LUT4, one above the +64 cap.

The Codex chat pilot is interactive and uses this active conversation as the decision model. The model ID, token count, and model-only latency are unavailable; the chat had broader context than the serialized four-tool boundary. It is a replay on consumed data, not a blinded API evaluation or live hardware experiment.

## Provenance

Every copied CSV and figure source is listed with a SHA-256 digest in `source_manifest.json`. Canonical artifacts are preserved in the repository under the source paths recorded there.
