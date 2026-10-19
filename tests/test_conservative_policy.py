from copy import deepcopy
import math

import pytest

from isaforge.conservative_policy import calibrate, apply_margin


def fixtures():
    train = [dict(benchmark='train', candidate_id='t', formula='add(in0,in1)', lut4_count=32, measurement_source='rtl_synthesis')]
    rows = [dict(benchmark='cal', candidate_id=str(i), formula=f'addi(in0,{i})', lut4_count=i,
                 measurement_source='rtl_synthesis') for i in range(1, 11)]
    predictions = [{**r, 'predicted_lut4': 2 * (r['lut4_count'] + 1) - 1} for r in rows]
    return train, rows, predictions


def test_one_sided_log_margin_preserves_identity_and_point_prediction():
    calibration = calibrate(*fixtures())
    assert calibration['calibration_novel_formula_count'] == 10
    assert calibration['log_overprediction_margin'] == pytest.approx(math.log(2))
    pred = [dict(benchmark='test', candidate_id='x', formula='xor(in0,in1)', predicted_lut4=21)]
    result = apply_margin(pred, calibration)
    assert result[0]['predicted_lut4'] == pytest.approx(10)
    assert result[0]['point_predicted_lut4'] == 21
    assert result[0]['candidate_id'] == 'x'
    assert pred[0]['predicted_lut4'] == 21


def test_training_duplicates_cannot_calibrate_margin():
    train, rows, pred = fixtures()
    rows.append({**train[0], 'benchmark': 'cal'})
    pred.append({**rows[-1], 'predicted_lut4': 1e20})
    assert calibrate(train, rows, pred)['log_overprediction_margin'] == pytest.approx(math.log(2))


def test_incomplete_or_wrong_calibration_predictions_rejected():
    train, rows, pred = fixtures()
    with pytest.raises(ValueError): calibrate(train, rows, pred[:-1])
    pred[0]['formula'] = 'xor(in0,in1)'
    with pytest.raises(ValueError): calibrate(train, rows, pred)


def test_underprediction_cannot_increase_rejection_score():
    train, rows, pred = fixtures()
    for r in pred: r['predicted_lut4'] = 0
    result = calibrate(train, rows, pred)
    assert result['log_overprediction_margin'] == 0
