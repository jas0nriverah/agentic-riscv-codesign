#include <stdint.h>
#include "bitops.h"
extern unsigned long bitcount_n,bitcount_randseed,bitcount_seed;extern int bitcount_res;
extern int bitcount_bit_shifter(long);
unsigned external_snapshot(int32_t *v){v[0]=bitcount_n;v[1]=bitcount_res;v[2]=bitcount_randseed;v[3]=bitcount_seed;
 const unsigned long inputs[]={0,1,2,3,7,127,255,65535,0x55555555,0x7fffffff};
 for(unsigned a=0;a<8;a++){uint32_t h=2166136261u;for(unsigned i=0;i<10;i++){int n=0;long x=inputs[i];
 switch(a){case 0:n=bitcount_bit_count(x);break;case 1:n=bitcount_bitcount(x);break;case 2:n=bitcount_ntbl_bitcnt(x);break;
 case 3:n=bitcount_btbl_bitcnt(x);break;case 4:n=bitcount_ntbl_bitcount(x);break;case 5:n=bitcount_BW_btbl_bitcount(x);break;
 case 6:n=bitcount_AR_btbl_bitcount(x);break;case 7:n=bitcount_bit_shifter(x);break;}h=(h^(uint32_t)n)*16777619u;}v[4+a]=(int32_t)h;}return 12;}