# Legacy RV32IM/Spike extraction flow below. New integrated RV32I processor
# contexts use isaforge.guarded_workload; see docs/guarded-sha256.md.
# Frozen older entrypoints remain available for their historical experiments.
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
.PHONY: help test reproduce reproduce-v4 reproduce-v5 reproduce-external-v5 reproduce-v6 reproduce-v8 reproduce-v9-coverage reproduce-v10d-hardware reproduce-v10d-timing reproduce-v10d-selection reproduce-v12 diagram
help:
	@echo 'Current ML experiment: make reproduce-jfdctint | make jfdctint-report | make export-seven-source-corpus (no native jobs)'
	@echo 'Preserved SHA model experiment: make reproduce-feasible-benefit | make feasible-benefit-report'
	@echo 'Interactive six-workload demo: make showcase | Four-tool matched controls: make selector-controls'
	@echo 'Current prospective comparison: make sha256-report | make reproduce-sha256 (no native hardware jobs)'
	@echo 'Preserved evidence: make reproduce-budget-campaign | make demo | make reproduce-prospective | make reproduce-speedup'
	@echo 'Research: make test | make reproduce | make reproduce-v4 | make reproduce-v5 | make reproduce-external-v5 | make reproduce-v6 | make reproduce-v8 | make reproduce-v9-coverage | make reproduce-v10d-hardware | make reproduce-v10d-timing | make reproduce-v10d-selection | make reproduce-v12 | make diagram'
	@echo 'make reproduce replays frozen scores/audit/figures; no training or synthesis.'
	@echo 'Legacy RV32IM/Spike extraction: make all | make run | make trace | make candidates'
	@echo 'See docs/README.md for methodology, results, and pinned toolchains.'

test:
	$(PYTHON) -m pytest -q

SHOWCASE_OUTPUT ?= generated/reproduction/selection-showcase
SELECTOR_OUTPUT ?= generated/reproduction/bounded-selector-controls
.PHONY: showcase selector-controls
showcase:
	$(PYTHON) scripts/build_selection_showcase.py --output "$(SHOWCASE_OUTPUT)"

selector-controls:
	$(PYTHON) scripts/run_bounded_selector.py --output "$(SELECTOR_OUTPUT)"

reproduce:
	$(PYTHON) scripts/reproduce_matched.py

.PHONY: reproduce-speedup
reproduce-speedup:
	$(PYTHON) scripts/reproduce_codesign.py replay
	$(PYTHON) scripts/reproduce_workload.py replay

.PHONY: reproduce-selection-research
reproduce-selection-research:
	$(PYTHON) scripts/reproduce_selection_research.py

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

reproduce-v10d-selection:
	$(PYTHON) scripts/reproduce_v10d_selection.py --root results/2026-10-15-v10d-timing --output generated/reproduction/v10d-selection
	cmp generated/reproduction/v10d-selection/policy-results.json results/2026-10-15-v10d-selection/policy-results.json

reproduce-v12:
	$(PYTHON) scripts/audit_v12_results.py --root results/2026-10-15-v12-target-transform --output generated/reproduction/v12/independent-results-audit.json
	$(PYTHON) scripts/plot_v12_target_transform.py --root results/2026-10-15-v12-target-transform --output generated/reproduction/v12/figures

.PHONY: reproduce-v13 model-diagram
reproduce-v13:
	mkdir -p generated/reproduction/v13
	$(PYTHON) scripts/audit_v13_comparison.py --action results --root results/2026-10-15-v13b-coverage-recovery --output generated/reproduction/v13/independent-results-audit.json
	$(PYTHON) scripts/plot_v13_coverage.py --root results/2026-10-15-v13b-coverage-recovery --output generated/reproduction/v13/figures

model-diagram:
	$(PYTHON) scripts/plot_ml_model_overview.py --output generated/reproduction/ml-model

.PHONY: reproduce-model-analysis
reproduce-model-analysis:
	$(PYTHON) scripts/reproduce_model_analysis.py

.PHONY: reproduce-prospective demo
reproduce-prospective:
	$(PYTHON) scripts/reproduce_prospective.py replay

