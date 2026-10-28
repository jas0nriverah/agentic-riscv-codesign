"""Current-corpus boundary checks; no model fit, LLM call or native job."""
import copy
import json
from pathlib import Path
import shutil

import pytest

from isaforge import budgeted_selection as b, codesign as c
from isaforge.bounded_selector import ReplaySelectionSession
from isaforge import grouped_agent_case as cases
from isaforge.speedup_corpus import family
from scripts.evaluate_feasibility_model_families import _split_with_failures
from test_budgeted_selection import predictions


def _target(group):
    return next(row for row in cases.list_grouped_agent_targets()
                if row["target_workload_group"] == group)


def _case(group):
    target = _target(group)
    return cases.load_grouped_agent_case(group, target["target_benchmark"])


def _keys(value):
    if isinstance(value, dict):
        return set(value) | set().union(*(_keys(item) for item in value.values()))
    if isinstance(value, list):
        return set().union(*(_keys(item) for item in value))
    return set()


def _copy_inputs(tmp_path):
    corpus_root = tmp_path / "corpus"
    screen_root = tmp_path / "screen"
    shutil.copytree(cases.CORPUS.parent, corpus_root)
    shutil.copytree(cases.SCREEN, screen_root)
    return corpus_root / "corpus.json", screen_root


def test_authenticated_roster_has_fifteen_exact_contexts_in_fourteen_groups():
    roster = cases.list_grouped_agent_targets()
    assert len(roster) == 15
    assert len({row["target_workload_group"] for row in roster}) == 14
    assert len({row["target_benchmark"] for row in roster}) == 15
    assert all(row["candidate_count"] >= 3 for row in roster)
    assert all(row["target_benchmark"] == row["target_workload_group"] + ":" + row["context_id"]
               for row in roster)
    assert not any({"reference_complete", "reference_censored", "speedup"} & set(row)
                   for row in roster)


def test_whole_workload_split_covers_both_sha_contexts_and_all_target_families():
    corpus = c.unseal(cases.CORPUS)
    group = "embench-nettle-sha256"
    roster = [row for row in cases.list_grouped_agent_targets()
              if row["target_workload_group"] == group]
    assert len(roster) == 2
    expected_training, successes, failures, excluded = _split_with_failures(
        corpus["rows"], corpus["failed_attempts"], group)
    expected_families = {family(row["formula"]) for row in successes + failures}
    for target in roster:
        case = cases.load_grouped_agent_case(group, target["target_benchmark"])
        assert case["training"] == expected_training
        assert case["metadata"]["target_formula_families"] == sorted(expected_families)
        assert case["metadata"]["training_ids_sha256"] == c.digest(sorted(
            row["candidate_id"] for row in expected_training))
        assert case["metadata"]["excluded_related_ids_sha256"] == c.digest(sorted(excluded))
        assert all(row["workload_group"] != group and family(row["formula"]) not in expected_families
                   for row in case["training"])
        assert {row["benchmark"] for row in case["public"]} == {target["target_benchmark"]}


def test_target_outcomes_are_private_and_public_lineage_contains_no_outcomes():
    case = _case("beebs-aha-compress")
    assert all(set(row) == set(b.PUBLIC_KEYS) for row in case["public"])
    forbidden = {"speedup", "candidate_cycles", "area_delta_lut4", "routed_fmax_min_mhz",
                 "correctness_verified", "measurement_seconds", "reference_complete",
                 "reference_censored", "censored_candidate_ids", "failed_target_attempts"}
    assert not forbidden & _keys(case["public_metadata"])
    assert all("speedup" in outcome for outcome in case["outcomes"].values())
    assert case["metadata"]["reference_complete"] is True
    assert "oracle" not in case["metadata"] and "regret" not in case["metadata"]

    # A caller mutating the evaluator's copy cannot change an agent-visible row.
    identity = case["public"][0]["candidate_id"]
    public_before = copy.deepcopy(case["public"])
    case["outcomes"][identity]["latency_features"]["estimated_saved_cycles"] = -999
    case["metadata"]["input_bindings"]["corpus_sha256"] = "changed-private-copy"
    assert case["public"] == public_before
    assert case["public_metadata"]["input_bindings"]["corpus_sha256"] == cases.CORPUS_SHA256


