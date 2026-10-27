# Ascon selector policy semantics correction — October 27, 2026

This append-only correction clarifies the broad `model_is_frozen_during_episode`
field in the zero-label Ascon preregistration. It does not change the frozen
candidate pool, model artifacts, predictions, policies, query budget, or target
labels. The original package authenticates with:

```sh
../work/audit-venv/bin/python scripts/prepare_ascon_selector_prereg.py authenticate
```

`model_is_frozen_during_episode=true` applies to the prefit XGBoost and
factorized-feasibility models: their fitted parameters and published predictions
stay fixed for the three-query episode. It does not describe every adaptive
policy in the package. In particular, `hybrid_gp_adapt` is the existing dynamic
refit control in `isaforge/budgeted_selection.py`: after a successful paid
observation, it refits its hardware surrogate on the family-filtered historical
rows plus that policy's own successful paid prefix. It does not update on a
failed attempt. `hybrid_gp_zero_shot` keeps its initial hardware predictions
fixed. Frequency, merit, calibrated-latency, and latency/cost heuristics use the
same public rows and update only their incumbent-dependent score where the
existing implementation does so.

The Ascon policy list does not contain `fixed_joint_myopic` or
`fixed_joint_lookahead`. Those are separate controls with the fixed-initial
preprocessing and Gaussian-conditioning semantics in
[`joint-posterior-update-contract.md`](joint-posterior-update-contract.md).
Do not describe their fixed-joint updates as equivalent to `hybrid_gp_adapt`'s
dynamic refit.

For every native selector, reserve and charge the candidate before evaluation.
A complete, correct, verified successful result may enter that selector's paid
prefix. A failed result consumes budget but supplies no numeric GP update. An
interrupted or unknown result stops the session and cannot be retried in that
root. The LLM receives only public candidate data, frozen predictions, declared
constraints, and outcomes returned by its own paid actions; it does not update
the fitted XGBoost models. Candidate evaluation time, GP fitting/inference time,
and LLM relay/model time remain separate cost fields.

This correction resolves an implementation-description ambiguity only. It does
not validate GP calibration, improve model accuracy, create an independent
workload-family result, or authorize candidate dispatch. The candidate-capable
controller must bind these semantics and be committed and pushed before native
measurements begin.
