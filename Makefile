# Command-line overrides support toolchains such as xPack's riscv-none-elf.
CC          = riscv64-unknown-elf-gcc
OBJDUMP     = riscv64-unknown-elf-objdump
SPIKE       = spike
PYTHON      = python3
SHELL       := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c

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

generated/programs/%.elf: $(SETUP) src/spike-setup/memory-layout.ld $(wildcard $(EMBENCH)/src/*/*.c)
	mkdir -p generated/programs
	$(CC) $(CFLAGS) -I $(EMBENCH)/support $(LDFLAGS) $(SETUP) $(EMBENCH)/src/$(SRC_$*) -lm -o $@

run: all
	for p in $(PROGRAMS); do $(SPIKE) $(SPIKE_FLAGS) generated/programs/$$p.elf; echo "$$p: exit 0 (self-check passed)"; done

generated/traces/%.jsonl: generated/programs/%.elf src/tracing.py
	mkdir -p generated/traces
	$(SPIKE) $(SPIKE_FLAGS) --log-commits --log=/dev/stdout $< | $(PYTHON) src/tracing.py $@

trace: $(PROGRAMS:%=generated/traces/%.jsonl)

generated/candidates/%.json: generated/traces/%.jsonl generated/programs/%.elf src/candidates.py
	mkdir -p generated/candidates
	$(PYTHON) src/candidates.py $< generated/programs/$*.elf $@ --objdump $(OBJDUMP)

candidates: $(PROGRAMS:%=generated/candidates/%.json)

# Research entry points. Activate .venv first, or set PYTHON=.venv/bin/python.
.PHONY: help test reproduce reproduce-v4 reproduce-v5 reproduce-external-v5 reproduce-v6 reproduce-v8 reproduce-v9-coverage reproduce-v10d-hardware reproduce-v10d-timing diagram
help:
	@echo 'Research: make test | make reproduce | make reproduce-v4 | make reproduce-v5 | make reproduce-external-v5 | make reproduce-v6 | make reproduce-v8 | make reproduce-v9-coverage | make reproduce-v10d-hardware | make reproduce-v10d-timing | make diagram'
	@echo 'make reproduce replays frozen scores/audit/figures; no training or synthesis.'
	@echo 'Hardware collection: make all | make run | make trace | make candidates'
	@echo 'See docs/README.md for methodology, results, and pinned toolchains.'

test:
	$(PYTHON) -m pytest -q

reproduce:
	$(PYTHON) scripts/reproduce_matched.py

reproduce-v4:
	$(PYTHON) scripts/evaluate_v4.py --manifest results/2026-10-13-v4/freeze.json --release results/2026-10-13-v4/label-release.json --output generated/reproduction/v4/evaluation.json
	$(PYTHON) scripts/report_v4.py --evaluation generated/reproduction/v4/evaluation.json --development results/2026-10-13-v4/development-evaluation.json --historical results/2026-10-13-v3/probe-evaluation.json --runtime-cost results/2026-10-13-v4/runtime-cost.json --output generated/reproduction/v4/report

reproduce-v5:
	$(PYTHON) scripts/evaluate_v5.py --root results/2026-10-14-v5 --output generated/reproduction/v5/evaluation.json
	$(PYTHON) scripts/report_v5.py --evaluation generated/reproduction/v5/evaluation.json --output generated/reproduction/v5/report --audit-dir results/2026-10-14-v5/audit

reproduce-external-v5:
	$(PYTHON) scripts/archive_external_v5.py restore
	$(PYTHON) scripts/evaluate_external_v5.py score --output generated/reproduction/external-v5/evaluation.json
	$(PYTHON) scripts/report_external_v5.py --evaluation generated/reproduction/external-v5/evaluation.json --output generated/reproduction/external-v5/report

reproduce-v6:
	$(PYTHON) scripts/measure_v6.py restore --scope calibration
	$(PYTHON) scripts/measure_v6.py restore --scope test
	$(PYTHON) scripts/evaluate_v6.py score --output generated/reproduction/v6/evaluation.json
	$(PYTHON) scripts/report_v6.py --evaluation generated/reproduction/v6/evaluation.json --output generated/reproduction/v6/report

reproduce-v8:
	$(PYTHON) scripts/reproduce_v8_applications.py

reproduce-v9-coverage:
	$(PYTHON) scripts/reproduce_v9_coverage.py

reproduce-v10d-hardware:
	$(PYTHON) scripts/audit_v10d_hardware.py --root results/2026-10-15-v10d-csd-hardware --output generated/reproduction/v10d/independent-audit.json

diagram:
	$(PYTHON) scripts/render_architecture.py

reproduce-v10d-timing:
	$(PYTHON) scripts/audit_v10d_timing.py --root results/2026-10-15-v10d-timing --output generated/reproduction/v10d-timing/independent-audit.json
