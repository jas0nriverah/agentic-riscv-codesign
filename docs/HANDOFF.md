# Current handoff — model evidence after Lift selection

## October 27 — Ascon v1.3.0 target baseline-only qualification accepted

The exact command `../work/audit-venv/bin/python scripts/qualify_ascon.py` passed
all six frozen phases: prepare, discover, opportunity, baseline, public, and
freeze. The pinned target translation unit compiles for the existing RV32I_zicsr
/ ILP32 `-Os` PicoRV32/PCPI path. Discovery found 45 legal executable formulas
and froze twelve; the unchanged public opportunity gate passed with a 2.3181%
maximum projected cycle reduction and 1,591,920 timed replacements. These are
instruction-level projections, not measured candidate results.

The baseline completed the 1,089 ordered Ascon length pairs and passed the
target checks at **247,224,006 cycles / 43,670,234 instructions**, returning the
KAT-derived fingerprint `0x06cf04e8`. The same translation unit's host-only
observer matched all 1,089 pinned KAT records byte-for-byte (34,848 ciphertext
bytes). Target firmware does not compare every output byte to the KAT; it uses
the 32-bit fingerprint with round-trip, length, tamper, and call-count checks.
That collision limitation is part of the evidence boundary.

Baseline synthesis used **1,653 LUT4, 295 carry cells, 20 RAM blocks, and 655
flip-flops**. Routed Fmax was **77.160 / 68.493 / 70.388 MHz** for seeds 1/2/3,
above the 12 MHz floor. Program/data ended at byte 5,712 of the 6,400-byte
limit; observed stack usage was 560 bytes of the 1,664-byte partition, leaving
1,104 bytes of stack headroom. The baseline measurement call took 54.011 seconds;
the six native qualification phases totaled 101.200 monotonic seconds. Five
phase clocks recorded UTC/monotonic disagreement; preserve the durations as
recorded and do not infer uninterrupted calendar time.

The exact emitted-family audit found overlap between six of twelve candidate
entries and prior crypto pools (AHA-compress, NDES, Nettle MD5, SHA-256). The
whole source remains same-domain cryptography transfer, not independent
confirmation. Candidate dispatch, attempts, labels, and model fits are all
zero. The sealed [qualification and raw archive](../results/2026-10-27-ascon-target-qualification/),
[target contract](ascon-target-adapter-contract-2026-10-27.md), and
[candidate-family audit](../generated/ascon-target-qualification-2026-10-27/target-formula-family-audit.json)
preserve the result. Do not dispatch candidates from this qualification; any
later campaign needs a separately frozen family-safe model, policies, live
controller, budget-matched controls, and measurement-time accounting. Continue
to pursue an independent non-crypto workload for confirmatory evidence.

## October 27 — selector controller v2 stopped before candidate evaluation

The separate v2 controller release reserved its first of three queries for
`C01`, then stopped on an unknown `ValueError`. The durable controller record
contains one charged reservation, but the target root has **zero candidate
attempt ledgers, zero candidate measurement directories, and zero target
outcomes**. No candidate label was exposed and the slot was not retried.

The error was a wrapper bug: before dispatching a candidate, the guarded
one-attempt evaluator requests the cached baseline through the same `measure`
method. The wrapper incorrectly required that `"baseline"` name appear in the
candidate pool, so it rejected the baseline lookup before native candidate
work began. The corrected wrapper permits the baseline path and continues to
check candidate membership and the Ascon KAT. The controller also verifies
that model observations match the ordered successful/failed outcomes in
durable attempt slots, and keys adaptive-GP refits by full verified outcome
rows. See the preserved [v2 run diagnosis](../results/2026-10-27-ascon-selector-controller-v2-attempt/README.md)
and [paid-update contract](paid-update-semantics.md).

The correction passes 107 focused tests and the full `make test` suite (4,265
tests / 181 subtests, one existing duplicate-ZIP warning). It has not yet been
frozen in a new pushed controller release or exercised on a real paid Ascon
prefix. The remaining experiment still needs family-safe matched controls and
an independent workload; this failed pilot is not a performance comparison.

## October 27 stopping point — model-selection scorecard and CoreMark screen

