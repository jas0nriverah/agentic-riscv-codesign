#include <stdint.h>
extern int adpcm_dec_result[];
unsigned external_snapshot(int32_t *values) {
    for(unsigned i=0;i<4;i++)values[i]=adpcm_dec_result[i]; return 4;
}
