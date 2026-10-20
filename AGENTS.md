# ISAForge coding-agent instructions

Read [README.md](README.md) before planning work. It is the active scope contract, grounded in the [original proposal](docs/original-project-proposal.txt) and the owner's latest clarification. Then read [docs/HANDOFF.md](docs/HANDOFF.md) and [CONTRIBUTING.md](CONTRIBUTING.md). Current user instructions take precedence over this file.

## Objective and next work

Build the complete connection: supported real workloads → automatic candidate extraction/lowering → measured whole-program speedup and hardware cost → learned predictions/rankings and uncertainty → bounded instruction selection → verified optimized program and processor.

Prioritize the first missing engineering connection. Automatic `aha-mont64`, RV32I CRC32, and the preregistered SLRE transfer are complete and preserved. The three learned policies miss SLRE's optimum through budget three; frequency, merit, and calibrated latency find it in one query. Read [the prospective results](docs/prospective-slre.md). Do not tune another model on these consumed pools and relabel that result as held-out improvement. Next expand independent workload/input coverage and tests where area/timing or slowdowns affect selection, freezing protocols before new labels. Continue toward non-agent constrained/cost-aware acquisition, a bounded LLM instruction-selection agent, and jointly measured final instruction sets. Check the handoff before repeating work.

The contribution under test is measurement-efficient, uncertainty-aware custom-instruction selection validated against real processor performance and hardware constraints. Read [the primary-method review](docs/research-foundation.md) before major new ML or selection features. Reuse established extraction and architectural constraints; do not invent another enumerator or RTL-generation framework. Identify a paper's exact version and methods before claiming adaptation or reproduction. Record inaccessible methods as unresolved; abstracts do not satisfy method review. No novelty claim is authorized by the proposal's expectations alone.

The [model diagnosis](docs/model-analysis.md) provides independently calibrated PicoRV32 latency merit and baseline-normalized features. The heuristic exactly explains the twelve historical outcomes and all six prospective SLRE outcomes. Include it in future comparisons. A predeclared execution-feature ablation improved SLRE MAE by 21.14% but did not improve selection; it is not a promoted selector. Both ensembles' nominal 90% intervals have zero SLRE coverage. Train a residual model only if new measurements reveal a systematic error in the calibrated baseline. Its timing costs do not predict routed Fmax or area, and cannot be summed across selected instruction sets.

The agent selects instructions; it does not rewrite RTL. Do not develop RTL optimization agents, GNNs, multi-agent frameworks, or unrelated extensions. Do not start another isolated LUT-model study or model-version sequence unless an observed selection failure demonstrates why it is necessary. Historical roadmaps, archived scripts, synthetic demos, and literature suggestions are not current assignments.

## Reuse and correctness

- Extend the existing extractor, assembly lowering, PicoRV32 PCPI evaluator, and measured-data contracts. Keep the compiler ISA, simulator, instruction encoding, software helpers, and synthesized core compatible.
- Reject unsupported operations, unsafe dataflow, excess inputs/outputs, overlapping rewrites, memory overflow, incorrect outputs, unexpected custom execution counts, and unmet area/timing constraints.
- Keep instruction-count heuristics separate from whole-program cycle labels. The primary label must come from executing the complete benchmark with the candidate installed.
- Preserve an unmodified baseline. Validate stock firmware on extended processors and custom firmware rejection on unextended processors where applicable.
- Do not sum individual speedups or integrated area increments. Implement and measure selected combinations together; one to three instructions is the intended bounded set size.

## Research integrity and budgets

- Predeclare candidate pools, measurement limits, seeds, target hardware, and primary comparisons before observing target labels. Use one native evaluation at a time and bounded build workers unless a protocol justifies another setting.
- Hold out entire workloads/source families; check exact and related-candidate leakage. Separate zero-shot predictions from paid target adaptation. Do not silently tune on held-out results.
- Keep the SLRE compiler/partition context distinct from the historical two-workload context. Three small workloads with different compiler flags do not establish uniform-context generalization. The six-candidate SLRE oracle excludes ten other eligible formulas. Stack observation establishes no observed partition overflow for recorded inputs, not arbitrary-input or object-level memory safety.
- The explicit two-workload `selection_pilot` is a consumed-data diagnostic only. It does not weaken the primary corpus evaluator's minimum-three-group gate. Its negative ranking result and poor ensemble coverage must remain visible; more groups are still required for credible generalization and calibration.
- Compare frequency, simple merit, architecture/latency/timing-aware merit, random, non-agent constrained/cost-aware acquisition, and the LLM agent with the same information and evaluation budget. An exhaustive oracle uses all measured labels only as a separate reference. Name missing baselines explicitly; do not call simple merit a CIDRE reproduction.
- The primary endpoint is best verified feasible whole-program performance versus evaluation count and actual evaluation time, with regret against the measured oracle. MAE, LUT error, and instruction-count reduction are secondary diagnostics.
- Charge measurement attempts, including failures. Report native measurements, cache hits, offline replay, historical training-label counts/time, baseline setup, and inference costs distinctly. Show total cost and any stated amortization; historical training is not free. Ensemble disagreement is not automatically calibrated confidence.
- Keep sealed target outcomes outside every policy's accessible files/tools until charged measurement. The current Python interface is an information boundary for cooperative replay, not an OS sandbox for an LLM. Build that isolation before connecting an external agent.
- Preserve negative outcomes and heuristic wins. Never claim learned or agent superiority without measured comparative evidence.
- Never overwrite frozen `results/` or hash-bound model/measurement sources. Create new run directories and retain failures. Do not delete or commit toolchains, virtual environments, trace spools, or simulator build directories.

## Deliver and verify

Run `make test` for code changes and `make reproduce` for evaluation/report changes. Replay affected frozen processor evidence as well; `make reproduce-prospective` checks SLRE chronology, all raw measurements, exact historical refits, and all 105 policy outcomes. `make demo` additionally rebuilds the SQLite/HTML analysis outputs. Keep these outputs outside selector access. Validate documentation links and actual CLI commands. Do not treat a synthetic fixture or passing unit test as a new measured research result.

For each milestone, report the command, tests, actual measured outcomes, limitations, and next blocker. Keep README status and handoff accurate. Prefer a working end-to-end increment over a new audit, diagram, infrastructure layer, or model variant without processor validation.
