Independent V8 target audit
===========================

`audit.py` uses only Python's standard library and imports no experiment code.
It never fits models, predicts points, runs RTL, or synthesizes circuits. Do not
run its target-data mode until the parent explicitly releases the labels.

After release and production scoring:

```sh
python3 audit.py \
  --root ../agentic-riscv-codesign/results/2026-10-15-v8-application-transfer \
  --released \
  --evaluation ../agentic-riscv-codesign/results/2026-10-15-v8-application-transfer/evaluation.json \
  --output result-audit.json
```

The audit authenticates every raw ZIP member; independently recomputes all
313,608 archived expected outputs; checks the two frozen seeded batches and
their output-to-physical-RTL connections; checks successful archived RTL runtime
logs; and recounts all 146 physical netlists against labels and metrics.

It independently recalculates all six models' full error summaries by program,
family, all rows and primary rows; the equal-four-family paired MAE difference
and leave-one-family sensitivity; and all 600 cap64/budget1 acquisition cases
and 24 aggregates (six models, four strategies, five programs, five seeds).
Production differences raise an error. Numeric comparison allows roundoff of
1e-10 absolute or 1e-11 relative. Selection IDs, counts and roles must agree.

The unsigned oracle implements arithmetic shifts by explicit high-bit filling,
signed comparisons by flipping the sign bit, and signed multiply-high via
unsigned-product correction. It has a separate formula parser. This tests the
retained expected values, rather than reusing the production oracle. Successful
archived runtime logs link those expectations to the original RTL's sampled
checks; the audit is not a new RTL execution or a universal equivalence proof.

Run synthetic tests with `python3 -m unittest -v test_audit`. These include
signed boundary arithmetic, independent integer definitions on 43,400 operation
cases, zero targets/oracles, public acquisition ordering, lexical ties, shared
point poisoning, missing pools, complete synthetic ZIP replay, an authenticated
wrong expected output, and authenticated incorrect resource counts.
