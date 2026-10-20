// Minimal C-locale support for unmodified Embench SLRE on pinned newlib headers.
// Table index 0 is EOF; indexes 1..256 represent unsigned char values 0..255.
#include <stddef.h>
#include <ctype.h>
#ifdef __NEWLIB__
_Static_assert(_U==1 && _L==2 && _N==4 && _S==8 && _P==16 && _C==32 && _X==64 && _B==128,
               "Unsupported newlib character-table ABI");
#endif
const char _ctype_[257] = {
    0,
    32, 32, 32, 32, 32, 32, 32, 32, 32, 40, 40, 40, 40, 40, 32, 32,
    32, 32, 32, 32, 32, 32, 32, 32, 32, 32, 32, 32, 32, 32, 32, 32,
    (char)136, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16,
    4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 16, 16, 16, 16, 16, 16,
    16, 65, 65, 65, 65, 65, 65, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 16, 16, 16, 16, 16,
    16, 66, 66, 66, 66, 66, 66, 2, 2, 2, 2, 2, 2, 2, 2, 2,
    2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 16, 16, 16, 16, 32,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
};
size_t strlen(const char *s) {
    const char *end=s;
    while (*end) ++end;
    return (size_t)(end-s);
}
char *strchr(const char *s, int c) {
    unsigned char target=(unsigned char)c;
    for (;;) {
        if ((unsigned char)*s==target) return (char *)s;
        if (!*s) return NULL;
        ++s;
    }
}

