# ISAForge

**An AI-guided RISC-V program optimization system that selects custom instructions using learned performance predictions and bounded hardware measurements.**

**Working research prototype:** eleven real sources (six Embench and five BEEBS), **87 verified candidate speedup labels**, twelve recorded contexts, **99 completed integrated processor evaluations including baselines**, and **297 routing results**. All 90 automatic candidate attempts are preserved, including three earlier failures. Original CRC32, aha-mont64 and every historical experiment remain intact.

**Useful new source qualified:** [TACLeBench bitcount](docs/bitcount-transfer.md) connects five unchanged C files through a declared ABI/amalgamation adapter to the existing guarded pipeline. Its original input/verifier passes at51,689 cycles; twelve automatically extracted formulas pass the unchanged opportunity gate. All fourteen fixed policies are frozen with the same67 source/family-filtered historical training rows before any candidate measurement. Next are three live semantic-GP queries followed by nine separate oracle-reference measurements. This preparation adds a verified baseline; the11-source corpus above remains the latest completed dataset.

**Latest implemented improvement:** [two fixed selection experiments and workload-support diagnosis](docs/selection-improvements-2026-10-22.md) complete the bounded changes from the preceding review. Removing duration weighting alone does not improve the three-query endpoint. Adding six formula-only hardware features raises expanded-history mean verified cycle reduction from **0.8394% to 1.6022%** on the three existing primary development sources, versus **1.1445% for merit**. It finds AHA's verified 70,797→69,177-cycle / +61-LUT4 design by query two and ties existing XGBoost regressors by query three. This is consumed-data development, not a fresh-source win; uncertainty remains uncalibrated. All fourteen policies and all negative outcomes are retained.

**Fresh-data blocker:** a fixed eight-source BEEBS qualification yields **zero valid pools**, seven profiled discovery failures and one static verifier rejection. No new custom-candidate labels or routed designs are added. An archive-only diagnostic exposes insufficient executable formulas and linked-helper coverage, including only 4.06% marked-source coverage for Prime. The next milestone is a useful untouched executable pool, not another model sweep. [Commands, measured results, limitations and validation](docs/selection-improvements-2026-10-22.md) distinguish new host computation from replayed historical hardware costs.

The [preceding October 22 diagnosis and primary-method review](docs/model-research-analysis-2026-10-22.md) and its [270-choice arithmetic replay](results/2026-10-22-model-research-diagnosis/README.md) remain preserved. Its proposed acquisition and narrow semantic experiments are now completed above; no model is promoted and frozen sources remain unchanged.

**Latest model/data result:** the [expanded-history and live-adaptation experiment](docs/ml-live-adaptation.md) retains every existing model setting. More historical labels improve raw/normalized XGBoost selection on consumed development targets, but worsen both GP controls and ranking. The fresh expint trial now connects the existing adaptive GP directly to native evaluation: three paid queries complete before three oracle-reference measurements. Models/runtime/baseline were pushed at `3b6f676cd5b68166f529c5be0020de0ddf540930` before any candidate attempt. The best verified instruction runs 31,832 versus 31,843 cycles, adds 17 LUT4 and passes all three routes (minimum 66.476 MHz). GP needs two queries; merit and normalized XGBoost need one. This tiny 0.034544% opportunity shows a working live feedback loop, not an ML win. [All six outcomes and twelve policies](results/2026-10-22-live-gp-report/results.md) and the [87-label corpus](results/2026-10-22-eleven-source-corpus/README.md) retain every result. Cloud/API/demo/LLM work remains paused.

**Preserved October 21 blind milestone.** The [three-source blind campaign](docs/blind-source-campaign.md) adds 36 verified labels from bit compression, DES and an MD5 compression block, with twelve candidates per source. All twelve existing policies and predictions were pushed together at `0b0884e112fbb3635487f7ae93d5d0f1616dbcb2` before any target candidate measurement. Every learned policy uses the same source/family-filtered historical cohort; the three targets never train one another. Live LLM and demo development remain paused.

At the primary +64-LUT4 cap, the measured pool optima are **1.023418×**, **1.007146×** and **1.018421×**, respectively. All 36 candidates pass correctness, integrated synthesis and three-route timing checks at the common 12 MHz target. RC4's qualification rejection is preserved. These are restricted single-instruction pools; the new independent test unit is three sources, not ten workloads or repeated seeds.

