# Held-out structural coverage of agent memory retrieval

This is a retrospective consumed-data diagnostic over the existing measured-label corpus. It
scores the structural operator-type coverage of the top three retrieved formula records. The
target query contains only candidate identity, workload group, and formula. Every target workload
and matching expression family is excluded from the historical index before retrieval. Target
speedup, area, timing, and correctness labels are not used in the score.

The result measures **structural support**, not semantic relevance, historical-outcome usefulness,
prediction accuracy, LLM decision quality, or improved hardware performance. The knowledge graph
uses operator overlap in its retrieval rule, so a high coverage score is not independent evidence
that graph retrieval improves selection. No model was trained and no LLM or target hardware was run.

See the sealed `protocol.json` and `report.json` for exact source hashes, group-level metrics, and
per-candidate retrieved IDs. The report records zero new labels, zero native jobs, and zero LLM calls.

| Mode | Workload-macro coverage@3 | Candidate-weighted coverage@3 | Empty-hit fraction |
| --- | ---: | ---: | ---: |
| none | 0.0000 | 0.0000 | 1.0000 |
| lexical | 0.9103 | 0.8948 | 0.0000 |
| semantic | 0.8765 | 0.8607 | 0.0000 |
| hybrid | 0.9041 | 0.8846 | 0.0000 |
| knowledge_graph | 0.9301 | 0.9242 | 0.0000 |
