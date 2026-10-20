# Stock PicoRV32 baseline: cycles in Verilator, instret checked against Spike,
# and LUTs and routed Fmax on the same iCE40 target the ML branch used.
# Included from the top-level Makefile; run with `make hw-baseline`.

VERILATOR   := verilator
YOSYS       := yosys
NEXTPNR     := nextpnr-ice40
OBJCOPY     := $(RISCV_PREFIX)objcopy
NM          := $(RISCV_PREFIX)nm

HW          := hw
HW_OUT      := generated/hw
HW_SEEDS    := 1 2 3 4 5 6 7 8 9 10
HW_FREQ_MHZ := 12
HW_MAX_CYCLES := 4000000000

# the same sources and flags as main's Spike build, with the PicoRV32 startup
HW_SETUP    := $(HW)/sw/startup.S benchmarks/embench-hooks.c \
               $(EMBENCH)/support/main.c $(EMBENCH)/support/beebsc.c

.PHONY: hw-baseline hw-sim hw-synth hw-route hw-pcf
# keeps the ELFs that the .bin files are made from
.SECONDARY: $(PROGRAMS:%=$(HW_OUT)/programs/%.elf) $(PROGRAMS:%=generated/programs/%.elf)

hw-baseline: $(HW)/results/baseline.csv

# clones Embench on a clean checkout
$(EMBENCH)/support/main.c $(EMBENCH)/support/beebsc.c: | $(EMBENCH)/.git

$(EMBENCH)/.git:
	git submodule update --init $(EMBENCH)

$(HW_OUT)/programs/%.elf: $(HW_SETUP) src/spike-setup/memory-layout.ld
	mkdir -p $(HW_OUT)/programs
	$(CC) $(CFLAGS) -I $(EMBENCH)/support $(LDFLAGS) $(HW_SETUP) $(EMBENCH)/src/$(SRC_$*) -lm -o $@

%.bin: %.elf
	$(OBJCOPY) -O binary $< $@

# Apple clang defaults to C++98 and the OSS CAD Suite Verilator needs at least C++14
$(HW_OUT)/sim/Vcore_top: $(HW)/rtl/picorv32.v $(HW)/rtl/core_top.v $(HW)/sim/core_sim.cpp
	$(VERILATOR) --cc --exe --build -j 4 -O3 -Wno-fatal --top-module core_top -CFLAGS -std=c++17 \
	  --Mdir $(HW_OUT)/sim $^ -o Vcore_top

# reads the window and tohost addresses from the ELF so the program is unchanged
sym = 0x$$($(NM) $(1) | awk '$$3 == "$(2)" {print $$1}')

$(HW_OUT)/runs/%.json: $(HW_OUT)/programs/%.bin $(HW_OUT)/programs/%.elf $(HW_OUT)/sim/Vcore_top
	mkdir -p $(HW_OUT)/runs
	$(HW_OUT)/sim/Vcore_top $< $(call sym,$(word 2,$^),tohost) \
	  $(call sym,$(word 2,$^),instret_start) $(call sym,$(word 2,$^),instret_stop) \
	  $(HW_MAX_CYCLES) > $@.tmp || { cat $@.tmp; exit 1; }
	mv $@.tmp $@

hw-sim: $(PROGRAMS:%=$(HW_OUT)/runs/%.json)

$(HW_OUT)/synth/core_top.json: $(HW)/synth/ice40.ys $(HW)/rtl/picorv32.v $(HW)/rtl/core_top.v
	mkdir -p $(HW_OUT)/synth
	$(YOSYS) -q -l $(HW_OUT)/synth/yosys.log -s $<

hw-synth: $(HW_OUT)/synth/core_top.json

# the ML branch's target: HX8K CT256 with a 12 MHz constraint, routed once per seed
# every seed and every later design uses the same committed pins
$(HW_OUT)/route/seed%/report.json: $(HW_OUT)/synth/core_top.json $(HW)/synth/core_top.pcf
	mkdir -p $(dir $@)
	$(NEXTPNR) --hx8k --package ct256 --json $< --pcf $(word 2,$^) \
	  --freq $(HW_FREQ_MHZ) --seed $* --threads 1 --report $@ --log $(dir $@)nextpnr.log --quiet

# regenerates hw/synth/core_top.pcf from a pin-free placement of the stock core
# not part of hw-baseline because the committed pins must stay fixed
HW_PCF_SEED := 3
HW_CHIPDB    = $(dir $(shell command -v $(NEXTPNR)))../share/icebox/chipdb-8k.txt

hw-pcf: $(HW_OUT)/synth/core_top.json
	mkdir -p $(HW_OUT)/pcf
	$(NEXTPNR) --hx8k --package ct256 --json $< --pcf-allow-unconstrained \
	  --freq $(HW_FREQ_MHZ) --seed $(HW_PCF_SEED) --threads 1 --write $(HW_OUT)/pcf/placed.json \
	  --log $(HW_OUT)/pcf/nextpnr.log --quiet
	python3 $(HW)/scripts/pcf.py $(HW_OUT)/pcf/placed.json $(HW_CHIPDB) ct256 $(HW)/synth/core_top.pcf

hw-route: $(HW_SEEDS:%=$(HW_OUT)/route/seed%/report.json)

$(HW)/results/baseline.csv: $(HW)/scripts/baseline.py hw-sim hw-route \
                            $(PROGRAMS:%=generated/traces/%.jsonl) \
                            $(PROGRAMS:%=generated/programs/%.bin) $(PROGRAMS:%=$(HW_OUT)/programs/%.bin)
	python3 $< --programs $(PROGRAMS) --seeds $(HW_SEEDS) --out $@

include $(HW)/dryrun/dryrun.mk
