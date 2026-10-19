"""Budget, information-boundary, and feasible-oracle regression tests."""

from unittest.mock import patch

import pytest

from isaforge.features import FEATURE_COLUMNS
from isaforge.selection import SelectionTools, evaluate_policies, run_policy


def row(candidate_id, *, speedup=1.2, area=1, runs=1, saved=1, benchmark="target"):
    return {
        **dict.fromkeys(FEATURE_COLUMNS, 0),
        "candidate_id": candidate_id, "benchmark": benchmark,
        "formula": "add(in0,in1)", "runs": runs, "saved": saved,
        "speedup": speedup, "area": area, "measurement_source": "synthetic",
    }


def test_cached_measurements_charge_unique_candidates_and_batch_is_atomic():
    tools = SelectionTools([row("a"), row("b"), row("c")], budget=2)
    assert len(tools.measure(["a", "a"])) == 1
    assert tools.measurements_used == 1
    tools.measure("a")
    assert tools.remaining_budget == 1
    with pytest.raises(ValueError, match="budget"):
        tools.measure(["b", "c"])
    assert tools.measured_candidate_ids == ["a"]
    with pytest.raises(ValueError, match="unknown"):
        tools.measure(["b", "missing"])
    assert tools.measurements_used == 1
    tools.measure(["a", "b"])
    assert tools.remaining_budget == 0


def test_discovery_hides_labels_and_does_not_allow_mutating_internal_rows():
    source = row("a", speedup=2, area=3)
    source["baseline_cycles"] = 20
    source["candidate_cycles"] = 10
    source["baseline_period_ns"] = source["candidate_period_ns"] = 1
    tools = SelectionTools([source], 1)
    source["speedup"] = 99
    candidates = tools.list_candidates()
    assert set(candidates[0]) == set(FEATURE_COLUMNS) | {"candidate_id", "benchmark", "formula"}
    candidates[0]["runs"] = 99
    assert tools.list_candidates()[0]["runs"] == 1
    observed = tools.measure("a")
    assert observed[0]["speedup"] == 2
    observed[0]["speedup"] = 99
    assert tools.choose_final()["speedup"] == 2


def test_acquisition_cannot_access_unmeasured_labels():
    rows = [row(str(i), speedup=i + 2) for i in range(6)]
    tools = SelectionTools(rows, 5)
    seen_training = []

    class InspectingPredictor:
        def __init__(self, seed):
            self.seed = seed

        def fit(self, training):
            assert {r["candidate_id"] for r in training} == set(tools.measured_candidate_ids)
            seen_training.append(len(training))
            return self

        def predict(self, candidates):
            assert all("speedup" not in r and "area" not in r for r in candidates)
            return [{"candidate_id": r["candidate_id"], "upper": float(r["candidate_id"])}
                    for r in candidates]

    with patch("isaforge.model.SpeedupPredictor", InspectingPredictor):
        result = run_policy(tools, "active_learning")
    assert seen_training == [3, 4]
    assert result["measurements_used"] == 5


def test_active_acquisition_is_invariant_to_hidden_outcomes():
    rows = [row(str(i), runs=i + 1, saved=10 - i, speedup=i + 2) for i in range(6)]

    class FeaturePredictor:
        def __init__(self, seed):
            pass

        def fit(self, training):
            return self

        def predict(self, candidates):
            return [{"candidate_id": r["candidate_id"], "upper": r["runs"]} for r in candidates]

    with patch("isaforge.model.SpeedupPredictor", FeaturePredictor):
        first = run_policy(SelectionTools(rows, 4, seed=13), "active_learning")
        hidden = set(r["candidate_id"] for r in rows) - set(first["measured_candidate_ids"])
        changed = [dict(r, speedup=999, area=999) if r["candidate_id"] in hidden else r for r in rows]
        second = run_policy(SelectionTools(changed, 4, seed=13), "active_learning")
    assert first == second


def test_frequency_and_merit_use_discovery_fields_and_ignore_labels():
    rows = [row("frequent", speedup=1.1, runs=9, saved=9),
            row("meritorious", speedup=1.2, runs=3, saved=15),
            row("oracle", speedup=5, runs=1, saved=1)]
    report = evaluate_policies(rows, budget=1, policies=("frequency", "merit", "random"))
    assert report["results"][0]["measured_candidate_ids"] == ["frequent"]
    assert report["results"][1]["measured_candidate_ids"] == ["meritorious"]
    assert report["oracle"]["selected"]["candidate_id"] == "oracle"
    assert report["results"][0]["regret"] == pytest.approx(3.9)
    assert all(result["measurements_used"] == 1 for result in report["results"] + [report["oracle"]])


