# Non-crypto workload search and discovery qualifications

**Outcome: no new workload qualified; do not launch a qualification from this
search.** This preserves the October 26 stop decision after `complex_updates`
was rejected under its unchanged memory limit and Ascon was identified as a
same-domain crypto transfer lead.

## Fannkuch-redux: rejected at discovery

The official Computer Language Benchmarks Game describes fannkuch-redux as an
exhaustive permutation/prefix-reversal computation with a signed checksum and
maximum-flip output. The sequential C listing, correctness output, and license
are now pinned to upstream commit
`40296663ed350d5fe4a6ab5e367bab61cb77c219`; Git blob IDs and SHA-256 hashes are
recorded in [`FANNKUCH_REDUX_PIN.json`](../benchmarks/fannkuch/FANNKUCH_REDUX_PIN.json).
The repository stores the C listing as rendered HTML, not a standalone C file.
The pinned HTML and license are preserved byte-for-byte; the source listing
and ABI adapter are deterministically generated and hash-bound in the pin
manifest. The N=7 reference is checksum 228 and maximum flips 16. See the
[benchmark description](https://benchmarksgame-team.pages.debian.net/benchmarksgame/description/fannkuchredux.html),
[sequential C submission](https://benchmarksgame-team.pages.debian.net/benchmarksgame/program/fannkuchredux-gcc-1.html),
and [license page](https://benchmarksgame-team.pages.debian.net/benchmarksgame/license.html).

The upstream program, oracle, and license have been reauthenticated against
their pinned Git blob IDs and SHA-256 hashes. A bounded historical source-family
review scanned 184 reachable commits with 184 source/public-metadata queries;
there were zero query errors and zero matches for fannkuch, pfannkuch, pancake,
topswops, distinctive identifiers, or named authors. Six distinct ref tips
covering nine refs also had no source-family genealogy match. All 21 historical
public pool/plan artifacts were authenticated; their 132 candidate identities
across 16 contexts showed no named exposure. The reviewed algorithm is
exhaustive permutation enumeration with prefix-reversal flip counting. WikiSort
reversal helpers, nsichneu permutation comments, and Ascon's cryptographic
permutation do not establish shared genealogy. This passes the bounded
workload-family audit, not arbitrary renamed-equivalence or exact operation-tree
leakage; formula-family exclusions must still be checked after candidate
discovery and before fitting/release.

The fixed n=7 adapter now retains and compares both outputs. Independent
contract review cleared deterministic extraction and host-only validation.
The original program matches the pinned output bytes, and the adapter tests
checked packing/decoding bounds and both corruption controls (3 tests / 2
subtests passed). Small arrays and integer-only code do not prove complete
firmware fit or candidate opportunity. No target-side fit or candidate claim
can be made until baseline-only qualification checks the unchanged memory,
pool, and opportunity gates.

The pinned adapter and host oracle checks passed. The corrected baseline-only
qualification was later attempted and is preserved as rejected at discovery:
the exact N=7 program executes and passes its self-check, but the frozen
extractor produces only two calibrated formulas against the 12-formula pool
requirement. A post-rejection identity audit maps both formulas to the
already-observed add/shift family. No routed-baseline resource phase or
candidate dispatch was reached. See the separate [discovery diagnosis](../results/2026-10-26-fannkuch-discovery-diagnosis/README.md)
and [qualification archive](../results/2026-10-26-fannkuch-qualification-r2/).
Do not shrink the pool or lower the numeric opportunity gates.

## Ascon-128 v1.3.0: same-domain transfer lead

The [Ascon preflight](ascon-qualification-preflight-2026-10-26.md) pins a
different program and authenticates thirteen source/KAT file hashes, but the
current corpus already contains Nettle MD5, Nettle SHA-256, and BEEBS NDES.
Ascon can be revisited as a crypto-domain transfer test after its adapter and
family exclusions are reviewed. It cannot currently be counted as a new
independent confirmatory family; its original harness does not compare emitted
values with the checked-in KAT file.

## Pinned BEEBS survey: no qualified fresh workload

Two independent source reviewers completed a source-only audit of all 85
program directories at the BEEBS pin recorded in
[`benchmarks/beebs/README.md`](../benchmarks/beebs/README.md). No program
passed the combined freshness, defined-behavior, verifier, target-fit, and
candidate-opportunity gates. In particular, do not treat the following
text-search routines as qualified candidates:

- `stringsearch1` is a hard reject unchanged. On its fixed input, the forward
  sentinel path forms `buf + 117` although the `buf` object is 100 bytes, and
  other `e + 3` paths also exceed the array bound. Forming the pointer already
  violates C's array-bound rule. Its original verifier checks only the product
  of the two result counts, not each count independently.
- `strstr` has no demonstrated fixed-input C defect in the original wrapper.
  It calls the routine with `f + 1`, so the implementation's initial
  `haystack--` returns to a position inside the same string object. The pinned
  source and original wrapper/verifier were preserved byte-for-byte; host
  preflight confirmed the seven expected offsets and eight calls (including
  the final miss). The baseline-only PicoRV32 discovery run then rejected the
  workload before the opportunity or routed-baseline phases: it found zero
  raw, executable, relocation-safe, or calibrated formulas, including at
  diagnostic operation caps 2 through 6. No candidate was dispatched or
  measured. See the [qualification](../results/2026-10-26-strstr-qualification/)
  and [discovery diagnosis](../results/2026-10-26-strstr-discovery-diagnosis/README.md).

A bounded review of 184 commits across nine reachable refs/reflogs, plus eight
literal changed-path searches, found no direct `stringsearch1` alias in the
scoped source/public metadata. This negative result does not establish semantic
or formula-family independence. No `stringsearch1` candidate was extracted,
built, profiled, measured, or qualified.

## Reproducible evidence and next move

Fannkuch adds deterministic source extraction, host validation, and an archived
instrumented discovery profile, but no new candidate label or eligible pool.
The detailed candidate scarcity and alias reconstruction is sealed in the
[Fannkuch discovery diagnosis](../results/2026-10-26-fannkuch-discovery-diagnosis/README.md).
The BEEBS survey still has no qualified fresh workload. `strstr` has now passed
its original-input correctness and discovery-profile checks but was rejected
at candidate discovery with zero formulas; this is preserved as a workload
opportunity-scarcity result, not as a candidate-performance result. No routed
baseline, candidate labels, or model fits were added. Do not relax gates, shrink
inputs, or turn source resemblance into a measured result.

## Append-only Ascon status — October 27, 2026

The pinned Ascon host adapter now passes the complete 1,089-record KAT, and a
separate [hash-bound source-family audit](ascon-source-family-audit-2026-10-27.md)
confirms same-domain crypto overlap with existing AHA-compress, NDES, MD5, and
SHA-256 candidate motifs. Ascon cannot increase the independent-family count.
Exact compiler-derived candidate trees still need to be checked after a
label-free target pool exists. No target build or label has yet been produced;
the existing memory, twelve-candidate, opportunity, and timing gates remain
fixed.

## October 27 CoreMark v1.01 baseline-fit rejection

The official EEMBC CoreMark v1.01 source was compiled as separate upstream
translation units with the pinned RV32I/Zicsr GCC 15.2 toolchain, `-O2`, the
standard 2 KB validation data size, fixed 10 iterations, and the unchanged
PicoRV32 8 KiB RAM / 4 KiB stack reservation. The baseline link failed: the
program exceeded the permitted RAM region by **6,360 bytes**. Do not enlarge
memory, reduce the stack reserve, shrink the benchmark, or change optimization
flags to clear this screen. No target run, candidate extraction, correctness
result, candidate measurement, synthesis, timing, or speedup label exists.
CoreMark is not an eligible workload family and contributes no model evidence.

The hash-bound evidence and exact source/tool configuration are preserved in
[`CoreMark fit rejection`](../results/2026-10-27-coremark-fit-rejection/README.md).
The separate host-only CRC smoke check is not target compatibility or
performance evidence.
