# Nanocobs selection verification amendment

The original frozen executor `verify` failed because its SQLite count dictionary omitted `action_contexts`, which is present in the sealed exporter receipt. The actual database contains exactly three action contexts and all other counts agree. The original failure is preserved; neither the frozen executor nor sealed study artifacts were changed.

The separate `scripts/verify_nanocobs_selection.py` includes the missing count and retains exact equality, database hash/integrity checks, ledger/cost checks, raw archive reconstruction, full guarded processor audit and deterministic policy replay. It passed for all ten candidate outcomes with zero new native jobs.

Command: `.venv/bin/python scripts/verify_nanocobs_selection.py`.

The pre-dispatch full suite passed 4,564 tests and 181 subtests (one expected duplicate-ZIP fixture warning). The added verifier and selector suite passed fourteen tests, including four checks of missing/tampered database counts/table/checksum. Report plots were rendered and visually inspected.
