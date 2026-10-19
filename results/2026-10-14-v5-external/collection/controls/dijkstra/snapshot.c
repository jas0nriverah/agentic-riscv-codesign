#include <stdint.h>
extern void dijkstra_init(void);
extern int dijkstra_find(int,int),dijkstra_queueNext;
int external_dijkstra_path(void) { return dijkstra_find(0,50); }
extern struct { int dist; int prev; } dijkstra_rgnNodes[];
unsigned external_snapshot(int32_t *values) {
    dijkstra_init();
    for(int i=0;i<20;i++) {
        if(dijkstra_find(i,i+50)!=0) { values[i]=-9999; return 20; }
        values[i]=dijkstra_rgnNodes[i+50].dist; dijkstra_queueNext=0;
    }
    return 20;
}
