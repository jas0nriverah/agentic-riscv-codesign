.section .text.start
.global _start
_start:
    li sp, 0x10000
    call main
    ebreak

.section .text
// Leaf calls retain the original instruction sequences, without padding NOPs.
.global formula0, formula1, run0, run1
formula0:
#if CUSTOM
    .insn r 0x0b, 0, 1, a0, a0, a1
#else
    xor a0, a0, a1
    andi a0, a0, 255
    slli a0, a0, 2
#endif
    ret
formula1:
#if CUSTOM
    .insn r 0x0b, 1, 1, a0, a0, a1
#else
    srli a1, a1, 8
    xor a0, a0, a1
#endif
    ret

// a0: state, a1: second input, a2: iterations. Leaf loop includes control.
run0:
    beqz a2, 2f
    li a3, 0x9e3779b9
1:
#if CUSTOM
    .insn r 0x0b, 0, 1, a0, a0, a1
#else
    xor a0, a0, a1
    andi a0, a0, 255
    slli a0, a0, 2
#endif
    add a1, a1, a3
    addi a2, a2, -1
    bnez a2, 1b
2:
    ret
run1:
    beqz a2, 2f
    li a3, 0x9e3779b9
1:
#if CUSTOM
    .insn r 0x0b, 1, 1, a0, a0, a1
#else
    srli a4, a1, 8
    xor a0, a0, a4
#endif
    add a1, a1, a3
    addi a2, a2, -1
    bnez a2, 1b
2:
    ret
