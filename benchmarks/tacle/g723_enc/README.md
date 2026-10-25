# Original-input g723_enc qualification target

The three upstream files are byte-identical to the primary pinned TACLeBench
archive at commit `c6a0d73e47bbd2bc86e34637156fb26dd4d5cf08`.
[Separate source provenance](../G723_SOURCES.json) records the archive SHA256,
file SHA256s and locally computed Git blob IDs. Independent Git fetch validation
of these new files has not been performed. Upstream notices, `license.txt` and
`ChangeLog.txt` are retained. Frozen bitcount provenance is unchanged.

`isaforge_adapter.c` asserts ILP32, renames the upstream main and includes the
unchanged source. It exposes the existing generic benchmark ABI. Initialization
is outside the timed interval; all 256 original A-law samples, encoding and the
original checksum return routine are inside it, matching the bitcount harness
convention. The original verifier requires checksum 24284. This is a fixed-input
self-check, not arbitrary-input correctness evidence.

`isaforge.next_tacle_workload` reuses guarded discovery, relocation rejection,
lowering, calibrated public opportunity, memory observation and baseline routing.
Qualification fixes twelve legal executable formulas, a same-candidate minimum
0.5% public calibrated cycle reduction and ten timed replacements, RV32I_zicsr /
ILP32 `-Os`, an integrated 8 KiB SoC and the original 6400/6528 partition. Code fit,
helper compatibility, original self-check and opportunity are unqualified until
the serialized native runner completes. Static storage size alone is insufficient.
Candidate dispatch is disabled by this qualification-only adapter; a later
complete model/controller preregistration and pushed release are required.

The [October 25 qualification](../../../results/2026-10-25-g723-qualification/qualification.json)
now records all six phases accepted, the original checksum passing and
3,783,237 baseline cycles. Twelve public formulas qualify. This baseline result
does not establish candidate correctness, optimized speedup or candidate costs;
those remain unmeasured at the prelabel checkpoint.
