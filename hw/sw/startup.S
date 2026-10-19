// PicoRV32 copy of src/spike-setup/startup.S.
// PicoRV32 has no mtvec, so the csrw is replaced by a nop of the same size.
// Every address in the program stays the same as in the Spike build, so the
// benchmark code PicoRV32 runs is byte-for-byte the code Spike traced.
// A crash halts PicoRV32 with its trap output instead of jumping to crashed.
    .section .text.start, "ax", @progbits
    .globl _start
_start:
    la      t0, crashed
    nop

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
