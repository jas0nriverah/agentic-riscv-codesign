# Current handoff — fixed joint updates and a new untouched workload

Read [README](../README.md), [AGENTS](../AGENTS.md), the [active goal](ACTIVE_GOAL.md), [primary methods](research-foundation.md) and [teammate compatibility](teammate-branch-review-2026-10-21.md). Branch: `ai-guided-ml`. The owner requests GPT-6.1 Sol subagents and continued measured improvement. Native jobs remain serialized and root-owned. Cloud, demo, live LLM and RTL-rewriting work remain paused.

The [preceding full handoff](HANDOFF-history-2026-10-25-pre-joint.md) preserves bitcount measurements, negative results, replay commands, clock qualifications and the pre-implementation diagnosis. Do not reinterpret those older pending tasks as current untested status.

## Verified state

The completed corpus is unchanged: **99 verified labels, three failures, 102 attempts, twelve sources, thirteen contexts, 112 integrated designs / 336 routes including baselines**. The [fresh bitcount test](bitcount-transfer.md) is negative for ML: the cost heuristic finds the +64-LUT4 optimum while the semantic GP retains baseline. Preserve every old frozen runtime, model and result.

[Original-input TACLeBench G.723 qualification](../results/2026-10-25-g723-qualification/qualification.json) now passes all six observed phases. Baseline: **3,783,237 cycles**, original checksum 24284, twelve legal public formulas, unchanged RV32I/8-KiB partition and opportunity gate. The maximum public calibrated cycle reduction is 4.223235%; this is not a measured optimized speedup. No candidate outcomes exist at this checkpoint. The qualification adds one baseline integrated design / three routes separately from the training corpus.

## Current bounded experiment

`joint_hardware.py` reconstructs the unchanged semantic initial fit, freezes preprocessing and distinguishes latent from assumed observation covariance. Paid updates and fantasies use the same immutable Gaussian conditioning; unknown failures consume budget without fabricated numerical labels. Independent outputs and the Beta device-fit model are explicit uncalibrated assumptions.

`finite_selection.py` implements known-benefit constrained myopic selection, finite two-step receding-horizon selection and a final-query incumbent fallback. Settings are fixed: 128 scrambled Sobol normal draws, seeds 0–4, cycle-reduction utility, exact final-query myopic choice and declared tie rules. These are adaptations of established acquisition methods, not new algorithms or faithful full-paper reproductions.

The [development experiment](../results/2026-10-25-finite-selection-development/README.md) seals all ten exact cached fitting cohorts, initial states and fantasy tables before parsing native outcomes. All fourteen existing controls remain exact. Planned budgets 1/2/3 execute independently; B3 prefixes and horizon-aware terminal results are distinct. Ten cases span six consumed sources, with old/expanded replicas reported separately. The completed 1,350 trajectories retain all 1,260 exact archived control summaries. Lookahead ties myopic at all thirty B3-terminal case/cap means; across ninety B3-prefix means it has four wins, thirteen losses and seventy-three ties. Fallback repairs bitcount but regresses DES. No fresh-source inference is possible from this scoring.

[Prelabel validation](../results/2026-10-25-finite-validation/README.md) preserves 157 focused test passes, exact 1,350-trajectory replay and historical reproduction. The first full suite has 3,617 passes / 179 subtests and the unchanged legacy external_v5 killpg PermissionError; it preceded the controller’s last eleven hardening tests. No entirely green full suite or cleanup fix is claimed. Fixtures are not processor measurements.

## Continue here

1. The independently reviewed [G.723 seventeen-policy freeze](../results/2026-10-25-g723-preregistration/cohort.json) has passed, with identical 86-row fitting cohorts and zero candidate labels. Push every model/controller/source/normal-table artifact and validate the complete Git checkpoint before dispatch.
2. Development scoring and exact replay are complete and were frozen at pushed25e2c27 before scoring. Preserve every win/loss without retuning or relabeling it as prospective.
3. Dispatch the already declared live G.723 policy: `fixed_joint_lookahead`, seed 0, +64 LUT4, 12 MHz, three queries. Seal each proof before dispatch and the complete live trace before the nine oracle-reference candidates. Never retry a charged attempt.
4. Pack and replay raw evidence, complete model refits, actual live prefixes and all seventeen policies; export the new corpus without changing previous rows. Record native ledger, CLI, paired-clock, baseline, historical and model computation scopes separately.
5. The next surrogate comparison should test one historical-marginal-likelihood ARD squared-exponential area GP, as used in the reviewed 2-OPT-C setup, with declared deterministic optimization bounds/starts and fixed paid preprocessing. Keep current cohorts, features, utility and all seventeen controls; do not tune on target performance. This is a single changed surrogate procedure, not a kernel sweep or full-paper reproduction. Strong publication comparisons require appropriate train-only surrogate/tuning procedures and untouched source-family evaluation. One pilot or a win over the fixed GP does not achieve the active research goal.

Use the pinned Python 3.12 environment `../work/audit-venv/bin/python`. New result/output directories must be fresh; never overwrite a sealed or failed run. Joint one-to-three-instruction execution remains a later required stage; individual speedups and integrated area are not additive.
