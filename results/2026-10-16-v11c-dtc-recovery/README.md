# V11c: complete transfer-input collection; independent replay pending

The fixed input-only recovery completed at **2026-10-16 04:50:46 UTC**, with no collector failures. Both original missing programs were captured once, decoded through EOF, checked against their retained outputs/oracles, and extracted with the unchanged full ROI and fusion policy. The four previous outcomes were reused unchanged. This is **input collection evidence**, not a new ML evaluation or model improvement.

| Program | Outcome | Canonical formulas per program | New traced ROI instructions |
|---|---|---:|---:|
| AMMUNITION | Recovered, collector complete | 129 | 166,490,305 |
| audiobeam | Reused complete | 169 | — |
| PM | Recovered, collector complete | 74 | 91,723,058 |
| fmref | Reused complete | 148 | — |
| fac | Reused complete | 1 | — |
| recursion | Reused empty | 0 | — |

All six outcomes and five nonempty algorithm families are present: **521 program/formula memberships, 327 unique canonical originals**. Both recovered traces have zero unknown instructions. Capture/compressor wall times were 77.2383 seconds for AMMUNITION and 42.0906 seconds for PM. These are collection timings, not processor-performance measurements. Both native producers/compressors exited zero and all owned worker cleanup completed cleanly.

Fusion checks passed for 381 AMMUNITION occurrences and 168 PM occurrences, with 16 vectors each and zero opaque skips. The resulting 8,784 individual and 8,096 joint/block comparisons are randomized software-equivalence checks, not formal RTL proofs or modified-processor execution. Original program selfchecks and retained O0/O2 outputs remain part of the input contract.

A separate independent raw-stream, decoder, ELF, extraction and fusion replay **is running; its result is not yet admitted**. Features, frozen-model predictions, area labels and fits all remain zero. The original equal-all-program MAE stays undefined because recursion has no formulas. The adopted [V11b-E1 endpoint](../../docs/v11b-transfer-protocol.md) can only be evaluated after independent input admission, a complete prediction freeze and complete-pool measurements.

## Evidence and reproduction boundary

- [Completion receipt](completion.json), [six outcomes](run/attempt-0000/programs.json), [full memberships](run/attempt-0000/completed-rows.json).
- [Evidence manifest](run/attempt-0000/evidence-manifest.json): 162 files, with 158 compact members in [metadata.zip](run/attempt-0000/metadata.zip).
- [Input audit](input-review/independent-input-audit.json), [preflight](preflight/receipt.json), [input-only release](recovery-approval.json), [environment amendment](../../docs/v11c-environment-amendment.md).

Four large raw/decoded gzip payloads remain at their manifest paths under local `generated/v11-spooled-recovery/dtc-attempt-0000/`. Their total is 3,830,104,615 bytes; each has an exact SHA256 and byte count in the committed manifest. They are not duplicated in the metadata ZIP or committed to Git. A clean clone can inspect compact records, but full raw replay also requires those exact payloads and the original historical evidence dependencies. This snapshot does not claim a self-contained raw replay from Git alone.

With those dependencies available, the read-only replay is:

```sh
.venv/bin/python scripts/audit_v11c_recovery.py \
  --root results/2026-10-16-v11c-dtc-recovery \
  --action results --output /tmp/v11c-independent-audit.json
```

Use a fresh output path. The audit starts no native simulation, feature extraction, model inference or synthesis. Its parser/extractor/oracle reuse and other independence limits are reported explicitly.
