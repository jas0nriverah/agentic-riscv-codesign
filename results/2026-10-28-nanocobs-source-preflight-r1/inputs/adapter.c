/* Preflight ABI only: preserve every upstream probe input and assertion. */
#define main nanocobs_probe_main
#include "upstream/tests/qemu/probe.c"
#undef main
void probe_init(void) {}
void probe_puts(char const *s) { (void)s; }
void probe_putu(unsigned long v) { (void)v; }
void probe_done(int bad) { (void)bad; }
void initialise_benchmark(void) { passed = 0; failed = 0; }
void warm_caches(int n) { (void)n; }
int benchmark(void) { return nanocobs_probe_main(); }
int verify_benchmark(int r) { return r == 0 && failed == 0 && passed == 8215; }
