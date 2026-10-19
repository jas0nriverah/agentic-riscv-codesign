"""Frozen fitting-fold isolation and correct macro weighting for V6 diagnostics."""
import importlib.util
from pathlib import Path

import numpy as np
import pytest

SCRIPT = Path(__file__).resolve().parents[1]/'scripts/develop_v6.py'
spec = importlib.util.spec_from_file_location('develop_v6', SCRIPT)
dev = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dev)


def test_fold_plan_excludes_nonfitting_calibration_rows_and_preserves_components():
    fit = [0, 2, 4, 6, 8, 10]
    validation = [[0, 2], [4], [6], [8], [10]]
    groups = {0: 'shared', 2: 'shared', 4: 'a', 6: 'b', 8: 'c', 10: 'd'}
    plan = dev.fold_plan(fit, validation, groups)
    assert len(plan) == 5
    for train, valid in plan:
        assert set(train) | set(valid) == set(range(len(fit)))
        assert not set(train) & set(valid)
        assert 1 not in {fit[i] for i in train} | {fit[i] for i in valid}


def test_component_crossing_fold_is_rejected():
    with pytest.raises(ValueError, match='Component crosses'):
        dev.fold_plan([0, 1, 2, 3, 4], [[0], [1], [2], [3], [4]],
                      {0: 'same', 1: 'same', 2: 'a', 3: 'b', 4: 'c'})


@pytest.mark.parametrize('folds', [
    [[0], [1], [2], [3], [99]], [[0], [1], [2], [3], [3, 4]],
    [[0], [1], [2], [3], []], [[0], [1], [2], [3, 4]],
])
def test_misdeclared_or_calibration_contaminated_validation_partition_is_rejected(folds):
    with pytest.raises(ValueError):
        dev.fold_plan([0, 1, 2, 3, 4], folds, dict(enumerate('abcde')))


def test_macro_metric_retains_balanced_stratum_weight_and_signed_bias():
    score = dev.metrics(np.array([10., 10., 100.]), np.array([10., 10., 70.]),
                        np.array(['many', 'many', 'rare']))
    assert score['mae_lut4'] == 10.
    assert score['macro_stratum_mae_lut4'] == 15.
    assert score['by_stratum']['rare']['signed_bias_lut4'] == -30.
    assert score['by_stratum']['rare']['maximum_underprediction_lut4'] == 30.
    assert score['by_stratum']['many']['exact_prediction_count'] == 2


def test_repository_result_destination_is_forbidden():
    with pytest.raises(ValueError, match='outside the frozen repository'):
        dev.run(dev.ROOT/'results/2026-10-14-v5', dev.ROOT/'generated/v6-diagnostics')
