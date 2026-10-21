from scripts.report_feasible_benefit import first_reference_points


def test_baseline_reference_was_known_before_any_paid_query():
    runs=[dict(curve=[dict(best_speedup=1.0,budget=1,target_measurement_seconds=20)])]
    assert first_reference_points(runs,1.0)==[dict(budget=0,target_measurement_seconds=0.0)]


def test_first_improving_reference_keeps_paid_cost_and_missing_hits():
    first=dict(best_speedup=1.02,budget=2,target_measurement_seconds=40)
    runs=[dict(curve=[dict(best_speedup=1.0,budget=1,target_measurement_seconds=20),first]),
          dict(curve=[dict(best_speedup=1.0,budget=1,target_measurement_seconds=30)])]
    assert first_reference_points(runs,1.02)==[first,None]
