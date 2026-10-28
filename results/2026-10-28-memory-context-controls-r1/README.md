# Memory context control replay — October 28, 2026

These two fresh deterministic runs validate the new context-control wiring against one already-consumed SHA256 target, seed 0, area cap +64 LUT4, and budget 1. The existing ten non-agent control policies replayed their archived paid prefix. Both modes produced 10 trajectories / 10 endpoints; every trajectory and cost matched the archived baseline (`all_controls_match=true`). Each protocol records zero LLM calls and zero native jobs.

`no_history` removes historical examples from the model-facing request while retaining the host's ML fit-row count. `budget_matched_history` exposes the same top-k of approved whole records in deterministic candidate-ID order, with the same maximum compact-JSON byte ceiling as retrieval modes. Payload sizes are not padded or guaranteed equal. The traces record context policy, record IDs/hashes, and exact byte counts.

This is a consumed-data **software/accounting noninterference check**, not an LLM ablation, causal retrieval result, or selection-quality experiment. The policies here are deterministic controls, and the target outcomes were already known to the privileged replay harness. It adds no labels and must not enter training. The two original runner outputs, private ledgers, protocols and manifests are preserved in the subdirectories.

Reproduce using the exact commands in [agent-memory-operations](../../docs/agent-memory-operations.md#reproduce-the-software-checks), choosing fresh output paths.
