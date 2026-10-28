"""Regression checks for the prospective Sudoku selector boundary."""
from __future__ import annotations

from scripts import execute_pulpino_sudoku_selector as study
from test_bounded_selector import grouped_metadata, grouped_prediction_bundle
from test_budgeted_selection import history, public


def _public_pool():
    return [
        public("sudoku-1", saved_cycles=60),
        public("sudoku-2", "sub(in0,slli(in1,1))", saved_cycles=20),
        public("sudoku-3", "add(in0,srli(in1,1))", saved_cycles=30),
    ]


def test_live_agent_request_names_held_out_sudoku_scope_and_no_inherited_failure(tmp_path):
    target = _public_pool()
    training = history()
    session = study.ProspectiveLiveSelectionSession(
        target,
        training,
        None,
        lambda row: row,
        area_cap=study.AREA_CAP,
        budget=study.BUDGET,
        ledger_path=tmp_path / "ledger.json",
        historical_available_rows=106,
        grouped_predictions=grouped_prediction_bundle(target),
        grouped_model_metadata=grouped_metadata(),
    )

    request = session.request()
    text = str(request)
    assert "fixed Sudoku instance" in text
    assert "exact operator-tree families are excluded" in text
    assert "regex" not in text.lower()
    assert "unseen-workload experiment" not in text
    assert "startup failure" not in text.lower()
    assert session.ledger["scope"] == (
        "prospective live measurement on a source- and exact-family-held-out workload"
    )
    assert not hasattr(study, "STARTUP_FAILURE")


def test_agent_measurement_and_resource_budget_remain_frozen():
    assert study.BUDGET == 3
    assert study.AREA_CAP == 64
    assert study.CLOCK_MHZ == 12.0
    assert study.MAX_MODEL_CALLS == 12
    assert study.MAX_TOOL_CALLS == 20
    assert study.RESULTS.name == "2026-10-28-pulpino-sudoku-selection-r1"