```sh
# Python 3.12; install the pinned replay environment first.
python -m pip install -r requirements-speedup.txt
make reproduce-blind-campaign PYTHON=python
make blind-report PYTHON=python
make export-blind-corpus PYTHON=python
make blind-figures PYTHON=python
# Open generated/reproduction/blind-report/results.md.
```

This checks raw processor evidence, the complete pre-measurement Git checkpoint and release chronology, exactly refits the frozen models, and replays **1,620 new endpoints without native jobs**. Reports retain every policy, cap and budget. Existing DCT, SHA256, CRC32 and other commands remain available. Derived output directories must be fresh.

**Three-source selection result:** the preserved constrained GP controls reach all three +64-LUT4 pool optima within three queries. Their mean verified cycle reduction is **1.6022%**, versus **1.1445%** for merit/calibrated latency, **1.4496%** for normalized XGBoost and **0.7194%** for the newer factorized classifier. The classifier loses to merit on two sources and ties on one; it is not promoted. Adaptive GP reaches compression's optimum on query two; zero-shot GP needs three. Both tie at the primary three-query endpoint. These are three-source descriptive results, not field superiority or calibrated uncertainty. [All twelve policies and 36 measurements](results/2026-10-21-blind-report/results.md), the [81-label corpus](results/2026-10-21-ten-source-corpus/README.md) and [selection curves](results/2026-10-21-blind-figures/blind-primary-curves.png) are preserved. The shared 48 historical attempts remain charged; no total-cost saving after training is established.

**Time-accounting limitation:** four MD5 runs have UTC timestamps inconsistent with intervals reconstructed from monotonic durations. The original strict packaging failure and raw clocks are preserved. A separate post-collection accounting amendment verifies serial receipts and nested duration totals; it does not correct timestamps or establish uninterrupted elapsed-wall-time savings. Count-budget results remain separate from qualified elapsed-cost results.

**Fresh-source result: a verified tie, not learned superiority.** The best DCT instruction executes **116,946 versus 117,522 cycles**, gives **1.004925× speedup**, adds **61 LUT4**, and passes correctness and all three routes with minimum Fmax **70.912 MHz**. At +64 LUT4, the new model finds it on query one in all five dependent seeds, tying frequency, merit and earlier models. The cost heuristic misses through query three. At +32, the new model misses the sole feasible instruction through query three. A retrospective six-source check gives a simple feasibility prior lower Brier error. Preserve these limitations; do not promote another variant from these consumed labels.

**Preserved SHA model improvement; the strongest heuristic still wins.** On the disjoint SHA256 pool at +64 LUT4, [budget-conditioned XGBoost](docs/ml-feasible-benefit.md) reaches the feasible optimum in **two queries**, versus **three** for unchanged normalized XGBoost, across five dependent seeds. At budget two, the new model obtains **1.026262×** while the old model retains baseline. The cost heuristic needs **one** query; adaptive GP ties at two. Fixed three-query runs spend all three attempts. This is consumed-source fresh-candidate evidence, separate from the new DCT source holdout.

The preserved original SHA256 study's +64 optimum remains 1.021385× at +50 LUT4, with the heuristic/adaptive-GP/normalized-XGBoost query counts 1/2/3. The faster 1.053940× instruction costs +68 LUT4 and exceeds the primary cap. These historical results are unchanged.

[The model and research-readiness analysis](docs/model-selection-readiness.md) identifies hardware-feasibility representation, uncalibrated confidence and mixed duration timers as concrete weaknesses. The [one ordered-descriptor ablation](results/2026-10-21-structure-feasibility-development/README.md) is negative and is not promoted. The new learned decision-utility model addresses the demonstrated area-budget failure; its output remains separate from speedup prediction and calibrated uncertainty. Neither a demo nor an LLM wrapper resolves these model-evaluation limits.

**Preserved demo and agent engineering:** `make showcase PYTHON=python` retains the earlier 33-label offline HTML/SQLite/CSV snapshot. `make selector-controls PYTHON=python` reproduces 450 earlier trajectories/1,350 endpoints through the bounded four-tool host. [Commands and limits](docs/bounded-selection.md) remain available. No live LLM trial or agent advantage is established; jointly verified final instruction sets remain unfinished.

The source-relocation guard runs before shortlisting, with one-attempt accounting and replayable evidence. The [earlier analysis](docs/improvement-analysis-2026-10-21.md) explains the collection and ML weaknesses. Hardware feasibility, uncertainty and measurement cost remain the decision problems; no performance residual model is justified while calibrated latency explains the measured cycle changes. [Earlier validation](results/2026-10-21-guarded-validation/README.md) preserves the intermittent legacy process-cleanup failure; no legacy fix is claimed.

