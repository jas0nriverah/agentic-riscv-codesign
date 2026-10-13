# Reproduce the measured research

Run commands from the repository root. The recorded workflow runs locally after its sources, toolchains, Python environment, and model artifacts are available. Fetching packages/submodules/toolchains requires network access; later tracing, verification, synthesis, inference, and RTL simulation do not require a cloud inference service. This document reproduces evidence, without retraining models on the independent test sets.

## Inputs, tools, and provenance

The repository retains the original corpus/model in `results/2026-10-13`. Prospective datasets, frozen models, evaluations, and deployment artifacts are copied under `results/2026-10-13-prospective/`. Large traces and complete circuit logs live under ignored `generated/` directories and require the accompanying evidence archive or regeneration. V2 artifacts are `results/2026-10-13-prospective/models/{resource-ridge,area-model-v2}.joblib` with adjacent JSON schemas and `preregistration.json`; the frozen policy is `results/2026-10-13-prospective/policy/conservative.json`.

Use the recorded versions, not an unrecorded tool update:

| Input/tool | Recorded version |
| --- | --- |
| Embench | `0466a18e4f6b47e19598d7c6ba72916d54b68f65` |
| GCC | xPack RISC-V embedded 15.2.0-1 |
| Spike | `f8a060b7bea8da6f738f193ed1b66b665978d092` |
| PicoRV32 | `ef203c2b0a3fb793280f5114941416c425c5b461` |
| Yosys | `0.69+post`, source `143eb14f9cc55d6f8927e68523b0c9d2166ed02c` |
| Verilator | `5.050`, recorded build `20260701` |
| Python numerical stack | Versions in the saved model schemas |

[Toolchain instructions](toolchain.md) give GCC archive SHA-256 and Spike build commands. The local toolchain directory in this run was `../toolchains`. Yosys and Verilator must be on `PATH`. Install this repository's Python environment using `pyproject.toml`; the recorded environment uses NumPy 2.5.4, SciPy 1.18.1, scikit-learn 1.9.1, XGBoost 3.4.1, and joblib 1.6.0. Use the schemas to verify the environment before expecting identical predictions.

```sh
.venv/bin/python -m pytest -q
../toolchains/xpack-riscv-none-elf-gcc-15.2.0-1/bin/riscv-none-elf-gcc --version
../toolchains/spike/bin/spike --help
yosys -V
verilator --version
git -C benchmarks/embench rev-parse HEAD
git -C ../toolchains/picorv32 rev-parse HEAD
```

Model loading checks schemas/artifact hashes; V2 also checks its recorded runtime-source hashes and configuration. Preserve the frozen source revision. The original v1 serialization was mechanically migrated to its canonical Python module without refitting; migration evidence preserves learned parameters and all original-row predictions. Do not silently train a replacement and call it the original artifact.

## Replay frozen inference and final evaluation

These commands use existing measured final data and frozen artifacts. They create separate replay files and retain the original evaluation. Inference strips all hardware labels and dynamic features before invoking a model; every repeated batch must return identical predictions.

```sh
.venv/bin/python -m isaforge.frozen_inference \
  --kind v1 --model results/2026-10-13/model/area-model.joblib \
  --candidates results/2026-10-13-prospective/final/dataset.json \
  --output generated/final-holdout/replay/v1.json

.venv/bin/python -m isaforge.frozen_inference \
  --kind v2 --model results/2026-10-13-prospective/models/resource-ridge.joblib \
  --candidates results/2026-10-13-prospective/final/dataset.json \
  --output generated/final-holdout/replay/resource.json

.venv/bin/python -m isaforge.frozen_inference \
  --kind v2 --model results/2026-10-13-prospective/models/area-model-v2.joblib \
  --candidates results/2026-10-13-prospective/final/dataset.json \
  --output generated/final-holdout/replay/v2.json

.venv/bin/python -m isaforge.conservative_policy apply \
  --calibration results/2026-10-13-prospective/policy/conservative.json \
  --predictions generated/final-holdout/replay/v2.json \
  --output generated/final-holdout/replay/conservative.json

.venv/bin/python -m isaforge.fresh_evaluation \
  --training-rows results/2026-10-13/dataset.json \
  --calibration-rows results/2026-10-13-prospective/transfer/dataset.json \
  --test-rows results/2026-10-13-prospective/final/dataset.json \
  --coverage results/2026-10-13-prospective/final/summary.json \
  --predictions v1=generated/final-holdout/replay/v1.json \
  --predictions resource=generated/final-holdout/replay/resource.json \
  --predictions v2=generated/final-holdout/replay/v2.json \
  --policy-predictions conservative=generated/final-holdout/replay/conservative.json \
  --output generated/final-holdout/replay/evaluation.json
```

