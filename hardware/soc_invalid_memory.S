.section .text.start
.global _start
_start:
    li t0, 0x2000
    sw zero, 0(t0)
    // A bounds fault must finish with failure before this success store.
    li t0, 0x10000000
    li t1, 0x600d600d
    sw t1, 4(t0)
    ebreak
