# V11d frozen V6/V9 comparison

Status: all 327 feature extractions and the 806-channel raw feature replay passed; evidence packaging remains in progress. Predictions and fresh target measurements have not started. All **327 original circuits and 521 program/circuit memberships** are retained. This is the fixed V6-versus-V9 comparison from the prospective V11b-E1 protocol, with no model fitting or calibration.

[Amendment](amendment.json) preserves the earlier preclaim launch failure and permits only the exact 36 recovery metadata files whose live bytes match the pinned archive and manifest. Numeric feature/inference workers are unchanged. [Feature plan](feature-plan.json) and [release](feature-approval.json) bind the source, input pool, model artifacts, tools and limits; full Git/provenance validation passed before launch.

The run permits two workers, up to 327 candidate extractions (at most 981 cold graph channels), 360 seconds per worker and a 4 GiB total feature workspace. All rows must complete and pass raw feature replay before a separately released inference stage. Failures remain recorded. No target labels or fits are permitted in this runner.

The inputs and initial failure are documented in [full-pool accounting](../2026-10-16-v11-model-inputs/README.md) and [preserved predecessor](../2026-10-16-v11-frozen-predictions/README.md). Packaging currently incurs repeated whole-directory scans; no completion is admitted before that gate passes. There is no fresh accuracy result yet; subsequent target measurements and independent audit are required. The complete local raw payload/runtime dependency boundary still applies.
