/*
 * ISAForge ABI adapter for the pinned MiBench Pratt-Boyer-Moore small case.
 * The upstream search source and its 57 literal input pairs are included
 * unchanged. Only main/console output are adapted to the existing freestanding
 * Embench ABI. The output shim records returned offsets for the post-timing
 * correctness check; its small bookkeeping cost is inside benchmark cycles.
 */
#include <limits.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

size_t strlen(const char *s) {
    const char *end = s;
    while (*end) ++end;
    return (size_t)(end - s);
}

int strncmp(const char *left, const char *right, size_t count) {
    while (count != 0) {
        unsigned char a = (unsigned char)*left++;
        unsigned char b = (unsigned char)*right++;
        if (a != b) return (int)a - (int)b;
        if (a == 0) return 0;
        --count;
    }
    return 0;
}

enum { MIBENCH_STRINGSEARCH_CASES = 57 };

static const int expected_offsets[MIBENCH_STRINGSEARCH_CASES] = {
     1,  0, -1,  4,  2,  0,  3,  1,  2, -1,  0,  0, -1, 21, 19, 30,
     0, -1, 10, 12, -1, -1,  8,  7, -1, -1, 11, 15, 12, -1, -1,  7,
     0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1,
    20, 10, 27, 19, -1,  8, -1, 19, -1
};

static int observed_offsets[MIBENCH_STRINGSEARCH_CASES];
static int observed_found[MIBENCH_STRINGSEARCH_CASES];
static int observed_cases;
static int capture_error;
static int current_found;
static int current_offset;
static const char *current_text;

static void record_report(const char *format, const char *needle,
                          const char *negation, const char *text) {
    (void)format;
    (void)needle;
    if (current_text != NULL || observed_cases >= MIBENCH_STRINGSEARCH_CASES) {
        capture_error = 1;
        return;
    }
    current_text = text;
    current_found = negation[0] == '\0';
    current_offset = -1;
}

static void record_suffix(const char *format, const char *suffix) {
    uintptr_t text_address;
    uintptr_t suffix_address;
    (void)format;
    if (current_text == NULL || !current_found) {
        capture_error = 1;
        return;
    }
    text_address = (uintptr_t)current_text;
    suffix_address = (uintptr_t)suffix;
    if (suffix_address < text_address ||
        suffix_address - text_address > (uintptr_t)INT_MAX) {
        capture_error = 1;
        return;
    }
    current_offset = (int)(suffix_address - text_address);
}

static int record_newline(int character) {
    if (character != '\n' || current_text == NULL ||
        observed_cases >= MIBENCH_STRINGSEARCH_CASES) {
        capture_error = 1;
        return character;
    }
    observed_found[observed_cases] = current_found;
    observed_offsets[observed_cases] = current_offset;
    ++observed_cases;
    current_text = NULL;
    current_found = 0;
    current_offset = -1;
    return character;
}

/* The upstream small driver uses only these two printf arities. */
#define ISA_PRINTF_SELECT(_1, _2, _3, _4, NAME, ...) NAME
#define printf(...) ISA_PRINTF_SELECT(__VA_ARGS__, record_report, \
                                      isaforge_unused_printf3, \
                                      record_suffix)(__VA_ARGS__)
#define putchar(character) record_newline(character)
#define main int isaforge_mibench_stringsearch_main
#include "pbmsrch_small.c"
#undef main
#undef putchar
#undef printf

void initialise_benchmark(void) {
    observed_cases = 0;
    capture_error = 0;
    current_found = 0;
    current_offset = -1;
    current_text = NULL;
}

void warm_caches(int heat) {
    (void)heat;
}

int benchmark(void) {
    (void)isaforge_mibench_stringsearch_main();
    return observed_cases;
}

int verify_benchmark(int result) {
    int i;
    if (result != MIBENCH_STRINGSEARCH_CASES ||
        observed_cases != MIBENCH_STRINGSEARCH_CASES || capture_error ||
        current_text != NULL) return 0;
    for (i = 0; i < MIBENCH_STRINGSEARCH_CASES; ++i) {
        int expected_found = expected_offsets[i] >= 0;
        if (observed_found[i] != expected_found ||
            observed_offsets[i] != expected_offsets[i]) return 0;
    }
    return 1;
}
