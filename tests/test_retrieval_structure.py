"""Structural memory coverage tests; no outcome labels enter target scoring."""
from scripts.evaluate_retrieval_structure import evaluate_rows, operator_coverage
from test_budgeted_selection import history


def test_operator_coverage_is_set_recall_over_retrieved_formulae():
    hits = [
        {"record": {"formula": "xor(in0,slli(in1,1))"}},
        {"record": {"formula": "sub(in0,in1)"}},
    ]
    result = operator_coverage("add(in0,xor(in1,2))", hits)
    assert result["target_operator_count"] == 2
    assert result["covered_operator_types"] == ["xor"]
    assert result["coverage_at_k"] == 0.5


def test_evaluator_accepts_target_rows_without_any_outcome_labels():
    historical = history()
    targets = [
        {"candidate_id": "target-1", "workload_group": "target", "formula": "add(in0,xor(in1,2))"},
        {"candidate_id": "target-2", "workload_group": "target", "formula": "sub(in0,andi(in1,3))"},
    ]
    report = evaluate_rows(historical + targets, target_groups=["target"])
    assert report["target_candidate_count"] == 2
    assert report["target_group_count"] == 1
    assert report["new_labels"] == report["new_native_jobs"] == report["llm_calls"] == 0
    assert all("speedup" not in query and "area_delta_lut4" not in query
               for query in report["queries"])
    for query in report["queries"]:
        assert query["target_group"] == "target"
        assert "target" not in query["history_groups"]
        assert not set(query["retrieved_candidate_ids"]) & {row["candidate_id"] for row in targets}


def test_related_formula_families_are_excluded_before_retrieval():
    historical = history()
    related_target = {"candidate_id": "target-related", "workload_group": "target",
                      "formula": "xor(in0,slli(in1,7))"}
    report = evaluate_rows(historical + [related_target], target_groups=["target"])
    matching = [query for query in report["queries"]
                if query["mode"] == "knowledge_graph"]
    assert matching
    assert all(query["excluded_target_family_count"] >= 1 for query in matching)
    assert all("h1" not in query["retrieved_candidate_ids"] for query in matching)
