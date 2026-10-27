from scripts import evaluate_feasibility_model_families as screen


def _success(identity, group, formula, *, speedup=1.1, area=20, fmax=20):
    return {
        "candidate_id": identity,
        "workload_group": group,
        "formula": formula,
        "candidate_family": "unused fixture annotation",
        "benchmark": group + ":context",
        "status": "success",
        "speedup": speedup,
        "area_delta_lut4": area,
        "device_fits": True,
        "routed_fmax_min_mhz": fmax,
        "measurement_seconds": 2.0,
    }


def _failure(identity, group, formula, *, censored=False):
    return {
        "candidate_id": identity,
        "workload_group": group,
        "formula": formula,
        "candidate_family": "unused fixture annotation",
        "benchmark": group + ":context",
        "status": "failed",
        "measurement_seconds": 3.0,
        "reference_censored": censored,
    }


def test_split_includes_failed_target_families_and_keeps_unknown_failures_out_of_training():
    held = _success("held", "target", "add(in0,in1)")
    same_target_family = _success("related", "history-a", "add(in1,in0)")
    unrelated = _success("unrelated", "history-b", "sub(in0,in1)")
    failed = _failure("failed", "target", "xor(in0,in1)")

    training, test, failures, excluded = screen._split_with_failures(
        [held, same_target_family, unrelated], [failed], "target")

    assert [row["candidate_id"] for row in training] == ["unrelated"]
    assert [row["candidate_id"] for row in test] == ["held"]
    assert [row["candidate_id"] for row in failures] == ["failed"]
    assert excluded == ["related"]
    assert all("speedup" not in row for row in failures)


def test_failed_query_consumes_budget_without_becoming_a_feasible_result():
    success = _success("success", "target", "add(in0,in1)")
    failed = _failure("failed", "target", "sub(in0,in1)", censored=True)
    by_success = {"success": success}
    by_failure = {"failed": failed}
    order = [failed, success]

    first = screen._evaluate_group("model", order, by_success, by_failure,
        1.1, True, seed=0, budget=1)
    second = screen._evaluate_group("model", order, by_success, by_failure,
        1.1, True, seed=0, budget=2)

    assert first["best_speedup"] == 1.0
    assert first["measured_success_count"] == 0
    assert first["failed_or_unresolved_attempts"] == 1
    assert first["measurement_seconds"] == 3.0
    assert first["cycle_reduction_regret"] is None
    assert second["best_speedup"] == 1.1
    assert second["measured_success_count"] == 1
    assert second["failed_or_unresolved_attempts"] == 1
    assert second["measurement_seconds"] == 5.0
    assert second["cycle_reduction_regret"] is None


def test_feasibility_requires_device_area_and_timing_constraints():
    assert screen._feasible(_success("ok", "g", "add(in0,in1)"))
    assert not screen._feasible(_success("area", "g", "add(in0,in1)", area=65))
    assert not screen._feasible(_success("timing", "g", "add(in0,in1)", fmax=11.9))