Expected final counts are 561 rows, 453 unique test formulas, and **331 novel formulas absent from both training and calibration**. Point-model novel MAEs are approximately 87.595 (v1), 23.154 (resource), and 33.165 (v2). Policy acquisition scores do not appear in accuracy metrics. The primary cap64/budget1 endpoint ties all models and merit at 1.000 retention. These checks must preserve the negative/tie findings, not select a policy after reading final results.

Timing sidecars distinguish model loading, first batch, and 20 warm batches. Warm inference excludes JSON IO and process startup. Bootstrap intervals resample programs; random-policy seeds are first averaged within programs. The fixed sensitivity grid is caps 32/64/128, budgets 1/3/5, and random seeds 0–99.

To replay stage two, use the same three inference commands with `results/2026-10-13-prospective/transfer/dataset.json`, then evaluate with `--coverage results/2026-10-13-prospective/transfer/summary.json`, no `--calibration-rows`, and no policy scores. Expected counts are 198 rows, 167 formulas, 81 novel formulas, six declared programs, and four candidate-bearing programs. V1/v2 primary retention is 0.855 versus merit 1.000; SLRE retention is 0.419. Statemate/nsichneu remain in coverage despite their empty pools.

## Regenerate untouched workloads and full resource pools

Use fresh output subdirectories so existing benchmark choices and reports remain intact. `--programs` and `--benchmarks` are aliases; the explicit list, hashes, flags, sampling seed, and freeze time are recorded before extraction or labels. The existing default sampling option is 48; the research's full pools require `--per-benchmark 10000`.

```sh
.venv/bin/python src/run_holdout_benchmarks.py \
  --benchmarks statemate nsichneu minver nbody slre ud \
  --cc ../toolchains/xpack-riscv-none-elf-gcc-15.2.0-1/bin/riscv-none-elf-gcc \
  --objdump ../toolchains/xpack-riscv-none-elf-gcc-15.2.0-1/bin/riscv-none-elf-objdump \
  --spike ../toolchains/spike/bin/spike \
  --spike-source ../toolchains/spike-source \
  --output generated/holdout/reproduction \
  --max-size 4 --per-benchmark 10000 --synthesize

.venv/bin/python src/run_holdout_benchmarks.py \
  --benchmarks cubic picojpeg qrduino sglib-combined st \
  --cc ../toolchains/xpack-riscv-none-elf-gcc-15.2.0-1/bin/riscv-none-elf-gcc \
  --objdump ../toolchains/xpack-riscv-none-elf-gcc-15.2.0-1/bin/riscv-none-elf-objdump \
  --spike ../toolchains/spike/bin/spike \
  --spike-source ../toolchains/spike-source \
  --output generated/final-holdout/reproduction \
  --max-size 4 --per-benchmark 10000 --synthesize
```

Each workload is built from all unchanged upstream C files, self-checks in Spike, and traces the exact same ELF. Full window records are gzip JSONL; PC counts/block starts accumulate during writing. Candidate pools are untruncated at four distinct operations. A 1,000-unique-circuit guard defers synthesis rather than silently samples an oversized pool. Existing frozen choices cannot be changed in place. Build/trace failures stop collection and retain evidence; they do not authorize substituting a workload.

Evidence gates and expected results:

| Gate | Stage two | Final |
| --- | ---: | ---: |
| Self-checks | 6/6 | 5/5 |
| Validated instructions | 16,520,138 | 18,614,267 |
| Candidate rows / distinct circuits | 198 / 167 | 561 / 453 |
| Fusion occurrences checked | 424 | 1,581 |
| Individual block comparisons | 6,784 | 25,296 |
| Joint block comparisons | 6,528 | 23,232 |
| Verilator comparisons | 187,708 | 509,172 |
| Skipped occurrences / synthesis failures | 0 / 0 | 0 / 0 |

