# ISAForge

**An AI-guided RISC-V program optimization system that selects custom instructions using learned performance predictions and bounded hardware measurements.**

**Working research prototype:** six executed Embench workloads, **33 verified candidate speedup labels**, **39 fully measured processor designs**, and **117 routing results**. All 36 automatic candidate attempts are preserved, including three earlier failures. The new SHA256 experiment adds six successful automatically extracted instructions and 450 prospective policy/budget/cap/seed endpoints. Original CRC32 and all earlier experiments remain intact.

```sh
# Python 3.12; install the pinned replay environment first.
python -m pip install -r requirements-speedup.txt
make sha256-report PYTHON=python
# Open generated/reproduction/guarded-sha256-report/results.md.
```

This verifies raw processor evidence and the pre-measurement Git checkpoint, exactly refits frozen historical predictions, and replays every comparison without new hardware jobs. [Results and working commands](docs/guarded-sha256.md), [all candidate/policy tables](results/2026-10-21-sha256-campaign/report/results.md), and the [six-workload dataset](results/2026-10-21-six-workload-corpus/README.md) are preserved.

**ML has not beaten the strongest heuristic.** Under the primary +64-LUT4 cap, SHA256 improves from 26,135,630 to 25,588,430 cycles (**1.021385×**, +50 LUT4). The cost-aware heuristic finds that design in one query, adaptive GP in two, and merit/normalized XGBoost in three. The faster 1.053940× design costs +68 LUT4 and exceeds that cap. This is a useful negative comparison, not a model promotion.

[The model and research-readiness analysis](docs/model-selection-readiness.md) identifies hardware-feasibility representation, uncalibrated confidence and mixed duration timers as concrete weaknesses. The next integration milestone is a bounded four-tool LLM selector, using current predictors and matched non-agent controls, alongside one focused feature experiment. The agent and jointly verified final instruction sets remain unfinished; adding an LLM is an experiment, not an established performance improvement.

The source-relocation guard now runs before shortlisting, with one-attempt accounting and replayable evidence. The [analysis](docs/improvement-analysis-2026-10-21.md) explains the demonstrated collection and ML weaknesses. All 33 verified cycle deltas match calibrated latency; hardware feasibility, uncertainty and measurement cost are the remaining decision problems. [Validation](results/2026-10-21-guarded-validation/README.md) records 2,863 passing tests and 179 subtests, with the unchanged intermittent legacy process-cleanup failure preserved. All new tests and affected research replays pass.

The earlier [EDN/UD campaign](docs/budget-campaign.md) retains 900 endpoints and its infrastructure-censored UD outcome. The earlier [SLRE report and SQLite demo](docs/prospective-slre.md) still reproduce with `make demo`; that database deliberately remains the frozen three-workload snapshot.

[Teammate branch review](docs/teammate-branch-review-2026-10-21.md): the hardware branches provide useful placement diagnostics and joint-instruction components. Their RV32IM/external-memory measurements remain a separate context, and their area-budget comparison is not an equal-query-budget ML experiment.

This README is the current project scope contract. It follows the [original project proposal](docs/original-project-proposal.txt) and the project owner's October 19, 2026 clarification. Contributors and coding agents must read it before choosing new work. [AGENTS.md](AGENTS.md) defines the engineering and evaluation guardrails.

## Research objective

Given a supported real RISC-V workload, ISAForge should automatically discover legal custom-instruction opportunities, predict their performance benefit and hardware cost, and select worthwhile instructions under area, timing, and evaluation budgets. The selected instructions must execute correctly in the modified program and integrated processor.

The research question is: **Can ML-guided and LLM-agent-guided instruction selection find better whole-program performance–area decisions with fewer expensive hardware evaluations than frequency, merit, random selection, and non-agent active learning?**

The contribution being tested is **measurement-efficient, uncertainty-aware RISC-V custom-instruction selection using learned predictions and an AI agent, validated against actual processor performance and hardware constraints**. The endpoint is the best verified feasible whole-program performance found for a given evaluation count **and actual evaluation time**, with regret against the measured pool oracle where available.

An agent or learned model losing to merit is a valid research result. Success requires a working, reproducible comparison; it does not require a favorable headline.

## Established research we build upon

Dataflow legality, bounded inputs/outputs, convex candidate identification, latency-based merit, synthesis-aware selection, and constrained Bayesian optimization have established precedents. We reuse those methods; we are not proposing a new enumerator or RTL-generation framework. The [primary-method review](docs/research-foundation.md) records Atasu (DAC 2003), Sun (TCAD 2004 and the separately reviewed ICCAD 2002 paper), CIDRE (ICCAD 2025), Hussein et al. (TACO 2026), LACE (2026), Gardner et al. (ICML 2014), and relevant performance/ranking/cost-aware methods, including exact references, assumptions, feasibility, and access gaps.

