// NIST-developed software is provided by NIST as a public service.
// You may use, copy and distribute copies of the software in any medium,
// provided that you keep intact this entire notice. You may improve,
// modify and create derivative works of the software or any portion of
// the software, and you may copy and distribute such modifications or
// works. Modified works should carry a notice stating that you changed
// the software and should note the date and nature of the change.
// Please explicitly acknowledge the National Institute of Standards and
// Technology as the source of the software.
//
// NIST-developed software is expressly provided "AS IS." NIST MAKES NO
// WARRANTY OF ANY KIND, EXPRESS, IMPLIED, IN FACT OR ARISING BY OPERATION
// OF LAW, INCLUDING, WITHOUT LIMITATION, THE IMPLIED WARRANTY OF
// MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, NON-INFRINGEMENT AND DATA
// ACCURACY. NIST NEITHER REPRESENTS NOR WARRANTS THAT THE OPERATION OF THE
// SOFTWARE WILL BE UNINTERRUPTED OR ERROR-FREE, OR THAT ANY DEFECTS WILL BE
// CORRECTED. NIST DOES NOT WARRANT OR MAKE ANY REPRESENTATIONS REGARDING THE
// USE OF THE SOFTWARE OR THE RESULTS THEREOF, INCLUDING BUT NOT LIMITED TO THE
// CORRECTNESS, ACCURACY, RELIABILITY, OR USEFULNESS OF THE SOFTWARE.
//
// You are solely responsible for determining the appropriateness of using and
// distributing the software and you assume all risks associated with its use,
// including but not limited to the risks and costs of program errors,
// compliance with applicable laws, damage to or loss of data, programs or
// equipment, and the unavailability or interruption of operation. This software
// is not intended to be used in any situation where a failure could cause risk
// of injury or damage to property. The software developed by NIST employees is
// not subject to copyright protection within the United States.
//
// This file has been modified. Date: October 26, 2026. Nature of change: adapt
// the pinned Ascon v1.3.0 KAT generator to fixed host buffers/stdout; check
// output length, recovered plaintext and first-byte tamper rejection; and emit
// runtime API call counts. Source: ascon/ascon-c commit
// b7ca60bbf86479785de08b75aab2425dce4e9e8b, tests/genkat_aead.c.
//
// The KAT output is captured and compared byte-for-byte against the pinned
// upstream vector file by scripts/preflight_ascon128_v13.py.

#include <stdio.h>
#include <string.h>

#include "api.h"
#include "crypto_aead.h"

#define MAX_MESSAGE_LENGTH 32U
#define MAX_ASSOCIATED_DATA_LENGTH 32U
#define MAX_CIPHERTEXT_LENGTH (MAX_MESSAGE_LENGTH + CRYPTO_ABYTES)
#define EXPECTED_RECORD_COUNT 1089U

static int fail(unsigned int count, const char *reason) {
  fprintf(stderr, "case %u: %s\n", count, reason);
  return 1;
}

static void init_buffer(unsigned char *buffer, unsigned int length) {
  unsigned int i;
  for (i = 0; i < length; ++i) buffer[i] = (unsigned char)i;
}

static void emit_bytes(const char *label, const unsigned char *data,
                       unsigned int length) {
  unsigned int i;
  fputs(label, stdout);
  for (i = 0; i < length; ++i) printf("%02X", (unsigned int)data[i]);
  fputc('\n', stdout);
}

int main(void) {
  unsigned char key[CRYPTO_KEYBYTES];
  unsigned char nonce[CRYPTO_NPUBBYTES];
  unsigned char message[MAX_MESSAGE_LENGTH];
  unsigned char recovered[MAX_MESSAGE_LENGTH];
  unsigned char associated_data[MAX_ASSOCIATED_DATA_LENGTH];
  unsigned char ciphertext[MAX_CIPHERTEXT_LENGTH];
  unsigned int mlen, adlen, count = 1U;
  unsigned int encryptions = 0U, decryptions = 0U;

  init_buffer(key, CRYPTO_KEYBYTES);
  init_buffer(nonce, CRYPTO_NPUBBYTES);

  for (mlen = 0; mlen <= MAX_MESSAGE_LENGTH; ++mlen) {
    init_buffer(message, mlen);

    for (adlen = 0; adlen <= MAX_ASSOCIATED_DATA_LENGTH; ++adlen) {
      unsigned long long ciphertext_length = 0;
      unsigned long long recovered_length = 0;
      int result;

      init_buffer(associated_data, adlen);
      result = crypto_aead_encrypt(ciphertext, &ciphertext_length,
          message, (unsigned long long)mlen, associated_data,
          (unsigned long long)adlen, NULL, nonce, key);
      ++encryptions;
      if (result != 0) return fail(count, "encryption failed");
      if (ciphertext_length != (unsigned long long)(mlen + CRYPTO_ABYTES))
        return fail(count, "encryption returned an unexpected ciphertext length");

      /* Preserve upstream Count/Key/Nonce/PT/AD/CT order before tampering. */
      printf("Count = %u\n", count);
      emit_bytes("Key = ", key, CRYPTO_KEYBYTES);
      emit_bytes("Nonce = ", nonce, CRYPTO_NPUBBYTES);
      emit_bytes("PT = ", message, mlen);
      emit_bytes("AD = ", associated_data, adlen);
      emit_bytes("CT = ", ciphertext, (unsigned int)ciphertext_length);
      fputc('\n', stdout);

      result = crypto_aead_decrypt(recovered, &recovered_length, NULL,
          ciphertext, ciphertext_length, associated_data,
          (unsigned long long)adlen, nonce, key);
      ++decryptions;
      if (result != 0) return fail(count, "valid ciphertext was rejected");
      if (recovered_length != (unsigned long long)mlen)
        return fail(count, "decryption returned an unexpected plaintext length");
      if (memcmp(message, recovered, mlen) != 0)
        return fail(count, "decryption did not recover the original plaintext");

      /* For mlen=0 this deliberately flips the first byte of the tag. */
      ciphertext[0] ^= 1U;
      result = crypto_aead_decrypt(recovered, &recovered_length, NULL,
          ciphertext, ciphertext_length, associated_data,
          (unsigned long long)adlen, nonce, key);
      ++decryptions;
      if (result == 0) return fail(count, "tampered ciphertext was accepted");

      ++count;
    }
  }

  if (count != EXPECTED_RECORD_COUNT + 1U)
    return fail(count, "unexpected number of cases");
  if (encryptions != EXPECTED_RECORD_COUNT ||
      decryptions != 2U * EXPECTED_RECORD_COUNT)
    return fail(count - 1U, "unexpected crypto API call counts");
  if (ferror(stdout)) return fail(count - 1U, "failed while writing KAT records");
  fprintf(stderr, "ASCON_HOST_PREFLIGHT PASS cases=%u encryptions=%u decryptions=%u\n",
      count - 1U, encryptions, decryptions);
  return 0;
}
