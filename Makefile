CC          := riscv64-unknown-elf-gcc
SPIKE       := spike

CFLAGS      := -march=rv32im -mabi=ilp32 -O2 -std=gnu17 -DCPU_MHZ=1 -DWARMUP_HEAT=1
LDFLAGS     := -nostartfiles -T src/spike-setup/memory-layout.ld
SPIKE_FLAGS := --isa=rv32im_zicntr -m16

EMBENCH     := benchmarks/embench
SETUP       := src/spike-setup/startup.S benchmarks/embench-hooks.c \
               $(EMBENCH)/support/main.c $(EMBENCH)/support/beebsc.c

PROGRAMS    := aha-mont64 crc32 edn huffbench matmult-int nettle-aes nettle-sha256 wikisort

SRC_aha-mont64    := aha-mont64/mont64.c
SRC_crc32         := crc32/crc_32.c
SRC_edn           := edn/libedn.c
SRC_huffbench     := huffbench/libhuffbench.c
SRC_matmult-int   := matmult-int/matmult-int.c
SRC_nettle-aes    := nettle-aes/nettle-aes.c
SRC_nettle-sha256 := nettle-sha256/nettle-sha256.c
SRC_wikisort      := wikisort/libwikisort.c

.PHONY: all run

all: $(PROGRAMS:%=generated/programs/%.elf)

generated/programs/%.elf: $(SETUP) src/spike-setup/memory-layout.ld
	mkdir -p generated/programs
	$(CC) $(CFLAGS) -I $(EMBENCH)/support $(LDFLAGS) $(SETUP) $(EMBENCH)/src/$(SRC_$*) -lm -o $@

run: all
	for p in $(PROGRAMS); do $(SPIKE) $(SPIKE_FLAGS) generated/programs/$$p.elf; echo "$$p: exit $$?"; done
