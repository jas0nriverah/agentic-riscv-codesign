.section .text.start
.global _start
_start:
li sp,8192
li t0,6400
sw zero,0(t0)
ebreak
