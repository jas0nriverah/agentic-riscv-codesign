# Paid-update semantics for hardware selection

ISAForge has two distinct Gaussian hardware-update policies. They answer different questions and must not be presented as equivalent.

## Adaptive refit policy

`hybrid_gp_adapt` and the Ascon controller's `hybrid_gp_adaptive` prediction refit `HardwareSurrogate` on the frozen historical training set plus the current session's verified, successful paid outcomes. Each refit recomputes input standardization and output centers/scales, as the original estimator does. A successful measurement remains a valid training row even when its area or timing makes it infeasible; feasibility is part of the target, not a reason to erase an observed hardware result.

Every terminal attempt remains charged. Correct, measured successes update the continuous hardware regressors, including a measured `device_fits=false` result. Classified failures are preserved but do not become Gaussian labels; unknown or interrupted attempts stop the selector. Before an adaptive prediction, the controller now requires its ordered model-observation list to match the outcomes in the durable terminal attempt slots. It validates each outcome against its frozen public candidate. The refit cache is keyed by the full verified outcome rows, not just candidate IDs.

## Fixed joint-posterior policy

`JointHardwarePosterior` is a separately named control. It freezes the initial input/output preprocessing and kernel, then applies Gaussian conditioning to a candidate-correlated latent covariance for each hardware output. The separate hardware outputs are assumed independent. Its `alpha` is assumed iid Gaussian observation noise in normalized units; it has not been calibrated as measurement noise. Its device-fit Beta update is explicit. This policy is not an exact shortcut for `hybrid_gp_adapt`: dynamic refitting changes preprocessing after a paid label, and the tests show that its predictions can differ from fixed conditioning.

Consequently, a dynamic-refit lookahead must refit on each hypothetical branch with exactly the frozen estimator recipe, while a fixed-joint lookahead must be reported as its own policy. Mixing the two update rules invalidates paid-prefix comparisons.

## Ascon paid-prefix audit — October 27, 2026

The earlier v2 wrapper failure and its charged unknown reservation remain
preserved in [the v2 diagnosis](../results/2026-10-27-ascon-selector-controller-v2-attempt/README.md).
The corrected v5 release was committed and pushed at `007d6593` before native
dispatch. Its three-query current-chat session is archived in
[`results/2026-10-27-ascon-selector-chat-run-v5/`](../results/2026-10-27-ascon-selector-chat-run-v5/).
The run measured C01 (`1.019698x`, +73 LUT4, 62.992 MHz), C06 (`1.017027x`,
+41 LUT4, 67.069 MHz), and C02 (`1.023731x`, +42 LUT4, 64.620 MHz); all three
passed correctness. Under the frozen +64-LUT4 / 12-MHz constraints, C02 is the
best feasible measured candidate. Nine candidates remain unmeasured, so the
pool oracle is incomplete and the run does not establish regret or an advantage
over any heuristic. This is same-domain cryptography-transfer development,
not independent workload confirmation.

The run exposed a production adaptive-refit defect. The guarded audit omits
`status` on successful rows. The controller defaulted the terminal slot to
`success` but appended the status-less row to `observations`; `_dynamic_gp`
then filtered only explicit `status == "success"` rows. The completed session
therefore recorded zero adaptive fit time and no paid-prefix cache. The chat
agent did see each paid outcome, but the adaptive-GP update did not run. Do not
count this run as validation of paid model adaptation.

The source now persists the terminal status with each observation and accepts
legacy status-less successful rows as successful paid data. Focused tests pass
for both the audit-shaped missing-status record and persisted terminal slots;
a consumed-data diagnostic refits on 90 historical plus three Ascon rows and
authenticates the ordered paid-prefix hash. That diagnostic is software
verification on already revealed same-domain labels, not prospective evidence.
These edits intentionally move the working tree beyond the v5 source binding;
the old release is archived to its exact commit and must not authorize another
measurement. A new source-bound release and an untouched eligible target are
required before prospective adaptive-policy evaluation.

The MD5 disabled bridge remains disabled: its nonempty paid-reconstruction path
is synthetic-only. Neither the Ascon session nor the update fix establishes
selection superiority. Matched policies, equal information and budgets,
complete measurement-cost accounting, and fresh independent workloads remain
required.
