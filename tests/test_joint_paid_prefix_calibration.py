from __future__ import annotations

from copy import deepcopy

from scripts.audit_joint_paid_prefix_calibration import prequential_sequence


class FakePosterior:
    def __init__(self, candidate_ids, observed=()):
        self.candidate_ids = tuple(candidate_ids)
        self.observed_ids = tuple(observed)
        self.conditioned_ids = self.observed_ids

    def joint(self, candidate_ids):
        assert len(candidate_ids) == 1
        mean = float(len(self.observed_ids))
        return {"outputs": {
            "area_delta_lut4": {"mean": [mean], "observation_covariance": [[1.0]]},
            "routed_fmax_min_mhz": {"mean": [mean], "observation_covariance": [[1.0]]},
            "log_measurement_seconds": {"mean": [mean], "observation_covariance": [[1.0]]},
        }}

    def condition(self, outcome, *, queried_id):
        assert queried_id == outcome["candidate_id"]
        assert queried_id not in self.observed_ids
        return FakePosterior(self.candidate_ids, (*self.observed_ids, queried_id))


def test_prequential_predictions_precede_success_and_failures_do_not_update():
    ids = ["a", "b", "c"]
    attempts = [
        {"candidate_id": "a", "status": "success"},
        {"candidate_id": "b", "status": "failed", "failure_class": "infra"},
        {"candidate_id": "c", "status": "success"},
    ]
    successes = [
        {"candidate_id": "a", "area_delta_lut4": 0.0,
         "routed_fmax_min_mhz": 0.0, "measurement_seconds": 1.0,
         "device_fits": True},
        {"candidate_id": "c", "area_delta_lut4": 1.0,
         "routed_fmax_min_mhz": 1.0, "measurement_seconds": 2.718281828459045,
         "device_fits": False},
    ]
    records, final = prequential_sequence(FakePosterior(ids), attempts, successes,
                                          workload_group="synthetic")
    assert [row["charged_attempts_before"] for row in records] == [0, 1, 2]
    assert [row["successful_conditions_before"] for row in records] == [0, 1, 1]
    assert [row["area_delta_lut4"]["predicted_mean"] for row in records] == [0.0, 1.0, 1.0]
    assert [row["conditioned_after_score"] for row in records] == [True, False, True]
    assert final.observed_ids == ("a", "c")


def test_attempt_order_and_success_rows_are_not_mutated():
    attempts = [{"candidate_id": "b", "status": "failed"},
                {"candidate_id": "a", "status": "success"}]
    success = {"candidate_id": "a", "area_delta_lut4": 0.0,
        "routed_fmax_min_mhz": 0.0, "measurement_seconds": 1.0, "device_fits": True}
    original_attempts, original_success = deepcopy(attempts), deepcopy(success)
    prequential_sequence(FakePosterior(["a", "b"]), attempts, [success],
                         workload_group="synthetic")
    assert attempts == original_attempts
    assert success == original_success
