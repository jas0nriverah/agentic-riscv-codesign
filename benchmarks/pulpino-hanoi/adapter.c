/* ISAForge freestanding benchmark adapter for the pinned PULPino Hanoi test.
 * The original twelve-plate input, recursive solver, and destination-array
 * oracle are preserved. Setup is inside the measured benchmark invocation.
 */
#include "algorithm.c"

#define NR_PLATES 12

static char A[NR_PLATES];
static char B[NR_PLATES];
static char C[NR_PLATES];

void computeGold(int, char*, char*, char*);

void initialise_benchmark(void) { }
void warm_caches(int iterations) { (void)iterations; }

int benchmark(void)
{
    for (int i = 0; i < NR_PLATES; i++) {
        A[i] = i;
        B[i] = 0;
        C[i] = 0;
    }
    computeGold(NR_PLATES, A, B, C);
    return 1;
}

int verify_benchmark(int result)
{
    if (result != 1) return 0;
    for (int i = 0; i < NR_PLATES; i++)
        if (B[i] != i) return 0;
    return 1;
}
