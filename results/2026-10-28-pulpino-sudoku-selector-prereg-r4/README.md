# PULPino Sudoku prospective selection preregistration

This zero-label package freezes the r4 selector release after code review and two preserved pre-action snapshots. The r1 directory remains unchanged and is not releasable: its guard did not recheck candidate-ledger emptiness at agent startup, cost reporting could omit a charged job after result-projection failure, and family wording overstated the canonicalization. The r2 prereg fixed those issues but its launch used no PTY and received no usable action; that failed episode is preserved with zero candidate measurements. The r3 prereg documented a PTY but did not enforce it. This r4 package requires an interactive PTY before creating the agent episode and contains no Sudoku candidate measurements.

## Frozen cohort and models

- Target: one pinned 9×9 Sudoku puzzle run twice; 12 legal, executable single-instruction candidates with calibrated public cycle-opportunity features.
- Historical data: 122 successful measured labels and 4 failed attempts across 14 workload groups. Exclude the target workload and all target canonical operation-tree families before fitting: 106 rows / 14 groups remain; 16 historical successes are excluded.
- Models: existing pairwise XGBoost speedup ranker, factorized feasibility XGBoost plus public analytic cycle savings, existing regression/ranking/active-learning controls. No new model family or hyperparameter sweep.
- Agent: one current Codex chat relay with frozen seed-zero ML outputs, public frequency/merit/timing signals, hybrid historical retrieval, and four structured tools. No LLM fine-tuning or cross-provider routing claim.

## Budget and evidence

Primary evaluation: 64 added LUT4, at least 12 MHz across all three routes, and a maximum of three charged measurements. The LLM agent runs first and sees only public information and its own paid outcomes. The remaining candidates are measured only after finalization to establish the complete measured oracle; non-agent policy replays release each policy only its own paid prefix. Physical corpus construction can cost twelve candidate evaluations.

The endpoint is best verified feasible whole-program speedup by budget and cycle-reduction regret versus the measured pool oracle. Correctness, timing, area, evaluation count and measured evaluation time are reported separately. No superiority claim is preregistered.

The qualification found baseline **1,024,889 cycles / 198,711 instructions**, a **2,288-byte image**, **3,968-byte observed stack** with **1,792-byte headroom**, no stack/guard violations, **1,653 LUT4**, 295 carry cells, 655 flip-flops, 20 BRAMs, and routed timing above 12 MHz on all three seeds. These are baseline measurements, not candidate speedups.

## Release rule

The earlier r2 bridge launch failure is preserved under `results/2026-10-28-pulpino-sudoku-selector-launch-failure-r3/`; it used zero candidate attempts. The r4 command enforces an interactive PTY before creating an agent episode. Candidate dispatch is blocked until the preregistration, source, and evidence hashes are committed and pushed to `ai-guided-ml`. The executor verifies the exact local and remote commit and rechecks zero candidate attempts immediately before agent startup. See `preregistration.json`, `agent-protocol.json`, `source-family-audit.json`, `model-fit-costs.json`, and `manifest.json`.
