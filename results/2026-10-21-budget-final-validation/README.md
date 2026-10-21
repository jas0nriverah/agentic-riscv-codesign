# Final campaign validation — October 21

`make test` finishes with **2,780 passed, 179 subtests passed, and one failed** in 147.90 seconds. The failure is `test_exited_producer_descendant_holding_commit_pipe_is_terminated` in the legacy capture tests: macOS returns `PermissionError(1, 'Operation not permitted')` during a process-group probe. Both that test and its capture implementation are byte-identical to commit `ee30bd38c34bad6306fbc79cffeed0bdbd93b001`. No fix is claimed, and this is not a fully passing test run.

`post-report-tests.log`, `validation.json`, and `raw-legacy-cleanup-failure/` preserve the complete failure. The earlier [2,704/three-failure and 2,732/one-failure runs](../2026-10-20-budget-validation/README.md) remain unchanged. Different legacy cleanup tests can expose the same permission problem; a failure not recurring does not imply it was fixed.

The 41 new relocation-guard tests and seven new report tests pass in this full run. They cover source-relocation rejection, source mapping and overlap checks, original evidence preservation, the real EDN failure, and the distinction between correctness rejection and infrastructure-censored outcomes.

Campaign archive replay and report generation both pass: all 12 target attempts, all 900 endpoints, seven failed qualifications, three linker diagnostics, and exact historical-only prediction refits are authenticated. Replays launch zero native hardware jobs. The figure was visually inspected. The portable expanded-corpus command reproduces the original export exactly. Historical processor/model replays and the final `make reproduce` check also pass; logs are retained here.

Documentation links, snapshot manifests, source bindings and the final Git diff are checked separately from experimental evidence. No new candidate is measured during validation.
