// Minimal freestanding byte-memory routines used by unmodified Embench sources.
// Compile with -fno-builtin; no host libc or ISA-specific assembly is required.
#include <stddef.h>
void *memcpy(void *destination, const void *source, size_t n) {
    unsigned char *d=destination;
    const unsigned char *s=source;
    for (size_t i=0; i<n; ++i) d[i]=s[i];
    return destination;
}
void *memset(void *destination, int value, size_t n) {
    unsigned char *d=destination;
    for (size_t i=0; i<n; ++i) d[i]=(unsigned char)value;
    return destination;
}
int memcmp(const void *first, const void *second, size_t n) {
    const unsigned char *a=first, *b=second;
    for (size_t i=0; i<n; ++i) if (a[i]!=b[i]) return (int)a[i]-(int)b[i];
    return 0;
}

// Freestanding assertion failure: terminate the SoC with a failing status.
__attribute__((noreturn)) void exit(int status) {
    (void)status;
    *(volatile unsigned int *)0x10000004 = 0xdead0005;
    for (;;) { }
}
