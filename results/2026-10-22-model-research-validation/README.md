# Model/research diagnosis validation

Validation for the arithmetic-only [diagnosis](../2026-10-22-model-research-diagnosis/README.md) and October 22 primary-method review. This does not introduce a fitted model, native evaluation, policy trajectory or prospective test result.

Commands use the pinned Python 3.12 environment and `requirements-speedup.txt`.

| Check | Outcome |
| --- | --- |
| `make test PYTHON=../work/audit-venv/bin/python` | **3,382 passed, 179 passing subtests, one unchanged legacy failure**, in 195.16 seconds. [Full log](full-suite.log). |
| `make reproduce PYTHON=../work/audit-venv/bin/python` | **Pass:** all six historical metrics match; 192 candidates and 10,000 bootstrap replicates reproduce. [Log](historical-reproduction.log). This is a regression check of historical cost studies, not a new isolated study. |
| `python -m pytest -q tests/test_current_model_diagnosis.py` on the final source | **5 passed** in 2.11 seconds. [Final log](final-focused-tests.log); [earlier portability run](focused-tests.log) also passes. Full integration forbids GP fitting/prediction and forces all twelve generated discovery paths absent. The archive test retains original JSON bytes and rejects nonregular entries. |
| Independent `diagnose_current_models.py --output generated/reproduction/model-research-diagnosis-final-review` | **Pass:** all 39 artifacts/manifest entries byte-identical to the committed diagnosis; all 270 archived first choices exact. [Final log](final-replay.log), [earlier archive replay](archive-replay.log), [verification receipt](verification.json). |
| Bound inputs/sources and local links | **Pass:** 90 input bindings, 11 source bindings, twelve original discovery snapshots and active-document local links checked; counts are in the receipt. |

The full suite ran on the initial diagnostic draft. The later portability change affects only the new diagnostic reader and was checked with the complete five-test focused suite plus an independent byte-exact archive replay. A final wording correction clarifies that old/expanded training cohorts each exclude the target/families; the cohorts overlap each other. The final source was independently replayed and focused-tested again. All twelve numerical/data files are unchanged from the initial draft; archive provenance and original-byte snapshots were added. The first draft remains intact locally at `generated/model-research-diagnosis-first-draft-2026-10-22`; [its initial replay log](diagnosis-replay.log) is retained. No historical model/runtime/evidence source was changed.

The unchanged full-suite failure is `tests/test_capture_v11_spooled.py::test_blocked_pipe_or_compressor_drain_has_finite_cleanup[pipe]`, already recorded in earlier validations. No process-cleanup fix or all-green full-suite result is claimed. The warning concerns an intentional duplicate ZIP-entry fixture.

The new diagnosis makes **zero scientific model fits, zero new predictions, zero native jobs and zero variant trajectories**. Full-suite/historical reproduction may exercise existing fitting code as regression tests; they do not create a new research model or a prospective result. The duration-free first choice is consumed-data arithmetic, not a fully evaluated policy. No source was reclassified as untouched, and no calibrated-confidence, total-cost saving or ML-superiority claim is made.