The earlier [EDN/UD campaign](docs/budget-campaign.md) retains 900 endpoints and its infrastructure-censored UD outcome. The earlier [SLRE report and SQLite demo](docs/prospective-slre.md) still reproduce with `make demo`; that database deliberately remains the frozen three-workload snapshot.

[Teammate branch review](docs/teammate-branch-review-2026-10-21.md): the hardware branches provide useful placement diagnostics and joint-instruction components. Their RV32IM/external-memory measurements remain a separate context, and their area-budget comparison is not an equal-query-budget ML experiment.

This README is the current project scope contract. It follows the [original project proposal](docs/original-project-proposal.txt) and the project owner's October 19–21, 2026 clarifications. Contributors and coding agents must read it before choosing new work. [AGENTS.md](AGENTS.md) defines the engineering and evaluation guardrails.

## Research objective

Given a supported real RISC-V workload, ISAForge should automatically discover legal custom-instruction opportunities, predict their performance benefit and hardware cost, and select worthwhile instructions under area, timing, and evaluation budgets. The selected instructions must execute correctly in the modified program and integrated processor.

The research question is: **Can ML-guided and LLM-agent-guided instruction selection find better whole-program performance–area decisions with fewer expensive hardware evaluations than frequency, merit, random selection, and non-agent active learning?**

The contribution being tested is **measurement-efficient, uncertainty-aware RISC-V custom-instruction selection using learned predictions and an AI agent, validated against actual processor performance and hardware constraints**. The endpoint is the best verified feasible whole-program performance found for a given evaluation count **and actual evaluation time**, with regret against the measured pool oracle where available.

An agent or learned model losing to merit is a valid research result. Success requires a working, reproducible comparison; it does not require a favorable headline.

## Established research we build upon

Dataflow legality, bounded inputs/outputs, convex candidate identification, latency-based merit, synthesis-aware selection, and constrained Bayesian optimization have established precedents. We reuse those methods; we are not proposing a new enumerator or RTL-generation framework. The [primary-method review](docs/research-foundation.md) records Atasu (DAC 2003), Sun (TCAD 2004 and the separately reviewed ICCAD 2002 paper), CIDRE (ICCAD 2025), Hussein et al. (TACO 2026), LACE (2026), Gardner et al. (ICML 2014), and relevant performance/ranking/cost-aware methods, including exact references, assumptions, feasibility, and access gaps.

Four requested papers' methods were read. The exact Sun 2004 and Hussein 2026 full methods remain inaccessible and are explicitly pending. The [October 20 review](docs/selection-methods-review.md) adds primary methods from AutoTVM, SMAC, RGPE, Ithemal, covariate-shift conformal prediction, and integrated arbitration-cost research. The EDN/UD campaign adds calibrated latency, a hardware-cost heuristic, and constrained/cost-aware GP acquisition. These are adaptations, not complete reproductions of the cited systems; two new workloads do not establish broad superiority or calibrated uncertainty. No novelty claim is made.

The [October 22 hardware methods](docs/research-notes-hardware-2026-10-22.md) add CIExplorer, ISAMORE, Clay and constant/demanded-bit analysis. [Acquisition/transfer notes](docs/research-notes-acquisition-2026-10-22.md) distinguish constrained lookahead, knowledge gradient, decoupled evaluations and paid-target transfer. [Current reliability research](docs/research-notes-reliability-2026-10-22.md) separates grouped prediction, calibration and verified selection; 2026 preprints are labeled as such. These are evidence for bounded experiments, not assignments to implement every method.

## Intended system

```text
Supported workload and inputs
  → compatible compilation and execution profile
  → legal candidate extraction and executable lowering
  → measured whole-program cycles, correctness, area, and timing
  → XGBoost speedup prediction/ranking and uncertainty estimates
  → bounded selection: heuristics, active learning, or LLM agent
  → jointly implemented and measured instruction set
  → optimized software/hardware and a baseline-versus-optimized report
```

The LLM agent is an **instruction-selection agent**. Its implemented interface lists candidates, queries predictions and uncertainty, charges bounded replay measurements, and validates one feasible instruction. Native guarded dispatch and joint-set selection remain future integration work. It does not rewrite or optimize RTL. Deterministic RTL generation, verification, synthesis, and routing implement and measure the selected instructions.

## Current engineering scope

