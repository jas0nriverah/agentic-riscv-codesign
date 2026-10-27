import pytest

from scripts.evaluate_feasible_benefit_ranker import _measured_feasible_relevance
from isaforge.features import FEATURE_COLUMNS


def _row(candidate_id, benchmark, speedup, area, fmax, *, status="success"):
    return dict(**{key: 0.0 for key in FEATURE_COLUMNS},
        candidate_id=candidate_id, benchmark=benchmark, speedup=speedup,
        area_delta_lut4=area, routed_fmax_min_mhz=fmax, device_fits=True,
        status=status, measurement_source="synthesis_estimate")


def test_relevance_prefers_measured_feasible_benefit_over_infeasible_raw_speedup():
    rows = [
        _row("a-infeasible-fast", "workload-a:build", 1.10, 70, 70),
        _row("b-feasible-slower", "workload-a:build", 1.02, 40, 70),
        _row("c-feasible-slower-clock", "workload-a:build", 1.05, 50, 11),
    ]

    ordered, labels, qids, groups = _measured_feasible_relevance(rows)

    by_candidate = dict(zip((row["candidate_id"] for row in ordered), labels))
    assert by_candidate["a-infeasible-fast"] == 0
    assert by_candidate["c-feasible-slower-clock"] == 0
    assert by_candidate["b-feasible-slower"] == 1
    assert qids == [0, 0, 0]
    assert groups[0]["feasible_training_rows"] == 1


def test_relevance_groups_are_independent_queries_and_preserve_ties():
    rows = [
        _row("a0", "workload-a:build", 1.02, 40, 70),
        _row("a1", "workload-a:build", 1.01, 50, 70),
        _row("b0", "workload-b:build", 1.00, 30, 70),
        _row("b1", "workload-b:build", 1.00, 50, 70),
    ]

    ordered, labels, qids, groups = _measured_feasible_relevance(rows)

    assert [row["candidate_id"] for row in ordered] == ["a0", "a1", "b0", "b1"]
    assert labels == [1, 0, 0, 0]
    assert qids == [0, 0, 1, 1]
    assert [group["distinct_relevance_levels"] for group in groups] == [2, 1]


def test_failed_attempt_cannot_be_given_training_relevance():
    row = _row("failed", "workload-a:build", 1.05, 20, 70, status="failed")
    with pytest.raises(ValueError, match="Failed attempts cannot train"):
        _measured_feasible_relevance([row])