@pytest.mark.parametrize("budget", [0, 1, 2, 7])
def test_all_policy_budgets_and_seeded_determinism(budget):
    rows = [row(str(i), speedup=i + 1) for i in range(4)]
    # Bootstrap accommodates the whole pool to isolate policy budget accounting.
    for policy in ("frequency", "merit", "random", "active_learning"):
        first = run_policy(SelectionTools(rows, budget, seed=8), policy, bootstrap=4)
        second = run_policy(SelectionTools(rows, budget, seed=8), policy, bootstrap=4)
        assert first == second
        assert first["measurements_used"] == min(budget, len(rows))
    report = evaluate_policies(rows, budget, seed=8, policies=("random",))
    assert report["oracle"]["measurements_used"] == min(budget, len(rows))


def test_area_cap_final_verification_and_oracle_use_same_feasible_pool():
    rows = [row("large", speedup=10, area=11, runs=5),
            row("small", speedup=2, area=3, runs=1)]
    tools = SelectionTools(rows, 2, area_cap=3)
    assert tools.choose_final() is None
    tools.measure("large")
    assert tools.choose_final() is None
    tools.measure("small")
    assert tools.choose_final()["candidate_id"] == "small"
    report = evaluate_policies(rows, 2, area_cap=3, policies=("frequency",))
    assert report["oracle"]["best_speedup"] == 2
    assert report["results"][0]["regret"] == 0


def test_baseline_is_available_for_zero_budget_slowdowns_and_infeasibility():
    for budget, area_cap in ((0, None), (2, None), (2, 0)):
        report = evaluate_policies([row("a", speedup=.8), row("b", speedup=1)],
                                   budget, area_cap, policies=("random",))
        for result in report["results"] + [report["oracle"]]:
            assert result["selected"] is None
            assert result["best_speedup"] == 1
            assert result["regret"] == 0


def test_provenance_training_separation_and_malformed_labels():
    with pytest.raises(ValueError, match="sources"):
        SelectionTools([row("a"), dict(row("b"), measurement_source="hardware")], 1)
    with pytest.raises(ValueError, match="exclude"):
        SelectionTools([row("a")], 1, training_rows=[row("train")])
    with pytest.raises(ValueError, match="sources"):
        SelectionTools([row("a")], 1, training_rows=[dict(row("train", benchmark="other"),
                                                        measurement_source="hardware")])
    with pytest.raises(ValueError, match="source"):
        SelectionTools([dict(row("a"), measurement_source="claimed")], 1)
    tools = SelectionTools([row("a", speedup=float("nan"))], 1)
    with pytest.raises(ValueError, match="finite"):
        tools.measure("a")
    assert tools.measurements_used == 0
    with pytest.raises(ValueError, match="predict requires"):
        SelectionTools([row("a")], 1).predict()


def test_timing_provenance_rejects_inconsistent_speedup():
    measured = dict(row("a", speedup=2), baseline_cycles=10, candidate_cycles=10,
                    baseline_period_ns=1, candidate_period_ns=1)
    tools = SelectionTools([measured], 1)
    with pytest.raises(ValueError, match="timing"):
        tools.measure("a")
    assert tools.remaining_budget == 1


def test_timing_ratio_handles_extreme_finite_inputs_and_tiny_inconsistencies():
    measured = dict(row("a", speedup=2), baseline_cycles=1e300, candidate_cycles=1e-300,
                    baseline_period_ns=2e-300, candidate_period_ns=1e300)
    assert SelectionTools([measured], 1).measure("a")[0]["speedup"] == 2
    tiny = dict(row("a", speedup=1e-200), baseline_cycles=2e-200, candidate_cycles=1,
                baseline_period_ns=1, candidate_period_ns=1)
    with pytest.raises(ValueError, match="timing"):
        SelectionTools([tiny], 1).measure("a")


@pytest.mark.parametrize("budget", [-1, 1.5, True])
def test_invalid_budget_rejected(budget):
    with pytest.raises(ValueError, match="budget"):
        SelectionTools([row("a")], budget)


@pytest.mark.parametrize("seed", [-1, 1.5, True])
def test_invalid_seed_rejected(seed):
    with pytest.raises(ValueError, match="seed"):
        SelectionTools([row("a")], 1, seed=seed)


def test_overflowing_numeric_feature_has_a_clear_validation_error():
    with pytest.raises(ValueError, match="finite"):
        SelectionTools([dict(row("a"), runs=10**400)], 1)


def test_duplicate_ids_and_mixed_benchmarks_rejected():
    with pytest.raises(ValueError, match="duplicate"):
        SelectionTools([row("a"), row("a")], 1)
    with pytest.raises(ValueError, match="one target"):
        SelectionTools([row("a"), row("b", benchmark="other")], 1)


def test_training_rows_are_available_without_target_measurements():
    tools = SelectionTools([row("target")], 0, training_rows=[row("train", benchmark="other")])

    class InspectingPredictor:
        def __init__(self, seed):
            pass

        def fit(self, training):
            assert [r["candidate_id"] for r in training] == ["train"]
            return self

        def predict(self, candidates):
            assert "speedup" not in candidates[0]
            return [{"candidate_id": "target", "mean": 1.2, "upper": 1.3}]

    with patch("isaforge.model.SpeedupPredictor", InspectingPredictor):
        assert tools.predict()[0]["mean"] == 1.2
    assert tools.measurements_used == 0
