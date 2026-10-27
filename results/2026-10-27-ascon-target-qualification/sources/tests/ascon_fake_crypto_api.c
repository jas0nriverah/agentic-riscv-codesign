/* Deliberately small API double used only to test host-wrapper rejection paths. */
#include <string.h>

#include "api.h"
#include "crypto_aead.h"

#ifndef ASCON_FAULT
#define ASCON_FAULT 0
#endif

int crypto_aead_encrypt(unsigned char *c, unsigned long long *clen,
    const unsigned char *m, unsigned long long mlen,
    const unsigned char *ad, unsigned long long adlen,
    const unsigned char *nsec, const unsigned char *npub,
    const unsigned char *k) {
  (void)ad;
  (void)adlen;
  (void)nsec;
  (void)npub;
  (void)k;
#if ASCON_FAULT == 1
  (void)c;
  (void)clen;
  (void)m;
  (void)mlen;
  return -1;
#else
  *clen = mlen + CRYPTO_ABYTES;
#if ASCON_FAULT == 2
  --*clen;
#endif
  memset(c, 0, (size_t)*clen);
  if (mlen > 0 && *clen >= mlen + CRYPTO_ABYTES)
    memcpy(c + CRYPTO_ABYTES, m, (size_t)mlen);
  return 0;
#endif
}

int crypto_aead_decrypt(unsigned char *m, unsigned long long *mlen,
    unsigned char *nsec, const unsigned char *c,
    unsigned long long clen, const unsigned char *ad,
    unsigned long long adlen, const unsigned char *npub,
    const unsigned char *k) {
  unsigned long long length;
  unsigned long long i;
  int tampered;
  (void)nsec;
  (void)ad;
  (void)adlen;
  (void)npub;
  (void)k;
  if (clen < CRYPTO_ABYTES) return -1;
  tampered = c[0] != 0;
#if ASCON_FAULT == 3
  if (!tampered) return -1;
#endif
  length = clen - CRYPTO_ABYTES;
  *mlen = length;
#if ASCON_FAULT == 4
  if (!tampered) ++*mlen;
#endif
  for (i = 0; i < length; ++i) m[i] = c[CRYPTO_ABYTES + i];
#if ASCON_FAULT == 5
  if (!tampered && length == 1) m[0] ^= 1U;
#endif
  if (!tampered) return 0;
#if ASCON_FAULT == 6
  return 0;
#else
  return -1;
#endif
}
