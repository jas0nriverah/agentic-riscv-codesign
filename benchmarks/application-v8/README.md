# Input-only application feasibility

`cohort-preflight.json` records parent admission after six bounded attempts:
bitcount, FFT, NDES and H264 are four primary algorithm families; isqrt is a
related MiBench/basicmath source control. There are150 primary all-ROI
program/formula rows plus2 isqrt rows. MPEG2 is retained as a failed complete
trace attempt and is not retried or reduced to a smaller window.

These are complete **declared benchmark computation regions** (`*_main`) with
all called helpers. Initialization, upstream return checks and supplemental
snapshot probes occur outside markers. The sources are kernel fragments, not
complete end-user applications/codecs. Kernel/helper attribution is secondary;
all-ROI formulas are the primary candidate pool. No top-K selection occurs.

TACLeBench source commit:
`c6a0d73e47bbd2bc86e34637156fb26dd4d5cf08` from
https://github.com/tacle/tacle-bench . Exact source/input/notice bytes are also retained in the portable archive below; a separately fetched checkout may be used.
`programs[*].upstream_source_sha256` binds all files in each program directory,
and `compiled_c_files` is the exact compile whitelist. Preserve the notices
under `source-notices/` when redistributing the upstream code. These notices
have different provenance and terms; the paper's license is not a code license.
No upstream algorithm or original input is changed by the snapshot adapters.

Existing raw traces/ELFs/fusion files are under
`generated/application-input-feasibility/` and are referenced by exact SHA in
the preflight manifest. The470MiB incomplete MPEG2 trace is deliberately retained
outside source control. Its300s owned-group trace deadline ended without a
complete marker window; the recorded cleanup exception is
`PermissionError(1, 'Operation not permitted')`. No process remained afterward.
Its official raw checksum−116 passed O0/O2; the external status adapter matches
upstream `main` rather than pretending the checksum is zero.

Input evidence validation (no program execution, fitting or target mapping):

```sh
.venv/bin/python scripts/collect_v8_applications.py
```

Reproduction requires restored raw evidence, the exact reviewed tool binaries
(SHA in manifest) and a checkout of the pinned source. To create a separate
attempt without overwriting anything:

```sh
.venv/bin/python scripts/collect_v8_applications.py --reproduce \
  --reference-dir /path/to/pinned/tacle-bench \
  --cc /path/to/riscv-none-elf-gcc \
  --objdump /path/to/riscv-none-elf-objdump \
  --spike /path/to/spike \
  --output generated/application-v8-reproduction-attempt-0001
```

This executes only the five admitted programs, uses exact whitelisted C files,
original snapshot adapters and the frozen external-v5 startup/runtime, and
requires original captured outputs, complete markers, no opaque fusion skips,
and the exact historical formula sets. Every build/selfcheck/trace is bounded
(60/60/300s). Any failed attempt is preserved and stops the run. Source/tool
changes require a prospective new plan. The script does not synthesize any
circuit, load a model or assign a calibration/test role.

`preflight-evidence/` preserves historical attempt/reconciliation records and
scripts, including helper mistakes and isqrt supplemental failures. Historical
scripts encode their original scratch layout; use the new collector for a new
attempt rather than relocating those scripts and overwriting old evidence.
The preflight manifest is an input-admission record, not a prediction/model or
resource-label release freeze. A later corpus plan must bind this manifest,
collector, source files, all features, artifacts and predictions separately.

Oracle limits: bitcount has independent fixed-input Python PRNG/popcount checks;
isqrt's official inputs match exact mathematical checks but four supplemental
high-u32 calls miss ideal fixed-point sqrt by2–3LSBs; FFT has checksum/output
hash checks; NDES's upstream check covers a key-schedule sum rather than cipher
output; H264 has upstream checks/output hashes. O0/O2 agreement and sampled
fusion checks do not establish universal software correctness or a complete
independent FFT/DES/video oracle. See the preserved per-program records.

Portable raw evidence: `evidence/retained-inputs.zip` is3,275,904bytes with176
SHA-verified regular-file members. `retained-inputs.manifest.json` records every
member and archive hash. It restores all admitted traces/ELFs/candidates/fusion,
MPEG build/selfcheck logs, and exact upstream directory snapshots under
`benchmarks/application-v8/upstream-sources/`. Validate every member before
extracting at repository root. The failed MPEG partial is explicitly omitted;
its local SHA/size/error remain bound by the original preflight and separate
`provenance-amendment.json`. Missing admitted data is never optional.

`evidence/runtime-replay.json` proves exact re-extraction of every full candidate
record, including occurrence/overlapSafeSaved metadata, secondary kernels and
fusion. `evidence/relocated-runtime-replay.json` repeats this after restoration
under a new root with no MPEG partial present. To replay without builds or
workload execution (objdump only):

```sh
.venv/bin/python scripts/collect_v8_applications.py --verify-runtime \
  --reference-dir benchmarks/application-v8/upstream-sources \
  --objdump /path/to/reviewed/riscv-none-elf-objdump \
  --output /path/to/fresh-runtime-replay.json
```

The original preflight bytes stayed immutable after first native input feature
extraction. The separate provenance amendment adds the CountedTrace dependency
and failed-partial publication policy; it does not retry a feature proof or
change any input, accepted normalform, formula pool or row weight.
