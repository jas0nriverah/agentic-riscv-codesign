# tiny-regex-c baseline qualification — October 28, 2026

## Status

The pinned `kokke/tiny-regex-c` fixed test suite **passed the existing
baseline-only workload gates** on the guarded PicoRV32 pipeline. This is a new
source and candidate-discovery result, but it contributes **zero measured
candidate outcomes**. Do not add it to the model corpus or fit/adapt a model
from it yet.

The first run stopped on an implementation error in the opportunity gate; the
second stopped after baseline measurement because discovery and baseline rows
used different public benchmark-group names. Both complete failure records and
archives are preserved. The third run, with both integration defects fixed,
passed all six frozen phases. See the [r1 failure](../results/2026-10-28-tiny-regex-c-qualification-r1/),
[r2 failure](../results/2026-10-28-tiny-regex-c-qualification-r2/), and
[accepted r3 qualification](../results/2026-10-28-tiny-regex-c-qualification-r3/).

## Frozen source and workload

- Upstream revision: [`kokke/tiny-regex-c` `f2632c6d9ed25272987471cdb8b70395c2460bdb`](https://github.com/kokke/tiny-regex-c/tree/f2632c6d9ed25272987471cdb8b70395c2460bdb), Unlicense.
- The original regex implementation and 76 fixed regex/text/expected-result test vectors are preserved byte-for-byte. The only C adapter suppresses output, supplies ASCII C-locale character classes, invokes upstream `main`, and reports its failure count to the existing harness.
- Host adapter check: **76 test vectors, zero upstream failures**. This is fixed-suite correctness, not arbitrary regex/input verification.
- Target baseline self-check returned zero and passed the existing verifier.
- Compiler and target remain unchanged: RV32I/Zicsr, ILP32, xPack GCC 15.2, `-Os`, PicoRV32 + PCPI, synchronous 8 KiB RAM, 12 MHz target floor, 6,400-byte program/data limit, 128-byte guard and 1,664-byte stack partition.

## Target results

| Metric | Baseline |
|---|---:|
| Fixed-suite cycles | 361,839 |
| Instructions | 66,206 |
| Correctness | Pass; upstream failure count 0 |
| Program/data end | 5,140 / 6,400 bytes (1,260 bytes remaining) |
| Observed maximum stack | 304 / 1,664 bytes (1,360 bytes headroom) |
| LUT4 / carry / BRAM / flip-flops | 1,653 / 295 / 20 / 655 |
| Routed Fmax, seeds 1 / 2 / 3 | 77.160 / 68.493 / 70.388 MHz |
| Minimum routed Fmax | 68.493 MHz (12 MHz constraint passed) |
| Setup / baseline / total command time | 6.701 / 24.561 / 31.262 seconds |

The current fixed candidate pool has 12 instructions. Discovery found 26 raw
formulae, 22 executable formulae and 17 calibrated eligible formulae before
the unchanged pool-size and opportunity gates. The best **public analytic
projection** predicts 0.8457% cycle reduction at 612 timed replacements; one
candidate clears the joint 0.5% / ten-replacement gate. This is an
instruction-level estimate used only to admit a workload. It is **not measured
whole-program speedup**.

An exact operation-tree comparison against the 122-label historical corpus
finds 3 overlapping and 8 unseen families among the 12 frozen pool entries.
This is a descriptive formula-family result. The source is still a small fixed
regex/text suite, so treat it as a related-domain transfer workload, not
independent confirmation of generalization.

## Reproduction and current gate

The accepted qualification was run with:

```sh
python3 scripts/qualify_tiny_regex.py \
  --output results/2026-10-28-tiny-regex-c-qualification-r3 \
  --native-root generated/tiny-regex-c-qualification-2026-10-28-r3
```

The exact compiler, source, inputs, routed baseline, pool, opportunity result,
commands and phase timings are source-bound in the qualification protocol and
the archived native root. The candidate dispatch remained disabled through all
three runs. Candidate attempts: **0**. Candidate speedup, correctness,
incremental area, routed timing and cost labels: **0**. The historical corpus
remains at **122 verified labels / 126 charged attempts / 14 workload groups**.

The focused workload checks pass:

```sh
python -m pytest tests/test_tiny_regex_workload.py -q
```

Result: **7 passed**. An isolated temporary pytest environment was used for
this run; no project dependency files were changed.

## Next experiment and limitations

Before measuring any candidate, prepare, review, commit and push a separate
zero-label protocol that binds the entire extracted pool, source-family
exclusions, current model predictions, frequency/merit/latency-cost/random
controls, the existing non-agent active-learning policy, and the LLM agent.
Give every policy the same public information and one to three paid
measurements. Seal each adaptive next choice before revealing its outcome;
keep the complete-pool oracle hidden from the selectors. Then collect candidate
correctness, whole-suite cycles, integrated resources, route seeds, and actual
evaluation time through the existing one-attempt pipeline. Do not infer
combined-instruction speedups by adding individual outcomes.

This pool is suitable for a bounded transfer pilot, not a claim that ML or an
agent beats heuristics. The fixed test's 361,839-cycle baseline is short, the
workload is related to prior text/regex work, and a single workload does not
establish workload-level generalization. The next blocker is a pushed,
source-bound prelabel selection protocol; no XGBoost fit or candidate
measurement is authorized by this qualification alone.
