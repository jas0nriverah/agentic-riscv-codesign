# PROVISIONAL measurement engine (see hw/engine/README.md). Included from hw/hw.mk.
#   make hw-measure CANDIDATES=<json> [ALLOW_MUL=1]
# builds one core with up to 3 fused units, rewrites and runs all 8 programs, routes seeds 1-10
# with the frozen pins, and writes generated/hw/engine/<id>/results.json and rows.jsonl.

EN          := generated/hw/engine
# each script is a prerequisite only of the step it runs, so a report change doesn't rebuild cores
EN_GEN      := hw/engine/units.py hw/isaforge/rtl.py hw/isaforge/features.py
EN_REWRITE  := hw/engine/rewrite.py hw/engine/asmscan.py
EN_UNITS     = python3 hw/engine/units.py --candidates $(CANDIDATES) $(if $(ALLOW_MUL),--allow-mul)

.PHONY: hw-measure

# the first call only validates the request (it stops here on a flagged mul) without writing
# anything, so an unchanged build is not redone; then the manifest, then everything that reads it
hw-measure:
	@test -n "$(CANDIDATES)" || { echo "usage: make hw-measure CANDIDATES=<json> [ALLOW_MUL=1]"; exit 2; }
	$(EN_UNITS) --id-only > /dev/null
	$(MAKE) --no-print-directory $(EN)/$$($(EN_UNITS) --id-only)/manifest.json EN_B=$(EN)/$$($(EN_UNITS) --id-only)
	$(MAKE) --no-print-directory $(EN)/$$($(EN_UNITS) --id-only)/results.json EN_B=$(EN)/$$($(EN_UNITS) --id-only)

# --- shared by every build: main's compile of each program's C sources, stopped at assembly,
# and the finder's sites per program (checked against its own saved and places)

EN_C = benchmarks/embench-hooks.c $(EMBENCH)/support/main.c $(EMBENCH)/support/beebsc.c $(EMBENCH)/src/$(SRC_$(1))
EN_S = $(foreach f,$(call EN_C,$(1)),$(EN)/asm/$(1)/$(basename $(notdir $(f))).s)

$(EN)/asm/%/done: $(HW_SETUP) | $(EMBENCH)/.git
	mkdir -p $(dir $@)
	for f in $(call EN_C,$*); do $(CC) $(CFLAGS) -I $(EMBENCH)/support -S $$f -o $(dir $@)$$(basename $${f%.c}).s || exit 1; done
	touch $@

$(EN)/finder/%.json: generated/traces/%.jsonl generated/programs/%.elf generated/candidates/%.json hw/engine/finder.py
	mkdir -p $(dir $@)
	python3 hw/engine/finder.py $(word 1,$^) $(word 2,$^) $(word 3,$^) $@ --prefix $(RISCV_PREFIX)

# placeability pre-check: the rewriter alone, no hardware, for every candidate of every program
.PHONY: hw-placeability
hw-placeability: $(PROGRAMS:%=$(EN)/asm/%/done) $(PROGRAMS:%=$(EN)/finder/%.json) hw/engine/placeability.py
	python3 hw/engine/placeability.py --prefix $(RISCV_PREFIX) --cflags "$(CFLAGS) -I $(EMBENCH)/support" \
	  --ldflags "$(LDFLAGS)" --programs $(PROGRAMS) --out hw/engine/results/placeability.csv

# the selection experiments (needs hw-sweep10): placement-aware frequency pick, oracle sets under
# LUT budgets, one core each, then the comparison -> hw/engine/results/experiments.csv
EN_R := hw/engine/results
.PHONY: hw-experiments
hw-experiments:
	python3 hw/engine/selection.py frequency --placeable --out $(EN_R)/frequency-placeable-top3.request.json
	for b in 100 250 500 750; do python3 hw/engine/selection.py oracle --budget $$b --keep 3 --out $(EN_R)/oracle-lut$$b || exit 1; done
	for b in 100 250 500 750; do python3 hw/engine/selection.py frequency-budget --budget $$b --out $(EN_R)/frequency-budget-lut$$b.request.json || exit 1; done
	for r in $(EN_R)/frequency-top3.request.json $(EN_R)/frequency-placeable-top3.request.json $(EN_R)/frequency-budget-lut*.request.json $(EN_R)/oracle-lut*-set*.request.json; do \
	  $(MAKE) --no-print-directory hw-measure CANDIDATES=$$r ALLOW_MUL=1 || exit 1; done
	python3 hw/engine/compare.py --single-candidate-builds 60