`benchmarks.json` retains commands, versions, hashes, counters, and candidate counts. `extraction_equivalence.json` compares all architectural registers, modeled memory, and control effects. `experiment/verification.json` records Verilator checks against the integer oracle. Circuit folders retain Verilog, Yosys scripts/logs, generic/iCE40 netlists, and metrics. `collector_checks.json` independently reproduces one saved-gzip extraction and checks source/ELF hashes. These sampled tests do not constitute formal proof.

Stage-two `initial_sampling/` preserves the original 48-per-family run; `full_pool_choices.json` records expansion before scoring. Expansion summaries include circuit-cache hits, so their wall times must not be described as cold full-pool synthesis time. The prediction target is isolated `SB_LUT4`; carry cells are separate, and zero-LUT circuits may still require other resources.

The original eight-workload collector and full study use [original reproduction instructions](toolchain.md) and `results/2026-10-13/README.md`. For exact study extraction, invoke `src/candidates.py --max-size 4`; the legacy Makefile candidate target otherwise uses the extractor's default five-operation limit.

## Reproduce processor cycles and whole-core mapping

```sh
.venv/bin/python -m isaforge.core_experiment \
  --core-dir ../toolchains/picorv32 \
  --toolchain-prefix ../toolchains/xpack-riscv-none-elf-gcc-15.2.0-1/bin/riscv-none-elf- \
  --output-dir generated/core/reproduction \
  --latencies 0 1 4 16 24
```

The script requires a clean checkout at the pinned processor revision. It saves licensed sources, firmware/disassembly, tool versions, simulator commands, decoded results, controls, Yosys netlists, and source hashes. All variants share core parameters, external zero-wait memory, counter windows, and clock assumptions. `CUSTOM` firmware deletes actual native instructions. Baseline-on-extended-core results must match, zero-work windows must match, host oracles and firmware checks must pass, unsupported encodings must trap, and PCPI counts must match instruction counts and response latency.

The default also measures the full source-modified Embench CRC32 RV32I port, with original stock and source-wrapper controls. Expected baseline cycles are 27,685,314; both formulas yield 25,770,434 at one wait cycle, or 25,422,274 for combinational response. Both delete 522,240 instructions in this compiled benchmark. The full checksum is 1,703,161,001; the upstream result is 11,433. Whole-core LUT4 counts are 1,488 baseline, 1,625 registered both-formula extension, and 1,570 combinational both-formula extension. All other resource types are also recorded.

These figures measure simulated cycles under matched settings. Source-level lowering can change allocation, the RV32I generator uses software multiplication, external RAM is excluded from the core mapping, and board clock/runtime have not been measured. Recurrence ratios are separate evidence from complete CRC32 benchmark ratios. The completed SoC experiment below includes memory; paired routing is documented below, separate from functional cycle counts.

## Reproduce the closed SoC with synchronous memory

```sh
.venv/bin/python -m isaforge.soc_experiment \
  --core-dir ../toolchains/picorv32 \
  --toolchain-prefix ../toolchains/xpack-riscv-none-elf-gcc-15.2.0-1/bin/riscv-none-elf- \
  --output-dir generated/soc/reproduction
```

The same synthesized/simulated top contains initialized 8 KiB synchronous byte-write RAM, a request/acknowledgement controller, and a synchronous result-bit stream. There are eight scalar package pins; none expose external memory. All 20 BRAM blocks use the top clock; 16 implement program/data RAM and four implement the register file. Firmware/data/BSS must fit below 4 KiB, reserving at least 4 KiB for stack. Reset does not reload initialized RAM; each standalone run starts a new design instance.

Expected CRC32 cycles are 32,387,382 baseline and 29,602,102 custom, deleting 522,240 instructions. LUT4 counts are 1,633 and 1,704; both use 20 BRAM. Stock-on-custom and source-wrapper execution controls match cycles, instructions, checksum, and protocol statistics. The source-wrapper binary is **not identical** to stock, which is recorded rather than hidden. Separate firmware checks validate byte stores, load extension, and an out-of-bounds fault. Netlist gates verify scalar ports, inferred RAM, and all BRAM read/write clocks. Use `generated/soc/summary.json` and the matching sources/netlists as authoritative evidence. The equal-clock cycle ratio is 1.0941; paired physical routing is summarized below; board reset/status electrical assumptions remain outside the synchronous clock estimate.

