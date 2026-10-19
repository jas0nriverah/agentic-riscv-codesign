# Frozen external application transfer, 2026-10-14

See [results and interpretation](../../docs/external-v5-results.md),
[evaluation protocol](../../docs/external-v5-evaluation.md), and
[collection protocol](../../docs/external-v5-protocol.md).

- `freeze.json`, `freeze-start.json`, `candidates.json`, `features.json`, `overlap.json`, `predictions/`: premeasurement evidence committed at `0db749ab0a4b0ba769d9b0bbd42bbfdef00343e9`.
- `collection/`: pinned source, original controller snapshot, program inputs, ELF files and checks.
- `label-approval.json`, `label-release.json`: later explicit review and measurement release.
- `measurements/`: complete 79 unique original targets expanded to 80 program rows, verification and attempt evidence.
- `evaluation.json`: all six predictors, fixed primary comparison, novel subsets, caps, bounds and OOD diagnostics.
- `raw-evidence.zip`, `raw-evidence.json`: portable hash-checked 560-file native evidence archive; restore with `python scripts/archive_external_v5.py restore`.
- `audit/`: independent pre-release replay, metrics, netlist recount and fresh-clone replay.

The fixed MasterRTL adaptation wins observed primary MAE. Full V5 beats equally tuned SOG by 4.31%, not the 59.01% synthetic gain. Both novelty subsets lack Dijkstra coverage; no complete novel-family macro can be claimed. Never edit frozen sources or evidence to repair this outcome.
