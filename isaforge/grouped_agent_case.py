"""Authenticated current-corpus cases for consumed-data agent development.

This module loads the fixed October 26 data pack; it fits no model and runs no
hardware. ``outcomes`` and ``metadata`` are evaluator-owned. Only ``public``,
the approved historical ``training`` rows, and ``public_metadata`` may enter a
model request. The historical corpus and its screen remain unchanged.
"""
from __future__ import annotations

import copy
import importlib.metadata
from pathlib import Path

from . import budgeted_selection as b, codesign as c
from .model import validate_training_rows
from .speedup_corpus import family
from scripts.evaluate_feasibility_model_families import _split_with_failures
from scripts.reproduce_guarded_sha256 import _manifest, _path

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "results/2026-10-26-lift-selection-corpus/corpus.json"
SCREEN = ROOT / "results/2026-10-26-feasibility-model-screen"
SCHEMA = "isaforge-current-grouped-agent-case-v1"
SOURCE = "isaforge/grouped_agent_case.py"
CORPUS_SHA256 = "901413111da94933a1c14f0e758c1cf96f959bde44325e79ded6e47c4b8743ef"
SCREEN_PROTOCOL_SHA256 = "7eff9339c71619fdf55dd24b2681314ac0740906f8ffdd36c452b645f810de5c"
SCREEN_MANIFEST_SHA256 = "235cfe3a6c993f78c184676f24441438facdaf1f7760ece7dacddc93ecff9f93"


def _public(row):
    return {key: copy.deepcopy(row[key]) for key in b.PUBLIC_KEYS}


def _authenticate(corpus_path, screen_root, source_root):
    """Check sealed inventories, the pinned corpus binding and model sources."""
    corpus_path, screen_root, source_root = map(
        lambda value: Path(value).resolve(), (corpus_path, screen_root, source_root))
    c.require(corpus_path.name == "corpus.json", "Expected named current corpus")
    c.require(c.sha(screen_root / "protocol.json") == SCREEN_PROTOCOL_SHA256 and
              c.sha(screen_root / "manifest.json") == SCREEN_MANIFEST_SHA256,
              "Expected the fixed October 26 grouped screen")
    screen_entries = _manifest(screen_root)
    c.require({"protocol.json", "protocol.json.sha256", "report.json", "report.json.sha256"}
              <= screen_entries.keys(), "Screen protocol and report must be authenticated")
    protocol = c.unseal(screen_root / "protocol.json")
    c.require(protocol.get("schema") == "isaforge-feasibility-model-family-screen-v1" and
              protocol.get("successful_measured_rows") == 122 and
              protocol.get("charged_failed_attempts") == 4,
              "Expected fixed 122-label/four-failure grouped screen")
    c.require(c.sha(corpus_path) == protocol.get("corpus_sha256") == CORPUS_SHA256,
              "Corpus differs from the grouped-screen input")
    corpus_entries = _manifest(corpus_path.parent)
    c.require({"corpus.json", "corpus.json.sha256"} <= corpus_entries.keys(),
              "Corpus and seal must be in its complete manifest")
    corpus = c.unseal(corpus_path)
    c.require(corpus.get("schema") == "isaforge-consumed-guarded-corpus-v1" and
              corpus.get("successful_labels") == 122 and
              len(corpus.get("rows", [])) == 122 and
              corpus.get("total_candidate_attempts") == 126 and
              len(corpus.get("failed_attempts", [])) == 4,
              "Expected authenticated 122-label/126-attempt consumed corpus")
    sources = protocol.get("source_bindings")
    c.require(isinstance(sources, dict) and sources,
              "Grouped-screen model source bindings are required")
    for name, expected in sources.items():
        path = _path(source_root, name)
        c.require(path.is_file() and c.sha(path) == expected,
                  "Grouped-screen model source changed: " + name)
    for name, expected in protocol.get("packages", {}).items():
        c.require(importlib.metadata.version(name) == expected,
                  "Grouped-screen model dependency changed: " + name)

    successes, failures = corpus["rows"], corpus["failed_attempts"]
    all_rows = successes + failures
    identities = [row.get("candidate_id") for row in all_rows]
    c.require(all(isinstance(identity, str) and identity for identity in identities) and
              len(set(identities)) == len(identities), "Unique corpus candidate identities required")
    validate_training_rows(successes)
    b.public_rows([_public(row) for row in all_rows])
    for row in all_rows:
        c.require(row["candidate_family"] == family(row["formula"]),
                  "Corpus candidate-family annotation differs")
        c.require(row["benchmark"].split(":", 1)[0] == row["workload_group"],
                  "Corpus workload/context identity differs")
        c.require(row["benchmark"] in corpus["contexts"], "Missing corpus context provenance")
    for row in successes:
        c.require(b.validate_outcome(row), "Invalid successful corpus measurement")
    for row in failures:
        c.require(row.get("status") == "failed" and not b.validate_outcome(row),
                  "Failed attempts cannot become successful labels")
        c.require(isinstance(row.get("failure_class"), str) and row["failure_class"],
                  "Failed attempts need a recorded failure class")
    censored = {row["candidate_id"] for row in failures if row.get("reference_censored") is True}
    c.require(censored == set(corpus.get("reference_censored_candidates", [])),
              "Censored candidate inventory differs")
    groups = sorted({row["workload_group"] for row in successes})
    c.require(groups == protocol.get("independent_workload_groups") and len(groups) == 14,
              "Grouped-screen workload roster differs")
    inputs = dict(corpus_sha256=c.sha(corpus_path),
        corpus_manifest_sha256=c.sha(corpus_path.parent / "manifest.json"),
        screen_protocol_sha256=c.sha(screen_root / "protocol.json"),
        screen_manifest_sha256=c.sha(screen_root / "manifest.json"),
        screen_report_sha256=c.sha(screen_root / "report.json"))
    bindings = dict(sources)
    bindings[SOURCE] = c.sha(Path(__file__))
    return corpus, inputs, bindings


