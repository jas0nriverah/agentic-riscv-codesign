# Repository alignment review — October 19, 2026

**Finding:** useful processor and extraction foundations were obscured by active documentation emphasizing isolated LUT-model iterations and leaving RTL-search work as an apparent next stage. The cleanup makes measured program optimization the active contract while preserving historical science.

The review checked the proposal, top-level instructions, active methodology/handoff/model/selection documents, source entry points, extraction/lowering and evaluator contracts, measurement records, and repository-wide references to conflicting priorities. It is a scope and experiment-integrity review, not a claim that every historical source line or all 3,000-plus result files received a fresh independent scientific audit.

| Area | Finding | Action / remaining limit |
| --- | --- | --- |
| Objective | Overview described a cost-model research sequence | Replaced README, added AGENTS; retained previous overview, handoff, and methodology as historical documents |
| Agent role | Unused rule-based RTL-search module suggested RTL optimization | Archived code/tests as non-importable text; agent milestone now means bounded instruction selection |
| Legal candidates | Extracted patterns lacked general executable integration | Added assembly mapping, operand binding, disjoint lowering, and checks using the existing extractor/interpreter |
| ISA consistency | Historical discovery used RV32IM; working processor uses RV32I | New aha profiler observes the actual processor binary; old CRC features remain explicitly mixed-provenance |
| Performance data | Many LUT labels did not form a multi-workload speedup dataset | Completed six automatic aha candidates with actual whole-program cycles and integrated hardware; combined corpus has 12 rows/two groups |
| Selection | XGBoost interface had little real performance evidence | Reused it for 120 aha policy replays with regret, query orders, and costs; no new model version |
| Strong baselines | Frequency/simple merit/random are insufficient for the final claim | Contract requires latency/timing-aware merit and constrained/cost-aware non-agent comparators; these remain missing |
| Research grounding | Automation/resource accuracy could be mistaken for the contribution | Added primary-method review with exact references, assumptions, feasible adaptations, and two explicit full-text access gaps |
| Reproduction | New processor evidence was local; CI omitted benchmark submodule initialization | Archived raw measurements, sources, hashes, controls, routes, policies, failures; added replay dependencies and `make reproduce-speedup`; initialized submodules in CI |
| Historical science | Cleanup could erase failures and stale context | Preserved every model/data/protocol snapshot, CRC slowdown, heuristic win, and failed probe; historical banners supersede old directions |

Active entry points are `isaforge.workload_experiment`, `workload_audit`, `workload_selection`, and the processor replay scripts. `codesign.py` remains the frozen CRC implementation and common evaluator interface. Legacy `make all/run/trace/candidates` is the RV32IM/Spike path and is labeled accordingly. Versioned area models remain available for reproduction rather than becoming new assignments.

## Guardrails: working checks and limits

Implemented checks cover source/input/tool hashes, fresh contexts, fixed pools, native count/time/concurrency budgets, binary/profile/counter consistency, restricted dataflow and lowering, whole-program correctness, custom execution counts, stock/custom processor controls, integrated resources/routes, feature-only policy discovery, charged observations/failures, and workload/related-candidate split gates.

These are useful correctness and provenance checks, not a complete security boundary. Sampled equivalence is not a universal proof. The Python tool interface is not an OS sandbox for an LLM; sealed outcomes need process/tool isolation before that integration. A minimum group gate does not establish generalization. Fixed inputs and merit-shortlisted pools limit coverage. All six aha designs pass generous constraints, so they do not validate difficult feasibility prediction. Combined instruction sets remain unmeasured. Documentation cannot prove that a researcher never inspected consumed test labels.

## What the learner actually learns

The current predictor fits 20 bootstrap XGBoost regressors, each 80 trees of depth two, on **measured application speedup** and 35 formula/profile features. In each current policy study it starts with no historical speedup labels and learns only from paid target-workload observations. Two bootstrap queries are charged; an upper ensemble quantile drives subsequent acquisition. This is not calibrated confidence, a dedicated ranker, or previous-workload transfer.

Historical V6/V9 models predict isolated LUT4 cost and do not supply predictions to this selector. Their circuit measurements cannot be relabeled as application-speedup examples. The new corpus preserves that distinction.

## Completed outcomes and next engineering order

CRC32's best design reduces cycles 4.84% with +31 LUT4. Aha's best reduces cycles 8.60% with +42 LUT4. Both meet their declared common clock and hardware cap. Merit finds aha's six-candidate optimum at budget one in 5/5 seeds; learned acquisition provides no advantage and loses to random at budget four. [CRC32 results](codesign-loop.md) and [aha results](automatic-workloads.md) retain every outcome.

The smallest implemented follow-up was equal-budget aha replay using unchanged policies. It tests whether the existing learner helps on the new measurement path and preserves the negative answer. It does not answer cross-workload generalization.

Next, harmonize CRC32 discovery through the automatic RV32I path and add independent workloads under the same hardware/memory contract. Then freeze grouped regression/ranking and stronger-heuristic comparisons before new target labels. Add calibration and constrained/cost-aware acquisition, followed by an isolated LLM selection agent sharing the same information and costs. Selected sets of one to three instructions need actual combined execution and synthesis. Preserve a final untouched cohort instead of repeatedly improving scores on the consumed pools.

No new isolated area-model study, GNN, RTL agent, or multi-agent framework is needed. The [research review](research-foundation.md) records methods and unresolved literature access; [AGENTS](../AGENTS.md) makes the priorities durable.

## Verification

The native aha run completed seven processor designs and their controls. Portable replay re-extracts/re-lowers candidates, recounts raw processor/hardware evidence, and recomputes 120 policy outcomes. The [final validation receipt](../results/2026-10-19-research-contract-validation/README.md) records full tests, historical-model replay, both processor replays, and documentation checks. Earlier validation remains attached to its original snapshot.
