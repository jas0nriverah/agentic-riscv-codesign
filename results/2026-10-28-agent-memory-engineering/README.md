# Offline memory engineering check

`summary.json` preserves the first four-mode software check at its recorded source
hashes. 40 deterministic control trajectories / 120 endpoints / 232 decisions /
174 retrieval events, all archived controls matching. No LLM calls or new native
jobs. Deterministic controls ignore retrieved evidence, so this checks integration
and noninterference, not retrieval quality. The later live pilot is separate.

Reproduce with `scripts/evaluate_agent_memory.py --output <fresh-directory>` using
the pinned Python environment. Full derived ledgers and SQLite exports are
recreated by that command. Later file-bridge and exporter changes are validated by
the focused suite; do not claim source hashes are identical to this first run.
