# tiny-regex selector relay startup failure

The first selector launch followed the pushed r3 release at commit
`1b8dcb2936a10cef1546525f439d191afda93636`. It was started without an
interactive terminal. The bridge wrote a public request, then its stdin reached
EOF before the current Codex model could return an action. The host finalized
to its safe baseline fallback.

This produced **zero successful provider responses, zero selector tool calls,
zero candidate measurements, and zero target labels revealed**. The one
`model_error` event is bridge accounting and must not be described as a model
decision, an LLM evaluation, or an agent selection trial. The preserved raw
ledger, public request, report, observability database, release receipt, and
checksums are in
[`results/2026-10-28-tiny-regex-c-selector-launch-failure-r1/`](../results/2026-10-28-tiny-regex-c-selector-launch-failure-r1/).

The startup issue was corrected by freezing a new r5 protocol and r2 run path,
then launching the bridge with an interactive terminal. The candidate pool,
historical cohort, models, policies, measurement budgets, and evaluation rules
remain unchanged. The original r3 release is preserved, never retried, and
remains a zero-measurement harness failure. If the amended launch also fails
before a model response, stop and report it rather than retrying.
