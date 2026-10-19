#include <stdint.h>
#include "snipmath.h"
extern unsigned long isqrt_checksum,isqrt_l;extern struct int_sqrt isqrt_q;extern void isqrt_usqrt(unsigned long,struct int_sqrt*);
unsigned external_snapshot(int32_t*v){v[0]=isqrt_checksum;v[1]=isqrt_q.sqrt;v[2]=isqrt_q.frac;v[3]=isqrt_l;
 const unsigned long inputs[]={0,1,2,3,4,15,16,17,65535,65536,0x7fffffff,0x80000000,0xffffffff,0x3fed0169,0x10000,0xffff0000};
 for(unsigned i=0;i<16;i++){struct int_sqrt q;isqrt_usqrt(inputs[i],&q);v[4+i]=(int32_t)((uint32_t)q.sqrt|((uint32_t)q.frac<<16));}return 20;}