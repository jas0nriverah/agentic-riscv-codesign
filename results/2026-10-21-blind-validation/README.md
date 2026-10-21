# Blind campaign validation

Prelabel full `make test`:3,223 passes,179 passing subtests,one pending-campaign integration skip,one intentional ZIP fixture warning and the previously documented intermittent legacy process-cleanup failure. The focused rerun passes110tests and skipsone, reproducing the same legacy pipe-cleanup failure. All109new focused tests pass. No legacy source was changed and no cleanup fix is claimed.

All three public baselines, complete model/source/package/cohort bindings and zero-candidate-attempt gates authenticate before measurement. The fixed per-target fitting cohorts contain44/33/29candidates acrossallsevenhistorical sources after related-family exclusions. Candidate results and final replay/export validation will be appended as separate records after the pushed checkpoint.
