# Research foundation and implementation decisions

Reviewed October 19, 2026. The [scope contract](../README.md) and [original proposal](original-project-proposal.txt) govern the project. This review informs implementation; it does not establish novelty or validate the proposal's expected ML advantage.

**Contribution being tested:** measurement-efficient, uncertainty-aware RISC-V custom-instruction selection using learned predictions and an AI agent, validated against actual processor performance and hardware constraints.

## Primary sources and access record

Method sections were read for four of the six requested papers. The exact Sun 2004 and Hussein 2026 full texts could not be retrieved: IEEE returned no readable article, ACM/TechRxiv returned access errors, and the indexed Oulu manuscript mirror timed out. Those two reviews remain incomplete. Metadata and abstracts are not treated as method evidence. Sun's accessible 2002 paper is a separately identified primary source, not a claimed reproduction of the 2004 journal article. No copyrighted paper files are redistributed in this repository.

### Atasu, Pozzi, and Ienne — DAC 2003

Kubilay Atasu, Laura Pozzi, Paolo Ienne. *Automatic Application-Specific Instruction-Set Extensions Under Microarchitectural Constraints*. DAC 2003, pp. 256–261. [DOI: 10.1145/775832.775897](https://doi.org/10.1145/775832.775897); [author-hosted full paper](https://www.epfl.ch/labs/lap/wp-content/uploads/2018/05/AtasuJun03_AutomaticApplicationSpecificInstructionSetExtensionsUnderMicroarchitecturalConstraints_DAC03.pdf). Read §§4–6 and evaluation §7.

The method searches basic-block DAG cuts subject to convexity and input/output limits. Reverse-topological include/exclude search prunes invalid branches; an intermediate excess of inputs alone is not a safe pruning rule. Multiple-cut search and iterative selection trade optimality for search cost. The merit model subtracts estimated hardware critical-path cycles from accumulated software latency, using synthesized operator delays. It is an approximation, not measured whole-program execution.

**ISAForge adaptation:** retain our existing conservative, connected, single-output extractor and explicit register-lifetime checks. Do not call it a complete implementation of their broader enumeration. Small exhaustive legal-subgraph fixtures can validate legality without inventing a new enumerator.

### Sun, Ravi, Raghunathan, and Jha — TCAD 2004; separate ICCAD 2002 methods

Fei Sun, Srivaths Ravi, Anand Raghunathan, Niraj K. Jha. *Custom-Instruction Synthesis for Extensible-Processor Platforms*. IEEE TCAD 23(2), February 2004, pp. 216–228. [DOI: 10.1109/TCAD.2003.822133](https://doi.org/10.1109/TCAD.2003.822133); [institutional publication record](https://collaborate.princeton.edu/en/publications/custom-instruction-synthesis-for-extensible-processor-platforms/). **Exact journal methods unavailable; do not claim a journal-method reproduction.**

The same authors' *Synthesis of Custom Processors Based on Extensible Platforms*, ICCAD 2002, pp. 641–648, [DOI: 10.1145/774572.774667](https://doi.org/10.1145/774572.774667), has an [accessible full paper](https://cecs.uci.edu/~papers/compendium94-03/papers/2002/iccad02/pdffiles/09c_1.pdf). Read §IV-A and §IV-B.1–4. It grows basic, dependent, then independent templates; prunes using profiled time divided by estimated custom latency plus excess-operand transfer overhead; bins similar priorities for detailed evaluation. Xtensa TIE synthesis and cycle-accurate simulation test clock/latency alternatives. Branch-and-bound proposes combinations using approximate additive area/cycle savings and maximum clock period; synthesis checks the best k combinations.

**ISAForge adaptation:** use a latency-aware shortlist followed by measured validation. Extra architectural state and commercial TIE integration are unnecessary for our two-input PCPI scope. Combined execution and synthesis already have precedent; they are required validation, not our novelty claim.

### Rezunov et al. — CIDRE, ICCAD 2025

Evgenii Rezunov, Niko Zurstraßen, Lennart M. Reimann, Rainer Leupers. *Automatic Microarchitecture-Aware Custom Instruction Design for RISC-V Processors*. ICCAD 2025. [DOI: 10.1109/ICCAD66269.2025.11240781](https://doi.org/10.1109/ICCAD66269.2025.11240781). Read [author preprint v2](https://arxiv.org/html/2509.15782v2), §§II–IV, especially Algorithm 1.

CIDRE combines constrained enumeration, canonical equivalence classes, nonconflicting covering, and synthesis-aware selection. Its implementation uses an nML RV64IM three-stage processor and commercial tools. The reported runtime estimate combines profiled instruction savings with synthesized processor clock period under one-cycle software/custom assumptions. Greedy selection and two-instruction lookahead account for clock degradation. Integrated synthesis includes surrounding processor costs. `aha-mont64` is already an evaluated workload.

**ISAForge adaptation:** implement a named, timing-aware heuristic adaptation and bounded pair lookahead after joint lowering works. Use our measured PicoRV32 cycles: neither CPI=1 nor single-cycle custom execution describes this PCPI system. Do not compare our speedup numbers directly with their different processor/process, or label our existing simple merit baseline “CIDRE.”

### Hussein, Waschneck, and Mayr — TACO 2026

Eslam Hussein, Bernd Waschneck, Christian Mayr. *Reinforcement Learning on Data-Dependence Graphs for Custom Instruction Identification*. ACM TACO 23(3), Article 93, July 2026, 25 pages. [DOI: 10.1145/3828552](https://doi.org/10.1145/3828552). Publisher/Crossref metadata verified; **full method review blocked by retrieval**.

The related author preprint *Scalable Custom Instruction Identification using Graph Neural Networks and Reinforcement Learning*, May 12, 2025, [DOI: 10.36227/techrxiv.174702136.65195692/v1](https://doi.org/10.36227/techrxiv.174702136.65195692/v1), is a different version and was also inaccessible. Do not silently equate it with the journal article.

**Pending checks:** state/action formulation, legality masks, reward, training-graph distribution, precise latency/area labels, simulation versus estimated speedup, and budget accounting. RL-based identification is relevant prior work; this review cannot yet support a detailed comparison or a claim that measured, learned instruction selection is unprecedented. Implementing a GNN/RL enumerator is outside our current scope.

### Zheng et al. — LACE, 2026

Pingqing Zheng, Jiayin Qin, Fuqi Zhang, Zishen Wan, Shang Wu, Yu (Kevin) Cao, Caiwen Ding, Yang (Katie) Zhao. *LACE: Large Language Model Aided Multi-Agent Framework for Agile RISC-V Instruction Extension*. [arXiv:2608.02915v1](https://arxiv.org/html/2608.02915v1), August 3, 2026. Read §§III–VI.

LACE translates instruction intent into operation/task representations, uses graph retrieval to locate HDL, and coordinates RTL edits with staged Verilator and RVFI-based formal checks. RVFI availability or instrumentation is an assumption. Its experiments implement selected extensions on four cores, including PicoRV32, and evaluate generation, localization, and verification outcomes.

**ISAForge adaptation:** reuse the principle of tool-checked decisions and explicit interface contracts. Our agent chooses which prevalidated candidates to measure; it does not generate RTL edits. LACE is related LLM integration work, not a demonstrated equal-budget workload-selection baseline. Do not infer agent-selection superiority from HDL generation success.

### Gardner et al. — ICML 2014

Jacob R. Gardner, Matt J. Kusner, Zhixiang (Eddie) Xu, Kilian Q. Weinberger, John P. Cunningham. *Bayesian Optimization with Inequality Constraints*. PMLR 32(2), pp. 937–945, 2014. [Primary paper](https://proceedings.mlr.press/v32/gardner14.pdf). Read §§3.1–3.2.

The method models expensive objective and constraint values using conditionally independent Gaussian processes. Constrained expected improvement is `EI(x) × P(feasible | x)` relative to the best observed feasible point. Independent constraints factorize; correlated constraints require joint probabilities. Infeasible observations still update the models.

**ISAForge adaptation:** a finite-pool constrained-EI baseline is feasible with existing Python dependencies and the unmodified processor as incumbent. Standardization, kernel, initial queries, and constraint treatment must be fixed on development data. A bootstrap XGBoost upper quantile is not this algorithm, and disagreement is not calibrated feasibility probability. Sparse current data cannot justify calibrated-confidence claims.

## Additional directly useful methods

- **Learned performance:** Benjamin C. Lee and David M. Brooks, *Accurate and Efficient Regression Modeling for Microarchitectural Performance and Power Prediction*, ASPLOS 2006, pp. 185–194, [DOI: 10.1145/1168857.1168881](https://doi.org/10.1145/1168857.1168881), [author paper](https://people.duke.edu/~BCL15/documents/lee2006-asplos.pdf), §§2–5. Randomly sampled simulations support regression with interactions and restricted cubic splines; application-specific models improve prediction. This supports measured surrogate modeling, not a claim of zero-shot custom-instruction transfer.
- **Evaluation cost:** Jasper Snoek, Hugo Larochelle, Ryan P. Adams, *Practical Bayesian Optimization of Machine Learning Algorithms*, NeurIPS 25, 2012, [author paper v2](https://arxiv.org/pdf/1206.2944), §3.2. A separate GP models log duration; independence permits EI times expected inverse duration. Our proposed constrained/cost-aware variant must disclose this adaptation and its assumptions. Report actual elapsed cost even when acquisition ignores it.
- **Ranking implementation:** [XGBoost's primary learning-to-rank documentation](https://xgboost.readthedocs.io/en/stable/tutorials/learning_to_rank.html), “Training,” “Loss,” and “Effective Pairs.” `XGBRanker` supports pairwise and LambdaMART objectives with query groups. For ISAForge, a group is a workload/input/hardware context; model tuning and test splitting must hold out whole workloads. Ranking scores are not speedup estimates. Freeze the objective and label mapping before evaluation; do not treat grouped ranking as random-candidate cross-validation. Current recorded runtime is XGBoost 3.4.1; the reviewed live documentation identifies 3.4.2.

## Strongest feasible baselines and implementation order

This is our implementation plan, not an assertion that published algorithms share our exact experimental setup.

| Comparator | Required behavior | Current status |
| --- | --- | --- |
| Frequency, instruction-saving merit, seeded random | Same frozen pool; only paid verified outcomes can win | Implemented; 120 outcomes each for CRC32 and aha-mont64 |
| Architecture/latency-aware merit | Profile-weighted software latency minus PCPI cost; explicit clock model; measured feasibility | Next stronger heuristic; do not assume CPI=1. Calibrate operation/handshake costs on separate microbenchmarks and charge that setup cost |
| Synthesis-aware greedy and pair lookahead | Revise decisions after paid integrated measurements; include overlap and joint timing | Adaptation after joint-set lowering; every tried set is charged |
| XGBoost regression and pairwise ranking | Train on earlier workloads; freeze before unseen-workload labels; report zero-shot and adaptation separately | Existing regressor only performs target-workload adaptation; cross-workload study and ranker missing |
| Non-agent uncertainty acquisition | Existing bootstrap-upper policy, plus constrained EI and cost-aware acquisition | Upper-quantile replay implemented; constrained/cost-aware comparators and calibration missing |
| LLM selection agent | Same public features, history, predictions, controls, and budget; auditable bounded queries | Missing; no RTL authoring, shell access to sealed labels, or extra privileged oracle tools |
| Measured exhaustive oracle | Best verified feasible design from the entire declared manageable pool, including baseline | Six single designs per workload measured; no oracle over all legal candidates or combinations |

The immediate completed follow-up is the [aha-mont64 matched-budget replay](automatic-workloads.md), which reuses the existing selector and exposes a negative learned-selection result without another model version. The next data experiment is to reprofile CRC32 using the automatic RV32I path, retaining the original six-candidate study, then add an independently grouped workload that fits the existing memory contract. Freeze that workload's pool and policies before target labels are released. A third workload is a minimum software gate, not sufficient evidence of broad generalization.

Once data support it, compare frozen regression, ranking, and stronger heuristics at zero target labels, then at identical limited adaptation budgets. Add constrained acquisition before evaluating whether an LLM adds value over the same non-agent tools. Validate one to three final compatible instructions jointly. This ordering tests the proposed contribution while preserving the working extractor, PCPI interface, simulator, and synthesis flow.

## Claims and unresolved questions

The useful question is whether reusable measured speedup predictions and uncertainty reduce the evaluations/time needed to reach the best **verified feasible whole-program performance** on an unseen workload, and whether a bounded LLM agent improves that frontier over non-agent acquisition. Neither “uses ML,” automatic enumeration, integrated synthesis, nor LLM-assisted RISC-V extension is itself a supported novelty claim.

Current pools are small, selected by merit, and all candidates pass a generous hardware cap. They cannot establish hard constraint prediction, arbitrary-workload support, calibrated uncertainty, or transferable agent advantage. Preserve their results. Complete the two inaccessible method reviews before making comparative claims about those papers. Do not describe the whole prior field as using only frequency or instruction count: latency-aware and synthesis-aware selection have longstanding precedent.
