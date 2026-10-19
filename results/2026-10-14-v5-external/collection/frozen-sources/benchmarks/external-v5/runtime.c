/* ISAForge-only HTIF output helper. All output happens outside trace markers. */
#include <stdint.h>
#include <stddef.h>
extern volatile uint64_t tohost, fromhost;
_Static_assert(sizeof(int)==4 && sizeof(long)==4 && sizeof(void*)==4, "RV32 ILP32 required");
static char output[1024];
static unsigned cursor;
static void text(const char *s) { while (*s) output[cursor++] = *s++; }
static void number(int32_t value) {
    char digits[12]; unsigned count=0;
    uint32_t magnitude=(uint32_t)value;
    if(value<0) { output[cursor++]='-'; magnitude=0u-magnitude; }
    do { digits[count++]=(char)('0'+magnitude%10u); magnitude/=10u; } while(magnitude);
    while(count) output[cursor++]=digits[--count];
}
void external_report(const int32_t *values, unsigned count, int status) {
    volatile uint64_t request[8] __attribute__((aligned(64)))={0};
    cursor=0;
    text("{\"kind\":\"external-output\",\"values\":[");
    for(unsigned i=0;i<count;i++) { if(i)text(","); number(values[i]); }
    text("],\"upstream_status\":"); number(status); text("}\n");
    request[0]=64; request[1]=1; request[2]=(uintptr_t)output; request[3]=cursor;
    __asm__ volatile("fence rw,rw" ::: "memory");
    tohost=(uintptr_t)request;
    while(!fromhost) { __asm__ volatile("" ::: "memory"); }
    __asm__ volatile("fence rw,rw" ::: "memory");
    fromhost=0;
}
