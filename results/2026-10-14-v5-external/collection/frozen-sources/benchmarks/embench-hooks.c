#include <stdint.h>

volatile uint32_t instret_start, instret_stop;

static inline uint32_t read_instret(void)
{
    uint32_t v;
    __asm__ volatile(".option push\n.option arch, +zicsr\ncsrr %0, 0xC02\n.option pop" : "=r"(v));
    return v;
}

void initialise_board(void) {}
void __attribute__((noinline)) start_trigger(void) { instret_start = read_instret(); }
void __attribute__((noinline)) stop_trigger(void)  { instret_stop  = read_instret(); }
