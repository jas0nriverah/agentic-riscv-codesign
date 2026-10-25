# One train-only ARD area surrogate development experiment

Known-benefit myopic acquisition and paid Gaussian conditioning are unchanged. The single new model identity is `ard_area__fixed_joint_myopic`. All seventeen original controls are retained exactly. No fresh-source, calibrated-confidence or superiority claim.

| Case | ARD cycle reduction % | Original myopic % | Difference pp |
| --- | ---: | ---: | ---: |
| old__beebs-aha-compress | 2.288232552 | 2.288232552 | 0.000000000 |
| old__beebs-ndes | 0.709537394 | 0.709537394 | 0.000000000 |
| old__beebs-nettle-md5 | 1.808785530 | 1.808785530 | 0.000000000 |
| old__beebs-jfdctint | 0.490120999 | 0.490120999 | 0.000000000 |
| expanded__beebs-aha-compress | 0.000000000 | 2.288232552 | -2.288232552 |
| expanded__beebs-ndes | 0.709537394 | 0.709537394 | 0.000000000 |
| expanded__beebs-nettle-md5 | 1.808785530 | 1.808785530 | 0.000000000 |
| expanded__beebs-jfdctint | 0.490120999 | 0.490120999 | 0.000000000 |
| fresh__beebs-expint | 0.034544484 | 0.034544484 | 0.000000000 |
| cached__tacle-bitcount | 0.174118284 | 0.000000000 | 0.174118284 |

B3 prefixes and separately executed B1/B2/B3 terminals have separate endpoint kinds. Old/expanded three-source macros are separate; DCT cohort cases, Expint and bitcount remain separate.

450 trajectories / 900 curve points / 180 new summaries; 1800 unchanged control summaries.

All three optimizer starts, statuses, convergence warnings, bound hits and training likelihoods are preserved in initial snapshots. Unused original semantic-area fits remain charged. Preparation fits and run reconstruction fits are separate; acquisition, conditioning, validation and initialization timers overlap their stated envelopes and are not summed twice.

- One area-surrogate specification changes covariance family, ARD and historical likelihood fitting together; this does not isolate their individual effects.
- All scored sources are consumed development data. Ten cohort/source cases span six sources; seeds, caps, budgets and repeated cohorts are dependent.
- The historical 99-label/102-attempt ledger is the frozen original-cohort scope, not all project costs after subsequent source collections.
- Only the existing myopic acquisition is evaluated with the new initializer. There is no model, kernel, prior or policy sweep.
- Every model fit uses only its original cached historical cohort. New paid observations never cross cases; all update parameters and preprocessing stay fixed after initialization.
- Gaussian observation noise, known analytic benefit and the common Beta device model are assumptions; probabilities are not calibrated confidence.
- Three deterministic optimizer starts are selected solely by finite historical marginal likelihood; nonconvergence and bound hits remain visible.
- Strongest archived control is a retrospective reporting envelope selected within each case/cap/horizon, not a deployable target-label-aware selector.
- All seventeen controls are copied exactly. Earlier fourteen-policy B1/B2 controls are prefixes of their horizon-independent three-query searches.
- Native ledger costs are reused and overlap across policies/cohorts. Host timers, initialization, original setup and recorded native costs are distinct scopes.
- No G723 artifact or outcome is read. Its frozen live policy is outside this experiment.
- No new native jobs, fresh-source result, promotion, calibrated-confidence or field-superiority claim.

Replay: `python scripts/evaluate_ard_selection.py replay --root results/2026-10-25-ard-selection-development --output generated/ard-selection-replay`.
