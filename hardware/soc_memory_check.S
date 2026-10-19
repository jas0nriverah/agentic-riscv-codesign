// Exercise the inferred RAM byte write masks and sign/zero-extending loads.
.section .text.start
.global _start
_start:
    li t0, 0x1000
    li t1, 0x11223344
    sw t1, 0(t0)
    li t1, 0xdd
    sb t1, 1(t0)
    li t1, 0xef
    sh t1, 2(t0)
    lw t2, 0(t0)
    li t3, 0x00efdd44
    bne t2, t3, fail
    lb t2, 1(t0)
    li t3, -35
    bne t2, t3, fail
    lbu t2, 1(t0)
    li t3, 0xdd
    bne t2, t3, fail
    lh t2, 2(t0)
    li t3, 0xef
    bne t2, t3, fail
    li t0, 0x10000000
    li t1, 0x00efdd44
    sw t1, 0(t0)
    li t1, 0x600d600d
    sw t1, 4(t0)
    ebreak
fail:
    li t0, 0x10000000
    li t1, 0xdead0004
    sw t1, 4(t0)
    ebreak
