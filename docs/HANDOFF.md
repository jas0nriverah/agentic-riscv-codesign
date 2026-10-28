# Current handoff — model evidence after Lift selection

## October 28: grouped XGBoost + live-chat selector replay and bounded memory

The existing pairwise-ranking and factorized-feasibility XGBoost recipes are
now exposed to the four-tool selector on an authenticated, whole-workload and
target-family-held-out CRC32 case. The current model bundle adds no estimator
or label: pairwise scores are relative ranks, feasibility outputs and ensemble
disagreement are uncalibrated, and the analytic latency feature remains the
only quantity equivalent to measured cycle speedup on the current corpus.

Two GPT-6.1 Sol chat-relay episodes replayed the same six-candidate, already
measured CRC32 pool under +64 LUT4 / 12 MHz constraints. The no-retrieval run
found the complete-pool best feasible design in two charged measurements; the
hybrid top-three retrieval run found it in one. The design measured
32,387,382 → 30,820,662 cycles (1.050833x), +31 LUT4, 71.489845 MHz, correct,
and 42.0438 archived evaluation seconds. Factorized-feasibility XGBoost also
finds it in one retrospective measurement; pairwise XGBoost, merit, calibrated
latency, latency-cost and random reach it by two, frequency by three. Thus the
LLM ties current best selection in this one replay. The no-retrieval run
includes two invalid manually relayed candidate IDs and measures one
area-infeasible candidate before the best; those invalid actions were not
charged. One seed, one consumed workload, differing context framing, a
non-sandboxed Codex relay, and unknown model latency/token use prevent a causal
memory or agent-quality claim. No native jobs or new labels were generated.

Hybrid retrieval now keeps full history out of the LLM context, returns at most
three approved records, and enforces a 40,000-byte retrieved-payload ceiling.
On the initial CRC32 request it reduced serialized context from 154,008 bytes
(101 raw historical rows) to 17,353 bytes (three rows, 5,103 retrieval bytes).
This is a byte-count result, not token, latency, or decision-quality evidence.
The second AHA-compress replay used the same hybrid policy and 12-candidate
pool: after three measurements it finalized baseline because all selected
candidates exceeded the area cap; its best feasible complete-pool oracle is
1.023418x (+61 LUT4, 64.184853 MHz, correctness passed). In the matched seed,
merit, calibrated latency and pairwise XGBoost hit that oracle by B3; the
factorized-feasibility model did not. This is a preserved counterexample, not
a prospective generalization result. The local SQLite exports record context
windows, retrievals, decisions, tool actions and null token usage for the Codex
relay. Three authenticated Ascon measurements remain a separate training-only
supplement; the two-model workload-holdout ablation changes no model promotion
decision. Details, commands, limitations and source references are in the
[integration record](ml-agent-integration-2026-10-28.md).

Validation for the combined memory, bounded-selector, grouped-prediction,
grouped-case, rationale and Ascon-supplement changes: **104 focused tests
passed**. No live Responses API call or native evaluation was made. The research
goal remains open; next require a fresh eligible workload and a preregistered,
same-information prospective comparison.

## October 28: trace-bound rationales and separate provider budgets

Accepted LLM finalization notes are retained as explicitly unverified prose and bound to the exact visible decision context, accepted action, provider/policy trace, host-verified outcome, constraints, and measurement references/hashes. Host fallbacks get deterministic evidence with no invented model explanation. Requests expose remaining outer decision turns and provider calls; routed recovery enforces the effective allowance. The runner records provider calls separately and stops before opening an empty decision after provider-budget exhaustion. SQLite includes rationale, measurement-evidence, host-event, and provider-call fields.

Validation: **122 focused tests pass** across selector, routing, memory, rationale, provider, chat bridge and SQLite export. The first full run returned **4,350 passed, 181 subtests passed, one failure** in the previously documented capture-cleanup fixture. The helper is hash-bound by historical V11c evidence, so an in-place fix would invalidate its exact-source check. The fixture now requires bounded completion and only accepts a residual group marker when the receipt records the matching `killpg` permission error. The helper's conservative uncertainty is unchanged; this does **not** establish that an `EPERM` group is gone. The refreshed full suite passes **4,351 tests and 181 subtests** (one duplicate-ZIP-name warning). This work does not change the speedup model, establish an LLM-quality result, or create new hardware labels.