Four requested papers' methods were read. The exact Sun 2004 and Hussein 2026 full methods remain inaccessible and are explicitly pending. The [October 20 review](docs/selection-methods-review.md) adds primary methods from AutoTVM, SMAC, RGPE, Ithemal, covariate-shift conformal prediction, and integrated arbitration-cost research. The EDN/UD campaign adds calibrated latency, a hardware-cost heuristic, and constrained/cost-aware GP acquisition. These are adaptations, not complete reproductions of the cited systems; two new workloads do not establish broad superiority or calibrated uncertainty. No novelty claim is made.

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

The LLM agent is an **instruction-selection agent**. Its bounded interface should let it list candidates, query predictions and uncertainty, request measurements, and choose a feasible set. It does not rewrite or optimize RTL. Deterministic RTL generation, verification, synthesis, and routing implement and measure the selected instructions.

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
| Held-out-workload evaluation | SLRE predictions used 12 older outcomes. EDN/UD predictions were jointly committed before either target's measurements, using the same 18 historical outcomes and 15 fitting rows per target after family exclusions. Exact refits, source hashes and receipt chronology are checked. Compiler/partition shifts remain explicit; repeated seeds are not independent workload tests. |
| Ranking and uncertainty | Fixed XGBoost pairwise ranking is implemented and compared in 420 consumed-data policy/budget/seed outcomes. It does not improve selection over regression or merit. Ensemble interval coverage is poor on aha-mont64; held-out calibration remains missing. |
| Execution-aware features and baseline | A separate 222-case processor calibration exactly explains all 33 successful automatic cycle deltas. No latency residual model is justified yet. Normalized XGBoost lowers mean speedup MAE by 98.43% on EDN and 91.00% on UD versus the original regression; uncertainty coverage remains below its nominal level and worsens on UD. The earlier SLRE regression failures remain preserved. |
| Data and reproducibility | The latest consumed JSON/CSV corpus contains 33 measured rows, three separate failed attempts and six contexts, linked to authenticated raw archives. New comparison tables reproduce with `make sha256-report`; the old `make campaign-report` remains unchanged. The frozen three-workload SQLite demo remains available with `make demo`. Analysis artifacts stay outside selector access. |
| Additional workload eligibility | All earlier failures remain preserved. Seven more qualification failures and three static linker diagnostics explain the EDN/UD partition choices, the former SHA256 partition limitation, and statemate's one-formula pool. SHA256 now qualifies with an explicit checked partition and the original full input. The guard is integrated before new pools are frozen. |
| LLM selection agent | Required later milestone; not implemented or evaluated yet. It must share candidate information and measurement budgets with non-agent methods. |
| Joint final instruction set | Fixed historical CRC32 pair experiments exist. Automatic selection, lowering, and measurement of compatible sets of one to three instructions remain to be connected. |

The small CRC32 study and historical LUT-prediction studies are not the finished project. [Current handoff](docs/HANDOFF.md) tracks the next blocker. [Historical checkpoints](README-research-history.md) retain earlier results without defining current priorities.

## Priority order and milestone acceptance

1. **Preserve the six-workload milestone.** Keep original CRC32, every prelabel checkpoint, raw outcome and failure, and every heuristic win or tie. All six workloads, including SHA256, are now consumed data. An infrastructure-censored attempt must never become an invented speedup label or a claim of hardware infeasibility.
2. **Connect the bounded LLM selection agent.** Build a thin list/predict/measure/finalize interface over the existing evaluator, with hidden-label isolation, hard budgets, verified acceptance and recorded costs. Validate on consumed replay first; freeze one prompt/model protocol before any research trials. Compare with unchanged predictors and identical public information.
3. **Improve demonstrated selection weaknesses.** Test one compact ordered-structure/immediate feature bundle with the current hardware GP/acquisition on consumed workload/family-held-out diagnostics. Keep calibrated latency and the cost-aware heuristic. Correct duration target scopes and measure full search time before time-efficiency claims; more cycle-model versions are not justified by the exact analytic baseline.
4. **Validate generalization and decision value.** Freeze any justified change before fresh source/input evidence, distinguish source holdout from input/context adaptation, and charge historical and target costs. Compare agent/non-agent stopping, uncertainty and feasible-performance frontiers; preserve heuristic wins and negative results.
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
