/* External ABI adapter; included original TACLeBench source is unchanged.
 * N=16, all four 32-float arrays, initialization and checksum144.0f remain.
 * The original checksum covers the first16 of32 D elements only.
 */
_Static_assert(sizeof(int) == 4 && sizeof(long) == 4 && sizeof(void *) == 4,
               "This context requires ILP32");
_Static_assert(sizeof(float) == 4, "This context requires 32-bit float");
#define main isaforge_tacle_original_main
#include "complex_updates.c"
#undef main

void initialise_benchmark(void) { complex_updates_init(); }
void warm_caches(int heat) { (void)heat; }
int benchmark(void) {
    complex_updates_main();
    return complex_updates_return();
}
int verify_benchmark(int result) {
    return result == 0 && complex_updates_return() == 0;
}
