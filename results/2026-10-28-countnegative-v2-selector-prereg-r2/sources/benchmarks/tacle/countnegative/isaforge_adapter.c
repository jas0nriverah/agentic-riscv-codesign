/* External benchmark ABI adapter; upstream countnegative.c is unchanged. */
_Static_assert(sizeof(int) == 4, "TACLeBench countnegative requires RV32 ILP32");
#define main isaforge_tacle_original_main
#include "countnegative.c"
#undef main

void initialise_benchmark(void) { countnegative_init(); }
void warm_caches(int heat) { (void)heat; }
int benchmark(void) {
    countnegative_main();
    return countnegative_return();
}
int verify_benchmark(int result) {
    return result == 0 && countnegative_return() == 0;
}
