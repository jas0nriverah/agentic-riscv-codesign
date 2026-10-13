# Fresh workload collection

The original eight-workload corpus remains under `generated/real`. The separate
`src/run_holdout_benchmarks.py` collector writes exclusively under
`generated/holdout` and accepts an explicit list of upstream Embench workload
directories. It never loads a model. All upstream C files in each selected
workload directory are compiled unchanged with the existing startup, hooks,
and RV32IM flags, using the pinned GCC and Spike installations.

The six families were frozen before extraction or new resource measurements:
`statemate`, `nsichneu`, `minver`, `nbody`, `slre`, and `ud`. Source hashes, flags,
sampling choices, and freeze time are retained in `benchmark_choices.json`.
Each ELF first passes Embench's native self-check in Spike. The same ELF then
runs with commit logging. The original strict `tracing.parse_trace` validates
exactly two retired-instruction markers, equality between marker delta and
window commits, and zero undecoded instructions. Full window records are saved
as gzip JSONL; exact PC counts and block starts are accumulated while writing,
including the end-window block boundary. All formulas are extracted with
`--max-size 4`, with no candidate truncation.

The control workloads `statemate` and `nsichneu` have validated executions but
zero candidates under the current safety-constrained extractor. They remain
in coverage metadata; they cannot contribute candidate prediction metrics.
The saved `zero_candidate_diagnostics.json` reports actual operation mixes and
executed block structure. `nsichneu` has 825 executed blocks (maximum eight
instructions), only 0.056% eligible dynamic operations, and no eligible-to-eligible
dependency edges. `statemate` has 63 executed blocks and 9.04% eligible dynamic
operations, but only one connected eligible pair, in libc `memset`. Its original
input x12 is overwritten by an intervening operation before the proposed final
replacement point, so the input-lifetime rule rejects it. The extractor was not
relaxed and neither workload was substituted.

The numerical workloads `minver` and `nbody` use software floating point on
RV32IM; the resulting circuits include library integer sequences.

The initial synthesis sampling policy was 48 formulas per workload, half top
instruction merit and half seeded random remainder. Before any holdout model
scoring, the parent froze expansion to the full 198-candidate pool. That
label-independent inclusion decision is recorded in `full_pool_choices.json`;
the initial selected rows remain under `initial_sampling/selection.json`.
The full pool uses `per_benchmark=10000`, which exceeds every family count.

Reproduce the collection from the repository root (use a fresh output
subdirectory if the frozen choices differ):

```sh
.venv/bin/python src/run_holdout_benchmarks.py \
  --programs statemate nsichneu minver nbody slre ud \
  --cc ../toolchains/xpack-riscv-none-elf-gcc-15.2.0-1/bin/riscv-none-elf-gcc \
  --objdump ../toolchains/xpack-riscv-none-elf-gcc-15.2.0-1/bin/riscv-none-elf-objdump \
  --spike ../toolchains/spike/bin/spike \
  --spike-source ../toolchains/spike-source \
  --output generated/holdout/reproduction \
  --max-size 4 --per-benchmark 10000 --synthesize
```

`benchmarks.json` records tool versions/commits, source and ELF hashes, command
logs, trace hashes, self-checks, counter validation, and candidate counts.
`extraction_equivalence.json` checks every occurrence independently and checks
all non-overlapping occurrences of each formula jointly, comparing registers,
modeled memory, and control results with 16 seeded random states per block.
`experiment/verification.json` records actual Verilator comparisons against
the formula oracle, including edge cases and 1,024 seeded random input pairs.
`experiment/circuits/*` retains RTL, complete Yosys logs, generic and iCE40
netlists, and measured metrics; `experiment/dataset.json` contains the final
measured labels. Both equivalence checks are sampled, not formal proof.

The labels represent isolated combinational LUT4/carry resources, generic
gates, and generic gate depth. They do not measure chip area, routed timing,
architectural cycles, or processor speedup. Full candidate inclusion is frozen
before scoring; exact formula overlap with the original training corpus must
be excluded and disclosed in novel-formula evaluation by the downstream
protocol. None of this collection changes or retrains the original model.

## Final independent collection

The remaining five upstream families were separately frozen before their new
labels: `cubic`, `picojpeg`, `qrduino`, `sglib-combined`, and `st`. They are saved
under `generated/final-holdout` with the same flags, tools, self-checks, full
gzip traces, four-operation extractor, full candidate inclusion, and correctness
checks. No workload was replaced or extractor constraint relaxed. Their 561
rows cover 453 distinct circuits; all synthesis jobs succeeded. All five
self-checks and 18,614,267 measurement-window instructions passed counter and
decode validation. All 1,581 fusion occurrences passed 25,296 individual and
23,232 joint block comparisons, with no skipped occurrences; actual Verilator
passed 509,172 formula/input comparisons.

Final resource labels remained unopened by the collection agent. The parent
reported conservative policy commit `2ace107` frozen before accessing final
labels; the blinded synthesis pipeline could run while the policy was being
finalized. The collection agent reported only counts/status and correctness
evidence. The policy uses the previous six-family stage as calibration; final
novel-formula metrics must therefore exclude both original training formulas
and formulas present in that calibration stage.

The collector accepts `--benchmarks` as an alias for `--programs`. For this
collection, replace the six-family list in the command above with the five
final families and use `--output generated/final-holdout/reproduction`. Full
synthesis is deferred if the extracted pool has 1,000 or more unique circuits;
all collected candidates/traces remain available for explicit review. The
existing default output and 48-per-family sampling option are preserved.
