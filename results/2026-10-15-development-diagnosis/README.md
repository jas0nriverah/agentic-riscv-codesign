# Consumed-V8 training-support diagnosis

This is a read-only development diagnosis of the original 1,665 training rows
and consumed V8 outcomes. It performed **zero fits, zero new measurements and
zero feature extractions**. The frozen models, points, feature vectors and V8
evidence remain unchanged. The 48-circuit coverage experiment is a proposal;
none of its proposed labels or its augmented forest has been created.

Read [report.txt](report.txt) for findings and
[the direction note](../../docs/v9-training-coverage-direction.md) for the next
experiment. `diagnosis-summary.json` retains every query/model summary, nearest
examples and leading training influences. `feature-snapshots.json` contains the
existing cost-feature values. `proposed-experiment-inputs.json` specifies all 48
proposed original formulas and the outstanding pre-release checks.

The full diagnostic contains all **10,500 tree-leaf records**: seven queries,
five frozen 300-tree forests, original training membership and final path
splits. It is retained only as `diagnosis.json.gz`, approximately 0.85 MB.
`manifest.json` gives the exact restored byte count and SHA256 for the original
approximately 12 MB JSON. No uncompressed duplicate is tracked.

## Verify the retained package

From the repository root:

```sh
python3 results/2026-10-15-development-diagnosis/verify_package.py
```

The standard-library verifier checks package members, the exact gzip restoration,
the diagnosis/source identity, and all repository-relative input hashes.
`source-input-hashes.json` retains model, schema, points, original training,
consumed features/labels and runtime source identities. The full diagnostic also
keeps the original observed absolute paths; those paths are descriptive, while
the relative hash ledger supports another checkout.

## Replay the diagnosis without creating a tracked 12 MB file

Use the repository Python environment containing the recorded ML versions
(NumPy 2.5.4, scikit-learn 1.9.1 and joblib 1.6.0). The run also imports the
unchanged model classes and their dependencies from this checkout. Frozen
artifacts/features must first be restored as described by
[V8 reproduction](../../docs/v8-application-results.md).

```sh
task_replay_dir="$(mktemp -d /tmp/v9-diagnosis.XXXXXX)"
cp -R results/2026-10-15-development-diagnosis/. "$task_replay_dir/"
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python \
  "$task_replay_dir/diagnose_support.py" \
  --root "$PWD/results/2026-10-15-v8-application-transfer" \
  --output "$task_replay_dir/diagnosis.json"
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python \
  "$task_replay_dir/render_report.py"
```

Run from the repository root so the portable scripts can discover its model
classes. `diagnose_support.py` imports the retained independent unsigned oracle
from `audit.py`, blocks ExtraTrees/DecisionTree fit methods, loads only frozen
estimators and sealed feature matrices, verifies leaf-target reconstruction,
and checks every observed input digest before returning. It never invokes a
feature extractor, normalizer, solver, simulator, synthesizer or target collector.

`render_report.py` produces the human report, slim summary, feature snapshots,
input proposal and compressed full JSON in the temporary replay directory. Its
query points, leaf membership, neighbors and influence weights should match the
retained evidence; observed absolute input paths can differ in another checkout.
The original execution log is `diagnosis-run.log`.

Range-scaled distances and tree influence weights describe the frozen forest;
they are not learned metrics, causal effects or calibrated probabilities.
Vector collisions do not establish functional equivalence. V8 improvements after
any tuning would be development results and require a newly reserved cohort for
a later transfer claim.
