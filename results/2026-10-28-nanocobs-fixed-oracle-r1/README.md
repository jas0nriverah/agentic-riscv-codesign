# Nanocobs independent fixed-input host audit

The independent short-frame oracle agrees with the pinned production codec on all **8,215 original probe payloads**, including exact encoded/decoded bytes, lengths, consumption and trailing sentinels. Command: `.venv/bin/python scripts/audit_nanocobs_fixed_oracle.py --output <fresh-directory>`. The combined workload/oracle suite passed 15 tests.

This is a host-only check using SWAR32 and `-Os`; host size_t remains native width. It is not target execution, performance evidence, malformed-frame coverage, or 254-byte-boundary coverage. The original target differential reference shares production source, so this separate oracle addresses common-mode risk only on these fixed short payloads.

The generated shared library is omitted; its hash remains in report.json. Compiler provenance, per-vector results, and reproducer/test snapshots are preserved here. Pinned upstream inputs remain in the preceding source-preflight artifact.
