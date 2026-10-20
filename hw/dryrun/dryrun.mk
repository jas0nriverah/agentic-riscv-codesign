# PROVISIONAL dry run: one crc32 candidate end to end on PicoRV32 (see hw/dryrun/README.md).
# Included from hw/hw.mk; run with `make hw-dryrun`. Uses the baseline's protocol unchanged.

DR          := generated/hw/dryrun
DR_FORMULA  := slli(andi(xor(in0,in1),255),2)
DR_MODULE   := cx_crc32_xoridx
DR_RTL      := $(HW)/rtl/picorv32.v $(HW)/rtl/core_top.v $(HW)/rtl/pcpi_fused.v $(HW)/rtl/$(DR_MODULE).v
DR_MICRO    := micro-check micro-fused-1x micro-fused-2x micro-original-1x micro-original-2x \
               micro-xor-1x micro-xor-2x trap-f3-1 trap-f7-1 trap-f7-3 trap-custom1

.PHONY: hw-dryrun hw-dryrun-rtl hw-dryrun-micro hw-dryrun-route
.SECONDARY: $(DR)/programs/crc32-fused.elf $(DR)/programs/crc32-control.elf \
            $(DR_MICRO:%=$(DR)/micro/%.elf)

# regenerates the datapath and fails if the committed copy differs
hw-dryrun-rtl:
	mkdir -p $(DR)
	python3 -I $(HW)/dryrun/gen_rtl.py --formula '$(DR_FORMULA)' --module $(DR_MODULE) --out $(DR)/$(DR_MODULE).v
	cmp $(DR)/$(DR_MODULE).v $(HW)/rtl/$(DR_MODULE).v

# --- software: main's exact compile of crc_32.c, stopped at assembly and rewritten

$(DR)/sw/crc_32.s: $(EMBENCH)/src/crc32/crc_32.c | $(EMBENCH)/.git
	mkdir -p $(DR)/sw
	$(CC) $(CFLAGS) -I $(EMBENCH)/support -S $< -o $@

$(DR)/sw/crc_32_fused.s: $(DR)/sw/crc_32.s $(HW)/dryrun/rewrite.py
	python3 -I $(HW)/dryrun/rewrite.py $< $@ --log $(DR)/sw/rewrite.json

# the control links the unrewritten assembly and must equal the baseline's PicoRV32 image
$(DR)/programs/crc32-control.elf: $(DR)/sw/crc_32.s $(HW_SETUP) src/spike-setup/memory-layout.ld
	mkdir -p $(DR)/programs
	$(CC) $(CFLAGS) -I $(EMBENCH)/support $(LDFLAGS) $(HW_SETUP) $< -lm -o $@

$(DR)/programs/crc32-fused.elf: $(DR)/sw/crc_32_fused.s $(HW_SETUP) src/spike-setup/memory-layout.ld
	mkdir -p $(DR)/programs
	$(CC) $(CFLAGS) -I $(EMBENCH)/support $(LDFLAGS) $(HW_SETUP) $< -lm -o $@

# --- microtests: bare assembly with main's linker script, so the harness runs them unchanged

$(DR)/micro/micro-check.S: $(HW)/dryrun/microtest.py $(HW)/isaforge/rtl.py
	python3 -I $< $(DR)/micro

$(DR_MICRO:%=$(DR)/micro/%.S): $(DR)/micro/micro-check.S

$(DR)/micro/%.elf: $(DR)/micro/%.S src/spike-setup/memory-layout.ld
	$(CC) -march=rv32im_zicsr -mabi=ilp32 -nostartfiles -T src/spike-setup/memory-layout.ld $< -o $@

# --- the fused core in Verilator

$(DR)/sim/Vcore_top: $(DR_RTL) $(HW)/sim/core_sim.cpp
	$(VERILATOR) --cc --exe --build -j 4 -O3 -Wno-fatal --top-module core_top -GFUSED=1 -CFLAGS -std=c++17 \
	  --Mdir $(DR)/sim $^ -o Vcore_top

# keeps the harness's JSON even when a run fails; report.py decides what each run had to do
# $(1): simulator, $(2): image, $(3): elf, $(4): output
dr_run = $(1) $(2) $(call sym,$(3),tohost) $(call sym,$(3),instret_start) $(call sym,$(3),instret_stop) \
	  $(HW_MAX_CYCLES) > $(4).tmp; mv $(4).tmp $(4)

$(DR)/runs/fused/crc32-fused.json: $(DR)/programs/crc32-fused.bin $(DR)/programs/crc32-fused.elf $(DR)/sim/Vcore_top
	mkdir -p $(dir $@)
	$(call dr_run,$(DR)/sim/Vcore_top,$<,$(word 2,$^),$@)

# every stock program on the fused core must match the baseline exactly
$(DR)/runs/fused/stock-%.json: $(HW_OUT)/programs/%.bin $(HW_OUT)/programs/%.elf $(DR)/sim/Vcore_top
	mkdir -p $(dir $@)
	$(call dr_run,$(DR)/sim/Vcore_top,$<,$(word 2,$^),$@)

$(DR)/runs/fused/%.json: $(DR)/micro/%.bin $(DR)/micro/%.elf $(DR)/sim/Vcore_top
	mkdir -p $(dir $@)
	$(call dr_run,$(DR)/sim/Vcore_top,$<,$(word 2,$^),$@)

# the stock core must trap on every custom encoding, including the one the fused core accepts
$(DR)/runs/stock/%.json: $(DR)/micro/%.bin $(DR)/micro/%.elf $(HW_OUT)/sim/Vcore_top
	mkdir -p $(dir $@)
	$(call dr_run,$(HW_OUT)/sim/Vcore_top,$<,$(word 2,$^),$@)

hw-dryrun-micro: $(DR_MICRO:%=$(DR)/runs/fused/%.json) $(DR)/runs/stock/micro-check.json \
                 $(DR)/runs/stock/trap-f3-1.json

# --- synthesis and routing: the baseline's settings and pins, with FUSED=1

$(DR)/synth/core_top.json: $(HW)/dryrun/ice40_fused.ys $(DR_RTL)
	mkdir -p $(DR)/synth
	$(YOSYS) -q -l $(DR)/synth/yosys.log -s $<

$(DR)/route/seed%/report.json: $(DR)/synth/core_top.json $(HW)/synth/core_top.pcf
	mkdir -p $(dir $@)
	$(NEXTPNR) --hx8k --package ct256 --json $< --pcf $(word 2,$^) \
	  --freq $(HW_FREQ_MHZ) --seed $* --threads 1 --report $@ --log $(dir $@)nextpnr.log --quiet

hw-dryrun-route: $(HW_SEEDS:%=$(DR)/route/seed%/report.json)

# --- the report checks every expectation and writes the measurement row

$(HW)/dryrun/results.json: $(HW)/dryrun/report.py $(HW)/results/baseline.csv hw-dryrun-rtl hw-dryrun-micro hw-dryrun-route \
                           $(DR)/runs/fused/crc32-fused.json $(PROGRAMS:%=$(DR)/runs/fused/stock-%.json) \
                           $(DR)/programs/crc32-control.bin generated/traces/crc32.jsonl generated/candidates/crc32.json
	RISCV_PREFIX=$(RISCV_PREFIX) python3 -I $< --formula '$(DR_FORMULA)' --seeds $(HW_SEEDS) --programs $(PROGRAMS) --out $@

hw-dryrun: $(HW)/dryrun/results.json
