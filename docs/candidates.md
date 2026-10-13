# Real trace candidate extraction

Run the study's two-to-four-operation extraction using a validated RV32IM trace
and its matching ELF:

```sh
python src/candidates.py generated/traces/crc32.jsonl \
  generated/programs/crc32.elf generated/real/candidates/crc32.json \
  --max-size 4 --objdump riscv64-unknown-elf-objdump
```

The three positional arguments remain compatible with the original CLI. The
legacy maximum is still five; `--max-size 4` explicitly selects the proposal's
study size. `--limit N` optionally retains the first N formulas after legacy
merit ranking; complete experiments should omit it. Disassembly failures, trace
addresses absent from the ELF, and inconsistent basic-block execution counts
fail extraction instead of yielding plausible empty or partial results. The
trace is read as a stream, so memory scales with static program size.

## Legality and formula identity

Candidates contain connected allowed integer ALU/multiply operations, at most
two incoming register values and exactly one outgoing value at the final member.
Every candidate member must contribute to that outgoing value. Intermediate
results consumed outside the candidate or still live at block exit are rejected.
Inputs must retain their required values until the replacement point. Unknown
instructions inside the candidate's span are opaque barriers. Register x0 is a
constant and never an input or a data dependency. Static branch targets,
dynamic trace discontinuities, address gaps, and the trace region's final
boundary split basic blocks.

This is deliberately conservative liveness analysis: every final register write
in a block is treated as live, even when later blocks might overwrite it. It does
not discover maximal opportunities requiring global liveness, scheduling,
compiler rewriting, memory fusion, or more than two input registers.

Equivalent expression text is merged. Shared DAG nodes and repeated original
computations can yield the same expression at different sizes. `size` is the
smallest original occurrence size, `sizeVariants` lists all encountered sizes,
and every occurrence records its actual distinct-operation count. This makes
size selection deterministic; the former set iteration could pick a different
representative between runs. Formula ties are now ordered alphabetically.

## Output fields and the claims they support

Each JSON row retains the original fields:

| Field | Meaning |
| --- | --- |
| `formula` | Canonical register-independent expression text. |
| `size` | Smallest distinct-operation occurrence size. |
| `runs` | Sum of dynamic executions of every matching static occurrence, including overlap. |
| `places` | Number of matching static occurrences, including overlap. |
| `saved` | Legacy heuristic `(size - 1) * runs`; used for the existing merit ranking. |
| `savedPercent` | That heuristic divided by all traced instructions, as a percentage. |

The additional fields make the accounting auditable:

| Field | Meaning |
| --- | --- |
| `traceTotalInstructions` | Full measured-region trace instruction count, including noneligible operations. |
| `occurrences` | Each matching block start, sorted PC set, containing function `symbols`, block execution count, actual size, and `selectedForSavings` flag. |
| `sizeVariants` | Distinct original sizes represented by the formula. |
| `occurrenceSaved` | Sum of `(occurrence.size - 1) * occurrence.blockRuns`, before overlap removal. |
| `nonOverlappingPlaces` | Number of accepted static occurrences after overlap removal. |
| `nonOverlappingRuns` | Dynamic execution count summed over those accepted occurrences. |
| `overlapSafeSaved` | Sum of `(occurrence.size - 1) * occurrence.blockRuns` over accepted occurrences. |
| `overlapSafeSavedPercent` | That reduction divided by `traceTotalInstructions`. |
| `overlapSelectionMethod` | `deterministic-greedy-pc-disjoint`. |

The overlap algorithm operates separately for each formula and basic block. It
considers larger occurrences first, breaks ties by ascending PC sets, and accepts
only occurrences whose PCs are disjoint from previously accepted occurrences.
This is conservative set packing, not an optimal maximum. Selected PC metadata
is retained so the result can be recomputed independently. The same formula's
occurrences cannot remove an original instruction twice. Two different formulas
can overlap; **their savings cannot be summed** without joint selection and
measurement.

All savings quantities are software instruction-count estimates. They assume
each legal occurrence becomes one custom instruction with the same semantics,
and are useful for generating a timing-aware synthesis estimate. They are not
observed processor cycles, actual speedup, integrated processor area, or clock
frequency. Spike's instruction trace establishes execution frequencies, not the
latency of the proposed extension. Standalone formula synthesis also does not
establish processor decode, pipeline, register-file, or routing overhead.

Tests cover overlapping repeated occurrences, dead branches in connected graphs,
input overwrites, escaping outputs, x0, opaque barriers, trace boundaries,
consistent grouping of shared/repeated expressions, failed disassembly, CLI
compatibility, and actual fusion equivalence on randomized small RV32 blocks.

Function symbols identify whether occurrences belong to the central kernel or
support routines executed inside the measured region. For example, a frequent
pattern in `beebs_rand` reflects the benchmark's pseudorandom generation cost and
should not be described as a kernel-specific arithmetic acceleration.

## Validate original-block replacement

The separate extraction check executes the actual disassembled blocks on seeded
random register states, models byte loads/stores and branch destinations, and
compares the entire final state before and after candidate replacement:

```sh
python src/verify_candidate_fusions.py --vectors 16 \
  --objdump riscv64-unknown-elf-objdump \
  --output generated/real/extraction_equivalence.json
```

It checks each original occurrence and the joint selected occurrences of one
formula in each block. Static block starts come from occurrence metadata and
static control flow; blocks containing unsupported instructions are explicitly
counted as skipped. The initial eight-benchmark run checked all 1,539 occurrences
with no skips: 24,624 individual and 8,880 joint replacement comparisons passed.
These are software state comparisons with modeled memory. The separate
Verilator stage checks actual generated RTL on independent input vectors.
Neither stage is a formal proof or a test of an extended processor.
