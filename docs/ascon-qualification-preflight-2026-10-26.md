# Ascon-128 v1.3.0 workload preflight

**Decision: provisional source lead only; not qualified.** The first new-source
qualification attempt after the recent workload review, TACLeBench
`complex_updates`, was rejected at discovery under the unchanged 6,400-byte
program/data limit. Ascon is a separate source candidate to review, not a
rescue or reinterpretation of that rejection.

The exact upstream identity is `ascon/ascon-c` tag `v1.3.0`, commit
`b7ca60bbf86479785de08b75aab2425dce4e9e8b`, path
`crypto_aead/ascon128v13/ref`. The source and artifact byte counts and SHA256s
are recorded in
[`benchmarks/ascon/ASCON128_V13_SOURCES.json`](../benchmarks/ascon/ASCON128_V13_SOURCES.json).
The upstream root license is CC0-1.0; retain the distinct NIST notice in the
original `tests/genkat_aead.c` if that file or derived test logic is copied.
The Ascon repository documents v1.3.0 as the earlier NIST-submission variant
and keeps its known-answer file at this path; do not silently substitute the
later standardized implementation or vectors. See the upstream
[repository/version note](https://github.com/ascon/ascon-c) and pinned
[v1.3.0 source](https://github.com/ascon/ascon-c/tree/v1.3.0).

The reference implementation's permutation uses 64-bit XOR, AND, complement,
and constant rotations. Those C operations are expressible for the existing
RV32I/ILP32 compiler; their actual lowering, helper calls, candidate count,
assembler acceptance, and integrated firmware fit have not been checked.
The source remains within the existing integer-only extraction scope in
principle, but that is not evidence that it passes the extractor or hardware
gates.

The upstream generator iterates all message and associated-data lengths from 0
through 32 bytes (1,089 pairs), initializes each byte to its index, encrypts,
decrypts and checks the returned length and recovered plaintext, then flips
the first ciphertext byte and requires authentication failure. It writes the
generated ciphertexts to a KAT file; it does **not** compare them with the
checked-in KAT file. The exact generator and 1,089-vector file are both pinned
in the source manifest. The driver itself uses allocation, stdio/file I/O, and
`exit`, so it cannot be used unchanged as the freestanding PicoRV32 workload.

No adapter, source copy, candidate extraction, compilation, native phase,
model fitting, reservation, or measurement has occurred. Local source search
found no Ascon identifier in the tracked project, but that alone does not
establish independence: the current corpus already includes Nettle MD5,
Nettle SHA-256, and BEEBS NDES. Ascon is a different algorithm and AEAD
interface, but it belongs to the same broad cryptographic domain. It may be
useful as an additional source-level transfer test; it cannot be counted as an
independent confirmatory family until the source-family taxonomy is frozen and
the historical candidate/formula-family overlap is audited.

Before any baseline-only native qualification, a root-owned prelabel adapter
specification must show how it preserves all 1,089 input pairs and the
generator's three checks without changing the fixed workload or turning a
checksum into a correctness claim. Then audit the full corpus for related
source/candidate families and freeze the unchanged compiler, 8 KiB RAM
partition, stack reservation, and gates. Qualification still requires twelve
legal, executable, calibrated formulas and at least one same candidate with
both at least 0.5% projected cycle reduction and ten timed replacements.
The exact gates are 6,400 bytes for program/data, 128-byte guard, 1,664-byte
stack, and 12 MHz routing. Do not lower these gates, shrink the source cases,
or run candidates during baseline-only qualification. Preserve a first
rejection without rescue.

This source review does not establish a new measured workload or any model
performance. The next decision is whether the verifier-preserving adapter and
family audit can be specified before spending a serialized qualification
attempt.

## Append-only implementation update — October 26, 2026

The source-only snapshot above records the earlier review state. The root-owned
adapter contract is now frozen in
[`ascon-adapter-contract-2026-10-26.md`](ascon-adapter-contract-2026-10-26.md).
All 13 files in the source manifest were copied byte-for-byte from the pinned
commit into `benchmarks/ascon/upstream/`; the separate
[`copy manifest`](../benchmarks/ascon/ASCON128_V13_COPY_MANIFEST.json) binds
their exact sizes and hashes. The [host-only preflight result](../results/2026-10-26-ascon-host-preflight-r3/result.json)
passes all 1,089 ordered cases, 1,089 encryption calls, 2,178 decryption
calls, every field in the KAT and byte-for-byte serialization equality. Six
fake-API controls exercise the wrapper's fail-closed paths; fifteen focused
tests pass. The derived wrapper includes the complete NIST notice and dated
modification description.

This update does **not** authorize a target qualification. The family-overlap
review, RV32 compile/lowering, 6,400-byte image fit, twelve-candidate pool and
public opportunity gates remain unresolved. No target jobs, candidate labels,
model fits or hardware claims are added.

## Append-only source-family update — October 27, 2026

The reproducible [source-family audit](ascon-source-family-audit-2026-10-27.md)
now confirms Ascon's source-level crypto overlap against four hash-pinned,
prelabel public pools. Its complemented-AND and rotate/shift/XOR motifs have
family matches in existing AHA-compress, NDES, MD5, and SHA-256 candidate
rosters. This confirms that Ascon is not an independent confirmatory family.
The Ascon target candidate pool has not yet been derived, so exact emitted
operation-tree exclusions remain pending target lowering. The machine-readable
[audit receipt](../results/2026-10-27-ascon-source-family-audit/report.json)
records zero target jobs, labels, model fits, and dispatches. This source-level
decision permits no candidate measurement; retain all existing target gates.
