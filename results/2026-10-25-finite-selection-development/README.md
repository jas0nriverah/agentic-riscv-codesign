# Fixed joint-posterior finite-pool development experiment

Consumed development data. All cached cohorts and fourteen historical controls are preserved. The new known-benefit constrained-EI and finite-pool 2-OPT-C adaptations share fixed preprocessing, noisy Gaussian conditioning, Beta device updates and cycle-reduction utility. No calibration or superiority is established.

Primary +64 LUT4 / planned B=3 terminal results; earlier B3 prefixes and separately executed B1/B2 horizons remain in JSON/CSV.

| Case | Policy | Cycle reduction % | Cost heuristic % | Difference pp |
| --- | --- | ---: | ---: | ---: |
| old__beebs-aha-compress | fixed_joint_myopic | 2.288232552 | 0.000000000 | 2.288232552 |
| old__beebs-aha-compress | fixed_joint_lookahead | 2.288232552 | 0.000000000 | 2.288232552 |
| old__beebs-aha-compress | fixed_joint_heuristic_fallback | 2.288232552 | 0.000000000 | 2.288232552 |
| old__beebs-ndes | fixed_joint_myopic | 0.709537394 | 0.307011372 | 0.402526021 |
| old__beebs-ndes | fixed_joint_lookahead | 0.709537394 | 0.307011372 | 0.402526021 |
| old__beebs-ndes | fixed_joint_heuristic_fallback | 0.307011372 | 0.307011372 | 0.000000000 |
| old__beebs-nettle-md5 | fixed_joint_myopic | 1.808785530 | 1.808785530 | 0.000000000 |
| old__beebs-nettle-md5 | fixed_joint_lookahead | 1.808785530 | 1.808785530 | 0.000000000 |
| old__beebs-nettle-md5 | fixed_joint_heuristic_fallback | 1.808785530 | 1.808785530 | 0.000000000 |
| old__beebs-jfdctint | fixed_joint_myopic | 0.490120999 | 0.040843417 | 0.449277582 |
| old__beebs-jfdctint | fixed_joint_lookahead | 0.490120999 | 0.040843417 | 0.449277582 |
| old__beebs-jfdctint | fixed_joint_heuristic_fallback | 0.490120999 | 0.040843417 | 0.449277582 |
| expanded__beebs-aha-compress | fixed_joint_myopic | 2.288232552 | 0.000000000 | 2.288232552 |
| expanded__beebs-aha-compress | fixed_joint_lookahead | 2.288232552 | 0.000000000 | 2.288232552 |
| expanded__beebs-aha-compress | fixed_joint_heuristic_fallback | 2.288232552 | 0.000000000 | 2.288232552 |
| expanded__beebs-ndes | fixed_joint_myopic | 0.709537394 | 0.307011372 | 0.402526021 |
| expanded__beebs-ndes | fixed_joint_lookahead | 0.709537394 | 0.307011372 | 0.402526021 |
| expanded__beebs-ndes | fixed_joint_heuristic_fallback | 0.307011372 | 0.307011372 | 0.000000000 |
| expanded__beebs-nettle-md5 | fixed_joint_myopic | 1.808785530 | 1.808785530 | 0.000000000 |
| expanded__beebs-nettle-md5 | fixed_joint_lookahead | 1.808785530 | 1.808785530 | 0.000000000 |
| expanded__beebs-nettle-md5 | fixed_joint_heuristic_fallback | 1.808785530 | 1.808785530 | 0.000000000 |
| expanded__beebs-jfdctint | fixed_joint_myopic | 0.490120999 | 0.040843417 | 0.449277582 |
| expanded__beebs-jfdctint | fixed_joint_lookahead | 0.490120999 | 0.040843417 | 0.449277582 |
| expanded__beebs-jfdctint | fixed_joint_heuristic_fallback | 0.490120999 | 0.040843417 | 0.449277582 |
| fresh__beebs-expint | fixed_joint_myopic | 0.034544484 | 0.021982853 | 0.012561630 |
| fresh__beebs-expint | fixed_joint_lookahead | 0.034544484 | 0.021982853 | 0.012561630 |
| fresh__beebs-expint | fixed_joint_heuristic_fallback | 0.034544484 | 0.021982853 | 0.012561630 |
| cached__tacle-bitcount | fixed_joint_myopic | 0.000000000 | 0.174118284 | -0.174118284 |
| cached__tacle-bitcount | fixed_joint_lookahead | 0.000000000 | 0.174118284 | -0.174118284 |
| cached__tacle-bitcount | fixed_joint_heuristic_fallback | 0.174118284 | 0.174118284 | 0.000000000 |

10 cohort/source cases span 6 sources; old/expanded AHA/NDES/MD5 macros are separate. DCT cohort results, Expint and bitcount remain case-level results.

1350 new replay trajectories / 2700 charged curve points; 1260 exact archived control rows. No native jobs.

Preparation fits, run authentication rebuilds, policy conditioning, validation conditioning and acquisition computation have separate raw host timers. Acquisition includes fantasy integration; these timers overlap the run envelope. Historical attempts, baseline/qualification provenance and counterfactual native ledger costs are distinct and overlapping scopes.

- All existing sources and every scored case are consumed development data; no superiority, calibration or promotion claim.
- Ten cohort/source cases are six sources; old/expanded replicas, caps, budgets and five seeds are dependent.
- Cached history already contains other consumed target sources. Only new paid observations are isolated across cases.
- Known calibrated benefit, independent area/timing outputs, assumed Gaussian observation noise and a common Beta device-fit model are assumptions.
- Fixed initial preprocessing/noisy conditioning and cycle-reduction utility are declared changes from the frozen semantic policy.
- Correctness and infrastructure failure probabilities are unmodeled; actual failures are charged without fabricated hardware labels.
- Three-query two-step receding horizon is an approximation; all final choices must be measured and feasible.
- Gardner known-benefit constrained EI and finite-pool 2-OPT-C are adaptations, not faithful full-paper reproductions or new algorithms.
- Cooperative local providers are not an operating-system sandbox. No native tools are launched.
- Counterfactual trajectories reuse overlapping historical measurements. Earlier oracle hits do not establish stopping or total-time savings.

Replay: `python scripts/evaluate_finite_selection.py replay --root results/2026-10-25-finite-selection-development --output generated/finite-replay`.
