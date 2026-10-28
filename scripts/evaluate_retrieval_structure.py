#!/usr/bin/env python3
"""Score held-out structural operator coverage for ISAForge memory retrieval.

This diagnostic measures formula-operator support only. It does not score
semantic relevance, hardware prediction, LLM decisions, or selection quality.
Target outcomes are stripped before evaluation; whole workload groups and
matching expression families are excluded from the retrieval index.
"""
from __future__ import annotations

import argparse
import importlib.metadata
import statistics
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from isaforge import codesign as c
from isaforge.agent_memory import HistoricalMemory, MODES, _operators
from isaforge.speedup_corpus import family

CORPUS = ROOT / "results/2026-10-26-lift-selection-corpus/corpus.json"
TOP_K = 3
SCHEMA = "isaforge-retrieval-structural-coverage-v1"
SOURCE_FILES = (
    "scripts/evaluate_retrieval_structure.py",
    "isaforge/agent_memory.py",
    "isaforge/features.py",
    "isaforge/speedup_corpus.py",
)


def operator_coverage(target_formula: str, hits: list[dict]) -> dict:
    """Fraction of target operator types present in the retrieved top-k rows."""
    target_ops = _operators(target_formula)
    if not target_ops:
        return {"target_operator_count": 0, "covered_operator_count": 0,
                "coverage_at_k": None, "covered_operator_types": []}
    hit_ops = set()
    for hit in hits:
        hit_ops.update(_operators(hit["record"]["formula"]))
    covered = sorted(target_ops & hit_ops)
    return {"target_operator_count": len(target_ops),
            "covered_operator_count": len(covered),
            "coverage_at_k": len(covered) / len(target_ops),
            "covered_operator_types": covered}


def evaluate_rows(rows: list[dict], *, target_groups: list[str] | None = None) -> dict:
    """Evaluate each target formula using only its public identity and syntax."""
    if not isinstance(rows, list) or not rows:
        raise ValueError("A nonempty measured corpus is required")
    if len({row.get("candidate_id") for row in rows}) != len(rows):
        raise ValueError("Corpus candidate IDs must be unique")
    all_groups = sorted({row.get("workload_group") for row in rows})
    if any(not isinstance(group, str) or not group for group in all_groups):
        raise ValueError("Each corpus row requires a workload_group")
    selected_groups = all_groups if target_groups is None else sorted(set(target_groups))
    if not selected_groups or not set(selected_groups) <= set(all_groups):
        raise ValueError("Requested target groups must exist in the corpus")

    score_rows = []
    group_summaries = []
    for group in selected_groups:
        # The retrieval query/scoring side receives only IDs, group, and AST text.
        targets = [{key: row[key] for key in ("candidate_id", "workload_group", "formula")}
                   for row in rows if row["workload_group"] == group]
        target_families = {family(row["formula"]) for row in targets}
        history = [row for row in rows
                   if row["workload_group"] != group and family(row["formula"]) not in target_families]
        history_groups = sorted({row["workload_group"] for row in history})
        memory = HistoricalMemory(history, target_groups={group},
                                  target_formulas={row["formula"] for row in targets})
        c.require(not any(row["workload_group"] == group or
                          family(row["formula"]) in target_families for row in history),
                  "Target workload or related formula family leaked into history")
        group_values = {mode: [] for mode in MODES}
        for target in targets:
            for mode in MODES:
                if mode == "none":
                    hits = []
                elif mode == "knowledge_graph":
                    hits = memory.search_graph([target["formula"]],
                                               target_groups={group}, k=TOP_K)
                else:
                    hits = memory.search(target["formula"], mode=mode, k=TOP_K)
                coverage = operator_coverage(target["formula"], hits)
                group_values[mode].append(coverage["coverage_at_k"])
                score_rows.append({
                    "target_group": group,
                    "target_candidate_id": target["candidate_id"],
                    "target_formula": target["formula"],
                    "mode": mode,
                    "top_k": TOP_K,
                    "history_record_count": len(history),
                    "history_groups": history_groups,
                    "excluded_target_family_count": len(target_families),
                    "retrieved_candidate_ids": [hit["record"]["candidate_id"] for hit in hits],
                    **coverage,
                })
        group_mode = {}
        for mode, values in group_values.items():
            valid = [value for value in values if value is not None]
            group_mode[mode] = {
                "candidate_count": len(values),
                "scored_candidate_count": len(valid),
                "mean_coverage_at_k": statistics.mean(valid) if valid else None,
                "empty_hit_fraction": sum(not row["retrieved_candidate_ids"]
                    for row in score_rows if row["target_group"] == group and row["mode"] == mode)
                    / len(values) if values else None,
            }
        group_summaries.append({"target_group": group,
            "target_candidate_count": len(targets),
            "history_record_count": len(history),
            "history_groups": history_groups,
            "excluded_target_family_count": len(target_families),
            "modes": group_mode})

    macro = {}
    for mode in MODES:
        group_values = [row["modes"][mode]["mean_coverage_at_k"]
                        for row in group_summaries
                        if row["modes"][mode]["mean_coverage_at_k"] is not None]
        candidate_values = [row["coverage_at_k"] for row in score_rows
                            if row["mode"] == mode and row["coverage_at_k"] is not None]
        empty = [row for row in score_rows if row["mode"] == mode]
        macro[mode] = {
            "workload_macro_mean_coverage_at_k": statistics.mean(group_values) if group_values else None,
            "candidate_weighted_mean_coverage_at_k": statistics.mean(candidate_values) if candidate_values else None,
            "empty_hit_fraction": (sum(not row["retrieved_candidate_ids"] for row in empty) / len(empty)
                                    if empty else None),
            "workload_groups_scored": len(group_values),
            "candidate_queries_scored": len(candidate_values),
        }

    return {
        "schema": SCHEMA,
        "metric": "held-out formula operator-type coverage@3",
        "interpretation": (
            "Structural support diagnostic only. It is not semantic relevance, outcome prediction, "
            "LLM quality, or selection benefit. Candidate outcomes are not used in the target query "
            "or coverage score. Workload and expression-family exclusions are applied before retrieval."
        ),
        "retrieval_modes": list(MODES),
        "top_k": TOP_K,
        "target_workload_groups": selected_groups,
        "target_group_count": len(selected_groups),
        "target_candidate_count": sum(row["target_candidate_count"] for row in group_summaries),
        "group_macro": macro,
        "groups": group_summaries,
        "queries": score_rows,
        "new_labels": 0,
        "new_native_jobs": 0,
        "llm_calls": 0,
    }


