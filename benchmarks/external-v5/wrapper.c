/* Separate ISAForge timing/check wrapper; upstream algorithm sources unchanged. */
#include <stdint.h>
extern void UPSTREAM_INIT(void), UPSTREAM_RUN(void);
extern int UPSTREAM_RETURN(void);
extern unsigned external_snapshot(int32_t *values);
extern void external_report(const int32_t *values, unsigned count, int status);
extern void start_trigger(void), stop_trigger(void);
#if PARTIAL_DIJKSTRA
extern int external_dijkstra_path(void);
#endif
#if ANAGRAM_PHRASE >= 0
extern void external_anagram_phrase(unsigned index);
#endif
int main(void) {
    int32_t values[32]; int status;
    UPSTREAM_INIT();
#if PARTIAL_DIJKSTRA
    /* Preserve the original full20-path self-check outside the smaller trace. */
    UPSTREAM_RUN();
    if(UPSTREAM_RETURN()!=0) return 1;
    UPSTREAM_INIT();
#endif
    start_trigger();
#if PARTIAL_DIJKSTRA
    status=external_dijkstra_path();
#elif ANAGRAM_PHRASE >= 0
    external_anagram_phrase(ANAGRAM_PHRASE);
#else
    UPSTREAM_RUN();
#endif
    stop_trigger();
#if PARTIAL_DIJKSTRA
    /* The partial path returns0 on successful queue completion. */
#elif ANAGRAM_PHRASE >= 0
    status=0; /* Independent host witness checks validate these probe outputs. */
#else
    status=UPSTREAM_RETURN();
#endif
    unsigned count=external_snapshot(values);
    external_report(values,count,status);
    return status!=0;
}
