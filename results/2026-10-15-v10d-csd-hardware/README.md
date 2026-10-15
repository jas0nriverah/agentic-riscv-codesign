# V10d paired CSD hardware artifact

Complete consumed development study: 32 fixed original/CSD pairs, 64 native word frontends, 32 universal parsed-RTL proofs and 64 fresh mappings. LUT4 deltas: mean −88.5625, median −39.5, 31 lower / 1 equal / 0 higher. Carry: 13 lower / 7 equal / 12 higher. All fresh original counts match V9. No timing, CPU, power, ASIC or independent-transfer claim.

- [Protocol](../../docs/v10d-csd-hardware-protocol.md) and [results/figures](../../docs/v10-csd-hardware-results.md)
- [Exact input preparation](preparation.json), [proof-method amendment](premeasurement-amendment.json), [independent release review](independent-release-review.json)
- [Parent approval](measurement-approval.json), [native release](label-release.json), [completion](measurements/completion.json)
- [64 frontends](measurements/attempt-0000/frontends.json), [32 proofs](measurements/attempt-0000/algebra-proofs.json), [64 arm measurements](measurements/attempt-0000/arm-measurements.json)
- [All paired results](measurements/attempt-0000/summary.json), [portable audit](independent-audit.json)
- [Raw ZIP](measurements/attempt-0000/raw-evidence.zip) and [1,137-member hash manifest](measurements/attempt-0000/raw-evidence.json)

The previous V10c SAT attempt remains incomplete (16 proofs, 16 timeouts, zero area jobs). The new attempt changes its proof method, not its inputs or synthesis settings. The portable auditor shares the reviewed formal checker, independently evaluates concrete word/mapped outputs and resource counts, and needs no native tools. Run from the repository root:

```sh
python scripts/audit_v10d_hardware.py --root results/2026-10-15-v10d-csd-hardware --output generated/reproduction/v10d/independent-audit.json
```

All 32 source proofs remain bound. Universal parsed-RTL equivalence is distinct from the 2,148 sampled mapped-netlist checks per arm. Original/CSD counts remain separate; no fitted model or existing label was changed.