- Real integer Embench workloads with fixed, recorded inputs. The proposal's initial programs are CRC32, aha-mont64, edn, huffbench, matmult-int, nettle-aes, nettle-sha256, and wikisort; support is conditional on compilation, memory fit, and correctness.
- The working processor target is pinned **PicoRV32**, using **RV32I plus supported counter reads**, ILP32, and PCPI. CRC32 and aha-mont64 use GCC `-O2`; SLRE, EDN, UD and SHA256 use `-Os` in separately recorded contexts. Software helpers implement unsupported multiply operations and UD's original double arithmetic. Compiler, simulator, and synthesized processor must agree on the ISA.
- Automatically discovered patterns contain two to four connected integer operations, at most two register inputs and one output, and no memory or control-flow operations inside the instruction. Lowering removes original instructions and reassembles labels. The new guarded entrypoint rejects symbolic relocations before pool selection: replacing a linked address with a literal can invalidate it and remove the referenced object. This guard does not retroactively change frozen pools.
- The SoC has 8 KiB synchronous RAM. Stack reservations are explicitly recorded: original contexts 4 KiB; SLRE 3,840 bytes; EDN 1,408 bytes; UD 896 bytes; SHA256 576 bytes. New contexts use continuous partition checks and deliberate overflow controls; all original evidence stays unchanged. Designs are measured at a common 12 MHz target and routed with seeds 1, 2, and 3 on iCE40 HX8K CT256. These checks cover recorded inputs, not arbitrary-input memory safety.
- The final system should select one to three compatible instructions under a hardware budget, with an unmodified baseline always available. Selected combinations require joint execution and synthesis; individual speedups and area increments are not additive.

PicoRV32/RV32I is the current feasible implementation of the proposal's objective. The proposal's RV32IM, Spike-extension, and VexRiscv integration choices are not additional integration requirements for this milestone. Arbitrary RISC-V binaries are outside the initial support contract.

## What works and what remains

