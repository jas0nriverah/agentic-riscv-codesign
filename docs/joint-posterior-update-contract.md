# Fixed-joint posterior update contract

**Status: implementation semantics accepted; empirical assumptions remain unvalidated.** This record prevents the completed update-contract work from being reopened as an implementation task. It does not establish that the fixed-joint model or its selection policy is accurate or superior.

## Declared policy

`isaforge/joint_hardware.py` freezes the initial feature transform, output centers/scales, fitted kernels, and normalized `alpha`. Latent covariance is converted to physical output units with scale squared; assumed observation-noise variance is `alpha × scale²`. The modeled outputs are integrated area (LUT4), minimum routed Fmax (MHz), and log evaluation time. The independent-output Gaussian assumption and noise scale are modeling assumptions, not calibrated findings.

Real paid observations and hypothetical fantasies use the same Gaussian conditioning equations. A paid update is accepted only for a previously queried candidate with a complete, successful, verified result. Charged failures do not create a Gaussian hardware observation or update the device-fit Beta prior. The planner uses the same update for its 128 deterministic scrambled-Sobol fantasy branches; its three-query setting is two-step receding horizon, not an exact three-step solution.

This is intentionally a different policy from the earlier dynamic-refit updater, which refits preprocessing and output normalization after paid observations. Fixed conditioning is not claimed to reproduce that dynamic refit.

## Verification evidence

The focused suite passed in the pinned environment:

```sh
../work/audit-venv/bin/python -m pytest tests/test_joint_hardware.py tests/test_finite_selection.py -q
# 66 passed in 2.43s
```

The tests check physical covariance/noise scaling, direct fixed-transform GP conditioning, explicit non-equivalence to dynamic refitting, exact paid-versus-fantasy state equality, and vectorized lookahead against explicit fantasy branches. The campaign receipts additionally replay the authenticated paid-prefix controller state before acquisition in [G.723 validation](../results/2026-10-25-g723-validation/README.md) and the [Lift selection report](../results/2026-10-26-lift-selection-report/results.md); the [Lift campaign protocol](lift-selection-campaign.md) records the collection checks and their limits.

The implementation-semantics prerequisite is therefore closed for this declared fixed-joint policy. Do not reimplement its conditioner or describe it as equivalent to refitting.

## What remains open

The assumed noise magnitude, Gaussian predictive support, independent output heads, common device-fit rate, and handling of correctness/infrastructure failures have not been empirically calibrated. The October 25 covariance diagnosis found weak information transfer between related candidates; the fixed-joint lookahead experiment found no selection gain over myopic control on its consumed development cases. The later G.723 and Lift campaigns do not establish a generalization advantage.

Any future change to covariance, noise, failure modeling, or utility is a new declared model/policy experiment. It must preserve frozen evidence, use the fixed-joint myopic policy as a matched control, and evaluate on eligible independent workloads under a predeclared measurement and time budget. The immediate blocker is a qualified independent workload and prospective evidence, not missing update semantics.
