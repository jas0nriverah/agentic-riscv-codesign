ENTRY(_start)
MEMORY { ram (rwx) : ORIGIN = 0, LENGTH = 8K }
SECTIONS {
    .text : { *(.text.start) *(.text*) } > ram
    .rodata : { *(.rodata*) } > ram
    .data : { _writable_start = .; *(.data*) *(.sdata*) } > ram
    .bss : { *(.bss*) *(.sbss*) *(COMMON) } > ram
    . = ALIGN(4);
    _program_end = .;
    ASSERT(_program_end <= 6400, "firmware must leave the declared guard and 1664-byte stack")
    /DISCARD/ : { *(.comment) *(.riscv.attributes) }
}
