ENTRY(_start)
MEMORY { ram (rwx) : ORIGIN = 0, LENGTH = 8K }
SECTIONS {
    .text : { *(.text.start) *(.text*) } > ram
    .rodata : { *(.rodata*) } > ram
    .data : { *(.data*) *(.sdata*) } > ram
    .bss : { *(.bss*) *(.sbss*) *(COMMON) } > ram
    . = ALIGN(4);
    _program_end = .;
    ASSERT(_program_end <= 4096, "firmware must leave at least 4 KiB for the stack")
    /DISCARD/ : { *(.comment) *(.riscv.attributes) }
}
