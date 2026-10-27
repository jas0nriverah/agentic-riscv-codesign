# Ascon source-family overlap audit — October 27, 2026

**Decision:** Ascon-128 v1.3.0 is a same-domain crypto transfer lead, not an
independent confirmatory family. Its source-level Boolean and rotate motifs
overlap with candidate families already present in AHA-compress, NDES, Nettle
MD5, and SHA-256. The exact Ascon formula-tree exclusions remain pending a
compiler-derived candidate roster; no Ascon target candidates or measurements
are claimed here.

## Reproduction and evidence boundary

Run the read-only audit with:

```sh
/tmp/isaforge-ml-20261026/bin/python scripts/audit_ascon_source_family.py
```

The [machine-readable report](../results/2026-10-27-ascon-source-family-audit/report.json)
and its SHA-256 sidecar bind the Ascon v1.3.0 upstream/copy manifests, every
copied source file, the audit script, and four prelabel public candidate pools.
The audited pool files match the hashes in the earlier bounded
[cross-context identity review](md5-cross-context-identity-audit-2026-10-26.md).
The audit reads only public candidate IDs and formula strings. It reads no
target outcomes and reports zero target jobs, labels, model fits, and candidate
dispatches.

## Source motifs and observed overlap

The pinned [`round.h`](../benchmarks/ascon/upstream/crypto_aead/ascon128v13/ref/round.h)
stores the state as five `uint64_t` words. Its substitution layer computes
`x XOR ((NOT y) AND z)` at lines 22–26. The `NOT-and` subtree has the same
canonical operation-family label `and(input,xori(input,constant))` as a
candidate in the AHA-compress public pool. Its diffusion layer implements
64-bit rotate-right as shifts plus OR (lines 8–9), then XOR-combines rotations
at lines 34–38. The existing AHA-compress pool contains the related shift/XOR
families `xor(input,srli(input,constant))` and
`xor(input,slli(input,constant))`; NDES, MD5, and SHA-256 pools contain
`or(input,slli(input,constant))`.

The four historical crypto pools also share exact canonical families with each
other: NDES/MD5, NDES/SHA-256, and MD5/SHA-256 each share
`add(input,slli(input,constant))` and `or(input,slli(input,constant))`.
The AHA-compress pool has no exact family intersection with those three pools
in the checked rosters. These are formula-family comparisons under the
project's existing canonicalizer; they are not arbitrary bit-vector
equivalence proofs.

## What this establishes—and what it does not

The algorithm-level source review establishes substantial crypto-domain and
primitive overlap. It does not show that every Ascon candidate will duplicate
an existing candidate, because the complete complemented-AND/XOR expression
may exceed the two-input PCPI boundary, and 64-bit rotations lower into
compiler-specific RV32I graphs. The actual emitted trees are needed to apply
the existing exact family exclusions. The source-level review is complete;
the target-derived formula-family audit is intentionally deferred until
label-free extraction produces an Ascon pool.

Next, prepare a target adapter that preserves the full declared Ascon input
workload and independent correctness checks, then check the unchanged RV32I,
6,400-byte program/data, twelve-candidate, 0.5% opportunity, and ten-timed-
replacement gates. If target extraction produces a pool, compare its exact
families against the frozen prior pools before any model fit or candidate
measurement. Preserve any gate failure. Even a successful Ascon campaign
would be same-domain transfer evidence and would not add an independent
confirmatory family.
