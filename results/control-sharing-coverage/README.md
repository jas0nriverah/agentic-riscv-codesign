# Control/sharing coverage: development failure and incomplete fresh cohort

**No candidate is selected or promoted.** The one fixed coverage intervention accepts all 62 required feasible cases, including the consumed sharing 125 failure, but fails 4/38 protected rejection targets and full-panel FA gates. Fresh validation is **incomplete**: only 16/55 area labels finished before the frozen wall deadline. No fresh population metrics or partial-subset success claims are produced. The goal remains unmet.

## Frozen intervention and retained evidence

One native multioutput ExtraTrees classifier uses the exact frozen 233 columns,300 trees, seed 2026101401, one thread, equal weights and probability≥0.5 rule. Its ordered 1,921 rows are the unchanged frozen 1,889 prefix plus 32 genuinely new training circuits. The prior `feasibility_augmented` model is reused with zero refits. No consumed evaluation labels are fitted; no descriptor, threshold, seed or synthesis-pass change is made.

The 32 inputs comprise 16 both-input AND-control and 16 shared-AND data/post-add/outer contrasts, with full/narrow widths and low/wide masks. Before freezing, two unmeasured challenge families with 16 hardware-family overlaps were revised; training 32/fixed 48 stayed byte-identical. All rejected drafts and the stronger low-bit/input-renaming family review are retained. Final joint 32+96 novelty passes against 11,288 historical formulas/aliases.

Retained gates cover 26 panels (1,113 metric rows/1,073 circuit records/40 duplicated shared controls),33 named groups,62 acceptances and 38 rejections. Existing six accuracy/tail comparators remain unchanged. The latest classifier's validated general 32/legacy 8 gains are additionally protected only on those populations; its unsafe active 8 is not an added accuracy comparator. The [analytical feasibility audit](analytical-feasibility-review.json) shows why correct cap snapping there cannot preserve its unsafe 2.0 MAE (minimum 5.9054), without removing any existing gate.

All per-cap FA≤release/FR≤signed and zero-new-case gates remain separate at 32/64/128. Positive MAPE is 100×mean(abs(actual−prediction)/actual) on positive targets; zero targets remain in MAE/cap/tail. Inference still starts from release and only selects a signed-supported physical cap; signed≤candidate≤release bounds leave inherited baseline limitations visible.

## Measured training coverage is not adverse-class coverage

All 32 training labels and 68,736 original RTL comparisons complete. Targets span 37–261 LUT4;13 exceed 128. The postmeasurement independent audit precedes the single parent-authorized fit, whose full model stage takes 3.19 seconds. All receipt bindings and measured target files are checked at runtime.

| Consumed target | New exact 16-descriptor matches | Measured new costs | Meaning |
|---|---:|---|---|
| Shared-AND actual 125 |2|125,127|Positive class support; repaired|
| Unsafe actual 129/130/129 profile |2|128,125|Both feasible; not unsafe class support|

These are local descriptor matches, not identical 233 vectors or cost-transfer proofs. The profile bins were covered, but they did not provide the adverse cost/class evidence needed for the three unsafe cases. No labels were replaced or extra fit tried after this finding.

## Development outcome

All 62 required acceptances pass, but only 34/38 required rejections pass. The sharing 125 prediction changes 130.57667→128. Latest passing general/legacy accuracy gains remain preserved. Other retained panel/subgroup gates fail, so the model is diagnostic only.

| Required rejection failure | Old classifier P 128 | New P 128 | New prediction |
|---|---:|---:|---:|
| Actual 157, shared AND with outer OR |.263333|.536667|128|
| Actual 129, both-input AND control |.873333|.933333|128|
| Actual 130, same control family |.713333|.873333|128|
| Actual 129, same control family |.633333|.650000|128|

The full-panel audit additionally catches three previously safe cases outside that explicit rejection inventory: actual 160 (consumed-ninth-general 0),157 and 159 (consumed-tenth-unsupported 2/4). Therefore there are **seven unique FA 128 mistakes versus release**: four newly introduced versus the frozen classifier (160/157/159/157), plus the three persistent 129/130/129 mistakes. No new FR versus signed is introduced. All seven identities/formulas/probabilities are in [supplemental development diagnostics](supplemental-development-diagnostics.json); the four inventory failures and profile evidence are in [failure diagnostics](failure-diagnostics.json). Counts are circuit-budget events, not pooled accuracy claims.

## Fresh cohort: missing primary outcome

Joint features complete 128/128: all 32 training vectors are unique with no historical matches; fresh 96 has no history/training matches. One within-pool descriptor duplicate[33,78] is retained under the frozen mandatory-key selection rule. There is no replacement or new novelty rule after features.

All 96 probabilities are frozen before labels. Prospective activity passes: seven new cap 128 actions across two templates, one legacy 64 veto and one sharing 128 veto. These are prediction-defined coverage checks, not correct decisions. Selected 55 is fixed 48 plus 7 actions; conditional full shares the same eight general controls.

The fresh original RTL proof completes 55 formulas/118,140 comparisons. Area-label workers then reach the frozen stage wall deadline:16 complete (selected indices 0–15), two time out (16/17),37 are unattempted. Only first 16 general labels exist. No complete-population score is called and `fresh-metrics.json` remains absent.

| Primary population | Requested | Completed labels | Outcome |
|---|---:|---:|---|
| General |32|16|Not evaluable|
| Sharing |8|0|Not evaluable|
| Legacy |8|0|Not evaluable|
| Conditional full |15|0|Not evaluable|
| Active only |7|0|Not evaluable|

All 55 statuses,96 pool points and partial raw evidence remain retained. Shared controls are disclosed; populations are not pooled or treated as independent. The completed 16 labels are descriptive evidence only. No MAE/MAPE/FA/FR rates or denominators for a complete fresh population can be inferred from them.

## Resource and integrity outcome

Native total is 288.6873995 summed worker-process seconds/300, with 152.0264791 seconds of stage wall time and peak two workers. There are 180 launched processes versus 217 scheduled/status records (37 never launch). The final phase stops at its 64.605877-second wall allocation; cleanup/status completion reaches 64.690923 seconds. The unused 11.3126 summed-second margin is not permission to retry or extend this frozen stage.

Totals:32 training+16 fresh measured circuits,87 original RTL-proved formulas/186,876 comparisons,2,873 archive members across both packs. All 1,008 previous scientific artifacts remain unchanged. Parent full suite passes 578 tests+40 subtests; cached CLI reproduces 55×13 predictions. No task-owned Yosys/ABC/worker descendants remain, and no retries or post-label changes occur.

The independent [core audit](audit.json) passes integrity while recording scientific failure/incomplete validation. [Incomplete outcome](incomplete-outcome.json) explicitly marks all five populations not_evaluable; [protocol](protocol.json), [preregistration](preregistration.md), [profile audit](measurement-input-profile-audit.json) and [development metrics](development-metrics.json) retain the complete trail. This is finite synthetic iCE40 LUT4 evidence, not calibrated safety or CPU speedup.

Read-only model replay verifies retained/frozen inference and reports `fresh_metrics_replayed=false`; it does not create a missing fresh score.

```sh
.venv/bin/python scripts/learn_control_sharing_coverage.py replay
.venv/bin/python scripts/audit_control_sharing_coverage.py final
```