## Reproduce paired closed-SoC routing

```sh
.venv/bin/python -m isaforge.core_routing \
  --synthesis-dir generated/soc/reproduction/synthesis \
  --output-dir generated/soc/routing/reproduction \
  --chipdb /opt/homebrew/Cellar/icestorm/1.1/share/icestorm/chipdb/chipdb-8k.txt \
  --top soc_top --configurations baseline custom \
  --memory-boundary onchip_initialized_memory --frequency 12 --seeds 1 2 3
```

The recorded tools are Homebrew nextpnr-ice40 0.11.1_1 and IceStorm 1.1. Binary/database hashes and the install receipt are saved. Routing targets iCE40HX8K CT256, uses one thread, and fixes clock pin J3 plus a common eight-pin PCF chosen by baseline-only seed-0 placement. Measured runs pair seeds 1, 2, and 3 with identical clock/device/package/router constraints. The bootstrap placement allows unconstrained pins only while choosing them; measured routes use the complete fixed PCF and no timing-failure override.

All six runs fit and meet 12 MHz. Baseline Fmax estimates are 71.803, 70.897, 69.080 MHz; custom estimates are 67.074, 67.454, 72.005 MHz. Paired `(baseline cycles/baseline Fmax)/(custom cycles/custom Fmax)` estimates are 1.02203, 1.04095, and 1.14041, with median 1.04095. Retain every seed: selecting seed 3 alone exaggerates the result. Routed packed logic cells increase from 1,870 to 1,961; this differs from synthesis LUT4 count. All runs include 20 on-chip BRAM and eight I/O sites.

Inspect `generated/soc/routing/{protocol,summary,runs}.json`, detailed per-seed reports/ASCs, and `timing-cycle-comparison.json`. The latter hashes the independent simulation and routing summaries. A shared feasible 12 MHz clock gives estimated benchmark-region durations of 2.69895 and 2.46684 seconds. Fmax and elapsed-time values are timing-model estimates, not measured FPGA-board frequency or runtime. Reset arrival/release and status observation remain asynchronous without board trace/load constraints. See [routing methodology and boundaries](soc-routing.md).

## Deployment refit is a different artifact

The chosen transparent baseline was refit **after** final evaluation on all 1,098 rows / 713 distinct formulas. `results/2026-10-13-prospective/deployment/resource-deployment.joblib` is for future inference and has no independent accuracy test. It must not replace frozen 301-formula models in reported prospective comparisons. Its schema preserves all dataset hashes, training counts, and this status.

To reproduce the refit in a separate directory:

```sh
.venv/bin/python -m isaforge.deployment \
  --rows results/2026-10-13/dataset.json \
  --rows results/2026-10-13-prospective/transfer/dataset.json \
  --rows results/2026-10-13-prospective/final/dataset.json \
  --output generated/deployment/reproduction

.venv/bin/python -m isaforge.frozen_inference \
  --kind v2 --model results/2026-10-13-prospective/deployment/resource-deployment.joblib \
  --candidates results/2026-10-13-prospective/final/dataset.json \
  --output generated/deployment/replay-final.json
```

Prediction strips labels and retains identities. A persistence smoke check confirms loaded and in-memory predictions agree; it is not a new heldout evaluation. Another untouched workload family or independently collected target is needed to test the refit.

## Freeze and cost accounting

The earlier [transfer protocol](fresh-evaluation-protocol.md) fixes accuracy and decision endpoints. The [final policy protocol](final-policy-protocol.md) fixes the revised margin policy before final labels are opened. V2/policy code and parameters were not tuned after final evaluation. Final resource labels remained blinded while collection proceeded; the policy freeze is commit `2ace107`.

Actual measurement costs include the original 301 circuits, another 167 stage-two circuits used as calibration, and 453 final oracle circuits. There are 713 distinct formulas across stages, but 921 summed stage measurements because overlap was remeasured. Each offline acquisition trial's 1/3/5 budget excludes historical training/calibration and exhaustive oracle work. Inference timing alone cannot demonstrate end-to-end acceleration of the measurement process. Preserve both historical costs and failed comparisons when exporting results.