The current broad model comparison is summarized in the reproducible [final
selection scorecard](../results/2026-10-27-final-selection-scorecard/README.md).
It uses the existing 122-label, 14-workload consumed-data LOCO screen, with
whole-workload holdouts and operation-tree-family exclusions. It produces no
new labels. **Take XGBoost `rank:pairwise` forward as one prospective ML
challenger, not as a promoted model; keep merit as the fallback.** Relative to
merit, pairwise regret advantage is +0.290 percentage points at B1, +0.027 at
B2, and -0.056 at B3. The first two paired intervals include zero; merit is
best at B3. Factorized-feasibility XGBoost has the best B1 point estimate but
loses that advantage at B2/B3. The scorecard adds cycle-reduction and oracle-
regret frontiers, paired workload bootstrap intervals, per-workload outcome
data, censored-oracle handling, target measurement time, and separate model
scoring-overhead examples.

CoreMark v1.01 was screened at the unchanged 8 KiB RAM / 4 KiB stack-reserve,
RV32I/Zicsr, GCC 15.2 `-O2` contract and rejected at baseline link for a
6,360-byte overflow. No target simulation or candidates were reached; its
hash-bound [rejection archive](../results/2026-10-27-coremark-fit-rejection/README.md)
adds zero labels. The next blocker remains a fresh eligible workload with
enough legal candidate opportunities. Do not relax gates or run another model
family sweep over the consumed corpus. The research goal remains active and
unachieved.

## Immediate stop point — October 26, Fannkuch qualification

The corrected Fannkuch run (`results/2026-10-26-fannkuch-qualification-r2/`) is preserved as **rejected at discovery**: the frozen pool requires 12 formulas, while the saved trace has two raw, executable, calibrated formulas. Discovery did run the original N=7 program: its instrumented profile reports **5,193,765 cycles / 974,182 instructions**, the exact packed oracle result, and a passing self-check. The standalone routed-baseline/resource phase and public opportunity phase were not reached. A separate post-rejection reconstruction finds that both formulas belong to the same already-observed add/shift family; one public calibrated projection clears the numeric opportunity threshold, but there is no fresh candidate-family pool. Candidate attempts are zero, and no candidate speedup, area, or timing labels exist. The prior r1 wrapper failure is separately preserved. See the [diagnosis and reproduction command](../results/2026-10-26-fannkuch-discovery-diagnosis/README.md). Keep the rejection; do not shrink the pool or lower gates.

Read [README](../README.md), [AGENTS](../AGENTS.md), [active goal](ACTIVE_GOAL.md), [model results](ard-area-results.md) and [coverage contract](cfg-liveness-experiment.md). Branch: `ai-guided-ml`. Cloud deployment, cost-aware model routing, and RTL rewriting remain out of the current milestone. The October 27 current-chat LLM selector pilot is complete and documented in [its record](codex-chat-selector-pilot.md); it is a consumed-data replay that ties several controls, not a superiority result. [Pre-ARD](HANDOFF-history-2026-10-25-pre-ard.md) and [pre-joint](HANDOFF-history-2026-10-25-pre-joint.md) handoffs preserve historical details.

## Current status — October 26, after the Lift campaign and model screen

The v4 source-bound selection package was pushed before labels. All **12 Lift candidates** then completed successfully, passed correctness, and produced integrated area and three-route timing results. The best +64-LUT4 result is `add(andi(in0,1),andi(in1,1))`: **2,218,414 → 2,148,344 cycles**, **1.032616×**, **+8 LUT4**, and **64.53 MHz minimum routed Fmax**. Pairwise XGBoost's one-query best-candidate hit is a post-collection replay across five dependent seeds, not a live native ML controller. [Full measurements and policy replay](../results/2026-10-26-lift-selection-report/results.md).

