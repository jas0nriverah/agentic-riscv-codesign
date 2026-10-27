// Workload-independent Embench harness on the existing serial-report SoC.
#include <stdint.h>
extern void initialise_benchmark(void), warm_caches(int);
extern int benchmark(void), verify_benchmark(int);
static inline uint32_t cycles(void) {
    uint32_t v; __asm__ volatile("rdcycle %0" : "=r"(v) :: "memory"); return v;
}
static inline uint32_t instructions(void) {
    uint32_t v; __asm__ volatile("rdinstret %0" : "=r"(v) :: "memory"); return v;
}
int main(void) {
    initialise_benchmark();
    warm_caches(1);
    uint32_t i0=instructions(), c0=cycles();
    int result=benchmark();
    uint32_t c1=cycles(), i1=instructions();
    int correct=verify_benchmark(result);
    volatile uint32_t *out=(volatile uint32_t *)0x10000000;
    *out=0x49534146; *out=(uint32_t)result; *out=c1-c0; *out=i1-i0; *out=correct;
    *(volatile uint32_t *)0x10000004=correct ? 0x600d600d : 0xdead0003;
    return 0;
}
