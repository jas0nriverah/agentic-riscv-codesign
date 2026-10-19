OUTPUT_ARCH("riscv")
ENTRY(_start)

MEMORY
{
  RAM (rwx) : ORIGIN = 0x80000000, LENGTH = 16M
}

SECTIONS
{
  .text : { *(.text.start) *(.text .text.*) } > RAM
  .rodata : ALIGN(8) { *(.rodata .rodata.*) } > RAM
  .tohost : ALIGN(64) { *(.tohost) } > RAM
  .data : ALIGN(8) {
    *(.data .data.*)
    __global_pointer$ = . + 0x800;
    *(.sdata .sdata.* .srodata .srodata.*)
  } > RAM
  .bss : ALIGN(8) {
    __bss_start = .;
    *(.sbss .sbss.* .bss .bss.* COMMON)
    . = ALIGN(4);
    __bss_end = .;
  } > RAM
  _end = .;
  __stack_top = ORIGIN(RAM) + LENGTH(RAM);
}