@pytest.mark.parametrize("group", ["embench-ud", "tacle-g723-enc"])
def test_infrastructure_censored_pools_never_become_complete_oracles(group):
    case = _case(group)
    assert case["metadata"]["reference_censored"] is True
    assert case["metadata"]["reference_complete"] is False
    assert case["metadata"]["censored_candidate_ids"]
    assert case["metadata"]["failed_target_attempts"] >= 1
    assert not {"reference_censored", "reference_complete", "censored_candidate_ids"} & _keys(
        case["public_metadata"])


def test_recorded_failed_outcome_retains_charging_data_and_no_numeric_label(tmp_path):
    case = _case("embench-ud")
    identity, failure = next((identity, row) for identity, row in case["outcomes"].items()
                             if row.get("status") == "failed")
    assert set(failure) == {*b.PUBLIC_KEYS, "status", "error", "measurement_seconds"}
    assert failure["measurement_seconds"] > 0
    assert failure["error"] in {"memory_contract_failure", "infrastructure_unknown"}
    assert not b.validate_outcome(failure)
    session = ReplaySelectionSession(case["public"], case["training"],
        predictions(case["training"], case["public"], 0),
        lambda row: case["outcomes"][row["candidate_id"]],
        area_cap=64, ledger_path=tmp_path / "ledger.json")
    result = session.call(dict(tool="measure", arguments=dict(candidate_id=identity,
        decision_summary="Measure this public candidate to learn its outcome.")))
    assert result["status"] == "failed"
    assert session.charged == 1 and session.observations == []
    assert session.ledger["replayed_target_measurement_seconds"] == failure["measurement_seconds"]
    assert not {"speedup", "area_delta_lut4", "candidate_cycles"} & set(result["observation"])


def test_historical_counts_and_cost_include_excluded_rows_and_failed_attempts():
    group = "beebs-aha-compress"
    case = _case(group)
    corpus = c.unseal(cases.CORPUS)
    historical_success = [row for row in corpus["rows"] if row["workload_group"] != group]
    historical_failed = [row for row in corpus["failed_attempts"] if row["workload_group"] != group]
    metadata = case["metadata"]
    assert metadata["historical_available_rows"] == len(historical_success)
    assert metadata["historical_available_attempts"] == len(historical_success) + len(historical_failed)
    assert metadata["historical_available_rows"] > len(case["training"])
    assert metadata["historical_attempt_seconds"] == sum(row["measurement_seconds"]
        for row in historical_success + historical_failed)


def test_changed_corpus_is_rejected_even_after_resealing(tmp_path):
    corpus_path, screen_root = _copy_inputs(tmp_path)
    corpus = c.unseal(corpus_path)
    corpus["scope"] = "substituted pack"
    c.seal(corpus_path, corpus)
    target = _target("beebs-aha-compress")
    with pytest.raises(ValueError, match="Corpus differs"):
        cases.load_grouped_agent_case(target["target_workload_group"], target["target_benchmark"],
                                     corpus_path=corpus_path, screen_root=screen_root)


def test_changed_screen_inventory_is_rejected_even_after_resealing(tmp_path):
    corpus_path, screen_root = _copy_inputs(tmp_path)
    manifest = c.unseal(screen_root / "manifest.json")
    manifest["report.json"] = "0" * 64
    c.seal(screen_root / "manifest.json", manifest)
    with pytest.raises(ValueError, match="fixed October 26"):
        cases.list_grouped_agent_targets(corpus_path=corpus_path, screen_root=screen_root)


def test_model_source_drift_is_rejected(tmp_path):
    source_root = tmp_path / "sources"
    protocol = c.unseal(cases.SCREEN / "protocol.json")
    for name in protocol["source_bindings"]:
        path = source_root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(cases.ROOT / name, path)
    (source_root / "isaforge/ranking.py").write_text("changed model source\n")
    with pytest.raises(ValueError, match="model source changed"):
        cases.list_grouped_agent_targets(source_root=source_root)


def test_unknown_workload_and_cross_workload_context_are_rejected():
    target = _target("beebs-aha-compress")
    with pytest.raises(ValueError, match="Unknown or empty"):
        cases.load_grouped_agent_case("unknown-workload", target["target_benchmark"])
    with pytest.raises(ValueError, match="does not belong"):
        cases.load_grouped_agent_case("embench-ud", target["target_benchmark"])