The updated corpus contains **122 verified speedup labels / 126 charged attempts / 14 workload groups / 15 contexts**. All 122 speedup labels exactly match the calibrated latency estimate. The current learning problem is integrated hardware feasibility. A failure-aware, grouped held-out screen tests pairwise XGBoost, factorized feasibility XGBoost, cap-specific/group-bootstrap XGBoost and conventional classifiers against frequency, merit, latency/cost heuristics and random. At B1, factorized feasibility/logistic reach 0.7292% versus frequency at 0.9414%; at B2, pairwise XGBoost reaches 0.4385% versus merit at 0.4654%; at B3, merit/calibrated latency reaches 0.0145% while the closest learner has 0.0383%. The existing cap-conditioned utility model nearly matches, but is slightly worse than, factorized feasibility at B1/B2; it improves over factorized at B3, while merit remains best. A follow-up ranker trained on measured feasible cycle-reduction relevance does not improve selection. Two infrastructure-censored pools are excluded from oracle regret. No model is promoted. [Main model screen](model-screen-2026-10-26.md), [utility-model result](feasible-benefit-loco-2026-10-26.md), and [decision-aware ranker result](feasible-benefit-ranker-2026-10-26.md).

**October 26 hardware-uncertainty diagnostic:** `scripts/audit_joint_posterior_calibration.py` replays the frozen joint hardware posterior on the sealed, consumed corpus, holding out each complete workload group and its matching operation-tree families. Run it with `/tmp/isaforge-ml-20261026/bin/python scripts/audit_joint_posterior_calibration.py`; the hash-bound report is in [the calibration artifact](../results/2026-10-26-joint-posterior-calibration/results.md). The 122-label marginal predictive diagnostic finds area interval coverage 0.549/0.779/0.926 and routed-Fmax coverage 0.533/0.770/0.926 at nominal 50/80/95%; log measurement-time coverage is 0.418/0.836/0.918, with standardized RMSE 1.690. Approximate feasibility Brier is 0.2564 versus 0.4497 for the training-only device-fit-rate prior. This is post-hoc development evidence, uses independent output heads and a fixed hardware constraint, and does not evaluate prospective query selection or compare against merit/XGBoost/oracle. Leave the model unchanged; time uncertainty needs fresh, predeclared measurements before any noise-policy adjustment. The joint posterior and paid-update implementation contract remains accepted, with empirical joint-update assumptions still unvalidated.

**Stop point after the BEEBS `strstr` discovery run:** all 85 program directories were reviewed; no fresh workload qualified. `stringsearch1` remains rejected unchanged for out-of-bounds pointer formation on its fixed input. The pinned `strstr` source, original wrapper/verifier and fixed input passed host preflight, then its baseline-only PicoRV32 discovery run found zero legal connected formulas at operation caps 2 through 6. It was rejected before the opportunity and routed-baseline phases; no candidate dispatch or labels occurred. Discovery reported 3,658 instrumented cycles / 644 instructions, an expected count of eight, 64-byte maximum stack, and no stack violations; this is not a routed baseline. The raw archive and hash-bound reconstruction are preserved in [the qualification](../results/2026-10-26-strstr-qualification/) and [diagnosis](../results/2026-10-26-strstr-discovery-diagnosis/README.md). The original archive omitted some plan-bound source snapshots; the diagnosis includes a separate exact-hash source-closure amendment without altering that archive. **Next blocker:** identify a source family that clears the existing opportunity gates before any candidate labels; do not spend time on another model sweep over the consumed corpus. Details: [BEEBS and non-crypto source-search record](noncrypto-workload-search-2026-10-26.md), [MD5 preflight](md5-candidate-heldout-preflight-2026-10-26.md).

Do not launch another model-family sweep on the consumed corpus. The constraint-aware ranker did not improve selection; the existing cap-conditioned utility model is nearly tied with, but slightly worse than, factorized feasibility at B1/B2. First inventory genuinely unmeasured independent workloads/families and record prior rejections and eligibility. If one qualifies, freeze candidate construction, exact sequential orders, controls and budget before labels; retain the existing 12-candidate gate unless a different size has a separately justified protocol. Current timing labels are all positive and at least 47 MHz above the 12-MHz constraint, so timing-boundary transfer and learned timing feasibility are unsupported. Stop before collection if no independent source qualifies. The six-independent-family confirmatory cohort and jointly measured compatible instruction sets remain outstanding. Research superiority is unestablished.