def run(output: Path, corpus_path: Path = CORPUS) -> dict:
    output, corpus_path = Path(output).resolve(), Path(corpus_path).resolve()
    if output.exists():
        raise ValueError("Fresh output directory required; preserve every sealed report")
    corpus = c.unseal(corpus_path)
    rows = corpus.get("rows")
    report = evaluate_rows(rows)
    output.mkdir(parents=True)
    protocol = {
        "schema": SCHEMA + "-protocol",
        "scope": "retrospective consumed-data structural-support diagnostic",
        "corpus_path": str(corpus_path.relative_to(ROOT)) if corpus_path.is_relative_to(ROOT) else str(corpus_path),
        "corpus_sha256": c.sha(corpus_path),
        "candidate_rows": len(rows),
        "target_workload_groups": report["target_workload_groups"],
        "target_exclusion": "whole workload_group plus all matching speedup_corpus.family(formula) rows",
        "query_fields": ["candidate_id", "workload_group", "formula"],
        "query_uses_target_outcomes": False,
        "metric_definition": "unique operator types in union of top-k retrieved formula ASTs intersect target formula operator types, divided by target operator-type count",
        "top_k": TOP_K,
        "modes": list(MODES),
        "packages": {name: importlib.metadata.version(name) for name in ("numpy", "scikit-learn")},
        "source_bindings": {name: c.sha(ROOT / name) for name in SOURCE_FILES},
        "new_labels": 0,
        "new_native_jobs": 0,
        "llm_calls": 0,
        "claims": [],
    }
    c.seal(output / "protocol.json", protocol)
    c.seal(output / "report.json", report)
    lines = [
        "# Held-out structural coverage of agent memory retrieval", "",
        "This is a retrospective consumed-data diagnostic over the existing measured-label corpus. It",
        "scores the structural operator-type coverage of the top three retrieved formula records. The",
        "target query contains only candidate identity, workload group, and formula. Every target workload",
        "and matching expression family is excluded from the historical index before retrieval. Target",
        "speedup, area, timing, and correctness labels are not used in the score.", "",
        "The result measures **structural support**, not semantic relevance, historical-outcome usefulness,",
        "prediction accuracy, LLM decision quality, or improved hardware performance. The knowledge graph",
        "uses operator overlap in its retrieval rule, so a high coverage score is not independent evidence",
        "that graph retrieval improves selection. No model was trained and no LLM or target hardware was run.", "",
        "See the sealed `protocol.json` and `report.json` for exact source hashes, group-level metrics, and",
        "per-candidate retrieved IDs. The report records zero new labels, zero native jobs, and zero LLM calls.", "",
        "| Mode | Workload-macro coverage@3 | Candidate-weighted coverage@3 | Empty-hit fraction |",
        "| --- | ---: | ---: | ---: |",
    ]
    for mode, result in report["group_macro"].items():
        lines.append(f"| {mode} | {result['workload_macro_mean_coverage_at_k']:.4f} | "
                     f"{result['candidate_weighted_mean_coverage_at_k']:.4f} | "
                     f"{result['empty_hit_fraction']:.4f} |")
    (output / "README.md").write_text("\n".join(lines) + "\n")
    inventory = {path.name: c.sha(path) for path in sorted(output.iterdir()) if path.is_file()}
    c.seal(output / "manifest.json", inventory)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, default=CORPUS)
    args = parser.parse_args()
    print(run(args.output, args.corpus))


if __name__ == "__main__":
    main()
