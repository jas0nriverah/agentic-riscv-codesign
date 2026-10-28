# Preserved incomplete Ascon augmentation ablation attempt

This directory records an incomplete software run. It wrote and sealed the
protocol and outcome-hidden predictions, then failed while aggregating the
report. No `report.json` or final manifest was produced, so this directory is
not a valid evaluation result and must not be used for model selection.

The implementation error was fixed in
`scripts/evaluate_ascon_training_augmentation.py`; the complete reproducible
analysis is preserved separately in
[`2026-10-28-ascon-training-ablation-r2`](../2026-10-28-ascon-training-ablation-r2/README.md).
The failed partial is retained unchanged except for this explanatory note.
It created no native jobs, new labels, or model release.
