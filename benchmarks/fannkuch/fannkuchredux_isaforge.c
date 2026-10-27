/* The Computer Language Benchmarks Game
 * https://salsa.debian.org/benchmarksgame-team/benchmarksgame/
 *
 * converted to C by Joseph Piché
 * from Java version by Oleg Mazurov and Isaac Gouy
 *
 */

#include <limits.h>
#include <stdint.h>

inline static int max(int a, int b)
{
    return a > b ? a : b;
}

static int fannkuchredux(int n, int *checksum_out)
{
    int perm[n];
    int perm1[n];
    int count[n];
    int maxFlipsCount = 0;
    int permCount = 0;
    int checksum = 0;

    int i;

    for (i=0; i<n; i+=1)
        perm1[i] = i;
    int r = n;

    while (1) {
        while (r != 1) {
            count[r-1] = r;
            r -= 1;
        }

        for (i=0; i<n; i+=1)
            perm[i] = perm1[i];
        int flipsCount = 0;
        int k;

        while ( !((k = perm[0]) == 0) ) {
            int k2 = (k+1) >> 1;
            for (i=0; i<k2; i++) {
                int temp = perm[i]; perm[i] = perm[k-i]; perm[k-i] = temp;
            }
            flipsCount += 1;
        }

        maxFlipsCount = max(maxFlipsCount, flipsCount);
        checksum += permCount % 2 == 0 ? flipsCount : -flipsCount;

        /* Use incremental change to generate another permutation */
        while (1) {
            if (r == n) {
                *checksum_out = checksum;
                return maxFlipsCount;
            }

            int perm0 = perm1[0];
            i = 0;
            while (i < r) {
                int j = i + 1;
                perm1[i] = perm1[j];
                i = j;
            }
            perm1[r] = perm0;
            count[r] = count[r] - 1;
            if (count[r] > 0) break;
            r++;
        }
        permCount++;
    }
}

_Static_assert(CHAR_BIT == 8, "ISAForge requires 8-bit bytes");
_Static_assert(sizeof(int) == 4, "ISAForge requires 32-bit int");
_Static_assert(INT_MIN == INT32_MIN && INT_MAX == INT32_MAX,
               "ISAForge requires signed 32-bit int");

static int encode_result(int checksum, int maximum_flips)
{
    uint32_t packed;

    if (checksum < -32768 || checksum > 32767 ||
        maximum_flips < 0 || maximum_flips > 32767) {
        return -1;
    }
    packed = ((uint32_t)(checksum + 32768) << 15) |
             (uint32_t)maximum_flips;
    return (int)packed;
}

static int decode_result(int result, int *checksum_out, int *maximum_flips_out)
{
    if (result < 0 || checksum_out == 0 || maximum_flips_out == 0) {
        return 0;
    }
    *checksum_out = (int)((uint32_t)result >> 15) - 32768;
    *maximum_flips_out = (int)((uint32_t)result & 0x7fffU);
    return 1;
}

void initialise_benchmark(void)
{
}

void warm_caches(int max_iterations)
{
    (void)max_iterations;
}

int benchmark(void)
{
    int checksum = 0;
    int maximum_flips = fannkuchredux(7, &checksum);

    return encode_result(checksum, maximum_flips);
}

int verify_benchmark(int result)
{
    int checksum;
    int maximum_flips;

    if (!decode_result(result, &checksum, &maximum_flips)) {
        return 0;
    }
    return checksum == 228 && maximum_flips == 16;
}
