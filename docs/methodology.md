# Current research methodology

ISAForge tests whether learned predictions, uncertainty-guided measurements, and a bounded instruction-selection agent find better **verified feasible whole-program performance** with fewer expensive evaluations than strong heuristics and non-agent acquisition. [Primary-method grounding](research-foundation.md) records established algorithms and our proposed adaptations. [Historical cost-model methodology](methodology-history.md) preserves earlier studies; their isolated LUT targets are not application-speedup labels.

## Supported execution and legality

Compile a pinned real workload with a recorded input configuration for the actual processor ISA. The current contract is PicoRV32, RV32I integer operations with supported counter reads, ILP32, a deterministic two-register-input/one-output PCPI interface, and the recorded synchronous memory system. Software helper routines count toward complete benchmark execution. Compilation, ELF/binary, source, compiler, processor, profile, hardware, and measurement-context hashes identify each outcome.

Use established basic-block dataflow and architectural constraints. The current conservative implementation only accepts two-to-four-operation connected integer patterns with legal operand lifetimes and complete observable outputs. Memory/control operations cannot be inside an instruction. Only complete assembly statements can be removed; assembler/linker relocation must remain correct. Preserve the full discovered pool and rejection reasons, the disjoint occurrence cover, and the predeclared measured shortlist. Do not describe this restricted extractor as exhaustive over all possible custom instructions.

Validate baseline output, profiling/counter consistency, byte-preserving profile instrumentation, sampled datapath semantics and block equivalence, full-program correctness, dynamic custom counts, stock firmware on the extended processor, and custom firmware rejection on an unextended processor. Infeasible or failed designs remain recorded and charged, and cannot become final selections. Sampled tests and synthesis timing are distinct from universal equivalence and physical-board validation.

## Labels and constraints

The primary performance observation is complete benchmark-region processor cycles. At a common feasible clock, `speedup = baseline_cycles / candidate_cycles`. If clock periods differ, use `baseline_cycles * baseline_period / (candidate_cycles * candidate_period)`. A routed maximum-frequency estimate is a conditional timing result, not an independently measured board runtime. Preserve every declared route seed and use the predeclared rule for timing feasibility.

Record baseline and candidate integrated LUT4, FF, carry, and memory resources, their deltas, isolated datapath resources separately, device fit, and timing. LUT4 is an FPGA resource proxy, not ASIC area or energy. The current cap is baseline plus 128 LUT4 and 12 MHz in all three route seeds. All current automatic candidates pass, so these results do not validate difficult feasibility prediction.

Instruction savings and profile frequency are public heuristic features. They are not cycle labels. Historical isolated-LUT datasets may inform hardware cost only when that prediction demonstrably improves the final decision; they must not be relabeled as performance data.

## Workload splits and models

A sample identifies workload/source family, input configuration, processor configuration, candidate formula/occurrences, implementation and firmware, and measurement context. Exact formulas and related structural families need explicit overlap checks. Split entire workloads/source families, keeping related inputs together. Distinguish testing on unseen workloads with familiar formulas from testing on entirely unseen formula families.

Train regression on measured whole-program speedup and ranking on within-context measured orderings. Keep ranker query groups intact; ranking scores do not carry speedup units. Tune only on training/development workloads, using inner groups where data permit. Freeze artifacts and predictions before exposing held-out target labels. Consumed test outcomes become development data for any revision. Separate zero-shot ranking from paid target adaptation; never report the latter as zero-shot.

Current status: the corpus has two workload groups and mixed discovery-ISA provenance. Its three-group software gate correctly rejects a generalization experiment. Harmonize features and collect more independent pools before reporting cross-workload performance. No target/workload labels may leak through features, oracle rank, measured cost, route files, candidate ordering derived from outcomes, or an LLM's filesystem tools.

## Fair acquisition comparisons

Required comparators are frequency, simple instruction-saving merit, architecture/latency/timing-aware merit, seeded random, non-agent uncertainty/constrained acquisition, the LLM selection agent, and a separately privileged exhaustive oracle on manageable pools. For set experiments, add synthesis-aware greedy/pair lookahead when feasible. Named published-method adaptations must document deviations. A simple merit implementation is not a CIDRE reproduction.

Every policy receives the same legal pool, public profile/features, prior training data, area/timing constraints, and paid measurement budget. Initial bootstrap measurements and failures count. Cache returns are not fresh physical evaluations; offline replay represents counterfactual policy charges over stored labels. Native evaluation must enforce count/time limits independently of the policy. The oracle may inspect all labels only outside the policy-facing tools. Final choices require paid verification, with the unmodified baseline always available.

Uncertainty-guided acquisition is decision support, not correctness authorization. Measure interval coverage, feasibility calibration, and ranking/selective errors on untouched workloads, and retain zero-spread/constant-prediction cases. A proposed constrained-EI baseline must explicitly state its GP/independence assumptions. A proposed cost-aware method may use past measured or predicted durations; unqueried target durations are evaluator-private.

For the LLM, freeze provider/model settings, prompts, available tools, stopping limits, repeated runs, and inference costs. Isolate the sealed oracle files from its process/tools. Do not give the agent uncharged compiler/synthesis calls or private observations unavailable to other policies. The current Python allowlist is suitable for cooperative replay but is not that isolation mechanism.

## Endpoints and accounting

For each workload and budget, report `best_feasible_speedup = max(1, verified feasible queried speedups)` and `regret = measured_pool_oracle_speedup - best_feasible_speedup`. Report oracle-hit rate and the complete search curve versus both evaluation count and recorded/actual evaluation seconds. Use paired seeds and workload-level aggregates; candidates within one workload are not independent experimental replications. Explain pool coverage and missing oracle outcomes.

Publish historical training/calibration measurement counts and time, baseline/profiling setup, target attempts/time including failures, model/agent cost, and any amortization assumption. Present total cost as well as incremental target cost. Distinguish native subprocess time, elapsed evaluation wall time, and retrospective sums; do not add timers with overlapping scopes. Report actual inference time even when measurement count is the primary budget.

Prediction MAE, Spearman correlation, ranking metrics, isolated LUT error, and retired instructions are secondary diagnostics. None substitutes for the primary verified-performance frontier. Preserve negative speedups and all heuristic wins. No current result establishes ML or LLM superiority.

## Multiple instructions and final deliverable

Choose one to three compatible instructions only after checking occurrence overlap, input lifetimes, scheduling, encoding, shared interface, and hardware constraints. Implement and measure the selected set together. Do not sum individual speedups, cycle savings, timing penalties, or integrated area deltas. Greedy or branch-and-bound estimates can propose sets but cannot certify their final performance/feasibility.

The final artifact must include baseline and optimized firmware/hardware, selected instruction definitions and lowering, correctness evidence, actual cycles/runtime ratio, integrated resource/timing changes, measurement and inference costs, comparator results, and reproducible commands. Current six-candidate snapshots are milestones toward that system, not a finished general optimizer.
