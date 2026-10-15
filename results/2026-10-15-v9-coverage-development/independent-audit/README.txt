Independent V9 coverage raw audit: PASS on first released-data audit run.

Seven synthetic tests pass. Reauthenticated corruptions of expected outputs,
input vectors, original RTL and resource counts are rejected independently of
the archive's own hashes.

Actual result:
  343 raw ZIP members authenticated
  103,104 expected outputs independently recomputed (48 x 2148)
  48 original RTL byte identities checked
  48 mapped netlists recounted for LUT4 and carry resources
  zero mismatches; LUT4 range 6..389; no zero-LUT circuits

The audit imports only Python's standard library and unsigned_oracle.py, an
unchanged copy of the independent V8 audit source. It imports no production
model, parser, evaluator, RTL generator or collector. A separate restricted RTL
renderer covers exactly the fixed V9 grammar. No model fit, feature extraction,
native RTL execution, synthesis or target collection occurs in this audit.

The retained readiness record binds the source and input hashes before this
audit's first target read. Collection had already completed by that readiness
timestamp; it does not claim to predate target release. The audit source was
unchanged between readiness and the successful target audit. No target values
were read while implementing the audit or running its synthetic tests.

Run synthetic checks from this directory:
  python3 -m unittest -v test_audit_v9_raw

Replay without overwriting retained evidence:
  python3 audit_v9_raw.py --root .. --released \
    --readiness audit-readiness.json --output /tmp/v9-raw-audit-replay.json

The replay requires the frozen preparation files and source/artifact bindings
plus the complete portable measurement archive in the parent result directory.
It never restores or executes archived code. Explicit --released is required
before target I/O. Output paths are created exclusively and cannot overwrite
earlier audit results.

raw-audit.json retains the full recount; first-released-run.log is the first
actual audit output. audit-readiness.json binds the exact source, inputs and
expected original RTL hashes. manifest.json hashes this independent package.
Logs may require git add -f under this repository's ignore rules.

The unsigned32 oracle recomputes the archived expectations; authenticated
successful runtime logs connect those expectations to the original collected
RTL checks. This is sampled verification, not universal equivalence, and does
not independently rerun Verilator or Yosys.