**October 26 qualification result:** one root-owned, baseline-only `complex_updates` run passed `prepare` and stopped at `discover`. Linking failed because `_program_end` violated the fixed 6,400-byte program/data assertion that reserves a 128-byte guard and 1,664-byte stack in 8 KiB RAM. No map was produced, so the exact overage and code/helper attribution are unknown. This proves failure under this exact memory contract only; it does not prove physical RAM overflow or intrinsic source/ISA incompatibility. Candidate attempts/labels are zero; baseline measurement and later phases did not run. Discovery monotonic time was 9.300423167 seconds; the receipt flags a UTC/monotonic bracket disagreement. Preserve this first rejection and do not rerun or loosen the contract. Full protocol and result: [qualification record](complex-updates-qualification.md), [raw archive](../results/2026-10-26-complex-updates-qualification/).

**October 26–27 Ascon host and source-family checkpoint — passed, target still gated:** the pinned v1.3.0 source and test artifacts are copied exactly (13 files / 288,906 bytes) under [`benchmarks/ascon/upstream`](../benchmarks/ascon/upstream) with a separate [copy manifest](../benchmarks/ascon/ASCON128_V13_COPY_MANIFEST.json). The fixed-buffer host wrapper checks every original length pair, encryption success, ciphertext length, valid decryption, recovered length/plaintext, and first-byte tamper rejection. It made **1,089 encryptions and 2,178 decryptions**; all **6,534 KAT fields** and **34,848 ciphertext bytes** match the 1,089 pinned records, and all **260,253 serialized bytes** are identical. Fifteen focused tests pass, including six fake-API fail-closed controls. A reproducible [source-family audit](ascon-source-family-audit-2026-10-27.md) finds crypto Boolean/rotation motif overlap in four hash-pinned public pools; this is same-domain transfer, not an independent confirmatory family. No RV32 compilation, target job, extracted Ascon pool, dispatch, measurements, labels, or model fits occurred. **Next step:** prepare a target adapter preserving the full declared input workload and correctness checks, then derive a label-free RV32 candidate pool. Compare exact formula families before any fit or measurement, and retain the 6,400-byte/12-candidate/0.5%-opportunity/ten-timed-replacement/12-MHz gates. See the [machine-readable family result](../results/2026-10-27-ascon-source-family-audit/report.json), [host result](../results/2026-10-26-ascon-host-preflight-r3/result.json), and [frozen adapter contract](ascon-adapter-contract-2026-10-26.md). Never lower gates or treat host KAT equivalence as a speedup/hardware result.

**Earlier Fannkuch source-search checkpoint:** the pinned source and host adapter passed their pre-qualification checks; the later corrected baseline-only run rejected it at discovery with only two calibrated formulas, both from an already-observed add/shift family. The original N=7 target self-check passed, but routed-baseline resources and candidate measurements were not reached. Preserve the rejection and its exact evidence in the [diagnosis](../results/2026-10-26-fannkuch-discovery-diagnosis/README.md) and [search record](noncrypto-workload-search-2026-10-26.md).

**GPT-6.1 Sol's read-only result:** a new candidate pool within consumed MD5 is a conditional candidate-measurement development experiment, not fresh-workload transfer. Saved public discovery has 297 eligible formulas; excluding all seven operation-tree families from the prior 12 attempts leaves 33 formulas in three families. A deterministic 12-formula stratification passes the unchanged **pool-level** public opportunity rule through candidate_03 alone (16 replacements; 48/6,192 = 0.7751938% projected saving). Do not describe this as measured benefit or require every candidate to pass the opportunity gate.

An isolated offline pass now produced certificates for all twelve entries, covering 59 archived occurrences and 768 sampled block comparisons. It checks saved-source mapping, relocation and bounded lowering, and records each emitted assembly hash. It does not prove assembler acceptance, universal equivalence, full-program correctness or integrated hardware feasibility; the old pool seal still does not authorize dispatch. The extended identity audit found no declared alias among 132 public candidates in 16 contexts; all 132 historical attempt-directory identities map to those pools. This closes the bounded identity-membership gate, not terminal outcomes or universal history. The [identity-audit record](md5-cross-context-identity-audit-2026-10-26.md) binds all inspected public pools and membership evidence. The prelabel audit requires rebuilding fixed existing model recipes from a common **28-row / seven-group** cohort: remove the one non-MD5 training row overlapping a new formula family from the original 29-row MD5 prelabel cohort. All old MD5 labels remain excluded. Old fitted weights, scalers, target predictions, and finite-pool covariance are invalid for this cohort and roster. The [preflight record](md5-candidate-heldout-preflight-2026-10-26.md) and [certificate artifact](../results/2026-10-26-md5-candidate-heldout-prereg/offline-certificates-v1/certificates.json) bind the roster and remaining stop gates.

