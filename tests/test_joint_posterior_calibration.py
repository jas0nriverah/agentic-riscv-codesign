import numpy as np
import pytest

from scripts import audit_joint_posterior_calibration as audit
from isaforge.speedup_corpus import family


def test_interval_metrics_uses_future_predictive_standardized_residuals():
    report = audit.interval_metrics([0.0, 0.7, 1.3, 2.0])
    assert report["n"] == 4
    assert report["coverage"] == {"50": 0.25, "80": 0.5, "95": 0.75}
    assert report["standardized_rmse"] == pytest.approx(np.sqrt((0.49+1.69+4)/4))


def test_hardware_feasibility_probability_respects_deterministic_constraint_edges():
    assert audit.feasible_probability(64, 0, 12, 0, 0.4) == 0.4
    assert audit.feasible_probability(64.01, 0, 30, 0, 1) == 0
    assert audit.feasible_probability(40, 0, 11.99, 0, 1) == 0
    assert audit.feasible_probability(40, 0, 30, 0, 0) == 0


def test_loco_family_exclusion_includes_unknown_target_failures():
    target = [
        dict(candidate_id="t-add", workload_group="target", formula="add(in0,in1)"),
        dict(candidate_id="t-xor", workload_group="target", formula="xor(in0,in1)"),
    ]
    successes = target + [
        dict(candidate_id="s-add", workload_group="source", formula="add(in0,in1)"),
        dict(candidate_id="s-mul", workload_group="source", formula="mul(in0,in1)"),
        dict(candidate_id="s-sub", workload_group="source", formula="sub(in0,in1)"),
    ]
    failures = [dict(candidate_id="t-sub-failed", workload_group="target",
        formula="sub(in0,in1)", status="failed")]
    training, scored, held_failures, excluded = audit.split_groups(successes, failures, "target")
    assert [row["candidate_id"] for row in training] == ["s-mul"]
    assert [row["candidate_id"] for row in scored] == ["t-add", "t-xor"]
    assert [row["candidate_id"] for row in held_failures] == ["t-sub-failed"]
    assert set(excluded) == {family(row["formula"]) for row in target+failures}


@pytest.mark.parametrize("z", [[], [float("nan")], [float("inf")]])
def test_interval_metrics_rejects_missing_or_nonfinite_values(z):
    with pytest.raises(ValueError):
        audit.interval_metrics(z)


def test_feasibility_probability_rejects_bad_uncertainty():
    with pytest.raises(ValueError):
        audit.feasible_probability(10, -1, 20, 1, 0.5)
    with pytest.raises(ValueError):
        audit.feasible_probability(10, 1, 20, 1, 1.01)
