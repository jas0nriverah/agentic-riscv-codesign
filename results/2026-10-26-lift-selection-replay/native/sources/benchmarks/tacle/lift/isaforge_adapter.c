/* External TACLeBench ABI/amalgamation adapter; included files are unchanged.
 * Preserve the original1001 zero-input controller iterations/checksum4005888.
 * No original lift_* symbol or storage is renamed or combined.
 */
_Static_assert(sizeof(int) == 4 && sizeof(long) == 4 && sizeof(void *) == 4,
               "TACLeBench lift requires the declared ILP32 layout");
_Static_assert(sizeof(short) == 2 && __CHAR_BIT__ == 8,
               "TACLeBench lift requires16-bit short and8-bit bytes");
#define main isaforge_tacle_lift_original_main
#include "lift.c"
#undef main
#include "liftlibio.c"
#include "liftlibcontrol.c"
_Static_assert(sizeof(lift_ctrl_io_in) == 40 && sizeof(lift_ctrl_io_out) == 16 &&
               sizeof(lift_ctrl_io_analog) == 16 && sizeof(lift_ctrl_io_led) == 64 &&
               sizeof(lift_levelPos) == 64, "Original lift array layout required");

void initialise_benchmark(void) { lift_init(); }
void warm_caches(int heat) { (void)heat; }
int benchmark(void) {
    lift_main();
    return lift_return();
}
int verify_benchmark(int result) {
    return result == 0 && lift_return() == 0;
}
