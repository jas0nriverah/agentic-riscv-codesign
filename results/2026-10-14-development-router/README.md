# Fixed input-only router: development analysis

[Design and findings](design-findings.md) report both fixed variants and all five inherited seeds on the original 1,665 fitting rows. This uses existing out-of-fold predictions: no new fits, calibration, test or external outcomes. A 0.876% development gain over full semantics is small and does not repair tail error. No deployable artifact or bound is promoted.

Run `python scripts/develop_v6_targeted.py --output /absolute/path/outside/repository/new-run` using the retained seed-diagnostics snapshot. Exact inputs/source hashes, the fixed plan and all ten router prediction lists are retained here.
