# Budgeted selection with measured resource verification

This pilot asks whether held-out area predictions help find a valuable custom
instruction with fewer candidate hardware evaluations. Each trial selects **one
candidate circuit** for one benchmark under an isolated LUT4 cap. The objective
is the candidate's `overlap_safe_saved` instruction count, with zero savings for
the original program when no measured candidate meets the cap.

The entire real candidate pool must be represented in both the synthesis dataset
and the nested outer benchmark evaluation report. Missing, extra, duplicate,
unevaluated, or nonfinite predictions cause an error. The final model refitted on
all data is not used for this experiment. Each outer model holds out the entire
benchmark and excludes matching formulas from training; model choice is made
inside the remaining benchmarks.

Historical training measurements from other benchmarks are outside each target
measurement budget. The report records those training formula counts; this
comparison does not establish a reduction in total end-to-end measurement cost.

## Prespecified comparison

| Strategy | Information used to order candidate measurements |
| --- | --- |
| `frequency` | Descending dynamic `runs`, then candidate ID |
| `merit` | Descending overlap-safe instruction savings, then candidate ID |
| `random` | Seeded shuffle of candidate IDs |
| `predicted_area_feasible_merit` | Predicted-feasible candidates first, descending savings; predicted area and candidate ID break ties. Remaining candidates follow ascending predicted area overshoot, then descending savings. |

The fixed grid uses LUT4 caps **32, 64, 128**, measurement budgets **1, 3, 5**
candidates, and seeds **0–4**. Each strategy attempts up to the budget, or the
entire pool when it is smaller. Each attempted circuit reveals its actual LUT4
count. The trial retains the measured feasible candidate with the greatest
savings; lower actual LUT4 then candidate ID break ties. An infeasible first
proposal consumes one measurement and the trial continues while budget remains.
No model is updated during a trial. Deterministic rankings repeat across seeds
for comparison with the same random cases; those repeated cases are not
independent experimental observations.

Acquisition is implemented over a public candidate structure containing only
identity, dynamic frequency, overlap-safe savings, and held-out predicted LUT4.
Measured labels are available separately to a measurement callback. The oracle
uses the fully measured pool retrospectively and cannot influence the ranking.
Tests change the hidden area labels while holding public information fixed and
require every strategy's attempted order to remain identical.

## Outputs and interpretation

For each benchmark, cap, budget, seed, and strategy, the report records:

- Each attempted candidate, its revealed area, and whether the cap was violated.
- The first proposal's actual feasibility, total attempted violations, and number
  of candidate measurements.
- The selected measured feasible candidate and its overlap-safe instruction savings.
- The best feasible candidate in the fully measured pool and the fraction of
  that oracle's instruction savings retained.

The aggregate report includes mean retention across cases with positive oracle
savings, pooled retention weighted by oracle savings, and proposal violation
rates. If the oracle saves zero instructions, retention is undefined (`null`)
and excluded from the mean; the trial's zero savings remains in the details.
Both retention summaries are useful: the mean weights benchmarks equally,
whereas pooled retention gives more weight to workloads with larger potential
instruction reductions. Proposal violations describe the cost of prediction
mistakes; every final selected candidate is actually verified against the cap.

A **LUT4 cap is a resource proxy**, not a full FPGA capacity or processor-area
constraint. It ignores carry cells, registers, routing, clock impact, and core
integration overhead. A zero-LUT4 candidate may still consume carry cells.
Overlap-safe instruction savings assume replacement by one custom instruction;
they do not measure CPU runtime, speedup, energy, or the feasibility of deploying
several candidates together. This is offline replay over an already synthesized
finite pool, not measured wall-clock acceleration of live synthesis.

## Reproduce

First complete the actual benchmark traces, candidate correctness checks,
synthesis of the entire pool, and nested area-model evaluation. From the
repository root:

```sh
python3 -m isaforge.area_selection \
  --rows generated/real/experiment/dataset.json \
  --outer-evaluation generated/real/model/evaluation.json \
  --output generated/real/area-selection.json
```

Change the evaluation path to the directory supplied to `isaforge.area_model
train` if needed. This command reads outer predictions; it does not train a new
model or run additional synthesis. Its reported measurement budgets count the
labels that each simulated trial reveals.

## Results from the full measured pilot

The fixed comparison covers 339 candidate rows across eight benchmarks (301
unique formulas). At one candidate measurement, the mean retained oracle
instruction-saving fraction is:

| LUT4 cap | Frequency | Merit | Random, five seeds | Held-out predicted area + merit |
| --- | ---: | ---: | ---: | ---: |
| 32 | 83.33% | 75.00% | 27.37% | 85.10% |
| 64 | 79.86% | 87.50% | 28.48% | 100.00% |
| 128 | 79.86% | 87.50% | 28.74% | 100.00% |

At caps 64 and 128, the predicted policy reaches the oracle on all eight
benchmarks with one revealed measurement. Merit alone reaches it on seven:
its first CRC32 proposal uses 635 LUT4 and fails the cap, while the predicted
policy proposes an 8-LUT4 circuit retaining 348,160 overlap-safe instruction
savings. Frequency reaches 79.86% mean oracle retention at those caps. These
numbers are descriptive results for this finite pool, not a claim about unseen
benchmark families or a CPU-performance result.

The tight 32-LUT4 cap exposes prediction errors. EDN's first predicted-feasible
proposal is predicted at 22.59 LUT4 but actually uses 49. WIKISORT's oracle
uses zero LUT4 but is predicted at 35.53; the policy instead selects a smaller
savings candidate and retains 80.84% of its oracle savings. That WIKISORT miss
persists at budgets three and five. Merit reaches 100% oracle retention at three
measurements for every cap, while the predicted policy reaches 97.60% mean
retention at cap 32 and 100% at caps 64 and 128. Thus the observed advantage is
most useful at the smallest measurement budget; additional measurements can
make the simpler merit strategy equally good or better.
