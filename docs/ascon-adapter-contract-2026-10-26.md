# Ascon-128 v1.3.0 host-adapter contract

**Frozen scope: host-only correctness preflight.** This stage prepares a possible
new workload transfer test; it does not authorize target qualification, candidate
extraction, candidate dispatch, synthesis, model fitting, or hardware labels.
Ascon remains a same-domain cryptography lead and does not count as an
independent confirmatory family.

## Pinned workload and oracle

Use only `ascon/ascon-c` v1.3.0 at commit
`b7ca60bbf86479785de08b75aab2425dce4e9e8b`, as listed in
[`ASCON128_V13_SOURCES.json`](../benchmarks/ascon/ASCON128_V13_SOURCES.json).
Preserve the upstream CC0 license and the NIST notice from the generator; the
derived adapter must retain that notice verbatim and append a dated description
of its changes.
The original source identity review is preserved in
[`ascon-qualification-preflight-2026-10-26.md`](ascon-qualification-preflight-2026-10-26.md).
The checked-in upstream known-answer file is the bytewise host oracle; the
upstream generator alone is insufficient because it writes vectors without
comparing them to that file.

The frozen workload has message length `mlen=0..32` in the outer loop and
associated-data length `adlen=0..32` in the inner loop. Both are inclusive, for
1,089 ordered cases. For each case, initialize key and nonce bytes to their
indices 0..15, message bytes to 0..`mlen-1`, and associated-data bytes to
0..`adlen-1`. Pass a null secret-nonce argument to encryption and decryption.

## Required checks

For each ordered case, the host wrapper must:

1. Encrypt once and require success and `clen == mlen + CRYPTO_ABYTES`.
2. Emit the canonical KAT record, including the ciphertext, before mutation.
3. Decrypt the original ciphertext once and require success, exact recovered
   length, and bytewise equality with the original message.
4. Flip only `ct[0] ^= 1`, decrypt once more, and require authentication failure.

The full run must report exactly **1,089 encryptions and 2,178 decryptions**.
Fixed host buffers are 32 bytes each for message, associated data, and recovered
message, 48 bytes for ciphertext, and 16 bytes each for key and nonce. The
zero-length cases still use valid buffer addresses; tampering the first
ciphertext byte therefore tests the first tag byte.

The preflight must parse exactly 1,089 records from both generated output and
the pinned KAT, verify count/order and all six fields (`Count`, `Key`, `Nonce`,
`PT`, `AD`, `CT`), and compare every field byte-for-byte. It must also require
the complete serialized generated output to equal the pinned KAT bytes. A
checksum-only comparison is insufficient. Keep the host comparison table
outside target firmware: expected ciphertexts alone occupy 34,848 bytes.
The C wrapper's rejection paths must also pass fake-API fault-injection tests
for encryption failure, ciphertext-length mismatch, rejection of valid
ciphertext, recovered-length mismatch, wrong recovered plaintext, and acceptance
of tampered ciphertext.

## Evidence and stop gates

Bind the compiler identity, exact compile/run argv and exit status, copied
upstream file hashes, adapter and preflight source hashes, KAT and generated
output hashes, record counts, and all check counts in a fresh immutable result
directory. Preserve stdout, stderr, and the generated KAT bytes. A failed host
run is a terminal preserved result; do not retry with changed inputs or checks.

After host success, perform a complete historical source/candidate-family
overlap audit and review the emitted source-family taxonomy before any native
qualification. A target attempt still requires the unchanged RV32I/ILP32
compiler, 8 KiB RAM with the exact 6,400-byte program/data limit, 128-byte
guard, 1,664-byte stack, twelve legal executable relocation-safe calibrated
formulas, and the same candidate meeting both the public 0.5% projected cycle
reduction and ten timed-replacement minima. Baseline-only qualification keeps
candidate dispatch disabled and preserves its first rejection without rescue.
The host preflight proves none of target lowering, memory fit, candidate-pool
size, integrated execution, correctness on target, area, timing, or speedup.

## Reproduction

From the repository root with Python 3.12 and a host C compiler:

```sh
python scripts/preflight_ascon128_v13.py \
  --output results/2026-10-26-ascon-host-preflight-r3
```

The output root must not already exist. Run focused parser/wrapper tests with:

```sh
python -m pytest tests/test_ascon_preflight.py -q
```
