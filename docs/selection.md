# Budgeted single-candidate selection

This milestone implements an offline measurement replay and a tool interface
for a future LLM runner. No LLM selector or live gem5 invocation is implemented.
An input pool contains candidate rows for exactly one benchmark, including
`candidate_id`, `benchmark`, `formula`, the numeric `FEATURE_COLUMNS`, and
recorded `speedup`, `area`, and `measurement_source` labels.

```python
from isaforge.selection import SelectionTools, evaluate_policies

tools = SelectionTools(target_rows, budget=5, area_cap=100, seed=0,
                       training_rows=historical_rows)
public_candidates = tools.list_candidates()
observation = tools.measure(public_candidates[0]["candidate_id"])
predictions = tools.predict()
selected = tools.choose_final()

comparison = evaluate_policies(target_rows, budget=5, area_cap=100, seed=0,
                               training_rows=historical_rows)
```

Historical rows must exclude the entire target benchmark and use the same
measurement source as its candidates. Their label count is reported as
`historical_training_size`; historical measurements are outside the target
benchmark's budget. Supported sources are `synthetic`, `synthesis_estimate`,
`gem5`, and `hardware`. These source tags are required provenance declarations;
the tool does not independently authenticate a recorded experiment. Synthetic
replay demonstrates plumbing and cannot establish real hardware improvements.
When raw timing columns are present, all four are required and their elapsed
time ratio must agree with the supplied speedup.

`list_candidates()` returns fresh feature records with no speedup, area,
measurement source, or raw timing outcomes. `predict()` trains only on
historical rows and target candidates already measured; the predictor receives
public features for inference. At least one training observation is required.
The predictor and its ML dependencies are imported when prediction is requested;
the standard package installation includes those dependencies.
The Python object is an application interface, not an adversarial sandbox.
A future external agent should receive only these explicit tool methods.

`measure(candidate_ids)` charges one unit for each unique target candidate.
Repeated measurements are returned from a cache at no additional cost. A batch
with an unknown candidate, malformed label, or too many new candidates fails
without partially changing the measurement cache. This is accounting for
recorded measurements; it does not estimate simulator wall time.

`choose_final()` selects the measured candidate with highest speedup within the
area cap. Ties prefer smaller area, then candidate ID. `None` represents the
always available no-extension baseline: speedup 1 and area 0. The baseline wins
when no feasible measured candidate improves speedup. Predictions cannot
authorize an unmeasured final selection. The area cap is checked after
measurement because area is also a recorded outcome.

The replay compares these policies with the same target measurement budget:

| Policy | Acquisition rule |
| --- | --- |
| `frequency` | Descending `runs` (dynamic occurrence count). |
| `merit` | Descending `saved` (optimistic saved instruction count). |
| `random` | Seeded random order. |
| `active_learning` | Seeded random bootstrap until at least three training observations, then repeatedly refit and select the largest prediction upper bound. |

All policies spend `min(budget, candidate_count)` unique measurements. Feature
ties use a seeded shuffle. Active learning includes historical rows in its
bootstrap threshold. Its uncertainty comes from bootstrap ensemble disagreement;
these intervals are not calibrated statistical coverage or guaranteed safe
upper bounds. With very little data they can collapse and offer no useful
exploration signal. Acquisition and model seeds make a fixed ordered input pool
reproducible.

The report contains `results` with measured candidate IDs, measurement counts,
the verified final candidate, `best_speedup`, and absolute `regret` relative to
the oracle. The privileged oracle reads all recorded outcomes, ranks feasible
candidates by speedup, and replays the same number of measurements. Its
`reference_label_count` exposes that full-pool knowledge; its replay count is
not its true label acquisition cost. It is an offline upper bound. With a zero
budget it returns the baseline. Oracle ranking runs after policy replay and
cannot affect ordinary acquisition.

Speedup always describes one measured custom instruction. Candidate speedups
are never added together: instruction overlap and shared clock effects make
that invalid. Multi-instruction selection requires a separate set measurement
interface and is outside this milestone. `area` and `area_cap` must use the same
units chosen by the dataset author.