Current assignments: the roster-certificate builder and its 12 synthetic tests are complete. The public-only identity audit is versioned in [audit v2](../results/2026-10-26-md5-candidate-heldout-prereg/cross-context-identity-audit-v2.json); [manifest v2](../results/2026-10-26-md5-candidate-heldout-prereg/artifact-manifest-v2.json) preserves the old manifest and records the README hash correction. `evidence_audit` verified the common 28-row/seven-group cohort, zero MD5 rows and zero selected-family overlap without reading labels; the independent audit binds all eight source hashes. `next_experiment` completed the [zero-label controller preparation](../results/2026-10-26-md5-candidate-heldout-prereg/controller-preparation-v1/README.md), and GPT-6.1 Sol independently checked its hashes, cohort, ID remap, recipes and controls. A later exact-cohort run rebuilt 31 existing-recipe model components and recorded 115 initial proofs; its [model-preparation receipt](../results/2026-10-26-md5-candidate-heldout-prereg/model-preparation-v1/model-preparation.json) reports zero target-outcome reads, new-pool labels and native jobs. The model artifacts are complete but unreleased; every collection authorization flag remains false.

The [append-only semantics erratum](../results/2026-10-26-md5-candidate-heldout-prereg/controller-preparation-v1-erratum-2026-10-26/README.md) binds the v1 contract without changing it. It adopts +64 LUT4 / 12 MHz and `fixed_joint_lookahead`, seed 0, B3 as a **development pilot**: one live three-query trace followed by nine reference attempts. Other methods and dependent seeds are cooperative replay, charged per policy; this supports query-budget comparisons with disclosed cost accounting, not equal wall-time or 85 independent native campaigns. It also corrects “fixed initial scoring” for the incumbent-dependent latency/cost heuristic and zero-shot hybrid, and distinguishes complete durably sealed terminal failures from unknown failures and interruptions. The erratum itself does not authorize fitting, model artifacts, candidate dispatch or native measurement; a separate exact-28-row historical-only preparation has since created the unreleased model artifacts described above.

Next bounded assignments: `next_experiment` owns the isolated new-pool adapter/controller and synthetic acceptance specification; `evidence_audit` owns fairness and the historical-only 28-row validity checklist; GPT-6.1 Sol independently reviews those deliverables. The controller must authenticate a bijective archived→preparation→release ID mapping, enforce proof before durable reservation at the evaluator boundary, isolate each policy's paid prefix, and stop on unknown/ambiguous attempts. The historical-only cohort checks and prefit are now complete, but the evaluator still lacks durable native reservation/terminal evidence and recovery, evaluator-side proof/reservation locking, real paid-model callbacks, authenticated native plan/remap/toolchain/baseline, and verified live-three-before-reference chronology. The offline certificates establish neither assembler acceptance, full-program correctness nor hardware feasibility. Preserve this as consumed-workload candidate-heldout development; the independent-workload research goal remains unresolved.

## Historical checkpoint before Lift collection

At the pre-Lift checkpoint, the corpus had **110 verified labels, four failures, 114 attempts, thirteen sources and fourteen contexts; 124 completed integrated designs / 372 complete-design routes**, plus two partial routes. The Lift collection below adds twelve verified candidate labels and two contexts. Preserve the original 110 rows and every historical result. The prior candidate ledger totals 6,749.807273 seconds; qualification, baseline and host costs are separate overlapping scopes.

[G.723](g723-transfer.md): seventeen policies were pushed before labels at `d8a5c91`. Live lookahead 09→00→47 finds 3,783,237→3,623,462 cycles / +30 LUT4 / 67.549 MHz at query two. Fifteen controls find the best verified result at query one. Candidate 57's route-3 timeout stays unknown, charged 219.421167 seconds and never retried. The full-pool oracle is unresolved; gaps are lower bounds. Exact replay passes 345 trajectories / 900 points / 180 summaries. No promotion.

