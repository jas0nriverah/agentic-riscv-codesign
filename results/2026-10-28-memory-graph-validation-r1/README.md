# Memory and graph noninterference validation — October 28, 2026

This is a consumed-data software replay, not a live-agent or processor experiment. It adds no candidate labels and ran no native hardware jobs.

## Command

```sh
../work/audit-venv/bin/python scripts/evaluate_agent_memory.py \
  --output results/2026-10-28-memory-graph-validation-r1
```

## Results

| Retrieval mode | Trajectories | Endpoints | Retrieval events | All controls match | LLM calls | New native jobs |
| --- | ---: | ---: | ---: | --- | ---: | ---: |
| none | 10 | 30 | 0 | yes | 0 | 0 |
| lexical | 10 | 30 | 58 | yes | 0 | 0 |
| semantic (TF-IDF/SVD) | 10 | 30 | 58 | yes | 0 | 0 |
| hybrid | 10 | 30 | 58 | yes | 0 | 0 |
| knowledge graph | 10 | 30 | 58 | yes | 0 | 0 |
| **Total** | **50** | **150** | **232** | **yes** | **0** | **0** |

All five modes preserve their archived SHA-256 control outcomes. This validates that adding retrieval instrumentation does not change these deterministic policies. The controls intentionally ignore retrieved context, so this is not a retrieval-relevance test, LLM test, model-quality test, or measured-performance improvement. Retrieval comparisons remain one live consumed-data episode per arm, where the non-retrieval heuristics reach the same pool oracle in fewer measurements.

The sealed [`summary.json`](summary.json), hash sidecar, and per-mode SQLite exports are the machine-readable evidence. Source digests are in the summary. The agent memory unit suite separately passes 24 tests covering graph paths, leakage rejection, empty-roster finalization, and target-roster stability.
