# Independent external audit

`pre-release.json` verifies all six artifacts, every output field, copied feature caches, outcome-metadata invariance and the committed freeze before label release. `raw-provenance.json` recounts all 79 original mapped netlists; `raw-relocation.json` repeats scoring in a fresh independent Git clone after archive restore. `summary.json` combines these phases.

`external-v5-input-audit.json` and `external-v5-final-audit.json` independently reconstruct identity, all five overlap keys, family weights, every metric/cap/error, and bound/OOD diagnostics. The numerical audit is independent of the production scorer. Its script imports the retained `audit_v5_statistics.py` helper. Audit artifacts record original absolute execution paths; the production score replay is portable and is the supported CI path. Audits do not fit models or collect target labels.