| Capability | Current evidence or remaining work |
| --- | --- |
| Six-candidate CRC32 experiment | Complete and preserved. Real program cycles, correctness, integrated area, three routing seeds, and equal-budget policy replay. Best single candidate reduces cycles 4.84%. Merit beats learned acquisition at the reported three-measurement budget. |
| Automatic second-workload pipeline | Complete for six `aha-mont64` candidates: automatic profiling/extraction/lowering, correctness, execution, integrated synthesis/routing, and 120 policy replays. Best cycle reduction **8.60%**, +42 LUT4. Merit finds the pool optimum in one measurement in all five seeds. [Results and replay](docs/automatic-workloads.md). |
| Automatic CRC32 / historical training data | CRC32 was reprofiled, automatically lowered, and remeasured in a new RV32I context. Twelve automatic outcomes share compatible feature provenance across CRC32 and aha-mont64; six older CRC32 adapter outcomes remain historical evidence. This earlier comparison has two workload groups; the new SLRE context is listed below. [Development results](docs/selection-pilot-results.md). |
| Automatic third workload / prospective transfer | **SLRE complete:** six candidates from 16 eligible formulas, seven integrated designs, 21 routes, and 105 policy/budget/seed outcomes. Best 16,333,432 → 16,221,562 cycles (**1.006896×**, +77 LUT4). Upstream self-check and every hardware control pass. Combined automatic evidence now covers **18 candidates across three workloads**, with the compiler/partition shift explicitly recorded. [Results](docs/prospective-slre.md). |
| Five-workload corpus / second prospective campaign | **EDN and UD complete as one-attempt campaigns:** 12 attempted candidates, nine new verified labels, two correctness failures and one infrastructure-censored result. Total automatic evidence: 27 labels / 32 measured designs / 96 routes across five workloads. Ten policies, three area caps, three budgets, five seeds: 900 endpoints. [Results and commands](docs/budget-campaign.md). |
| Guarded sixth workload / fresh prospective selection | **SHA256 complete:** six of six candidates verified, 21 new routes, 450 equal-budget endpoints. Guarding rejects three symbolic-address formulas before selecting six from 56 eligible formulas. The +64-LUT4 optimum is 1.021385× at +50 LUT4; the cost-aware heuristic finds it sooner than ML. [Evidence](docs/guarded-sha256.md). |
| Speedup regression and acquisition | Raw-speedup and normalized-cycle-savings bootstrap XGBoost, pairwise ranking, and zero-shot/paid-adaptation constrained GP policies are measured against heuristics. Normalization improves the original regressor's UD choice at +128 LUT4 but does not beat merit. The GP predicts integrated hardware cost, timing and measurement duration for selection; historical isolated-LUT studies remain separate. |
| Budget-conditioned learned benefit | Complete fixed model and fresh-candidate test: new SHA256 +64 optimum1.026262× is reached after two queries versus the old normalized model's three; strongest heuristic still needs one. Portable JSON ensembles, complete prelabel Git proof, all 495 new endpoints and every negative development outcome are preserved. [Model and evidence](docs/ml-feasible-benefit.md). |
| Fresh seventh source / factorized model | Six automatically extracted BEEBS DCT candidates pass all checks. The fixed feasibility ensemble ties frequency/merit at query one under +64 LUT4, misses the +32 optimum, and does not repair calibration. All twelve policies, 540 endpoints, outer-operation timers and exact refits are preserved. [Results and commands](docs/ml-factorized-selection.md). |
| Held-out-workload evaluation | SLRE predictions used 12 older outcomes. EDN/UD predictions were jointly committed before either target's measurements, using the same 18 historical outcomes and 15 fitting rows per target after family exclusions. Exact refits, source hashes and receipt chronology are checked. Compiler/partition shifts remain explicit; repeated seeds are not independent workload tests. |
| Ranking and uncertainty | Fixed XGBoost pairwise ranking is implemented and compared in 420 consumed-data policy/budget/seed outcomes. It does not improve selection over regression or merit. Ensemble interval coverage is poor on aha-mont64; held-out calibration remains missing. |
| Execution-aware features and baseline | A separate 222-case processor calibration exactly explains all 87 successful automatic cycle deltas. No latency residual model is justified yet. Normalized XGBoost lowers mean speedup MAE by 98.43% on EDN and 91.00% on UD versus the original regression; uncertainty coverage remains below its nominal level and worsens on UD. The earlier SLRE regression failures remain preserved. |
| Three-source blind campaign | Compression, DES and an MD5 compression block add36 verified candidates under one common context,108 candidate routes and1,620 fixed-policy endpoints. All three targets were frozen before labels and never train one another. Count-budget results and qualified monotonic costs remain separate. [Contract](docs/blind-source-campaign.md). |
| Data and reproducibility | Latest JSON/CSV: 87 measured rows, three failures, eleven source workloads and twelve contexts. Source holdouts exclude all contexts together. `make reproduce-live-gp` checks the new native/live trace, exact refits, paired clocks and 540 endpoints. The preserved three-source command checks its earlier 1,620 endpoints. All earlier corpora, sources, negative outcomes and commands remain unchanged. Analysis artifacts stay outside selector access. |
| Additional workload eligibility | All earlier failures remain preserved. Seven more qualification failures and three static linker diagnostics explain the EDN/UD partition choices, the former SHA256 partition limitation, and statemate's one-formula pool. SHA256 now qualifies with an explicit checked partition and the original full input. The guard is integrated before new pools are frozen. |
| LLM selection agent | Four-tool host and isolated remote provider implemented; 450 matched control trajectories reproduce exactly. Live LLM trials are unrun (missing API key); native dispatch and joint sets remain missing. [Guide](docs/bounded-selection.md). |
| Joint final instruction set | Fixed historical CRC32 pair experiments exist. Automatic selection, lowering, and measurement of compatible sets of one to three instructions remain to be connected. |

The small CRC32 study and historical LUT-prediction studies are not the finished project. [Current handoff](docs/HANDOFF.md) tracks the next blocker. [Historical checkpoints](README-research-history.md) retain earlier results without defining current priorities.

## Priority order and milestone acceptance

1. **Preserve the eleven-source milestone.** Keep original CRC32, every prelabel checkpoint, raw outcome and failure, and every heuristic win or tie. All eleven sources are now consumed data. An infrastructure-censored attempt must never become an invented speedup label or a claim of hardware infeasibility.
2. **Resolve the useful-source coverage gap and validate the fixed improvement.** The [duration-removal and six-feature experiments](docs/selection-improvements-2026-10-22.md) are complete; do not repeat or sweep them. Preserve the eight-source failed qualification and its fixed gates. Next obtain an untouched workload with multiple legal executable candidates, addressing demonstrated extraction coverage within an explicit compatible context. Freeze models, public opportunity criteria and a compatible controller before labels; keep all source contexts and related families excluded. No model is promoted from the 87 consumed labels.
3. **Evaluate uncertainty and decision value.** Use whole-workload/family exclusions, include all strong heuristics, and report feasible-performance frontiers and oracle regret. Charge historical failures and consumed model-development measurements as well as target evaluations. Keep fitting/inference, ledger and overlapping command timers distinct, with the recorded clock qualification. More model versions or hyperparameter sweeps on these consumed pools are not the next milestone.
4. **Connect later selection stages after model/data evidence.** Preserve the existing agent implementation, but keep demo/live LLM development paused under current instructions. Any future agent-only comparison must hold predictors, public information and measurement budgets fixed. Validate source transfer and uncertainty before claiming intelligent-selection superiority.
5. **Validate the final implementation.** Implement compatible selected sets together. Report baseline/optimized execution, correctness, integrated area, timing, evaluation count/cost, and regret against the fully measured manageable-pool oracle.

