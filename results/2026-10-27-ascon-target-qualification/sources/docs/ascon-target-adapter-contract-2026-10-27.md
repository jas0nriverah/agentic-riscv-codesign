# Ascon-128 v1.3.0 target-adapter contract

**Scope: label-free, baseline-only qualification.** This contract extends the
host-only checkpoint in [the frozen host contract](ascon-adapter-contract-2026-10-26.md).
It permits preparing the guarded PicoRV32 context, extracting a public candidate
pool, applying the unchanged opportunity gate, measuring and synthesizing the
baseline, and freezing public inputs. It does not permit candidate dispatch,
candidate measurements, model fitting, or performance labels. Ascon is a
same-domain cryptography transfer and contributes zero independent confirmatory
workload families.

## Pinned input and executable

Use only `ascon/ascon-c` v1.3.0 at commit
`b7ca60bbf86479785de08b75aab2425dce4e9e8b`. The exact-copy manifest and the
host KAT result remain authoritative. `scripts/build_ascon128_v13_target_adapter.py`
deterministically builds the single translation unit required by the existing
ISAForge compiler. It inlines the pinned quoted headers into that translation
unit and preserves the `aead.c` implementation body; it does not rewrite the
cryptographic algorithm.

The benchmark iterates the original 33 × 33 ordered `(mlen, adlen)` pairs,
inclusive from 0 through 32. It constructs key, nonce, message, and associated
data bytes exactly as the host KAT generator does and passes a null secret
nonce. For each case it encrypts once, checks the ciphertext length, decrypts
and checks the original plaintext and length, then flips only the first
ciphertext byte and requires authentication failure. It hashes ciphertext bytes
in record order with 32-bit FNV-1a. The expected value `0x06cf04e8` is derived
from all 34,848 ciphertext bytes in the pinned KAT. The loop must execute
exactly 1,089 encryptions and 2,178 decryptions.

The generic firmware harness captures cycle and instruction counters before
`benchmark()` and after it. The timed region therefore includes the complete
crypto loop, round-trip/tamper checks, counters, and KAT fingerprint calculation.
The harness calls `verify_benchmark()` after the timed region; that check confirms
the counts and fingerprint. The host-only KAT observer and its serialization
are compiled out of RV32 firmware. No 34,848-byte expected-output table is placed
in target memory.

The host build uses the same generated translation unit and the same nested
loops, with an observer enabled only at compile time. Its complete emitted KAT
must remain byte-identical to the pinned 1,089-record file. The target performs
round-trip, length, tamper, count, and 32-bit fingerprint checks. **It does not
perform bytewise RV32 ciphertext-to-KAT comparison.** A 32-bit fingerprint can
collide; this limitation must accompany any target result and prevents claiming
formal or bytewise target KAT equivalence.

## Preserved processor and rejection gates

Reuse the existing guarded workload pipeline and exact PicoRV32, PCPI, compiler,
simulator, and synthesis inputs. Preserve RV32I_zicsr/ILP32, `-Os`, the 8 KiB
integrated memory, 6,400-byte program/data ceiling, 128-byte guard, and 1,664-byte
observed stack partition. Use 12 MHz and routing seeds 1, 2, and 3. Candidate
eligibility requires exactly twelve legal executable relocation-safe calibrated
formulas. The unchanged public opportunity rule requires at least one same
candidate to project at least 0.5% cycle reduction and at least ten timed
replacements.

Qualification must run in this order: prepare, discover, opportunity, routed
baseline, public projection, freeze. Candidate dispatch must remain disabled in
every phase, with zero candidate-attempt artifacts. The first rejection is
terminal and preserved. Do not change compiler flags, inputs, memory partition,
pool size, opportunity thresholds, or retry a failed phase. A frozen pool is not
authorization for candidate evaluation.

The baseline-only command is:

```sh
../work/audit-venv/bin/python scripts/qualify_ascon.py
```

It requires the existing reference root named in the qualification protocol and
fresh output/native roots. It archives the first rejection or complete readiness
evidence. It never dispatches a candidate.

The exact Ascon source-family audit identifies overlapping crypto Boolean and
rotation motifs in previously seen pools. Compare the compiler-derived formula
families against the authenticated history before any model fit or candidate
measurement. Even if target qualification succeeds, it is a transfer/development
result within cryptography, not a new independent-family confirmation.

## Evidence boundary

The host KAT equality is verified by
`tests/test_ascon_target_adapter.py` against all six fields and all 34,848
ciphertext bytes. The RV32 benchmark self-check adds runtime round-trip,
length, tamper rejection, call-count and fingerprint evidence. A baseline-only
qualification may establish compiler compatibility, memory fit, candidate-pool
readiness, baseline correctness under these checks, integrated resources, and
routed timing. It produces no candidate speedup label and no evidence that a
learned selector improves over frequency, merit, random, active learning, or the
measured oracle.

Any future candidate campaign requires a separate prelabel model/policy/controller
release, archived family-exclusion result, a guarded paid-attempt ledger, matched
frequency/merit/timing-aware/random/non-agent acquisition/LLM controls, and
explicit search-cost accounting. It must retain correctness, measured
whole-program cycles, integrated resources, all route seeds, failures, and
oracle censorship. The later one-to-three-instruction endpoint requires the
chosen combination to be measured and verified together; individual speedups or
area deltas may not be added.
