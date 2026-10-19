# Preserved V6 attempt: serialization check failure

This attempt stopped after one fixed ExtraTrees fit, when its immediate artifact
save/load check rejected the estimator fingerprint. No calibration or test
labels were released, and no point-prediction freeze was created.

The original whole-object hash included unused padding bytes in scikit-learn's
structured tree arrays. Independent loads of the same artifact changed those
bytes while preserving every named field. The diagnostic proof, failed artifact,
training inputs and original source snapshots remain here. Independent audit
and model snapshots use separate layouts intentionally.

The corrected runtime hashes named numeric fields, shapes, dtypes, tree state
and estimator parameters. A new input preparation is stored in
[`../2026-10-14-v6/`](../2026-10-14-v6/). Its independent audit checks identical
candidate bytes, component assignments and all numerical feature values.
Only artifact-integrity checks changed; no outcome directed the retry.

The retained `input-attempts/` directory also records an earlier input-only
preparation that was stopped before completion. Neither aborted stage is a
successful experiment or an independent accuracy result. Count the failed fit
when reporting total computational work across attempts.