## October 28: MachSuite Viterbi source-screen closure

At pinned upstream commit [`6236e59`](https://github.com/breagen/MachSuite/tree/6236e593012cb86b0d2f08d9fb9ba0411ff989b4), Viterbi's harness actively compares all 140 reference path bytes, despite a conflicting suite-wide README statement that final checks are not performed. Its standard configuration still cannot enter the current PicoRV32 pipeline: arrays occupy 66,328 bytes and the local dynamic-programming table adds 71,680 bytes of stack, before code/runtime, versus 8,192 bytes of total RAM. Its bundled text input is 157,301 bytes and would need to be re-expressed in the fixed input/ROM contract. No workload was modified, no compiler or target job was run, and no labels were created. The commented small dimensions would need a separate context review. See the [source census](training-dataset-census-2026-10-28.md) for exact source links and arithmetic.

## October 28: expanded public-source screen and memory retrieval evaluation

An independent source review added LLVM Richards, jsmn, and heatshrink to the census. Richards is the strongest new lead because it has a deterministic built-in oracle and a small live data structure, but its upstream small mode fails its own reference, while the default needs `malloc` and an unresolved indirect function call that the current CFG extractor rejects. jsmn's stock 128-token stack array exceeds our stack contract; heatshrink's full tests include a 32-KiB VLA and compression-family overlap. No source passed all current gates, and none was built or run on target. The [census](training-dataset-census-2026-10-28.md) records exact pins, licenses, and blockers.

The [held-out retrieval structural-coverage diagnostic](../results/2026-10-28-retrieval-structural-coverage-r1/README.md) reports 0.9301 workload-macro operator-type coverage@3 for the knowledge graph, 0.9103 for lexical TF-IDF, 0.9041 for hybrid, and 0.8765 for TF-IDF/SVD. It excludes each entire workload and all related expression families before indexing, and scores only formula operator types—not outcomes. This shows structural support for the existing retrieval feature; it does not measure relevance or improve LLM decisions. It used the consumed 122-label / 14-group corpus and added no labels, jobs, LLM calls, or model fit. A new prospective controller in [the finite-benefit guard contract](prospective-finite-benefit-guard.md) also stops before a second dispatch if a successful paid outcome contradicts the selector's calibrated-cycle-benefit assumption. Its software tests use synthetic fixtures only; no existing frozen campaign or report was changed.

## October 28: selector v2 incumbent guard and failure audit

The owner resumed a 10-hour improvement block focused on the bounded LLM selector and evidence-backed ML decisions. Selector protocol v2 exposes the host-computed current best feasible incumbent, rejects finalization of any stale/lower candidate or an unnecessary baseline choice, and returns canonical measured fields separately from the LLM's unverified `agent_summary`. The four-tool allowlist and charged-measurement behavior remain unchanged. The earlier pilot's three rejected no-memory finalizations are a concrete motivation; this implementation does **not** establish that a future LLM run will need fewer turns.

Validation: **79 focused tests pass**. `scripts/run_bounded_selector.py --provider controls --target sha256 --seed 0 --cap 64 --budget 3` reproduced **10 policy trajectories / 30 budget endpoints** exactly against archived controls; zero LLM calls and zero native jobs. The sealed run is [`results/2026-10-28-incumbent-v2-control-replay-r2/`](../results/2026-10-28-incumbent-v2-control-replay-r2/). Frequency and latency/cost still find the 1.0213847× measured candidate in one query; merit and XGBoost ranking reach it by query three. Raw regression is worse at 1.0052618× after three. This is consumed SHA-256 replay only; it is not an ML or LLM win.

The [failure audit](../results/2026-10-28-incumbent-v2-control-replay-r2/README.md#historical-failure-audit) clarifies four charged attempts: two candidate correctness/contract rejections (`edn` memory guard and `ud` self-check), one storage-censored attempt (`ud`, under 2 GiB free), and one G.723 routing timeout (route seed 3 at 180 seconds). Preserve all four rows and their budget cost. Only the first two are correctness failures; the latter two provide no target outcome label. Do not retry them as if the old measurements did not happen.

No new model fit is warranted: speedup labels still equal the calibrated latency estimate on the current corpus, and no independent held-out workload has established transfer. The next useful experiment remains a frozen prospective comparison on a newly qualified workload or family, with merit/frequency/latency-cost, XGBoost and an LLM agent sharing the same public state and paid budget. Fresh workload gates remain binding.

## October 28: host-feedback recovery routing

The bounded model router now allows one stronger-model call after either malformed structured output or a specific recoverable host result: selector v2 rejected a finalization and returned the current incumbent ID. The reason is preserved in the model-call trace and `model_calls.trigger_reason` SQLite column. Both roles receive the same public snapshot; the escalation shares the model-call allowance and can occur only once per episode. Measurement failures, transport errors, timeouts, and unrelated tool errors do not trigger it. This directly addresses the prior no-memory Luna pilot's three rejected finalizations while preserving incumbent-only host acceptance. It is a software recovery feature; there is no live v2 LLM comparison or evidence of improved selection quality yet.

The focused selector/router suite passes **85 tests**, including a full host-correction recovery loop. The live API key is not configured in this workspace, so no paid model call was made. Slides 7–8 and the seven-minute notes now show the trigger and distinguish software validation from live evidence; the regenerated 11-slide deck validates at 420 seconds / 966 spoken words. The next experiment is a frozen fixed-primary / fixed-stronger / recovery-router comparison on the same consumed pool and measurement budget, with model calls, observed tokens, latency, paid measurements, and final feasible speedup reported separately. Keep the original live pilot unchanged.

## October 28: host-owned fail-safe finalization

If the primary and permitted recovery fail, or the bounded model/tool loop runs out before the LLM finalizes, `run_selector` now closes through `host_finalize`. The host commits only its best paid, verified, feasible incumbent or the baseline. `status=host_fallback`, `finalization_source=host`, and `fallback_reason` distinguish this from a model-authored finalize; the `host_events` audit record preserves trigger, error type, model/tool calls, charged attempts, and selected ID. It adds no model/tool call or measurement and does not create an `agent_summary`. Process interruption is still re-raised after an interrupted ledger write; target-evaluator and host-integrity failures remain failures.

SQLite export now includes a `host_events` table. The focused suite passes **87 tests**, including a failed stronger-model recovery that safely closes on the incumbent, provider/tool-budget fallback, and SQL export checks. This is offline engineering evidence only: no live call, target job, label, model fit, or selection comparison was added. It improves completion/accountability of the agent loop, not candidate ranking or speedup.

## October 28: live Luna memory and operations evidence

Implemented local TF-IDF/LSA/hybrid historical retrieval over approved training records, memory augmentation, decision-to-tool links, sealed-run SQLite export and file-based public request transport. No general document RAG, pretrained embeddings, production deployment or live model-routing improvement is claimed. [Implementation](agent-memory-operations.md).

The frozen two-arm GPT-6 Luna pilot is complete: no retrieval 9 turns/3 charged archive queries/3 rejected finalizations; hybrid 4 turns/2 queries/0 rejections. Both reach 1.0213847x at +50 LUT4, 65.99353MHz. Strong frequency and cost heuristics reach it at query one. Preserve [all evidence](../results/2026-10-28-live-luna-memory/README.md). No replacement runs or new hardware measurements. One trial per arm does not establish causal memory improvement. Configured alias known, exact deployment version/tokens unavailable. Public-file restrictions are instruction-enforced, not sandboxed.


## October 28: bounded agent routing engineering

The owner resumed implementation of useful agent-plan components. Added schema-error-only primary/escalation routing, a shared reserved-call allowance, per-call identity/request-hash/usage/latency traces, and separate dispatched-call accounting in the remote replay CLI. Host-owned hardware charging, hidden-outcome boundaries and incumbent fallback remain intact. See [implementation analysis and commands](agent-routing-implementation.md).

Validation: 74 focused selector/provider/bridge tests pass. The separate `generated/routing-controls-20261028` CLI replay has 10 trajectories / 30 endpoints, all archived controls exact, zero LLM calls and zero new native jobs. No routed live-model comparison, model fit or candidate label was produced. Routing handles invalid structured output only; uncertainty-based routing, token-aware compression, RAG/frameworks and deployment remain deferred. Current slides retain their presentation snapshot; do not present planned routing quality/cost improvements as measured. Next is a frozen fixed-primary/fixed-strong/routed comparison with matched hardware budgets and separately reported model costs.


## October 27 — historical presentation stopping point (superseded October 28)

This is a preserved historical checkpoint, not the current instruction. On
October 27 the owner paused research for presentation preparation. On October 28
the owner explicitly resumed a 10-hour research and implementation goal focused
on the bounded agent, measured-outcome ML decisions, and reproducible evidence.
Follow [the active goal](ACTIVE_GOAL.md) and the October 28 entries above; do not
use the old stopping-point instructions below to block resumed work.

The owner asked to stop research after one bounded implementation and prepare
to present. The final change adds archive-only reproduction of the countnegative
diagnosis. The original diagnostic and sealed results remain byte-for-byte
unchanged; the new wrapper restores authenticated regular-file archive members
into temporary storage, runs the original diagnostic, and requires exact report
and file-hash agreement. It rejects unsafe/duplicate members and writes only to
a fresh directory under `generated/`.

Command: `make reproduce-countnegative-diagnosis PYTHON=../work/audit-venv/bin/python`.
For repeat checks, set `COUNTNEGATIVE_REPLAY_OUTPUT` to a fresh generated path.
The focused tests include an actual complete replay with subprocess execution
and reads of the original native root forbidden. No new measurements, model
fits, target qualification, or policy sweep was launched.

[Stopping-point validation](../results/2026-10-27-presentation-stop-validation/README.md)
records eight latest focused passes, exact archive replay, and successful
six-model/processor replays. The full suite had 4,293 passes / 181 passing
subtests and the previously documented blocked-pipe cleanup failure; no fix is
claimed. Its reported child PID was absent at the final process check.

The [AI report inserts and presentation notes](../submissions/midterm-2026-10-28/ai-track-insert.md)
provide Sections 2.3/3.3, a seven-minute allocation, and Q&A grounded in the
current evidence. The supplied PDF and slide files are unchanged. The central
message is a functioning prototype with 122 historical measured labels across
14 groups, a pairwise XGBoost challenger, and bounded agent integration, with
no established overall ML/LLM advantage. Merit leads at budget three. The
timing constraint is loose in the existing cohort, the uncertainty assumptions
remain provisional, and final instruction combinations remain unmeasured.

At that historical checkpoint, presentation work was the requested next action.
The broader research objective remained unachieved. This dated record remains
for provenance; its next-action guidance was superseded by the October 28
resumption above.

## October 27 — countnegative rejected at target discovery

The original TACLeBench `countnegative` integer kernel is now pinned by the
existing full-suite archive hash and per-file Git/SHA-256 hashes. Its external
adapter preserves the deterministic 20×20 matrix, original checksum, and
initialization outside the timed benchmark function. The host smoke test and
exact baseline-only target self-check pass. Discovery recorded 12,477
instrumented cycles / 2,510 instructions, 2,472 / 6,400 program+BSS bytes and
64 / 1,664 observed stack bytes; these are not routed-baseline measurements.

The unchanged guarded extractor produced 5 raw / 5 executable formulas, of
which 4 were relocation-safe and calibrated, against the frozen pool
requirement of 12. Qualification was rejected at discovery before opportunity
scoring or routed-baseline measurement. No candidate pool was frozen; there are
zero candidate attempts, measured labels, candidate area/timing outcomes, or
model updates. Two formula families are absent from the historical corpus,
which is not enough to claim independent workload transfer. Preserve the
rejection and do not retry it or relax any gate. The archive-authenticated
[offline diagnosis](../results/2026-10-27-countnegative-discovery-diagnosis/README.md)
reconstructs the counts without another target job; the [qualification
archive](../results/2026-10-27-countnegative-qualification/) preserves the
original raw run.

This leaves the same central blocker: find a separate supported workload that
clears the frozen candidate and opportunity gates before attempting a
prospective matched-budget policy comparison. The measured corpus remains
122 verified labels across 14 workload groups; this rejection adds none.

## October 27 — nested uncertainty-scaling diagnostic: do not promote

Command: `../work/audit-venv/bin/python scripts/audit_nested_joint_uncertainty_scaling.py run --output results/2026-10-27-nested-joint-uncertainty-scaling-r3`.
The authenticated report uses 122 historical verified outcomes and four
charged failures, with nested workload-group and operation-family holdouts.
The calibration factor is estimated from the other workload groups only; each
fold evaluates its first three charged attempts, so failures consume budget but
do not condition the GP. The run made **196 fits, zero native jobs, and zero new
measurements**. Four focused test modules pass 86 tests in the current
checkpoint, including five nested-audit tests. Reported host time is 7.23 seconds
for nested calibration and 0.56 seconds for the outer fit/scoring passes; no
target evaluation time was incurred.

Nested variance scaling improves some 80% interval-coverage figures after paid
measurements, but it does **not** improve the selection-relevant hardware
feasibility Brier score on the budget-three prefix: candidate-weighted Brier
increases **0.2508 → 0.2593** on 41 scored outcomes; equal-workload macro Brier
increases **0.2237 → 0.2323**. Whole-workload paired bootstrap intervals for
both differences cross zero. The query-three Fmax variance factors are highly
unstable (median **98.7×**, maximum **586.3×**), so the interval gain is not a
selection win. Do not promote this correction or tune it further on these same
labels. The [sealed report and figures](../results/2026-10-27-nested-joint-uncertainty-scaling-r3/results.md)
preserve the method and negative outcome. This is consumed-data diagnosis only;
the next evidence needed remains a frozen comparison on an eligible untouched
workload.

## October 27 — MiBench stringsearch rejected at discovery

After its source-bound adapter and protocol were committed and pushed, the
baseline-only qualification ran once using
`../work/audit-venv/bin/python scripts/qualify_mibench_stringsearch.py`. The
pinned program passed its host 57-case offset oracle and target self-check.
Target discovery reported **393,191 cycles / 67,989 instructions**, with
program+BSS at **5,556 / 6,400 bytes** and stack use **592 / 1,664 bytes**.
It found ten calibrated formulas, only two relocation-safe, against the frozen
12-candidate requirement. Discovery stopped before opportunity scoring or the
routed baseline; there were zero candidate attempts or labels, zero resource
or timing results, and no model update. These discovery counters are not a
routed baseline or speedup labels. Preserve the [qualification archive and
offline diagnosis](../results/2026-10-27-mibench-stringsearch-qualification/README.md).
Do not rerun this context or lower any gates. This single text-search source
has no frozen candidate pool or completed historical formula-family audit and
cannot establish independent confirmation. See the [adapter
contract](mibench-stringsearch-adapter-contract-2026-10-27.md) and [source
scout](mibench-scout-2026-10-27.md).

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

The [MiBench source scout](mibench-scout-2026-10-27.md) records five source-level
exclusions and the later `stringsearch` target rejection. The latter completed
its target correctness/profile run, then failed discovery at ten calibrated
formulas (two relocation-safe) versus the fixed twelve-candidate gate. It
produced no routed baseline or candidate labels; see its [raw qualification
and diagnosis](../results/2026-10-27-mibench-stringsearch-qualification/README.md).
Continue searching for an eligible independent integer workload; the
six-family confirmatory cohort remains unestablished.

**Latest October 27 update — Ascon three-query run and paid-update bug:** the v5 release passed its pushed-source gate at `007d6593`, then the operator-relayed chat agent measured three candidates. C01: 1.019698×, +73 LUT4, 62.992 MHz (area-infeasible); C06: 1.017027×, +41 LUT4, 67.069 MHz; C02: 1.023731×, +42 LUT4, 64.620 MHz. All passed correctness; C02 is best among the three measured feasible results. Nine candidates are still censored, so there is no complete-pool oracle or heuristic comparison. The complete generated campaign is preserved as a hash-checked archive in [`results/2026-10-27-ascon-selector-chat-run-v5/`](../results/2026-10-27-ascon-selector-chat-run-v5/). A real paid-prefix audit found `_dynamic_gp` excluded all three successes because audit rows omitted `status`; it recorded zero fit time. The working source now persists success status and includes a regression test. Four focused test modules pass (30 tests), and a post-hoc 90+3-row replay confirms refit execution and the paid-prefix hash, but this is consumed-data software validation. The v5 release remains archived against commit `007d6593` and is no longer valid for further dispatch after these source changes. Treat this run as integration development, not a prospective comparative result. The next blocker is still a fresh independent workload; the disclosed Ascon pool cannot be reused to claim confirmation.

October 28 agent release validation: 84 focused provider/selector/memory/bridge tests pass. Preserved live pilot artifacts and SQL exports are in `results/2026-10-28-live-luna-memory/`; the 11-slide, 420-second presentation includes the live result and stronger heuristic caveat. No new model-quality or workload-generalization conclusion is established.