[ARD model experiment](ard-area-results.md): source/contract pushed at `c124452f`; all initial models pushed at `b77ecf7b` before scoring. One area initializer changes; 37 features, cohorts, other predictors, calibrated benefit, myopic acquisition and paid conditioner stay fixed. All 450 trajectories / 900 points / 180 summaries reproduce exactly, retaining 1,800 summaries from seventeen controls. G.723 is excluded.

At +64 LUT4 / B3, the old three-source macro stays 1.602185159%; the expanded macro falls from 1.602185159% to 0.839440974% because AHA returns baseline. Bitcount repairs 0→0.174118284%, its existing heuristic optimum. DCT and Expint tie. Across thirty case/cap B3 means: one win, one loss and twenty-eight ties against original myopic; zero wins, six losses and twenty-four ties against the strongest archived envelope. No promotion or superiority. All thirty starts converge; 316 bound hits / 356 warnings remain recorded. Each preparation/reconstruction charges sixty scalar GP attempts, including unused semantic-area fits. Zero fits inside queries; zero new native labels.

[Sealed model validation](../results/2026-10-25-model-validation/README.md): 217 focused tests, 3,689 full tests / 179 subtests and historical six-model reproduction pass at the pre-CFG checkpoint. The historical cleanup failure does not recur; no fix is claimed. Exact replay retains raw host timers. Concurrent checks and clock disagreement prevent controlled-latency or uninterrupted-calendar claims.

[Original Lift qualification](../results/2026-10-25-lift-qualification/qualification.json) is rejected during discovery: eleven formulas remain after relocation filtering, below twelve. It adds zero candidate attempts and no synthesized baseline. Preserve that context's first rejection and archive. Original 1,001 zero-input iterations / checksum 4005888 remain unchanged. Phase observer: 12.802695 seconds; outer observer: 13.606164 seconds, overlapping. Static review identifies dead Boolean temporaries falsely counted as outputs in two loops.

## Lift qualification and tail-transfer development history

The owner resumed development. The first CFG-context Lift qualification did run and remains finally rejected at discovery with zero candidate attempts. Its four unsupported JALR entries are compiler-emitted exact AUIPC/JALR tail transfers. The [v2 implementation](cfg-liveness-tail-transfer.md) recognizes that narrow form, retains it as a hard dataflow barrier, and keeps the v1 source/results unchanged. Its offline preflight is authenticated against the v1 rejected raw archive and records **four resolved tail transfers, 17 executable formulas, 13 relocation-safe/calibrated formulas and a 12-formula stratified pool**.

The focused CFG v1/v2 suite passes **199 checks**, including exact-proof fallback tests, linked-call preservation, and validation that preflight inputs match the rejected raw archive. The general analyzer retains explicit ABI-return and firmware-trap opt-ins; exact tail proof is required even when a JALR resembles an ABI return. Original extraction/verifier and v1 CFG files remain unchanged. The full repository suite completed with **3,887 passes, 179 passing subtests and one failure**: `tests/test_capture_v11_spooled.py::test_blocked_pipe_or_compressor_drain_has_finite_cleanup[pipe]` left a producer process in its cleanup record. This is outside the ISAForge patch; the separate previously recorded external_v5 cleanup failure is also preserved.

The source/contract checkpoint was pushed as `0ce10d19`. The separate baseline-only qualification has now run once and is **accepted**. Its exact command was:

```sh
../work/audit-venv/bin/python scripts/qualify_cfg_lift_tail.py \
  --output results/2026-10-25-lift-cfg-tail-qualification \
  --native-root generated/tacle-lift-cfg-tail-2026-10-25
```