Each milestone must include its working command, tests, measured outcomes, limitations, preserved negative results, and next blocker. Complete these connections before starting more model versions or new infrastructure.

## Evaluation rules

- **Primary outcome:** best verified feasible whole-program runtime/speedup as a function of expensive evaluations, with performance–area tradeoffs reported separately.
- **Comparators:** frequency, instruction-saving merit, strong architecture/latency/timing-aware merit, seeded random, non-agent uncertainty/constrained acquisition, LLM selection agent, and exhaustive oracle on the same manageable pool. Pair lookahead joins set selection once joint lowering works. Report unimplemented methods as missing.
- **Fair information and costs:** hold pools, training data, area/timing limits, and budgets constant. Only queried target labels reach a selector. Charge failed attempts; distinguish cached/replayed observations from fresh evaluations. Report historical training-label counts/time, baseline/profiling setup, target measurements/time, and inference cost separately, with total and amortized costs rather than treating training as free.
- **Timing:** at a common feasible clock, speedup is baseline cycles divided by optimized cycles. If periods differ, use `baseline_cycles × baseline_period / (optimized_cycles × optimized_period)`. Report all routing seeds and timing feasibility.
- **Labels:** instruction savings, isolated datapath cost, simulated whole-program cycles, routed timing estimates, and physical-board measurements are different quantities. Do not relabel one as another.
- **Generalization:** hold out entire workloads/source families; detect duplicates and related candidates. Freeze protocols and predictions before examining held-out labels. Test sets used for revisions become development data.
- **Set selection:** account for overlapping occurrences, register dependencies, encoding compatibility, and shared hardware. Measure selected combinations together instead of summing individual speedups.

## Outside the current project

RTL-rewriting optimization agents, GNN development, multi-agent frameworks, unrelated model architectures, arbitrary RISC-V support, and power/energy claims without measurements are outside scope. Further isolated LUT-prediction studies are deferred unless they directly address a demonstrated final-selection failure. Historical code and results remain available for reproduction; their old roadmaps do not authorize new work.

## Run and reproduce

From a source checkout:

```sh
git submodule update --init --recursive
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev,reports,proofs]'
# For exact October 19 processor-policy replay, use Python 3.12 and:
python -m pip install -r requirements-speedup.txt
make test
python scripts/reproduce_codesign.py replay
python scripts/reproduce_workload.py replay
```

Each processor replay verifies seven preserved designs and 120 policy/seed/budget outcomes without new native measurements. The [recorded replay dependencies](requirements-speedup.txt) are separate from historical model-version requirements. Automatic collection needs recorded RISC-V GCC, Verilator, Yosys, nextpnr, and a prepared pinned evaluator context:

```sh
python -m isaforge.workload_experiment prepare \
  --reference-root generated/codesign-crc32-2026-10-19-r1 \
  --root generated/automatic-aha-new --workload aha-mont64 --pool-size 6
python -m isaforge.workload_experiment discover --root generated/automatic-aha-new
python -m isaforge.workload_experiment collect --root generated/automatic-aha-new
python -m isaforge.workload_selection --root generated/automatic-aha-new
```

Use a fresh output directory for a fresh protocol. Resume completed measurements only after evidence hashes are verified. [Automatic-workload instructions](docs/automatic-workloads.md) cover setup and portable replay. [CRC32 commands](docs/codesign-loop.md) cover reference preparation. `make reproduce` remains a regression check for the historical six-model cost comparison; it is not the primary project experiment.

[Agent instructions](AGENTS.md) · [Contribution rules](CONTRIBUTING.md) · [Documentation](docs/README.md) · [Frozen evidence](results/README.md) · [Original proposal](docs/original-project-proposal.txt)
