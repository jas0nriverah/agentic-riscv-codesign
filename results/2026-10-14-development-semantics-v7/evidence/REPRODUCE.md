# Reproduce the saved V7 development evidence

This package preserves the original pre-score seal, all six feature matrices,
proof/feature ledgers, original parent approval, 18 full OOF prediction files,
18 metric files, completed fit summary and independent audits. It contains no
new model artifact, target collection or independent application test. The
saved scores describe the consumed 1,665-row development cohort and inherited
folds; one newly proved equivalence spans two folds and inherited vector
collisions remain reported.

Run from a clean checkout of the commit containing this evidence package. The
helper verifies every original repository dependency by its recorded SHA256
using a relative path map. It never modifies absolute paths inside the original
seal, plan or review. Their bytes remain unchanged.

Set `package_dir` to the directory containing `evidence-manifest.json`,
`evidence.tar.gz` and `package_v7_evidence.py` (the repository documentation gives
its relative location):

```sh
package_dir=results/2026-10-14-development-semantics-v7/evidence
python3 "$package_dir/package_v7_evidence.py" verify \
  --manifest "$package_dir/evidence-manifest.json" --repo-root "$PWD"
python3 "$package_dir/package_v7_evidence.py" restore \
  --manifest "$package_dir/evidence-manifest.json" --repo-root "$PWD" \
  --destination ../v7-restored-evidence
```

Verification and restoration use the Python standard library; they need no
Yosys, graph cache, fitting process or solver. Restoration requires a fresh
directory outside the checkout and rejects duplicate/traversing/link archive
members and changed hashes.

Independent reconstruction of all saved metrics needs NumPy. The interpreter observed immediately after the study was Python3.14.7. The
original pre-score plan sealed the five ML library versions, but did NOT record
the Python version;3.14.7 is a later observation, not a retroactive sealed claim.
The sealed libraries are NumPy2.5.4, SciPy1.18.1, scikit-learn1.9.1, XGBoost3.4.1
and joblib1.6.0; the proof audit used z3-solver4.15.4.0. Python3.13 is the distinct
CI/replay environment. A pinned replay environment can be created with:

```sh
python3.13 -m venv .venv
.venv/bin/python -m pip install -e '.[proofs]' -r requirements-research.txt
.venv/bin/python "$package_dir/package_v7_evidence.py" score \
  --restored ../v7-restored-evidence --repo-root "$PWD" \
  --output ../v7-independent-score-replay
```

The score command calls the archived independent `replay_metrics.py`. It
rechecks the exact review, seal, proof/preparation audits and every source/data
binding at the new checkout, then recomputes all 29,970 saved predictions'
errors: six views, three seeds, 1,665 rows. It checks nine-stratum macro MAE,
pooled error/bias/RMSLE, positive-only MAPE, zero errors, p95/p99/worst tails,
cap false accepts/rejects, every seed and paired contrast, and exact historical
217-column baseline replay. It reports into a new directory and performs zero
fits. A changed dependency, prediction, metric, source or review is an error.

Full training reproduction is a separate, optional development run. The original
runner deliberately binds absolute audited input/review paths; this package
does not monkeypatch its validation or transplant approval onto another seal.
For a new checkout, first run a fresh local `prepare`, review the resulting
source-bound seal and independent audit, then pass a separately authored local
parent review to `fit`:

```sh
.venv/bin/python scripts/develop_v7_semantics.py prepare \
  --output ../v7-new-development-prepared
# Obtain a new review of that exact preparation; preserve the archived review.
.venv/bin/python scripts/develop_v7_semantics.py fit \
  --prepared ../v7-new-development-prepared --review ../v7-new-parent-review.json
```

That optional run must record its Python implementation/version/build/platform
BEFORE fitting, in addition to libraries and solver. The missing original Python
version record is a reproducibility limitation; a successful3.13 saved-score
replay does not demonstrate identical retraining across Python versions.
That optional run uses the fixed original rows/folds, all six views, three seeds
and at most90 fits. It is a new timestamped preparation, not byte reproduction
of the original seal. It needs the proof solver and exact versions. The saved
score replay above is the portable, read-only reproduction of the published
completed evidence.

Archive safety/hash/restore tests are included and need no fitting or third-party
packages:

```sh
python3 "$package_dir/tests/test_archive.py" -q
```

The package additionally binds `requirements-research.txt` and `pyproject.toml`
for environment reproduction. These are package documentation dependencies; the
original study plan, sources and seal are retained verbatim.
