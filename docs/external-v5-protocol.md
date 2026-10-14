# External V5 input collection protocol

This cohort collects actual external application formulas, correctness controls,
and retired-instruction activity. It authorizes no model predictions or FPGA
resource labels. Any accuracy or processor-speedup evaluation requires a later
prediction/measurement freeze and its own protocol.

The fixed official TACLeBench commit is
`c6a0d73e47bbd2bc86e34637156fb26dd4d5cf08`.
The initial programs are `dijkstra` (graph shortest paths), `adpcm_dec` (speech
codec), and `anagram` (packed multiset word search). Their exact source/input
hashes are in `benchmarks/external-v5/fetch.json`. Preserve its per-program
notices; no uniform suite license or specific GPL version is inferred.

All are distinct algorithmic sources from the consumed historical Embench
programs. This does not imply formula independence: report overlap against all
consumed development formulas before any future independent transfer claim.
The previously inspected V4 test remains development permanently.

Before building or tracing, the collector writes `input-plan.json` with this
protocol, collector/extractor/startup/wrapper/hook hashes, source/input hashes,
tool executable identities, flags, the inclusion rule and downselection rule.
Every program remains represented if it fails or yields no candidate. Completed
collections are immutable. Incomplete collections require a fresh output directory once execution has
started, preserving every log/ELF/partial trace. A prepared input plan can resume
only before execution and with identical source/plan hashes.

Compilation uses RV32IM, ILP32, GCC O2, GNU17, no LTO or compressed/FPU extension.
Initialization runs once, then one declared workload invocation lies between
the two existing `instret` hooks. Checks/output run after the stop marker. Dijkstra traces only the original graph search for pair (0,50), while its full
20-path checksum runs before markers and its vector diagnostic afterward. This
is explicitly a partial-workload discovery trace, not the original complete
20-path application trace. ADPCM and anagram retain their full pinned core.
No
Embench warmup or repetition factor is inherited. The startup/linker and Spike
`--isa=rv32im_zicntr -m16` match the existing workflow. Spike activity is retired
instructions, not target cycles, board timing, or application speedup.

Upstream files are fetched unchanged into the generated evidence folder and
verified individually by SHA256. Separate adapters expose output buffers and
produce correctness diagnostics. The anagram adapter includes upstream C
unchanged to access its file-local buffer; single-phrase diagnostic probes
reproduce its core call sequence and are outside the traced/scored cohort.
All source and adapter differences are explicit in retained build records.

Correctness checks are fixed before tracing:

- Dijkstra's checksum must pass. A separate Python heap shortest-path algorithm
  computes all 20 target distances from the pinned 100x100 matrix. A diagnostic
  replay after the stop marker emits the C algorithm's corresponding distances,
  and every element must match. This adds a full selected-vector control to the
  original checksum; it does not capture each original loop iteration directly.
- ADPCM's checksum must pass. The actual source decodes two compressed codes
  (`0`, `253`) into four samples; the unused third code and introductory comment
  do not justify claiming a long audio workload. An independent mathematical
  derivation checks all four samples. It models initial zero predictor state,
  quantized reconstruction, second-step predictor terms and QMF taps for this
  exact instance. It is not an independent implementation of a general G.722
  decoder and does not validate arbitrary input streams.
- Anagram's upstream prefix check must pass. Host checks require a terminated
  answer, dictionary membership of every output word, and exact preservation
  of the input phrase's letter multiset. Separate fresh-process probes validate
  witnesses for all three phrases. These checks validate returned witnesses,
  not enumeration completeness or the correctness of every intermediate state.
- All three stock programs run from the same source at O0 as a compiler control;
  their full output vectors must equal O2. Compiler agreement is an additional
  control, not an independent algorithm oracle or a portability proof.

Source-specific constraints remain visible: ADPCM uses signed fixed-point
arithmetic and arithmetic right shifts; anagram's fixed heap and four-byte
alignment suit ILP32. The wrapper asserts 32-bit int/long/pointers. No arbitrary
source rewriting or compiler-flag workaround is silently introduced on failure.

Cohort01 is preserved as an infrastructure failure: HTIF stdout and the commit
logger shared a stream, causing shutdown timeouts despite successful source
checks. Cohort02 uses separate descriptors and the input-only Dijkstra scope
amendment above. No hardware labels or model predictions informed that change.
Only a self-checked, unchanged O2 ELF is traced. Retain complete measurement-window
commits as gzip JSONL, tool logs, counters and ELF hash. A separate inherited commit pipe keeps program
HTIF output outside the parser stream. The operational deadline is saved in the
plan; it kills only the collector-created process group and retains partial
streams/logs on failure. The existing parser must
find exactly two markers, zero unknown instructions, and delta = trace count + 1.

Candidate inclusion uses functions whose symbol starts with that program's
namespace (`dijkstra_`, `adpcm_dec_`, `anagram_`). Wrapper/main/runtime functions
are excluded. Symbol boundaries also become block boundaries. The full trace is
retained; the candidate merit denominator is application-scope instructions.
Extraction uses the unchanged RV32 candidate logic, maximum distinct size four,
and all qualifying formulas. Preserve all occurrences, source symbols and full
candidate lists, then run the existing randomized register/memory/control fusion
checks with 16 vectors and seed `2026101503`.

For a manageable input-only future cohort, retain at most 200 formulas per
program ordered by SHA256(`seed:canonical_formula`), then canonical formula for
ties. This selection sees no area labels, model predictions or correctness
outcomes beyond admission of a passing program. Full candidate pools remain
available. Empty/failed programs remain explicit; they are not replaced by more
favorable sources. All selected formulas are written as unlabelled dataset rows.

No automatic target synthesis, model loading, normalization-based relabeling,
or baseline selection is allowed in this collector. Future work must freeze
model/configuration/calibration/comparator predictions before measuring ORIGINAL
emitted RTL, retain all failures, and publish exact canonical/structural overlaps.
Whole-processor integration and complete output checks are separate requirements
for application-acceleration claims.

Run from the repository root:

```sh
.venv/bin/python scripts/collect_external_v5.py \
  --reference-dir ../references/tacle-bench \
  --output generated/external-v5/cohort-02
```

Without `--reference-dir`, the exact selected upstream files are downloaded from
the pinned official commit; each expected hash must match before use. No upstream
build script executes. No compiler/simulator command runs until the input plan
is saved. Evidence resides exclusively under `generated/external-v5`.
