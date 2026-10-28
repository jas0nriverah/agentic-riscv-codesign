# Preserved relay startup failure (r1)

The first r3 release reached the interactive bridge, wrote a public request, then received EOF because the process had no interactive stdin. The host safely finalized to baseline. This is a harness startup failure, not an LLM decision. It produced zero successful model responses, zero tool calls, zero candidate measurements, and zero target labels.

The original `agent/` evidence directory and zero-attempt release receipt are preserved byte-for-byte. See `failure-summary.json` and the nested checksums for the exact recorded state. A future launch requires a new committed and pushed zero-label protocol; this r1 release is not retried.
