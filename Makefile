.DEFAULT_GOAL := help
PYTHON ?= python
.PHONY: help test reproduce predict figures feature-check coverage-check
help:
	@echo 'make reproduce  Verify saved evidence and recompute three benchmark summaries'
	@echo 'make predict    Run the default pretrained model on cached arithmetic features'
	@echo 'make figures    Regenerate the model and improvement diagrams'
	@echo 'make feature-check  Replay the matched feature comparison without training'
	@echo 'make coverage-check  Audit targeted coverage and fresh policy validation'
	@echo 'make test       Run current implementation and replay tests'
test:
	$(PYTHON) -m pytest -q
reproduce:
	$(PYTHON) scripts/reproduce.py --check
predict:
	$(PYTHON) scripts/predict.py --model base --candidates results/arithmetic-stress/candidates.json --features results/arithmetic-stress/features.json --output generated/predictions.json
figures:
	$(PYTHON) scripts/render_research_figures.py
	$(PYTHON) scripts/render_feature_comparison.py
	$(PYTHON) scripts/render_selection_validation.py
	$(PYTHON) scripts/render_targeted_coverage.py

feature-check:
	$(PYTHON) scripts/replay_feature_comparison.py
	$(PYTHON) scripts/replay_selection_stability.py
	$(PYTHON) scripts/replay_selection_validation.py replay

coverage-check:
	$(PYTHON) scripts/replay_coverage_audits.py

# Workload extraction and hardware integration from main.
# uses riscv64-unknown-elf- when it is installed and xPack's riscv-none-elf- otherwise
RISCV_PREFIX ?= $(if $(shell command -v riscv64-unknown-elf-gcc),riscv64-unknown-elf-,riscv-none-elf-)
CC          := $(RISCV_PREFIX)gcc
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

.PHONY: all run trace candidates
.DELETE_ON_ERROR:

all: $(PROGRAMS:%=generated/programs/%.elf)

generated/programs/%.elf: $(SETUP) src/spike-setup/memory-layout.ld
	mkdir -p generated/programs
	$(CC) $(CFLAGS) -I $(EMBENCH)/support $(LDFLAGS) $(SETUP) $(EMBENCH)/src/$(SRC_$*) -lm -o $@

run: all
	for p in $(PROGRAMS); do $(SPIKE) $(SPIKE_FLAGS) generated/programs/$$p.elf; echo "$$p: exit $$?"; done

generated/traces/%.jsonl: generated/programs/%.elf src/tracing.py
	mkdir -p generated/traces
	$(SPIKE) $(SPIKE_FLAGS) --log-commits --log=/dev/stdout $< | python3 src/tracing.py $@

trace: $(PROGRAMS:%=generated/traces/%.jsonl)

generated/candidates/%.json: generated/traces/%.jsonl generated/programs/%.elf src/candidates.py
	mkdir -p generated/candidates
	python3 src/candidates.py $< generated/programs/$*.elf $@

candidates: $(PROGRAMS:%=generated/candidates/%.json)

include hw/hw.mk