ifdef EN_B
# the microtest list comes from the manifest, which the first sub-make creates
EN_MICRO := $(if $(wildcard $(EN_B)/manifest.json),$(shell python3 -c "import json; print(' '.join(json.load(open('$(EN_B)/manifest.json'))['microtests']))"))

# keeps every file of the build: make 3.81 would otherwise delete the chain's intermediates
EN_KEEP := $(foreach p,$(PROGRAMS),$(EN)/asm/$(p)/done $(EN_B)/sw/$(p)/sites.json \
             $(foreach k,marked fused,$(EN_B)/programs/$(p)-$(k).elf $(EN_B)/programs/$(p)-$(k).bin)) \
           $(foreach m,$(EN_MICRO),$(EN_B)/micro/$(m).elf $(EN_B)/micro/$(m).bin) \
           $(EN_B)/sim/Vcore_top $(EN_B)/synth/core_top.json $(HW_SEEDS:%=$(EN_B)/route/seed%/report.json)
.SECONDARY: $(EN_KEEP)

$(EN_B)/manifest.json: $(CANDIDATES) $(EN_GEN)
	$(EN_UNITS) > /dev/null

# --- software: rewrite every program's assembly with the build's formulas, in priority order

$(EN_B)/sw/%/sites.json: $(EN_B)/manifest.json $(EN)/asm/%/done $(EN_REWRITE)
	python3 hw/engine/rewrite.py --manifest $< --out $(dir $@) --prefix $(RISCV_PREFIX) \
	  --flags "$(CFLAGS) -I $(EMBENCH)/support" $(call EN_S,$*)

# marked = the original code plus labels at every site (must equal the baseline image)
$(EN_B)/programs/%-marked.elf: $(EN_B)/sw/%/sites.json src/spike-setup/memory-layout.ld
	mkdir -p $(dir $@)
	$(CC) $(CFLAGS) $(LDFLAGS) $(HW)/sw/startup.S $(patsubst %.s,%.marked.s,$(subst $(EN)/asm/$*/,$(EN_B)/sw/$*/,$(call EN_S,$*))) -lm -o $@

$(EN_B)/programs/%-fused.elf: $(EN_B)/sw/%/sites.json src/spike-setup/memory-layout.ld
	mkdir -p $(dir $@)
	$(CC) $(CFLAGS) $(LDFLAGS) $(HW)/sw/startup.S $(patsubst %.s,%.fused.s,$(subst $(EN)/asm/$*/,$(EN_B)/sw/$*/,$(call EN_S,$*))) -lm -o $@

$(EN_B)/micro/%.elf: $(EN_B)/manifest.json
	$(CC) -march=rv32im_zicsr -mabi=ilp32 -nostartfiles -T src/spike-setup/memory-layout.ld $(EN_B)/micro/$*.S -o $@

# --- the engine core in Verilator

$(EN_B)/sim/Vcore_top: $(EN_B)/manifest.json $(HW)/rtl/picorv32.v $(HW)/rtl/core_top.v $(HW)/sim/core_sim.cpp
	mkdir -p $(EN_B)/sim
	$(VERILATOR) --cc --exe --build -j 4 -O3 -Wno-fatal --top-module core_top -GFUSED=2 -CFLAGS -std=c++17 \
	  --Mdir $(EN_B)/sim $$(cat $(EN_B)/rtl/files.txt) $(HW)/sim/core_sim.cpp -o Vcore_top > $(EN_B)/sim/build.log 2>&1 \
	  || { tail -20 $(EN_B)/sim/build.log; exit 1; }

