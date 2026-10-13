# Candidate features and measurement data

`isaforge.features.extract_features(candidate)` consumes the existing
`src/candidates.py` JSON format. `isaforge.dataset.build_dataset(benchmark,
candidates, measurements=None)` joins optional experiment records to those
candidates and returns one flat dictionary per candidate, in input order.

## Discovery candidates

```json
{
  "formula": "add(in0,addi(in1,1))",
  "size": 2,
  "runs": 40,
  "places": 1,
  "saved": 40,
  "savedPercent": 5.0
}
```

`size` is the number of original instruction nodes (integer, at least two).
`runs` is the aggregated dynamic execution count (nonnegative integer), and
`places` counts static occurrences (positive integer). `saved` must equal
`(size - 1) * runs`. `savedPercent` is a finite nonnegative number reported by
discovery; its denominator cannot be reconstructed from this record.

These are instruction-saving heuristics, not measured cycles or speedup.
Discovery can count overlapping occurrences of a pattern, so even a single
pattern's reported percentage can exceed 100. Selection must obtain timing
labels independently; it cannot turn `saved` into a measured performance label.

The formula parser uses a restricted structural grammar, without `eval`, Python
AST evaluation, imports, or executable expressions. Only operations eligible in
the existing extractor are accepted:

```text
add sub and or xor sll srl sra slt sltu
addi andi ori xori slli srli srai slti sltiu
lui mul mulh mulhu mulhsu
```

Operations have two operands except `lui`, which has one. Immediate operations
require an integer as their final operand; `lui` requires an integer operand.
Leaves are `in0`, `in1`, or signed decimal integers in the RV32 value range
[-2^31, 2^32 - 1]. Zero represents the architectural zero register as well as
literal zero. Whitespace between tokens is allowed. The formula root must be an
operation. Other inputs, unknown operations, incorrect arity, trailing text,
floating point literals, and executable syntax are errors. Length and nesting
limits prevent unbounded parsing work. This is structural validation; it does
not certify hardware timing or prove semantic equivalence to the source binary.

## Stable identity

`candidate_id(benchmark, formula)` returns a full SHA-256 hex digest of a compact
JSON array containing the exact nonempty benchmark string and canonical parsed
formula. Whitespace between formula tokens and decimal leading zeros normalize
away; operand order is preserved. Benchmark names are case sensitive. For the
example above under benchmark `crc32`, the ID is:

```text
3302689d1a1434f31a60cc450465d3fa431c581abb9eeed925d65c1fb47c9eb4
```

This identity is scoped to a formula within a benchmark. Changes in binary,
compiler settings, or trace require a separate experiment dataset; this schema
does not hash those artifacts. A candidate's optional supplied `candidate_id`
or `benchmark` must agree with the computed identity and dataset benchmark.
Duplicate canonical formulas within one benchmark are rejected.

## Model feature columns

`FEATURE_COLUMNS` is an ordered tuple. Every feature is stored directly on each
dataset row, alongside `candidate_id`, `benchmark`, and `formula`.

| Feature | Meaning |
| --- | --- |
| `size`, `runs`, `places`, `saved` | Validated discovery metadata |
| `saved_percent` | Discovery's `savedPercent` with a Python field name |
| `depth` | Maximum number of operations on a root-to-leaf path |
| `tree_op_count` | Number of operation occurrences in the textual tree |
| `input_count` | Number of distinct input leaves, at most two |
| `constant_count` | Number of literal occurrences, including zero leaves |
| `unique_constant_count` | Number of distinct literal values |
| `max_abs_constant` | Largest absolute literal, or zero when none occur |
| `op_<mnemonic>` | Occurrence count for each eligible operation |

The textual formula is an **expression tree**, whereas the extracted candidate
is a dataflow graph that may share intermediate values. For example,
`add(mul(in0,in1),mul(in0,in1))` can come from two instructions when both operands
read the same multiplication result. Its `size` can therefore be two while
`tree_op_count` is three and `op_mul` is two. Equal subtree text does not prove
that the original graph shared an instruction. Tree features count textual
occurrences and `size` retains the extractor's original distinct-node count.
The schema deliberately does not infer graph sharing from textual equality.

Timing, area, speedup, provenance, IDs, and formula text are excluded from
`FEATURE_COLUMNS`. Predictors must explicitly select this tuple to prevent
label leakage; inference rows may omit all labels.

## Timing and area records

```json
{
  "candidate_id": "3302689d1a1434f31a60cc450465d3fa431c581abb9eeed925d65c1fb47c9eb4",
  "measurement_source": "gem5",
  "baseline_cycles": 1000,
  "candidate_cycles": 500,
  "baseline_period_ns": 2.0,
  "candidate_period_ns": 3.0,
  "area": 20.0
}
```

Required source values are `gem5`, `hardware`, `synthesis_estimate`, and
`synthetic`. The field records the producer's declared provenance; validation
cannot independently verify that a simulator or hardware experiment occurred.
Synthetic demonstration labels must be explicitly marked `synthetic` and must
not be reported as measured acceleration. Synthesis estimates must remain
distinguishable from simulator or hardware results. Model fitting and policy
evaluation should use one homogeneous source per dataset.

All four timing fields must be finite and strictly positive. `area` must be
finite and nonnegative; use one documented area unit consistently across the
dataset and its selection cap (for example, square micrometers or gate
equivalents). Booleans and numeric strings are not accepted as numbers. No
measured timing fields are inferred from discovery counts.

The flattened row retains these fields and adds:

```text
speedup = (baseline_cycles * baseline_period_ns)
          / (candidate_cycles * candidate_period_ns)
```

The example yields `4/3`, despite halving the cycle count, because its candidate
period is slower. The builder rejects nonfinite or nonpositive ratios. An
optional supplied `speedup` must match the calculated value within relative
tolerance 1e-9. Decimal intermediate arithmetic avoids overflow when the final
ratio is representable as a float.

For actual `gem5` or `hardware` runs, periods describe the clock used by the
experiment. A faster candidate clock is preserved exactly; the builder never
silently replaces it with the baseline period.

For a conservative **synthesis estimate**, the producer may model an added
combinational instruction's effective period as
`max(baseline_period_ns, estimated_custom_path_period_ns)`. That choice belongs
to the synthesis producer and must be documented there; pass the resulting
effective period as `candidate_period_ns`. The builder uses the supplied
effective period directly for every source.

Measurement records join by `candidate_id`. Missing IDs, unknown IDs, duplicate
records, and optional mismatched `benchmark` or `formula` fields raise
`ValueError`. Missing required timing, area, or provenance fields also raise
`ValueError`. Candidates without a measurement record retain feature-only rows;
this is intentional for inference and incremental measurement. The builder
does not fabricate labels for them.
