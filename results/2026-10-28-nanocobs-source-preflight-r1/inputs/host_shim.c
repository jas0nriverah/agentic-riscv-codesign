#include <stdio.h>
void probe_init(void) {}
void probe_puts(char const *s) { fputs(s, stdout); }
void probe_putu(unsigned long v) { printf("%lu", v); }
void probe_done(int failed) { (void)failed; }
