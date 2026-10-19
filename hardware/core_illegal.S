// An unsupported instruction must trap before this success MMIO store.
.section .text.start
.global _start
_start:
    .word INVALID_INSN
    li t0, 0x10000000
    li t1, 0x600d600d
    sw t1, 4(t0)
    ebreak
