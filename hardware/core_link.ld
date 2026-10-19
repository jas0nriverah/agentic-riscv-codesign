ENTRY(_start)
MEMORY { ram (rwx) : ORIGIN = 0, LENGTH = 64K }
SECTIONS {
    .text : { *(.text.start) *(.text*) } > ram
    .rodata : { *(.rodata*) } > ram
    .data : { *(.data*) *(.sdata*) } > ram
    .bss : { *(.bss*) *(.sbss*) *(COMMON) } > ram
    /DISCARD/ : { *(.comment) *(.riscv.attributes) }
}
