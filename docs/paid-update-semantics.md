# Paid-update semantics for hardware selection

ISAForge has two distinct Gaussian hardware-update policies. They answer different questions and must not be presented as equivalent.

## Adaptive refit policy

`hybrid_gp_adapt` and the Ascon controller's `hybrid_gp_adaptive` prediction refit `HardwareSurrogate` on the frozen historical training set plus the current session's verified, successful paid outcomes. Each refit recomputes input standardization and output centers/scales, as the original estimator does. A successful measurement remains a valid training row even when its area or timing makes it infeasible; feasibility is part of the target, not a reason to erase an observed hardware result.

Every terminal attempt remains charged. Correct, measured successes update the continuous hardware regressors, including a measured `device_fits=false` result. Classified failures are preserved but do not become Gaussian labels; unknown or interrupted attempts stop the selector. Before an adaptive prediction, the controller now requires its ordered model-observation list to match the outcomes in the durable terminal attempt slots. It validates each outcome against its frozen public candidate. The refit cache is keyed by the full verified outcome rows, not just candidate IDs.

## Fixed joint-posterior policy

`JointHardwarePosterior` is a separately named control. It freezes the initial input/output preprocessing and kernel, then applies Gaussian conditioning to a candidate-correlated latent covariance for each hardware output. The separate hardware outputs are assumed independent. Its `alpha` is assumed iid Gaussian observation noise in normalized units; it has not been calibrated as measurement noise. Its device-fit Beta update is explicit. This policy is not an exact shortcut for `hybrid_gp_adapt`: dynamic refitting changes preprocessing after a paid label, and the tests show that its predictions can differ from fixed conditioning.

Consequently, a dynamic-refit lookahead must refit on each hypothetical branch with exactly the frozen estimator recipe, while a fixed-joint lookahead must be reported as its own policy. Mixing the two update rules invalidates paid-prefix comparisons.

## Scope and remaining evidence

The October 27 Ascon controller release v2 was stopped after a wrapper bug prevented its baseline cache lookup. Its charged unknown reservation is preserved in [the v2 diagnosis](../results/2026-10-27-ascon-selector-controller-v2-attempt/README.md); it produced no candidate measurement or target label. The corrected wrapper and paid-prefix checks are covered by fake-only unit tests, but this correction has not yet been frozen in a new pushed release or demonstrated on a real paid Ascon prefix.

The MD5 disabled bridge remains disabled: it authenticates zero-paid initial models, and its nonempty paid-reconstruction path is synthetic-only. The semantics above do not enable that bridge or establish selection superiority. A future prospective run still needs source-bound controller release, matched policies with the same public information and evaluation budget, complete cost accounting, and an untouched target workload.
