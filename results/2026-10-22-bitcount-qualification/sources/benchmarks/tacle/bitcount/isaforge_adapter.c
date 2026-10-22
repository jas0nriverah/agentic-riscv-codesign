/* External TACLeBench ABI adapter; all included upstream bytes are unchanged.
 * A single translation unit lets the existing source-marker/rewriter cover all
 * five files. The two private lookup arrays retain separate storage. This is a
 * declared amalgamated -Os context, not the upstream separate-object build.
 */
_Static_assert(sizeof(long) == 4, "TACLeBench bitcount requires ILP32 here");

#define main isaforge_tacle_original_main
#include "bitcount.c"
#undef main
#include "bitcnt_1.c"
#include "bitcnt_2.c"
#define bitcount_bits isaforge_bitcount_bits_3
#include "bitcnt_3.c"
#undef bitcount_bits
#define bitcount_bits isaforge_bitcount_bits_4
#include "bitcnt_4.c"
#undef bitcount_bits

void initialise_benchmark(void) { bitcount_init(); }
void warm_caches(int heat) { (void)heat; }
int benchmark(void) {
    bitcount_main();
    return bitcount_return();
}
int verify_benchmark(int result) {
    return result == 0 && bitcount_return() == 0;
}
