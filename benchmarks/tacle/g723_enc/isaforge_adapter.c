/* External ABI adapter; included TACLeBench source bytes remain unchanged.
 * Original 256 A-law samples, encoder and checksum 24284 are preserved.
 */
_Static_assert(sizeof(long) == 4, "TACLeBench g723_enc requires ILP32 here");
#define main isaforge_tacle_original_main
#include "g723_enc.c"
#undef main

void initialise_benchmark(void) { g723_enc_init(); }
void warm_caches(int heat) { (void)heat; }
int benchmark(void) {
    g723_enc_main();
    return g723_enc_return();
}
int verify_benchmark(int result) {
    return result == 0 && g723_enc_return() == 0;
}