$(EN_B)/runs/fused/%.json: $(EN_B)/programs/%-fused.bin $(EN_B)/programs/%-fused.elf $(EN_B)/sim/Vcore_top
	mkdir -p $(dir $@)
	$(call dr_run,$(EN_B)/sim/Vcore_top,$<,$(word 2,$^),$@)

$(EN_B)/runs/stock/%.json: $(HW_OUT)/programs/%.bin $(HW_OUT)/programs/%.elf $(EN_B)/sim/Vcore_top
	mkdir -p $(dir $@)
	$(call dr_run,$(EN_B)/sim/Vcore_top,$<,$(word 2,$^),$@)

# make 3.81 takes the first matching pattern, so the stock-core rule comes first
$(EN_B)/runs/micro/trap-stock-%.json: $(EN_B)/micro/trap-stock-%.bin $(EN_B)/micro/trap-stock-%.elf $(HW_OUT)/sim/Vcore_top
	mkdir -p $(dir $@)
	$(call dr_run,$(HW_OUT)/sim/Vcore_top,$<,$(word 2,$^),$@)

$(EN_B)/runs/micro/%.json: $(EN_B)/micro/%.bin $(EN_B)/micro/%.elf $(EN_B)/sim/Vcore_top
	mkdir -p $(dir $@)
	$(call dr_run,$(EN_B)/sim/Vcore_top,$<,$(word 2,$^),$@)

# --- synthesis, routing with the frozen pins, and the critical-path check

$(EN_B)/synth/core_top.json: $(EN_B)/manifest.json $(HW)/rtl/picorv32.v $(HW)/rtl/core_top.v
	mkdir -p $(dir $@)
	$(YOSYS) -q -l $(EN_B)/synth/yosys.log -s $(EN_B)/engine.ys

$(EN_B)/route/seed%/report.json: $(EN_B)/synth/core_top.json $(HW)/synth/core_top.pcf
	mkdir -p $(dir $@)
	$(NEXTPNR) --hx8k --package ct256 --json $< --pcf $(word 2,$^) \
	  --freq $(HW_FREQ_MHZ) --seed $* --threads 1 --report $@ --log $(dir $@)nextpnr.log --quiet

$(EN_B)/critical_paths.csv: $(DR_CRIT_SCRIPTS) $(HW_SEEDS:%=$(EN_B)/route/seed%/report.json)
	python3 $(HW)/scripts/critcone.py --selftest --netlist $(EN_B)/synth/core_top.json
	rm -f $@
	python3 $(HW)/scripts/critpath.py --core engine --netlist $(EN_B)/synth/core_top.json \
	  --routes $(EN_B)/route --seeds $(HW_SEEDS) --out $@ > /dev/null

# --- every check, the reconciliation and the measurement rows

$(EN_B)/results.json: hw/engine/report.py $(HW)/results/baseline.csv $(EN_B)/critical_paths.csv \
                      $(EN_MICRO:%=$(EN_B)/runs/micro/%.json) \
                      $(PROGRAMS:%=$(EN_B)/runs/fused/%.json) $(PROGRAMS:%=$(EN_B)/runs/stock/%.json) \
                      $(PROGRAMS:%=$(EN_B)/programs/%-marked.bin) $(PROGRAMS:%=$(EN)/finder/%.json)
	RISCV_PREFIX=$(RISCV_PREFIX) python3 hw/engine/report.py --build $(EN_B) --programs $(PROGRAMS) \
	  --seeds $(HW_SEEDS) --out $@
endif

# the checkpoint sweep: each program's top 3 candidates, each measured alone
#   make hw-sweep [CLEAN=1] [ALLOW_MUL=1]    (CLEAN=1 deletes every engine build first)
.PHONY: hw-sweep
hw-sweep:
	$(if $(CLEAN),rm -rf $(EN))
	python3 hw/engine/sweep.py --top 3 $(if $(ALLOW_MUL),--allow-mul) --jobs 8
