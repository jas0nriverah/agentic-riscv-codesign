    .section .text.start, "ax", @progbits
    .globl _start
_start:
    .option push
    .option arch, +zicsr
    la      t0, crashed
    csrw    mtvec, t0
    .option pop

    .option push
    .option norelax
    la      gp, __global_pointer$
    .option pop
    la      sp, __stack_top

    la      t0, __bss_start
    la      t1, __bss_end
clear_bss:
    bgeu    t0, t1, run_main
    sw      zero, 0(t0)
    addi    t0, t0, 4
    j       clear_bss

run_main:
    call    main

    slli    a0, a0, 1
    ori     a0, a0, 1
    la      t0, tohost
    sw      a0, 0(t0)
wait_for_spike:
    j       wait_for_spike

crashed:
    li      a0, 5
    la      t0, tohost
    sw      a0, 0(t0)
wait_after_crash:
    j       wait_after_crash

    .section .tohost, "aw", @progbits
    .align  6
    .globl  tohost
tohost:   .dword 0
    .align  6
    .globl  fromhost
fromhost: .dword 0
