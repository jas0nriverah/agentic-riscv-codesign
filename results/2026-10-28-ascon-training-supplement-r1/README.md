# Ascon training-only measurement supplement

This separate release imports three verified native Ascon v5 measurements from
the preserved October 27 archive. It authenticates the report, raw manifest,
all 679 ZIP members and their paired seals, then reproduces all three original
native audit-prefix hashes. It runs no native job, predictor fit or prediction.
The original 122-row corpus and every frozen result remain unchanged.

The supplement contains three training rows, the full twelve-candidate public
roster, and nine explicitly unmeasured IDs. It is `training_only=true`,
`evaluation_eligible=false`, `complete_pool=false`, with no oracle and zero new
independent confirmatory families. Every imported expression family already
occurs in the original history. These are additional context/area observations,
not new family coverage or evidence of an ML/agent advantage.

| Handle | Measured cycles | Speedup | Added LUT4 | Minimum routed MHz | Correct |
| --- | ---: | ---: | ---: | ---: | --- |
| C01 | 242,448,246 | 1.019698 | 73 | 62.992 | yes; exceeds +64 LUT4 |
| C06 | 243,085,014 | 1.017027 | 41 | 67.069 | yes |
| C02 | 241,493,094 | 1.023731 | 42 | 64.620 | yes |

Baseline: 247,224,006 cycles at a common 12 MHz. Target verification includes
round-trip/tamper checks and a 32-bit KAT fingerprint; it is not bytewise RV32 KAT
comparison. The stale adaptive-GP behavior in the original agent run remains a
preserved limitation. The earlier v2 unknown reservation remains separately
preserved and is outside this v5-only supplement.

Use `isaforge.ascon_training_supplement.load(path, purpose="training")` to obtain
the three rows. Any evaluation/oracle purpose is rejected. This file deliberately
uses `training_rows`, not the generic evaluation corpus's `rows`. A future frozen
training release must exclude the entire target workload and every family in its
full public candidate roster before adding this history. Do not run a new model
sweep, replace old scores or construct a three-candidate oracle from this data.

Reproduce to a fresh directory:

```sh
../work/audit-venv/bin/python scripts/export_ascon_training_supplement.py \
  --output generated/ascon-training-supplement-reproduction
```