The complete result is preserved at [v2 qualification](../results/2026-10-25-lift-cfg-tail-qualification/qualification.json) with the 210-file raw native archive. All six phases succeeded. Baseline correctness self-check passed at **2,218,414 cycles / 435,473 instructions**, with **1,653 LUT4, 295 carry cells, 20 RAM blocks and 655 flip-flops**. It met the 12 MHz clock constraint at all three routing seeds (77.16 / 68.49 / 70.39 MHz). The public opportunity gate accepted 10 of 12 formulas; its 6.4976% maximum public cycle-reduction projection and 18,018 timed replacements are not measured candidate speedups. Candidate dispatch was disabled, with **zero candidate attempts and zero measured labels**. The protocol records `unchanged_verifier=false` and `unchanged_full_register_lowering_verifier=false`: the v2 projected-equivalence verifier is a changed validation component, although the upstream correctness self-check remains enabled. Preserve this as an explicit limitation.

Keep the original hardware, inputs, compiler flags, partition, twelve-formula and .5%/ten-execution gates. Lift has informed development and cannot count as untouched confirmation. This accepted baseline/pool adds no candidate label or model improvement.

The broader research goal is active and remains unachieved. No model superiority is established. A later candidate campaign requires another complete pushed model/policy/controller release before labels, equal-budget controls and actual correctness, whole-program and integrated hardware results.

A later candidate campaign needs a new complete pushed model/policy/controller release before labels, matched information/budgets and actual correctness, whole-program and integrated hardware results. Do not bypass G.723's context guards. Six independent eligible confirmatory families remain unestablished. Joint sets of one to three instructions remain required later; never sum individual performance or integrated area. No further model sweep or benefit-residual learner while all 110 cycle labels match calibration.

## Methods and commands

[Full-text update](research-fulltext-update-2026-10-25.md) resolves exact Sun TCAD 2004 methods and separately reviews Hussein's 2025 preprint. Exact TACO 2026 remains inaccessible. Sun's timing-aware shortlist, charged verification and joint top-k synthesis guide named adaptations; our current single-instruction flow is not a full reproduction. No GNN/RL enumerator is assigned.

Use Python 3.12 / `requirements-speedup.txt`, locally `../work/audit-venv/bin/python`. The tail preflight command is in [its contract](cfg-liveness-tail-transfer.md); its v2 native qualification is complete and must not be rerun. [ARD replay](ard-area-results.md) and [G.723 commands](g723-transfer.md) need fresh outputs and launch no native jobs. Never rerun completed qualifications/collections or change frozen sources. Track every manifest-referenced artifact, including ignored logs. Use a new validation directory for CFG work; model validation is sealed. The active goal remains unachieved.

## October 26 — prelabel package and completed candidate collection

The accepted Lift pool has a complete separate candidate campaign in [`lift-selection-campaign.md`](lift-selection-campaign.md). It froze all 17 existing policies, ran fixed-joint myopic at +64 LUT4/B3 as the only live policy, sealed each choice before its guarded native attempt, then sealed the completed live trace before measuring the public-order remainder. A post-collection replay evaluates all policies under identical candidate outcomes and query budgets, records censored-reference regret and paired CLI/native costs, and exports all charged outcomes without modifying the earlier 110-label corpus.

The complete zero-label model/controller package is frozen and authenticated at `results/2026-10-26-lift-selection-preregistration-v4`: 12 Lift candidates, 100 fitting rows across 13 prior source groups, 17 policies, 345 expected trajectories, 900 endpoint points and 180 summaries. Same-day v1, v2, and v3 packages are retained as superseded; none read outcomes or ran candidate jobs. v1 lacked complete replay/export. v2 exposed terminal-failure, moved-path, archive-restore, frozen-model-binding, and root-bound verification defects. The final v3 review caught a selection-inventory binding mismatch and missing validation-refit cost accounting. The accepted Lift baseline remains separate. Lift remains consumed engineering development, not untouched confirmation.

**Validation after the campaign extension:** 40 focused campaign tests pass. A hardware-free synthetic policy replay produces 345 trajectories /900 points /180 summaries and correctly marks infrastructure-censored regret as a lower bound; this is a software smoke test, not measured evidence. The accepted baseline's raw archive also passed a real pack/restore audit round trip with zero candidate attempts and zero native jobs. Frozen selection validation checks 5 original-control, 5 utility, and 5 feasibility refits; its host duration is reported separately. The initial October 26 full-suite checkpoint passed 3,928 tests and 179 subtests. A subsequent full rerun after the latest model-screen tests passed **3,936 tests and 179 subtests** (one duplicate-ZIP-name warning), using `../work/audit-venv/bin/python -m pytest -q`. The later failure-aware model screens are in [model-screen results](model-screen-2026-10-26.md), [decision-aware ranker results](feasible-benefit-ranker-2026-10-26.md), and [existing utility-model results](feasible-benefit-loco-2026-10-26.md); they are retrospective, add no native jobs, and promote no learner. All 122 speedup labels still match calibrated latency, so do not build another speedup regressor without a new demonstrated residual.