def list_grouped_agent_targets(*, corpus_path=CORPUS, screen_root=SCREEN, source_root=ROOT):
    """List exact context identities and public pool sizes without outcomes."""
    corpus, inputs, _ = _authenticate(corpus_path, screen_root, source_root)
    pools = {}
    for row in corpus["rows"] + corpus["failed_attempts"]:
        key = (row["workload_group"], row["benchmark"])
        pools.setdefault(key, []).append(_public(row))
    return [dict(target_workload_group=group, target_benchmark=benchmark,
        context_id=corpus["contexts"][benchmark]["context_id"],
        candidate_count=len(rows), public_sha256=c.digest(sorted(rows,
            key=lambda row: row["candidate_id"])), input_bindings=copy.deepcopy(inputs))
        for (group, benchmark), rows in sorted(pools.items())]


def load_grouped_agent_case(group, benchmark, *, corpus_path=CORPUS,
                            screen_root=SCREEN, source_root=ROOT):
    """Build one private evaluator case with a strictly public candidate view.

    Split exclusions cover every context and failed candidate in the held-out
    workload, matching the existing screen. Reference completeness is computed
    for the exact context pool and stays in host-only ``metadata``. Historical
    cost includes all non-target-workload attempts, including failed and
    family-excluded attempts; their recorded timer scopes are not harmonized.
    """
    c.require(isinstance(group, str) and group and isinstance(benchmark, str) and benchmark,
              "Explicit held-out workload and exact benchmark context required")
    corpus, inputs, sources = _authenticate(corpus_path, screen_root, source_root)
    successes, failures = corpus["rows"], corpus["failed_attempts"]
    training, test_success, test_failures, excluded = _split_with_failures(
        successes, failures, group)
    target_all = test_success + test_failures
    c.require(benchmark in {row["benchmark"] for row in target_all},
              "Benchmark context does not belong to the held-out workload")
    pool = sorted([row for row in target_all if row["benchmark"] == benchmark],
                  key=lambda row: row["candidate_id"])
    c.require(len(pool) >= 3, "Current agent pool must support three charged attempts")
    public = b.public_rows([_public(row) for row in pool])
    c.require(len(training) >= 3 and len({row["workload_group"] for row in training}) >= 2,
              "Insufficient unrelated historical training")
    validate_training_rows(training)
    target_families = sorted({family(row["formula"]) for row in target_all})
    c.require(all(row["workload_group"] != group and
                  family(row["formula"]) not in target_families for row in training),
              "Held-out workload or family remained in training")

    outcomes = {}
    for row in pool:
        if row.get("status", "success") == "success":
            outcome = copy.deepcopy(row)
        else:
            # Keep recorded charging data, but never relay paths or raw errors.
            outcome = dict(**_public(row), status="failed", error=row["failure_class"],
                           measurement_seconds=row["measurement_seconds"])
        b.validate_outcome(outcome, _public(row))
        outcomes[row["candidate_id"]] = outcome

    history_available = [row for row in successes if row["workload_group"] != group]
    history_failed = [row for row in failures if row["workload_group"] != group]
    history_seconds = sum(row["measurement_seconds"] for row in history_available + history_failed)
    context = corpus["contexts"][benchmark]
    c.require(benchmark == group + ":" + context["context_id"] and
              context.get("workload_group", group) == group,
              "Target context provenance identity differs")
    public_metadata = dict(schema=SCHEMA, scope="consumed-data engineering replay",
        target_workload_group=group, target_benchmark=benchmark,
        context_id=context["context_id"], context_sha256=c.digest(context),
        hardware_context_id=context.get("hardware_context_id"),
        target_formula_families=target_families,
        training_ids_sha256=c.digest(sorted(row["candidate_id"] for row in training)),
        excluded_related_ids_sha256=c.digest(sorted(excluded)),
        target_ids_sha256=c.digest([row["candidate_id"] for row in public]),
        training_sha256=c.digest(training), public_sha256=c.digest(public),
        training_rows=len(training),
        training_workload_groups=sorted({row["workload_group"] for row in training}),
        historical_available_rows=len(history_available),
        historical_available_attempts=len(history_available) + len(history_failed),
        historical_attempt_seconds=history_seconds,
        timer_scope="Sum of recorded historical attempt durations; heterogeneous original timer scopes, excluding the held-out workload.",
        input_bindings=inputs, source_bindings=sources,
        target_outcomes_in_public_metadata=False, new_native_jobs=0)
    censored_ids = sorted(row["candidate_id"] for row in pool
                          if row.get("reference_censored") is True)
    metadata = dict(**copy.deepcopy(public_metadata),
        reference_censored=bool(censored_ids), reference_complete=not bool(censored_ids),
        censored_candidate_ids=censored_ids,
        successful_target_outcomes=sum(row.get("status", "success") == "success" for row in pool),
        failed_target_attempts=sum(row.get("status") == "failed" for row in pool),
        outcomes_sha256=c.digest(outcomes),
        metadata_visibility="private evaluator metadata; use public_metadata for model requests")
    return dict(public=public, training=copy.deepcopy(training), outcomes=outcomes,
                metadata=metadata, public_metadata=public_metadata)
