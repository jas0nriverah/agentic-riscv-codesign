# V11c: pin Spike's device-tree compiler dependency

This is an environment correction to the [failed V11b capture attempt](../results/2026-10-16-v11b-transfer-recovery/STATUS.md). It introduces no new model, workload, candidate-selection rule or target-measurement release.

Both V11b captures exited with code 1 before workload execution. Their stderr reports `Failed to run dtc: No such file or directory` and `Child dtc_output process failed`. Each raw gzip contains zero uncompressed bytes. The [independent failure audit](../results/2026-10-16-v11b-transfer-recovery/run/input-review/independent-failure-audit.json) authenticates these failures and the four unchanged historical outcomes. Original manifests, logs, empty partials and source versions remain preserved. V11b is not resumed or overwritten.

## The correction

The new runner explicitly inventories the already installed device-tree compiler, its version, executable hash and available direct dependencies. The controlled PATH includes its resolved parent directory. It continues to pass only public execution settings (`PATH`, `LANG`, `LC_ALL`, `TZ`), rather than copying the host's full environment.

The prepared dependency is DTC 1.8.1 at `/opt/homebrew/Cellar/dtc/1.8.1/bin/dtc`, SHA256 `74774b657de86b0c658c6dd14f88767af051dd16d075f722df44afb0a3b71c3d`. The existing Spike, compiler, objdump, native gzip and original ELF identities remain checked. Available direct-library hashes do not constitute a hermetic operating-system image; shared-cache and unresolved transitive dependencies remain an explicit limitation.

A separate startup preflight runs the already completed `fac` O2 ELF under this same controlled environment, without commit logging or candidate extraction. Its deadline is 60 seconds, with owned process-group cleanup and output/log limits. It must match the retained output and program-specific oracle before any new AMMUNITION or PM capture. The preflight is an infrastructure check; it does not replace the original fac outcome or add a transfer observation.

The actual [preflight receipt](../results/2026-10-16-v11c-dtc-recovery/preflight/receipt.json) records success: expected and captured output `[154, 5]`, return code 0, empty stderr, no remaining owned processes, and 0.2781 seconds including supervision/cleanup. It retains the executed runner/helper source snapshots, exact tool inventory and logs. This proves startup under that environment, not completion of the two long traces.

## Preserved experiment and release

V11c uses a fresh result root and `generated/v11-spooled-recovery/dtc-attempt-0000`. Recover AMMUNITION then PM once each, from their exact original O2 ELF bytes, with the same original inputs and complete computation ROI including all called helpers. Preserve the four earlier complete/empty outcomes byte-for-byte. Do not shorten loops, change inputs, exclude software helpers, select candidates or replace programs.

The prior finite budgets remain: one worker; 300 seconds per capture plus at most 30 seconds compressor drain; 1,800 seconds offline decode; 300 seconds full extraction/fusion; 4 GiB per raw or decoded gzip; 18 GiB for the attempt including metadata; 26 GiB initially free, 18 GiB before the second program and an 8 GiB free-space floor. Resource/provenance breaches stop the cohort; an ordinary per-program deadline is retained as that program's failed outcome, with no automatic retry or extension. Failed/partial streams cannot supply candidates. Native compression, strict full-stream validation, unchanged extraction/fusion and independent evidence replay remain required.

The same [V11b-E1 endpoint adoption](../results/2026-10-16-v11b-transfer-recovery/endpoint-adoption.json) applies. Original equal-all-program MAE stays undefined because recursion has no eligible formulas. The amended error endpoint requires complete outcomes for all six programs and a nonempty eligible set in each of five families. V9 and V6 remain the same frozen predictors; no fitting, adaptation, prediction or target label is authorized by this environment amendment.

Before the two captures, freeze the new runner/auditor, dependency inventory, successful preflight, original inputs and preserved failure evidence, then issue a separate input-only release. Features and predictions require a complete audited input package. The later complete-pool synthesis budget and prediction seal remain separate, prospective stages. The failure was an infrastructure problem observed before any new outcomes or labels, not a reason to change the scientific comparison.
