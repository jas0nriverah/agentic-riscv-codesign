# Candidate evidence graph

**Status:** a small, local, read-only knowledge-graph retrieval prototype is implemented in `isaforge/agent_memory.py`. It is a typed provenance layer over already approved historical measurements. It does not replace XGBoost, the numerical hardware predictors, the four host tools, or processor evaluation. It has no live-agent comparison yet.

## Graph model

Each historical candidate is connected to its workload, normalized expression family, operator nodes, and measured result. Result nodes retain the verified speedup, LUT4 delta, minimum routed Fmax, correctness flag, device-fit flag, and source-record hash. Relations are explicit:

| Relation | Meaning |
| --- | --- |
| `measured_on` | Candidate was evaluated in this workload group |
| `belongs_to_family` | Candidate has this input/constant-normalized expression-tree shape |
| `uses_operator` | Candidate formula contains this operation |
| `has_measurement` | Candidate links to its measured result record |

For each unattempted target formula, graph retrieval finds historical candidates that share one or more operation nodes. It ranks them by Jaccard overlap of operation sets and returns the matched operators plus the graph triples linking the target query to the historical candidate, workload, and measurement. The overlap score does not use measured speedup, area, or timing. Those outcomes are shown only as historical evidence already present in the approved training history.

## Leakage and provenance rules

- Construct the graph only from the host-approved historical training rows.
- Reject the target workload group and any matching normalized expression family before indexing; repeat these checks at graph-query time.
- Keep target candidates label-free until their measurement tool is called. A target candidate can be represented by its public formula for a graph query, but no target measurement node is created early.
- Bind the graph content to a deterministic hash. Return record hashes and relation paths with every hit.
- Treat returned graph records as untrusted evidence for the LLM. The host remains authoritative for IDs, measurement charges, correctness, area, timing, and finalization.

This is an in-memory typed graph, not a graph database, graph neural network, general document RAG system, or pretrained embedding service. It adds a structure-aware retrieval mode alongside none, lexical, latent-semantic, and hybrid retrieval. It does not train another speedup model.

## Evaluation plan

First, test graph determinism, split exclusion, path provenance, and the absence of measured labels from the retrieval score. Run the existing deterministic memory-control replay to confirm the new mode leaves all selector outcomes and charges unchanged; those controls ignore retrieved context, so that replay is only a noninterference test. Then compare graph retrieval with no retrieval and lexical/semantic/hybrid retrieval on held-out workloads using the same available historical information and measurement budget. Report retrieval relevance and contamination separately from the primary endpoint: best measured feasible whole-program cycle reduction and regret to a complete measured-pool oracle.

No claim of better retrieval, LLM decisions, or processor performance follows from the implementation or unit tests. A live comparison requires an available explicitly configured model and preregistered target/workload; no API call or native job was made for this prototype.
