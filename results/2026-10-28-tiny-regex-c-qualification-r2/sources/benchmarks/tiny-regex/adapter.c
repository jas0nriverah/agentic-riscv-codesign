/* ISAForge freestanding adapter for the pinned upstream 76-case test suite.
 * The test table and regex implementation remain byte-for-byte upstream.
 * Console output is suppressed; upstream main's failure count is the result.
 */
#include <stddef.h>

#define printf(...) ((void)0)
#define fprintf(...) ((void)0)
#define re_print isaforge_tiny_regex_diagnostic_print
#define main isaforge_tiny_regex_upstream_test_main
#include "upstream/re.c"
#include "upstream/tests/test1.c"
#undef main
#undef re_print
#undef fprintf
#undef printf

/* The upstream implementation uses the C-locale classification functions.
 * These ASCII definitions are sufficient for the pinned fixed inputs and
 * preserve the C-locale classes for every ASCII byte.
 */
int isdigit(int value) {
    return value >= '0' && value <= '9';
}

int isalpha(int value) {
    return (value >= 'A' && value <= 'Z') ||
           (value >= 'a' && value <= 'z');
}

int isspace(int value) {
    return value == ' ' || value == '\f' || value == '\n' ||
           value == '\r' || value == '\t' || value == '\v';
}

void initialise_benchmark(void) {}

void warm_caches(int heat) {
    (void)heat;
}

int benchmark(void) {
    if (sizeof(test_vector) / sizeof(test_vector[0]) != 76) return -1;
    return isaforge_tiny_regex_upstream_test_main();
}

size_t isaforge_tiny_regex_case_count(void) {
    return sizeof(test_vector) / sizeof(test_vector[0]);
}

int verify_benchmark(int result) {
    return result == 0;
}
