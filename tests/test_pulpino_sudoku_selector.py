"""Regression checks for the prospective Sudoku selector boundary."""
from __future__ import annotations

from io import StringIO

import pytest

from isaforge import codesign as c
from isaforge import guarded_attempts as attempts
from isaforge import pulpino_sudoku_workload as workload
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
    assert session.ledger["returned_observation_measurement_seconds"] == 0
    assert "target_attempt_wall_seconds" not in session.ledger
    assert not hasattr(study, "STARTUP_FAILURE")


def test_agent_measurement_and_resource_budget_remain_frozen():
    assert study.BUDGET == 3
    assert study.AREA_CAP == 64
    assert study.CLOCK_MHZ == 12.0
    assert study.MAX_MODEL_CALLS == 12
    assert study.MAX_TOOL_CALLS == 20
    assert study.RESULTS.name == "2026-10-28-pulpino-sudoku-selection-r4"
    assert study.PREREG.name == "2026-10-28-pulpino-sudoku-selector-prereg-r4"


def test_agent_refuses_a_noninteractive_stdin_before_creating_an_episode():
    with pytest.raises(ValueError, match="interactive PTY"):
        study._require_interactive_relay(StringIO())


def test_agent_attempt_costs_include_charged_attempt_even_when_projection_is_missing(tmp_path):
    native = tmp_path / "native"
    study_root = tmp_path / "study"
    names = {"target-a": "candidate_1", "target-b": "candidate_2"}
    first = attempts.ledger_path(native, names["target-a"])
    second = attempts.ledger_path(native, names["target-b"])
    c.seal(first, dict(schema=attempts.SCHEMA, name=names["target-a"],
        status="failed", elapsed_seconds=2.5, artifacts={}))
    c.seal(second, dict(schema=attempts.SCHEMA, name=names["target-b"],
        status="started", elapsed_seconds=None, artifacts={}))
    timer = study_root / "outer-times" / "target-a.json"
    c.seal(timer, dict(candidate_id="target-a", status="failed", elapsed_seconds=3.0))

    costs = study._agent_attempt_costs(native, study_root, set(names), names, {"target-a"})

    assert costs["measurement_seconds"] is None
    assert costs["known_measurement_seconds"] == 2.5
    assert costs["measurement_time_unknown_ids"] == ["target-b"]
    assert costs["outer_operation_seconds"] is None
    assert costs["known_outer_operation_seconds"] == 3.0
    assert costs["outer_operation_time_unknown_ids"] == ["target-b"]
    assert costs["attempts"][0]["outcome_returned_to_selector"] is True
    assert costs["attempts"][1]["outcome_returned_to_selector"] is False


def test_agent_startup_refuses_any_preexisting_candidate_attempt(tmp_path):
    workload.require_zero_candidates(tmp_path)
    ledger = attempts.ledger_path(tmp_path, "candidate_1")
    c.seal(ledger, dict(schema=attempts.SCHEMA, name="candidate_1",
        status="failed", elapsed_seconds=0.1, artifacts={}))
    try:
        workload.require_zero_candidates(tmp_path)
    except ValueError:
        pass
    else:
        raise AssertionError("preexisting target attempt was not rejected")
