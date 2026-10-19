#include <stdint.h>
#include "vectors.h"
extern uint32_t formula0(uint32_t, uint32_t), formula1(uint32_t, uint32_t);
extern uint32_t run0(uint32_t, uint32_t, uint32_t), run1(uint32_t, uint32_t, uint32_t);
static inline uint32_t cycles(void) {
    uint32_t v; __asm__ volatile ("rdcycle %0" : "=r"(v) :: "memory"); return v;
}
static inline uint32_t instructions(void) {
    uint32_t v; __asm__ volatile ("rdinstret %0" : "=r"(v) :: "memory"); return v;
}
static inline uint32_t reference(unsigned f, uint32_t a, uint32_t b) {
    return f == 0 ? ((a ^ b) & 255u) << 2 : a ^ (b >> 8);
}
static void emit(uint32_t kind, uint32_t f, uint32_t n, uint32_t a, uint32_t b,
                 uint32_t result, uint32_t c, uint32_t i) {
    volatile uint32_t *out = (volatile uint32_t *)0x10000000;
    *out=kind; *out=f; *out=n; *out=a; *out=b; *out=result; *out=c; *out=i;
}
int main(void) {
    const unsigned lengths[] = {0, 1, 8, 64, 256, 1024};
    for (unsigned f=0; f<2; f++) {
        for (unsigned v=0; v<VECTOR_COUNT; v++) {
            uint32_t a=vectors[v][0], b=vectors[v][1];
            uint32_t result = f == 0 ? formula0(a,b) : formula1(a,b);
            if (result != reference(f,a,b)) {
                *(volatile uint32_t *)0x10000004 = 0xdead0001; return 1;
            }
            emit(0,f,1,a,b,result,0,0);
        }
        for (unsigned s=0; s<3; s++) {
            for (unsigned l=0; l<sizeof(lengths)/sizeof(lengths[0]); l++) {
                unsigned n=lengths[l];
                uint32_t a=vectors[VECTOR_COUNT-1-s][0], b=vectors[VECTOR_COUNT-1-s][1];
                uint32_t i0=instructions(), c0=cycles();
                uint32_t result = f == 0 ? run0(a,b,n) : run1(a,b,n);
                uint32_t c1=cycles(), i1=instructions();
                uint32_t expected=a, second=b;
                for (unsigned k=0; k<n; k++) {
                    expected=reference(f,expected,second);
                    second += 0x9e3779b9u;
                }
                if (result != expected) {
                    *(volatile uint32_t *)0x10000004 = 0xdead0002; return 2;
                }
                emit(1,f,n,a,b,result,c1-c0,i1-i0);
            }
        }
    }
    *(volatile uint32_t *)0x10000004 = 0x600d600d;
    return 0;
}
