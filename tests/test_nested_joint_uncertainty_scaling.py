import pytest

from scripts import audit_joint_posterior_calibration as prior
from scripts import audit_nested_joint_uncertainty_scaling as audit
from isaforge import codesign as c, speedup_corpus


def test_variance_scale_weights_workload_groups_equally():
    groups = {}
    for index in range(5):
        groups[f"g{index}"] = {
            prefix: {
                output: ([2.0, 2.0] if index == 0 and output == "area_delta_lut4"
                         and prefix == 0 else [1.0])
                for output in audit.OUTPUTS
            }
            for prefix in audit.PREFIXES
        }

    scales = audit.variance_scales(groups, minimum_groups=5)

    # Equal-group E[z^2] = (4 + 1 + 1 + 1 + 1) / 5. A flat candidate
    # average would incorrectly give the two observations in g0 extra weight.
    assert scales[0]["area_delta_lut4"] == pytest.approx(1.6)
    assert scales[1]["area_delta_lut4"] == pytest.approx(1.0)
    assert scales[0]["routed_fmax_min_mhz"] == pytest.approx(1.0)


def test_variance_scaling_changes_z_by_square_root_not_direct_factor():
    records = [dict(workload_group="g", attempt_index=0,
        calibration_variance_scale_by_output={output: 4.0 for output in audit.OUTPUTS},
        **{output: dict(residual=4.0, predictive_std=2.0) for output in audit.OUTPUTS})]

    base = audit._coverage(records, "base")["area_delta_lut4"]
    calibrated = audit._coverage(records, "nested_calibrated")["area_delta_lut4"]

    assert base["standardized_rmse"] == pytest.approx(2.0)
    assert calibrated["standardized_rmse"] == pytest.approx(1.0)


def test_outer_and_inner_workload_and_family_exclusions_are_enforced():
    corpus, successes, failures, _ = prior._read_corpus(
        audit.ROOT / "results/2026-10-26-lift-selection-corpus/corpus.json")
    for group in corpus["independent_workload_groups"]:
        training, target, target_failures, families, outer_failures = audit.split_outer(
            successes, failures, group)
        training_groups = {row["workload_group"] for row in training}
        target_families = {speedup_corpus.family(row["formula"])
                           for row in [*target, *target_failures]}
        assert group not in training_groups
        assert not target_families.intersection(
            speedup_corpus.family(row["formula"]) for row in training)
        assert all(row["workload_group"] != group for row in outer_failures)
        assert all(speedup_corpus.family(row["formula"]) not in set(families)
                   for row in outer_failures)


def test_nested_calibration_fit_excludes_both_outer_and_inner_groups():
    corpus, successes, failures, _ = prior._read_corpus(
        audit.ROOT / "results/2026-10-26-lift-selection-corpus/corpus.json")
    outer = "embench-crc32"
    training, target, target_failures, outer_families, outer_failures = audit.split_outer(
        successes, failures, outer)
    _, group_z, inner_folds, fit_count = audit.calibration_for_outer(
        successes, failures, outer, training, outer_failures)
    formula_by_id = {row["candidate_id"]: row["formula"] for row in
                     [*successes, *failures]}
    outer_ids = {row["candidate_id"] for row in [*target, *target_failures]}

    assert fit_count == len(inner_folds)
    assert set(group_z) == {row["workload_group"] for row in inner_folds}
    for inner in inner_folds:
        train_ids = set(inner["training_ids"])
        target_ids = set(inner["attempt_ids"])
        train_families = {speedup_corpus.family(formula_by_id[identity])
                          for identity in train_ids}
        heldout_families = {speedup_corpus.family(formula_by_id[identity])
                            for identity in target_ids}
        assert not outer_ids.intersection(train_ids)
        assert not target_ids.intersection(train_ids)
        assert not set(outer_families).intersection(train_families)
        assert not heldout_families.intersection(train_families)
        assert inner["workload_group"] != outer


def test_variance_calibration_fails_closed_on_too_few_groups():
    only_four = {
        f"g{index}": {prefix: {output: [1.0] for output in audit.OUTPUTS}
                       for prefix in audit.PREFIXES}
        for index in range(4)
    }
    with pytest.raises(ValueError, match="Insufficient independent calibration groups"):
        audit.variance_scales(only_four, minimum_groups=5)


def test_paired_bootstrap_resamples_whole_workloads_deterministically():
    group_brier = {
        "a": dict(n=2, base=0.3, nested_calibrated=0.2),
        "b": dict(n=10, base=0.2, nested_calibrated=0.4),
        "c": dict(n=3, base=0.4, nested_calibrated=0.1),
    }

    first = audit.paired_group_bootstrap(group_brier, iterations=100, seed=5)
    second = audit.paired_group_bootstrap(group_brier, iterations=100, seed=5)

    assert first == second
    assert first["unit"] == "whole workload group"
    assert first["macro"]["point_estimate"] == pytest.approx(-1/15)