.PHONY: reproduce-budget-campaign campaign-report
reproduce-budget-campaign:
	$(PYTHON) scripts/reproduce_budget_campaign.py replay

campaign-report:
	$(PYTHON) scripts/report_budget_campaign.py

demo:
	$(PYTHON) scripts/reproduce_prospective.py demo
	$(PYTHON) scripts/style_research_demo.py generated/reproduction/prospective-slre/index.html
	@echo 'Open generated/reproduction/prospective-slre/index.html; SQLite is alongside it.'

.PHONY: reproduce-v14
reproduce-v14:
	$(PYTHON) scripts/audit_v14_routing.py --output generated/reproduction/v14/independent-routing-audit.json

# Fresh guarded SHA256 workload; authenticates prelabel Git chronology and
# raw processor evidence before exact fixed-model/policy replay. No native jobs.
.PHONY: reproduce-sha256 sha256-report
reproduce-sha256:
	$(PYTHON) scripts/reproduce_guarded_sha256.py replay

sha256-report: reproduce-sha256
	$(PYTHON) scripts/report_guarded_selection.py

# Fixed budget-conditioned XGBoost and genuinely new candidate measurements on
# consumed SHA256 source/input. Exact refits are not a new source holdout.
BENEFIT_REPORT_OUTPUT ?= generated/reproduction/feasible-benefit-report
BENEFIT_CORPUS_OUTPUT ?= generated/reproduction/expanded-model-corpus
.PHONY: reproduce-feasible-benefit feasible-benefit-report export-model-corpus
reproduce-feasible-benefit:
	$(PYTHON) scripts/reproduce_disjoint_sha256.py replay

feasible-benefit-report:
	$(PYTHON) scripts/report_feasible_benefit.py --output "$(BENEFIT_REPORT_OUTPUT)"

export-model-corpus:
	$(PYTHON) scripts/export_feasible_pool_corpus.py --output "$(BENEFIT_CORPUS_OUTPUT)"

# One fresh BEEBS source, a fixed factorized model, and eleven unchanged controls.
JFDCTINT_REPORT_OUTPUT ?= generated/reproduction/jfdctint-report
SEVEN_SOURCE_CORPUS_OUTPUT ?= generated/reproduction/seven-source-corpus
FACTORIZED_DIAGNOSIS_OUTPUT ?= generated/reproduction/factorized-source-diagnosis
.PHONY: reproduce-jfdctint jfdctint-report export-seven-source-corpus diagnose-factorized-selection
reproduce-jfdctint:
	$(PYTHON) scripts/reproduce_jfdctint.py

jfdctint-report:
	$(PYTHON) scripts/report_jfdctint.py --output "$(JFDCTINT_REPORT_OUTPUT)"

export-seven-source-corpus:
	$(PYTHON) scripts/export_jfdctint_corpus.py --output "$(SEVEN_SOURCE_CORPUS_OUTPUT)"

diagnose-factorized-selection:
	$(PYTHON) scripts/diagnose_factorized_selection.py --replay results/2026-10-21-factorized-development --output "$(FACTORIZED_DIAGNOSIS_OUTPUT)"

# Larger pools, three independently held-out sources, unchanged twelve policies.
# Each derived output must be fresh; override these variables on subsequent runs.
BLIND_REPLAY_OUTPUT ?= generated/reproduction/blind-campaign
BLIND_REPORT_OUTPUT ?= generated/reproduction/blind-report
BLIND_CORPUS_OUTPUT ?= generated/reproduction/blind-corpus
.PHONY: reproduce-blind-campaign blind-report export-blind-corpus
reproduce-blind-campaign:
	$(PYTHON) scripts/blind_campaign.py replay --campaign results/2026-10-21-blind-campaign --preregistration results/2026-10-21-blind-preregistration --output "$(BLIND_REPLAY_OUTPUT)"

blind-report:
	$(PYTHON) scripts/report_blind_campaign.py --output "$(BLIND_REPORT_OUTPUT)"

export-blind-corpus:
	$(PYTHON) scripts/export_blind_corpus.py --output "$(BLIND_CORPUS_OUTPUT)"
