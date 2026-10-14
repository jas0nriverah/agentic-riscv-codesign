# Separate V6 exact-output mapping cache

The optional wrapper caches the unchanged 23 mapping descriptors and leaves all
frozen feature definitions, fitted weights, point predictions and calibrated
bounds unchanged. It does not read target labels or choose a model. Only three
new repository files are added: `isaforge/cached_mapping_inference_v6.py`,
`tests/test_cached_mapping_inference_v6.py`, and `docs/v6-cached-inference.md`.

The mechanism profile (`../v6-cache-profile/profile.json`) attributed 26.5231 s
of 43.6622 s profiled time to 384 mapping-analysis calls (60.746%), exceeding the
15% predeclared implementation threshold. That profile includes instrumentation
and is not a speedup estimate.

`replay.json` proves all 384 × 336 input feature values equal the sealed vectors.
The first pass creates 384 mapping-block entries; a second pass has 384 hits with
the descriptor function disabled. Both point and calibrated artifacts for both
new models reproduce every frozen prediction field for ordinary and poisoned
outcome metadata (8 cases × 384 rows). Native subprocess creation is forbidden.
All frozen source/model/schema hashes remain unchanged. `cli.json` separately
records actual CLI replay for both calibrated artifacts across all 384 rows,
including upper bounds. No target labels were read by these checks.

The 13 focused tests cover initial computation, reuse without graph analysis,
strict payload/schema/source/column corruption rejection, original graph and
manifest byte changes, tool mismatch, invalid dimensions/negative values even
with a self-consistent digest, and runtime changes before/during extraction.
Independent read-only source review found no material production path issue.

The key binds formula, original generic graph/manifest bytes, runtime/wrapper
source, tool, ordered columns and schema. Payload digest/shape/finite/nonnegative
checks fail closed. Atomic writes are deterministic and guarded per key within
a process. Hashes detect accidental corruption; they do not authenticate against
an actor who rewrites data and its digests. The public extractor checks source
identity before and after; the low-level cache captures source identity at init.

Formal latency comparison passed after the parent's full CPU-idle gate. The
fixed script `benchmark.py` requires an explicit idle certificate tied to the
current point-freeze digest. It creates independent byte-identical warm generic
caches, starts its mapping cache absent, warms each side once, then runs three
alternating matched pairs with retained extractors and the identical frozen
mapping predictor. All vectors and predictions must remain exact; no native
processes are allowed and generic-cache hashes must remain unchanged. Loading,
cold native acquisition and population performance are outside its scope.

Completed warm comparison (seconds per 384 input rows):

| Pair | Frozen V6 baseline | Cached wrapper |
| --- | ---: | ---: |
| 0 | 19.711030 | 8.680570 |
| 1 (cached first) | 20.161094 | 7.827637 |
| 2 | 19.824076 | 8.828206 |
| Median | 19.824076 | 8.680570 |

The median ratio is 2.283730×, saving 11.143506 seconds (56.21%).
The untimed first mapping-cache construction took 19.569488 seconds versus
20.666539 seconds for baseline warm-up. This initial construction has no claimed
speedup. Every timed vector and prediction was exact, no native process was
created, and both generic caches remained byte-identical. Model loading and
cold native acquisition were excluded. Both sides retained their extractors.
These are three matched observations on one host and a fixed 384-row corpus,
not a population latency or accuracy claim. Point/calibrated prediction equality
was tested separately across both models; timed prediction used mapping_v6.

The first attempted timing was stopped during the untimed baseline warm-up after
a peer reported competing audit CPU work. It produced no accepted measured pair.
The executed source, plan, initial idle message, interrupt traceback and status
are preserved in aborted-contended-attempt-0000. The successful rerun used the
same fixed protocol after all peers and target collection were explicitly idle.
