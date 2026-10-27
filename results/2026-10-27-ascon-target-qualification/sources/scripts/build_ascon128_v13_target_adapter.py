#!/usr/bin/env python3
"""Build the freestanding, single-translation-unit Ascon RV32 test workload.

The generator inlines only quoted includes from the byte-pinned v1.3.0 reference
tree so the existing ISAForge compiler can compile the workload as program.c.
It does not alter the upstream implementation body. The host-only observer
build verifies this exact loop against every pinned KAT record.
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import preflight_ascon128_v13 as preflight

REF = ROOT / preflight.REFDIR
TESTS = ROOT / preflight.TESTDIR
OUTPUT = ROOT / "benchmarks/ascon/ascon128v13_isaforge.c"
EXPECTED_KAT_FNV32 = 0x06CF04E8

def _nist_notice() -> str:
    """Retain the complete notice verbatim from the pinned NIST KAT adapter."""
    host = (ROOT / preflight.WRAPPER).read_text()
    marker = "// This file has been modified."
    if host.count(marker) != 1:
        raise ValueError("Pinned host adapter NIST notice boundary changed")
    notice = host.split(marker, 1)[0]
    if not notice.startswith("// NIST-developed software is provided by NIST"):
        raise ValueError("Complete NIST notice is missing from host adapter")
    return (notice +
        "// This file has been modified. Date: October 27, 2026. Nature of change: "
        "combine the pinned Ascon v1.3.0 reference implementation with a "
        "freestanding 1,089-case benchmark and fail-closed self-check. Preserve "
        "the crypto implementation body. The host-only build emits ciphertexts "
        "for bytewise comparison to the pinned KAT; RV32 additionally checks "
        "the KAT-derived 32-bit fingerprint, round-trip, and tamper rejection. "
        "Source: ascon/ascon-c commit "
        "b7ca60bbf86479785de08b75aab2425dce4e9e8b.\n\n")

TARGET_LOOP = r'''
#include <stdint.h>

#ifndef ASCON_V13_EMIT_HOST_KAT
#define ASCON_V13_EMIT_HOST_KAT 0
#endif
#ifndef ASCON_V13_HOST_TEST_MAIN
#define ASCON_V13_HOST_TEST_MAIN 0
#endif
#ifndef ASCON_V13_FAKE_API
#define ASCON_V13_FAKE_API 0
#endif

#if ASCON_V13_EMIT_HOST_KAT || ASCON_V13_HOST_TEST_MAIN
#include <stdio.h>
#endif

#define ASCON_V13_MAX_MESSAGE 32U
#define ASCON_V13_MAX_AD 32U
#define ASCON_V13_MAX_CIPHERTEXT (ASCON_V13_MAX_MESSAGE + CRYPTO_ABYTES)
#define ASCON_V13_EXPECTED_CASES 1089U
#define ASCON_V13_EXPECTED_ENCRYPTIONS 1089U
#define ASCON_V13_EXPECTED_DECRYPTIONS 2178U
#define ASCON_V13_EXPECTED_KAT_FNV32 0x06cf04e8u

enum {
  ASCON_V13_OK = 0,
  ASCON_V13_ENCRYPT_FAILURE = 1,
  ASCON_V13_CIPHERTEXT_LENGTH_FAILURE = 2,
  ASCON_V13_VALID_DECRYPT_FAILURE = 3,
  ASCON_V13_RECOVERED_LENGTH_FAILURE = 4,
  ASCON_V13_RECOVERED_BYTES_FAILURE = 5,
  ASCON_V13_TAMPER_ACCEPTED_FAILURE = 6,
  ASCON_V13_KAT_OR_COUNT_FAILURE = 7
};

static uint32_t ascon_v13_cases;
static uint32_t ascon_v13_encryptions;
static uint32_t ascon_v13_decryptions;
static uint32_t ascon_v13_failure;
static uint32_t ascon_v13_failure_case;

static int ascon_v13_fail(uint32_t code, uint32_t count) {
  ascon_v13_failure = code;
  ascon_v13_failure_case = count;
  return 0;
}

static void ascon_v13_fill(unsigned char *buffer, uint32_t length) {
  uint32_t i;
  for (i = 0; i < length; ++i) buffer[i] = (unsigned char)i;
}

static int ascon_v13_equal(const unsigned char *left,
                           const unsigned char *right,
                           uint32_t length) {
  uint32_t i;
  for (i = 0; i < length; ++i) {
    if (left[i] != right[i]) return 0;
  }
  return 1;
}

static uint32_t ascon_v13_hash_byte(uint32_t hash, unsigned char value) {
  hash ^= (uint32_t)value;
  return hash * 16777619u;
}

#if ASCON_V13_EMIT_HOST_KAT
static void ascon_v13_emit_bytes(const char *label,
                                 const unsigned char *bytes,
                                 uint32_t length) {
  uint32_t i;
  printf("%s = ", label);
  for (i = 0; i < length; ++i) printf("%02X", (unsigned int)bytes[i]);
  putchar('\n');
}

static void ascon_v13_observe(uint32_t count,
                              const unsigned char *key,
                              const unsigned char *nonce,
                              const unsigned char *message,
                              uint32_t message_length,
                              const unsigned char *associated_data,
                              uint32_t associated_data_length,
                              const unsigned char *ciphertext,
                              uint32_t ciphertext_length) {
  printf("Count = %u\n", (unsigned int)count);
  ascon_v13_emit_bytes("Key", key, CRYPTO_KEYBYTES);
  ascon_v13_emit_bytes("Nonce", nonce, CRYPTO_NPUBBYTES);
  ascon_v13_emit_bytes("PT", message, message_length);
  ascon_v13_emit_bytes("AD", associated_data, associated_data_length);
  ascon_v13_emit_bytes("CT", ciphertext, ciphertext_length);
  putchar('\n');
}
#else
static void ascon_v13_observe(uint32_t count,
                              const unsigned char *key,
                              const unsigned char *nonce,
                              const unsigned char *message,
                              uint32_t message_length,
                              const unsigned char *associated_data,
                              uint32_t associated_data_length,
                              const unsigned char *ciphertext,
                              uint32_t ciphertext_length) {
  (void)count;
  (void)key;
  (void)nonce;
  (void)message;
  (void)message_length;
  (void)associated_data;
  (void)associated_data_length;
  (void)ciphertext;
  (void)ciphertext_length;
}
#endif

void initialise_benchmark(void) {
  ascon_v13_cases = 0;
  ascon_v13_encryptions = 0;
  ascon_v13_decryptions = 0;
  ascon_v13_failure = ASCON_V13_OK;
  ascon_v13_failure_case = 0;
}

void warm_caches(int iterations) {
  (void)iterations;
}

int benchmark(void) {
  unsigned char key[CRYPTO_KEYBYTES];
  unsigned char nonce[CRYPTO_NPUBBYTES];
  unsigned char message[ASCON_V13_MAX_MESSAGE];
  unsigned char recovered[ASCON_V13_MAX_MESSAGE];
  unsigned char associated_data[ASCON_V13_MAX_AD];
  unsigned char ciphertext[ASCON_V13_MAX_CIPHERTEXT];
  uint32_t mlen, adlen, count = 1;
  uint32_t hash = 2166136261u;

  ascon_v13_fill(key, CRYPTO_KEYBYTES);
  ascon_v13_fill(nonce, CRYPTO_NPUBBYTES);

  for (mlen = 0; mlen <= ASCON_V13_MAX_MESSAGE; ++mlen) {
    ascon_v13_fill(message, mlen);
    for (adlen = 0; adlen <= ASCON_V13_MAX_AD; ++adlen) {
      unsigned long long ciphertext_length = 0;
      unsigned long long recovered_length = 0;
      uint32_t i;
      int result;

      ascon_v13_fill(associated_data, adlen);
      result = crypto_aead_encrypt(ciphertext, &ciphertext_length,
          message, (unsigned long long)mlen, associated_data,
          (unsigned long long)adlen, 0, nonce, key);
      ++ascon_v13_encryptions;
      if (result != 0) return ascon_v13_fail(ASCON_V13_ENCRYPT_FAILURE, count);
      if (ciphertext_length != (unsigned long long)(mlen + CRYPTO_ABYTES))
        return ascon_v13_fail(ASCON_V13_CIPHERTEXT_LENGTH_FAILURE, count);

      ascon_v13_observe(count, key, nonce, message, mlen, associated_data,
                        adlen, ciphertext, (uint32_t)ciphertext_length);
      for (i = 0; i < (uint32_t)ciphertext_length; ++i)
        hash = ascon_v13_hash_byte(hash, ciphertext[i]);

      result = crypto_aead_decrypt(recovered, &recovered_length, 0,
          ciphertext, ciphertext_length, associated_data,
          (unsigned long long)adlen, nonce, key);
      ++ascon_v13_decryptions;
      if (result != 0)
        return ascon_v13_fail(ASCON_V13_VALID_DECRYPT_FAILURE, count);
      if (recovered_length != (unsigned long long)mlen)
        return ascon_v13_fail(ASCON_V13_RECOVERED_LENGTH_FAILURE, count);
      if (!ascon_v13_equal(message, recovered, mlen))
        return ascon_v13_fail(ASCON_V13_RECOVERED_BYTES_FAILURE, count);

      /* For mlen=0 this deliberately flips the first byte of the tag. */
      ciphertext[0] ^= 1u;
      result = crypto_aead_decrypt(recovered, &recovered_length, 0,
          ciphertext, ciphertext_length, associated_data,
          (unsigned long long)adlen, nonce, key);
      ++ascon_v13_decryptions;
      if (result == 0)
        return ascon_v13_fail(ASCON_V13_TAMPER_ACCEPTED_FAILURE, count);

      ++ascon_v13_cases;
      ++count;
    }
  }
  return (int)hash;
}

int verify_benchmark(int result) {
  if (ascon_v13_failure != ASCON_V13_OK) return 0;
  if (ascon_v13_cases != ASCON_V13_EXPECTED_CASES ||
      ascon_v13_encryptions != ASCON_V13_EXPECTED_ENCRYPTIONS ||
      ascon_v13_decryptions != ASCON_V13_EXPECTED_DECRYPTIONS) {
    ascon_v13_fail(ASCON_V13_KAT_OR_COUNT_FAILURE, ascon_v13_cases + 1u);
    return 0;
  }
  if ((uint32_t)result != ASCON_V13_EXPECTED_KAT_FNV32) {
    ascon_v13_fail(ASCON_V13_KAT_OR_COUNT_FAILURE, ASCON_V13_EXPECTED_CASES);
    return 0;
  }
  return 1;
}

#if ASCON_V13_HOST_TEST_MAIN
int main(void) {
  int result;
  int correct;
  initialise_benchmark();
  warm_caches(1);
  result = benchmark();
  correct = verify_benchmark(result);
  if (correct) {
    fprintf(stderr, "ASCON_TARGET_HOST PASS cases=%u encryptions=%u decryptions=%u hash=%08x\n",
        (unsigned int)ascon_v13_cases, (unsigned int)ascon_v13_encryptions,
        (unsigned int)ascon_v13_decryptions, (unsigned int)result);
  } else {
    fprintf(stderr, "ASCON_TARGET_HOST FAIL code=%u case=%u\n",
        (unsigned int)ascon_v13_failure, (unsigned int)ascon_v13_failure_case);
  }
  return correct ? 0 : 1;
}
#endif
'''


def _path_label(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def _resolve_quoted(current: Path, name: str) -> Path:
    candidates = [current.parent / name, TESTS / name]
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise ValueError(f"Unpinned quoted include {name!r} from {_path_label(current)}")


def _expand_headers(path: Path, active: tuple[Path, ...] = ()) -> str:
    path = path.resolve()
    if path in active:
        raise ValueError(f"Quoted include cycle: {_path_label(path)}")
    output = [f'#line 1 "{_path_label(path)}"\n']
    for line_number, line in enumerate(path.read_text().splitlines(keepends=True), 1):
        match = re.fullmatch(r'\s*#\s*include\s+"([^"]+)"\s*\n?', line)
        if match:
            include = _resolve_quoted(path, match.group(1))
            output.append(_expand_headers(include, (*active, path)))
            output.append(f'#line {line_number + 1} "{_path_label(path)}"\n')
        else:
            output.append(line)
    return ''.join(output)


def _implementation_body() -> str:
    path = REF / "aead.c"
    lines = path.read_text().splitlines(keepends=True)
    includes = []
    body = []
    for line in lines:
        match = re.fullmatch(r'\s*#\s*include\s+"([^"]+)"\s*\n?', line)
        if match:
            includes.append(match.group(1))
        else:
            body.append(line)
    expected = ["api.h", "ascon.h", "crypto_aead.h", "permutations.h",
                "printstate.h", "word.h"]
    if includes != expected:
        raise ValueError("Pinned upstream aead.c include list changed")
    return ''.join(body)


def _expected_fingerprint() -> tuple[int, int]:
    records = preflight.parse_kat((ROOT / preflight.KAT).read_bytes())
    value = 2166136261
    count = 0
    for row in records:
        ciphertext = bytes.fromhex(row["CT"])
        for byte in ciphertext:
            value = ((value ^ byte) * 16777619) & 0xFFFFFFFF
            count += 1
    return value, count


def build_source() -> bytes:
    preflight.verify_source_copy()
    fingerprint, byte_count = _expected_fingerprint()
    if fingerprint != EXPECTED_KAT_FNV32 or byte_count != 34848:
        raise ValueError("Pinned KAT-derived fingerprint/count differs from adapter contract")
    headers = []
    for name in ("api.h", "ascon.h", "constants.h", "crypto_aead.h",
                 "permutations.h", "printstate.h", "round.h", "word.h"):
        path = (TESTS if name == "crypto_aead.h" else REF) / name
        headers.append(_expand_headers(path))
    implementation = _implementation_body()
    source = (_nist_notice() +
        "\n/* Deterministically generated by scripts/build_ascon128_v13_target_adapter.py. */\n" +
        "\n".join(headers) +
        "\n#ifndef ASCON_V13_FAKE_API\n#define ASCON_V13_FAKE_API 0\n#endif\n" +
        "#if !ASCON_V13_FAKE_API\n#line 1 \"" + _path_label(REF / "aead.c") + "\"\n" +
        implementation + "\n#endif /* !ASCON_V13_FAKE_API */\n" + TARGET_LOOP)
    return source.encode("utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true",
                      help="create the adapter, refusing to replace different bytes")
    mode.add_argument("--replace", action="store_true",
                      help="replace the generated adapter with its deterministic output")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    expected = build_source()
    if args.write:
        if OUTPUT.exists() and OUTPUT.read_bytes() != expected:
            raise SystemExit(f"refusing to overwrite changed adapter: {OUTPUT}")
        if not OUTPUT.exists():
            OUTPUT.write_bytes(expected)
        print(f"wrote {OUTPUT.relative_to(ROOT)} sha256={hashlib.sha256(expected).hexdigest()}")
        return 0
    if args.replace:
        OUTPUT.write_bytes(expected)
        print(f"replaced {OUTPUT.relative_to(ROOT)} sha256={hashlib.sha256(expected).hexdigest()}")
        return 0
    if not OUTPUT.is_file() or OUTPUT.read_bytes() != expected:
        raise SystemExit("checked-in Ascon target adapter differs from deterministic build")
    print(f"verified {OUTPUT.relative_to(ROOT)} sha256={hashlib.sha256(expected).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
