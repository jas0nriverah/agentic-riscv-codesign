#ifndef FLAGS_STR
#define FLAGS_STR "ISAForge fixed-iteration validation"
#endif
#ifndef VALIDATION_RUN
#define VALIDATION_RUN 1
#endif
#ifndef HAS_FLOAT
#define HAS_FLOAT 0
#endif
#ifndef HAS_TIME_H
#define HAS_TIME_H 0
#endif
#ifndef HAS_STDIO
#define HAS_STDIO 0
#endif
#ifndef HAS_PRINTF
#define HAS_PRINTF 0
#endif
#ifndef TOTAL_DATA_SIZE
#define TOTAL_DATA_SIZE 2000
#endif
#ifndef ITERATIONS
#define ITERATIONS 10
#endif
#define EE_TICKS_PER_SEC 1000000u
#include <stdarg.h>
#include <stddef.h>
#include <stdint.h>
#include "coremark/coremark.h"

volatile ee_s32 seed1_volatile = 0x3415;
volatile ee_s32 seed2_volatile = 0x3415;
volatile ee_s32 seed3_volatile = 0x66;
volatile ee_s32 seed4_volatile = ITERATIONS;
volatile ee_s32 seed5_volatile = 0;
ee_u32 default_num_contexts = 1;
static ee_u32 start_ticks, stop_ticks;
static ee_u32 observed_list, observed_matrix, observed_state;
static ee_u8 saw_list, saw_matrix, saw_state, saw_success, saw_duration_warning, saw_error;
extern int coremark_entry(int argc, char **argv);
static int text_equal(const char *a, const char *b) {
    while (*a && *b && *a == *b) { ++a; ++b; }
    return *a == *b;
}
static int text_contains(const char *haystack, const char *needle) {
    for (; *haystack; ++haystack) {
        const char *a = haystack, *b = needle;
        while (*a && *b && *a == *b) { ++a; ++b; }
        if (!*b) return 1;
    }
    return 0;
}
int ee_printf(const char *fmt, ...) {
    va_list args;
    va_start(args, fmt);
    if (text_contains(fmt, "crclist")) {
        int context = va_arg(args, int); int value = va_arg(args, int);
        if (context == 0) { observed_list = (unsigned)value & 0xffffu; saw_list = 1; }
    } else if (text_contains(fmt, "crcmatrix")) {
        int context = va_arg(args, int); int value = va_arg(args, int);
        if (context == 0) { observed_matrix = (unsigned)value & 0xffffu; saw_matrix = 1; }
    } else if (text_contains(fmt, "crcstate")) {
        int context = va_arg(args, int); int value = va_arg(args, int);
        if (context == 0) { observed_state = (unsigned)value & 0xffffu; saw_state = 1; }
    }
    if (text_contains(fmt, "Correct operation validated")) saw_success = 1;
    if (text_contains(fmt, "Must execute for at least 10 secs")) saw_duration_warning = 1;
    if ((text_contains(fmt, "ERROR!") && !text_contains(fmt, "Must execute for at least 10 secs")) ||
        text_contains(fmt, "Cannot validate operation") || text_contains(fmt, "list_head structure too big")) saw_error = 1;
    va_end(args);
    return 0;
}
void start_time(void) { __asm__ volatile ("rdcycle %0" : "=r"(start_ticks) :: "memory"); }
void stop_time(void) { __asm__ volatile ("rdcycle %0" : "=r"(stop_ticks) :: "memory"); }
CORE_TICKS get_time(void) { return stop_ticks - start_ticks; }
secs_ret time_in_secs(CORE_TICKS ticks) { return ticks / EE_TICKS_PER_SEC; }
void portable_init(core_portable *p, int *argc, char *argv[]) {
    (void)argc; (void)argv; p->portable_id = 1;
    if (sizeof(ee_ptr_int) != sizeof(ee_u8 *) || sizeof(ee_u32) != 4) saw_error = 1;
}
void portable_fini(core_portable *p) { p->portable_id = 0; }
void *portable_malloc(ee_size_t n) { (void)n; return NULL; }
void portable_free(void *p) { (void)p; }
void initialise_benchmark(void) {
    observed_list = observed_matrix = observed_state = 0;
    saw_list = saw_matrix = saw_state = saw_success = saw_duration_warning = saw_error = 0;
}
void warm_caches(int n) { (void)n; }
int benchmark(void) { return coremark_entry(0, (char **)0) == 0 ? 1 : 0; }
int verify_benchmark(int result) {
    return result && (saw_success || saw_duration_warning) && !saw_error &&
           saw_list && saw_matrix && saw_state && observed_list == 0xe3c1u &&
           observed_matrix == 0x0747u && observed_state == 0x8d84u;
}
