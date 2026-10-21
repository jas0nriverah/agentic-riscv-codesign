# Model/data improvement validation

- **54 new tests pass** in12.24s: candidate bootstrap/utility, model serialization and exact reload, generic freeze/evaluation, disjoint native wrapper, prelabel integrity, raw-outcome authentication and dataset/report accounting.
- **Full suite:3,014 passed,179 subtests passed, one failed** in152.69s. The same intermittent legacy `test_blocked_pipe_or_compressor_drain_has_finite_cleanup[pipe]` reports a producer in its owned-process-group residual list. PID13456 was absent in the subsequent `ps` check. The test source is byte-identical to the prior checkpoint. The failure is preserved; no legacy fix or fully green suite is claimed.
- Complete raw native/model/policy replay and export pass: six verified candidate attempts, five exact original control refits, five byte-identical utility model refits and495 endpoints. No new native process runs during replay.
- Historical `make reproduce` passes: all six frozen model metrics and the10,000-replicate audit reproduce.
- Exported corpus:39 successes, three earlier failures,42 attempts, six source workloads, seven contexts.
- Portable inference command passes with six predictions and zero target labels read.

`checks.json` and complete logs preserve the commands, source hashes, failure and scopes. The primary fresh test improves new XGBoost's two-query frontier over normalized XGBoost, while the cost heuristic still reaches the optimum first. Utility uncertainty remains uncalibrated.