The campaign command and archive details remain in [`lift-selection-campaign.md`](lift-selection-campaign.md). The active research goal remains unachieved; no model superiority is established.

## October 27 — current-chat selector integration and midterm materials

The active Codex chat model completed one bounded EDN selection replay through `scripts/run_codex_chat_selector.py`. It chose a correctness-passing 1.0004323× candidate at +32 LUT4 and 71.1187 MHz minimum routed Fmax, matching the measured-pool oracle. One shortened candidate ID consumed an invalid charged attempt, so the pilot used two charged attempts for one valid measurement. Frequency, merit, pairwise ranker, raw regression, and GP controls reach the same oracle at the two-attempt endpoint; no LLM advantage is established. It made no API call and launched no native job. The exact transcript-derived action ledger, protocol and limitations are under `results/2026-10-27-codex-chat-agent-edn-b64-s0/`; see [interpretation and reproduction](codex-chat-selector-pilot.md).

The report, slides and frozen dataset export are under `submissions/midterm-2026-10-28/`. The report and slide deck include the current-chat pilot and explicitly label dynamic model routing as unimplemented. Team names, contribution attribution and exact shares still require human confirmation before Canvas upload.

## October 27 — Ascon selector release recovery

The v1 Ascon prelabel package remains preserved but cannot authorize dispatch
because its `AGENTS.md` and `README.md` bindings no longer match the committed
tree. V2 is preserved as an intermediate because it omitted the package
generator hash. The current v3 package is reproducibly frozen and authenticated
at `results/2026-10-27-ascon-selector-prereg-v3/`: it binds 32 inputs including
the preparation script, and contains twelve public candidates, 90 family-safe
historical labels across 14 groups, 13 fixed policies, five seeds, budgets one
through three, and zero target labels or attempts at freeze time. Controller
release v5 passed its exact pushed-source gate at commit `007d6593`; its live
three-query trajectory is now sealed in the result archive below. Subsequent
status-normalization changes invalidate v5 for any further dispatch. The old v2
campaign root still contains one charged unknown reservation and remains
untouched. The v5 run is same-domain crypto transfer, not independent-family
confirmation, and its nine unmeasured candidates leave the oracle incomplete.

The [MiBench source scout](mibench-scout-2026-10-27.md) rejected four
read-only source candidates under the current target contract. It ran no
benchmark and contributes no labels. Continue searching for an eligible
independent integer workload; the six-family confirmatory cohort remains
unestablished.

**Latest October 27 update — Ascon three-query run and paid-update bug:** the v5 release passed its pushed-source gate at `007d6593`, then the operator-relayed chat agent measured three candidates. C01: 1.019698×, +73 LUT4, 62.992 MHz (area-infeasible); C06: 1.017027×, +41 LUT4, 67.069 MHz; C02: 1.023731×, +42 LUT4, 64.620 MHz. All passed correctness; C02 is best among the three measured feasible results. Nine candidates are still censored, so there is no complete-pool oracle or heuristic comparison. The complete generated campaign is preserved as a hash-checked archive in [`results/2026-10-27-ascon-selector-chat-run-v5/`](../results/2026-10-27-ascon-selector-chat-run-v5/). A real paid-prefix audit found `_dynamic_gp` excluded all three successes because audit rows omitted `status`; it recorded zero fit time. The working source now persists success status and includes a regression test. Four focused test modules pass (30 tests), and a post-hoc 90+3-row replay confirms refit execution and the paid-prefix hash, but this is consumed-data software validation. The v5 release remains archived against commit `007d6593` and is no longer valid for further dispatch after these source changes. Treat this run as integration development, not a prospective comparative result. The next blocker is still a fresh independent workload; the disclosed Ascon pool cannot be reused to claim confirmation.
