/* ISAForge adapter for the exact LLVM Stanford Queens fixed workload.
 * Upstream Queens.c remains unchanged, including all 100 x 50 solves.
 * Its only failure signal is printf(" Error in Queens.\n"). Preserve that
 * signal in volatile state; never replace the output calls with no-ops.
 * Check the original 1..100 output sequence without a libc or output buffer.
 * The LLVM license accompanying the upstream file is in LICENSE.TXT.
 */
#include <stdarg.h>

static volatile unsigned int output_errors;
static volatile unsigned int output_calls;
static volatile unsigned int expected_next;

static int equal_text(const char *left, const char *right) {
    while (*left && *left == *right) {
        ++left;
        ++right;
    }
    return *left == *right;
}

void isaforge_queens_reset_output(void) {
    output_errors = 0;
    output_calls = 0;
    expected_next = 1;
}

int isaforge_queens_printf(const char *format, ...) {
    if (equal_text(format, "%d\n")) {
        va_list arguments;
        va_start(arguments, format);
        int value = va_arg(arguments, int);
        va_end(arguments);
        if (value < 1 || value > 100 || (unsigned int)value != expected_next)
            ++output_errors;
        ++output_calls;
        ++expected_next;
    } else {
        /* Includes the exact upstream failure string and any unexpected text. */
        ++output_errors;
    }
    return 0; /* The original program ignores printf's result. */
}

#define printf isaforge_queens_printf
#define main isaforge_queens_upstream_main
#include "upstream/Queens.c"
#undef main
#undef printf

unsigned int isaforge_queens_output_calls(void) { return output_calls; }
unsigned int isaforge_queens_output_errors(void) { return output_errors; }

int isaforge_queens_output_valid(void) {
    return output_errors == 0 && output_calls == 100 && expected_next == 101;
}

void initialise_benchmark(void) { isaforge_queens_reset_output(); }
void warm_caches(int heat) { (void)heat; }

int benchmark(void) {
    isaforge_queens_reset_output();
    int result = isaforge_queens_upstream_main();
    return result == 0 && isaforge_queens_output_valid() ? 0 : -1;
}

int verify_benchmark(int result) {
    return result == 0 && isaforge_queens_output_valid();
}
