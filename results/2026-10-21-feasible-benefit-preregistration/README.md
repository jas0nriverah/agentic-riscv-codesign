# Pre-measurement ML checkpoint

Frozen before the six disjoint SHA256 candidate attempts. The native baseline was authenticated immediately before and after fitting, with zero candidate ledgers both times. The complete source-bound JSON models and predictions for eleven policies are in `selection/`; baseline inputs, partition, pool and native evaluation protocol are under `baseline/`. The later campaign provenance records the Git checkpoint.

This is fresh-candidate evidence on consumed SHA256 source/input, not unseen-workload generalization. All 27 available non-SHA successful labels and three historical failures are charged separately. All six old SHA labels are excluded from fitting but retained as development cost. Related-family exclusions are identical for all learned policies.

The preparation command was `python scripts/freeze_disjoint_sha256.py`; it requires the unmeasured native pool and refuses reuse after candidate attempts. For prediction reproduction after collection, use `python -m isaforge.feasible_benefit_experiment freeze` with the sealed `inputs/` files, area caps32/64/128, fixed five seeds, calibration5.095776124944678seconds, `--target-labels-observed 0` and `--scope "consumed-source fresh-candidate-pool"`. That refit reproduces the original predictions, not a new prospective claim.
