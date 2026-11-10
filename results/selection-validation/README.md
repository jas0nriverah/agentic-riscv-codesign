# Fresh validation of selected features

**The development improvement did not transfer. Keep the existing 217-feature model.** The selected candidate loses accuracy and adds hardware-budget mistakes on this new synthetic cohort. No model is promoted, and these 40 labels were not used to retrain it.

## Results

| Predictor | MAE ↓, LUT4 | MAPE ↓ | Worst underprediction ↓, LUT4 |
| --- | ---: | ---: | ---: |
| Fixed 217 | **15.4586** | **14.09%** | **52.15** |
| All 336 | 17.5690 | 16.36% | 59.48 |
| Selected 128 | 16.9423 | 15.56% | 56.05 |

Selected128 increases MAE **9.60%** and MAPE **1.48 percentage points** relative to217. It improves only one of five template MAEs. All 40 circuits have positive area, so MAPE includes every case. Five equally sized templates make pooled MAE equal-template MAE.

| LUT4 cap | 217 false accepts | 128 false accepts | 217 false rejects | 128 false rejects |
| --- | ---: | ---: | ---: | ---: |
| 32 | 0 | 0 | **7** | 8 |
| 64 | **6** | 7 | 0 | 0 |
| 128 | **0** | 1 | 0 | 0 |

A false accept predicts a circuit fits when its measured area exceeds the cap. A false reject excludes a measured-feasible circuit. Neither error count may increase under the frozen success rule; both accuracy and budget criteria fail. These are empirical point decisions, not calibrated guarantees. The refitted 217 forest exactly matches the deployed base tree state and all 40 frozen predictions; see the [equality receipt](base-equality-receipt.json). [All metrics and template results](metrics.json).

## Prospective procedure

1. Declare 40 formulas across five templates: Boolean/add/shift, Boolean/subtract/shift, signed comparison mixtures, masked variable shifts, and constant-product mixtures.
2. Screen against 8,706 recovered historical formulas and their recorded normalization identities. No match was found under the implemented identity rules; this is not exhaustive semantic equivalence checking.
3. Freeze the input set and protocol. The auditor detected a feature-column ordering mismatch before native work. A [pre-native amendment](pre-native-amendment.json) records the correction while preserving the original plan and cohort.
4. Finish [selection stability](../selection-stability/README.md) and freeze the full-data models. Extract label-free features, reorder by exact feature names, and freeze all predictions **before** fresh target measurement.
5. Verify original RTL on **85,920 sampled/boundary comparisons**, then synthesize all 40 circuits with the recorded Yosys iCE40 flow. All cases pass; no failures, retries or replacements were removed.

This is fresh synthetic transfer, not independent application-family or full-CPU validation. The templates were manually specified after prior development work, and their eight members are related. Novelty screening covers recoverable inventories and known sufficient identities only. LUT4 counts do not measure carry use, timing, power or integrated processor cost.

## Decision and next experiment

The repeated-seed development gain is real within that development procedure, but it is insufficient evidence for deployment. On this panel, masked variable shifts have the largest template MAE (28.46 LUT4 for217;31.76 for selected128), followed by constant-product mixtures. Those weaknesses motivate training-coverage and representation diagnosis rather than another search over subset sizes.

Keep both candidates frozen. The next model revision should use an explicitly separated development set and a new untouched evaluation cohort; these 40 circuits are now consumed evidence. Fix the accuracy and per-cap decision criteria before training. Do not tune a threshold on these labels and call it independent validation. Promotion requires passing both the stability and fresh-validation criteria; neither condition is relaxed after seeing results.

## Compute and replay

Native extraction, verification and synthesis completed in **47.94 seconds**, with at most two workers, zero fits and a 600-second cap. Full raw evidence is retained as a compact [archive](raw-evidence.zip) with a [member hash manifest](raw-evidence-manifest.json). Rebuildable compiler intermediates are listed separately; source, vectors, logs and mapped netlists are retained.

```sh
python scripts/replay_selection_validation.py replay
```

This replays retained evidence without native jobs or training. Use the pinned Python dependencies; it is not a standard-library-only command. [Protocol](plan.json) · [Prediction freeze](point-freeze.json) · [Predictions](predictions.json) · [Measured labels](labels.json) · [Independent audit](audit.json).

Repository validation: 415 tests and 40 subtests passed; all three feature-study evidence replays pass without new fits.

The independent audit replays all 120 forest predictions, checks 1,144 archived members, recounts mapped LUT/carry resources and verifies all 85,920 saved RV32 oracle values. Run `.venv/bin/python scripts/audit_selection_validation.py` for that audit without new fits or native synthesis.
