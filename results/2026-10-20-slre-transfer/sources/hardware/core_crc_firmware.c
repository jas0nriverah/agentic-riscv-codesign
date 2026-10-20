// Embench's benchmark(), random generator and table are separate upstream TUs.
#include <stdint.h>
extern void initialise_benchmark(void), warm_caches(int), srand_beebs(unsigned);
extern int benchmark(void), verify_benchmark(int);
extern unsigned long crc32pseudo(void);
static inline uint32_t cycles(void) {
    uint32_t v; __asm__ volatile ("rdcycle %0" : "=r"(v) :: "memory"); return v;
}
static inline uint32_t instructions(void) {
    uint32_t v; __asm__ volatile ("rdinstret %0" : "=r"(v) :: "memory"); return v;
}
int main(void) {
    initialise_benchmark();
    srand_beebs(0);
    uint32_t full_checksum=crc32pseudo();
    warm_caches(1);
    uint32_t i0=instructions(), c0=cycles();
    int result=benchmark();
    uint32_t c1=cycles(), i1=instructions();
    volatile uint32_t *out=(volatile uint32_t *)0x10000000;
    *out=full_checksum; *out=(uint32_t)result; *out=c1-c0; *out=i1-i0;
    *out=verify_benchmark(result);
    *(volatile uint32_t *)0x10000004 = verify_benchmark(result) ? 0x600d600d : 0xdead0003;
    return 0;
}
