"""V3 inference isolation, selection leakage, and artifact persistence contracts."""
import json
import os
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest

from isaforge.area_model_v3 import (CONFIG_GRID, FEATURE_COLUMNS, MODEL_CONFIG,
                                   develop_and_freeze, feature_matrix,
                                   load_area_model_v3, metrics, save_model,
                                   select_model, train_structural_resource,
                                   train_v3_model)
from isaforge.area_model import benchmark_split, _validated_rows


def rows():
    # Artificial labels exercise contracts, not claimed accuracy.
    pairs = [('add(in0,in1)', 61), ('addi(in0,1)', 31), ('xor(in0,in1)', 32),
             ('sll(in0,in1)', 155), ('sltu(in0,in1)', 32),
             ('mul(andi(in0,255),andi(in1,255))', 128),
             ('mul(andi(in0,65535),andi(in1,65535))', 512),
             ('mul(in0,3)', 45), ('xor(in0,in0)', 0)]
    return [{'benchmark': str(index % 3), 'candidate_id': str(index),
             'formula': formula, 'lut4_count': value, 'measurement_source': 'rtl_synthesis'}
            for index, (formula, value) in enumerate(pairs)]


def test_formula_only_features_and_prediction_ignore_poisoned_measurements():
    clean = {'formula': 'andi(srl(in0,in1),1)'}
    poison = {**clean, 'lut4_count': -1000, 'ice40_lut4_count': 100000,
              'generic_cell_count': 700, 'runs': 99999, 'saved': 900, 'benchmark': 'poison'}
    for feature_set in ('original', 'structural'):
        np.testing.assert_array_equal(feature_matrix([clean], feature_set), feature_matrix([poison], feature_set))
        model = train_v3_model(rows(), 'ridge_100', feature_set)
        assert model.predict([clean])[0]['predicted_lut4'] == model.predict([poison])[0]['predicted_lut4']
    assert feature_matrix([]).shape == (0, len(FEATURE_COLUMNS))


def test_resource_prior_and_bounded_residual_are_transparent_and_nonnegative():
    base = train_structural_resource(rows())
    assert np.all(base.coefficients >= 0)
    model = train_v3_model(rows(), 'huber_100', baseline=base)
    candidates = [{'formula': 'mul(in0,in1)'}, {'formula': 'add(in0,in1)'}]
    b = base.values(candidates)
    p = np.array([row['predicted_lut4'] for row in model.predict(candidates)])
    shift = np.log1p(p)-np.log1p(b)
    assert np.all(np.abs(shift) <= MODEL_CONFIG['residual_clip'][1]+1e-9)
    assert model.predict([]) == []
    assert len(CONFIG_GRID) == 6


@pytest.mark.parametrize('formula', ['mul(in0,8)', 'addi(in0,0)', 'xor(in0,in0)',
                                      'add(in0,in0)', 'sub(add(in0,in1),in1)'])
def test_proved_wiring_and_cancellation_have_zero_predicted_cost(formula):
    model = train_v3_model(rows(), 'ridge_10')
    assert model.predict([{'formula': formula}])[0]['predicted_lut4'] == 0


def test_distinct_formulas_get_one_fit_weight_and_labels_require_synthesis():
    data = rows()
    duplicate = {**data[0], 'benchmark': 'other'}
    a, b = train_structural_resource(data), train_structural_resource(data+[duplicate])
    np.testing.assert_array_equal(a.coefficients, b.coefficients)
    assert b.training_formula_count == len(data)
    with pytest.raises(ValueError, match='inconsistent'):
        train_v3_model(data+[{**duplicate, 'lut4_count': 700}])
    with pytest.raises(ValueError, match='rtl_synthesis'):
        train_v3_model([{**data[0], 'measurement_source': 'synthetic'}])


def test_mape_excludes_zero_and_reports_zero_false_predictions_separately():
    result = metrics([0, 0, 10, 20], [0, 3, 0, 30])
    assert result['nonzero_mape_percent'] == 75
    assert result['nonzero_lut4_metrics']['sample_count'] == 2
    assert result['zero_error_counts'] == {'true_zero_count': 2,
                                         'true_zero_predicted_nonzero_count': 1,
                                         'positive_true_predicted_zero_count': 1,
                                         'zero_mae_lut4': 1.5,
                                         'zero_max_predicted_lut4': 3.0}
    assert metrics([0], [0])['nonzero_mape_percent'] is None
    assert metrics([1], [1])['pearson'] is None


def test_inner_selection_excludes_program_and_matching_formulas():
    data = _validated_rows(rows()+[{**rows()[0], 'benchmark': 'other'}])
    seen = []

    class SpyModel:
        convergence_warning_count = 0
        def predict(self, validation):
            return [{'predicted_lut4': 0} for row in validation]

    class SpyFitter:
        def model(self, train, candidate, feature_set):
            seen.append((train, candidate, feature_set))
            return SpyModel()

    chosen, report = select_model(data, 'structural', SpyFitter())
    assert chosen == 'v2_resource'  # Same score => fixed simplicity ordering.
    assert len(seen) == 4 * len(CONFIG_GRID)
    for detail in report['folds']:
        train, validation, excluded = benchmark_split(data, detail['held_out_benchmark'])
        assert detail['excluded_matching_formula_rows'] == excluded
        assert not {row['formula'] for row in train} & {row['formula'] for row in validation}
        assert detail['held_out_benchmark'] not in {row['benchmark'] for row in train}
        assert set(detail['predictions']) == set(CONFIG_GRID)
        assert all(len(predictions) == len(validation) for predictions in detail['predictions'].values())


def test_roundtrip_and_reject_schema_source_and_artifact_tampering(tmp_path):
    model = train_v3_model(rows(), 'ridge_10')
    paths = save_model(model, tmp_path)
    loaded = load_area_model_v3(paths['model_path'])
    assert loaded.predict(rows()) == model.predict(rows())
    schema_path = Path(paths['schema_path'])
    schema = json.loads(schema_path.read_text())
    altered = json.loads(schema_path.read_text())
    altered['model_config']['residual_clip'] = [0, 0]
    schema_path.write_text(json.dumps(altered))
    with pytest.raises(ValueError, match='configuration mismatch'):
        load_area_model_v3(paths['model_path'])
    schema['runtime_source_sha256']['features.py'] = 'wrong'
    schema_path.write_text(json.dumps(schema))
    with pytest.raises(ValueError, match='dependency source'):
        load_area_model_v3(paths['model_path'])
    # Independent artifact hash failure occurs before source checks.
    Path(paths['model_path']).write_bytes(Path(paths['model_path']).read_bytes()+b'tampered')
    with pytest.raises(ValueError, match='artifact hash'):
        load_area_model_v3(paths['model_path'])


def test_cli_train_and_label_free_load_in_fresh_process(tmp_path):
    dataset = tmp_path/'rows.json'; dataset.write_text(json.dumps(rows()))
    output = tmp_path/'models'
    root = Path(__file__).resolve().parents[1]
    environment = {**os.environ, 'PYTHONPATH': str(root)}
    training = subprocess.run([sys.executable, '-m', 'isaforge.area_model_v3', 'train',
                               '--rows', str(dataset), '--output-dir', str(output)],
                              cwd=root, env=environment, capture_output=True, text=True)
    assert training.returncode == 0, training.stderr
    report = json.loads((output/'development-evaluation.json').read_text())
    assert report['unique_formula_count'] == len(rows())
    assert len(report['folds']) == 3
    assert 'DEVELOPMENT' in report['evaluation_status']
    assert set(report['artifacts']) == {'resource_v2', 'v1_xgboost_log', 'v2_residual_xgb', 'v3_original', 'v3_structural'}
    candidates = tmp_path/'candidates.json'; candidates.write_text(json.dumps([{'formula': 'add(in0,in1)'}]))
    predictions = tmp_path/'predictions.json'
    inference = subprocess.run([sys.executable, '-m', 'isaforge.area_model_v3', 'predict',
                                '--model', str(output/'area-model-v3.joblib'),
                                '--candidates', str(candidates), '--output', str(predictions)],
                               cwd=root, env=environment, capture_output=True, text=True)
    assert inference.returncode == 0, inference.stderr
    assert len(json.loads(predictions.read_text())) == 1
    assert type(load_area_model_v3(output/'area-model-v3.joblib')).__module__ == 'isaforge.area_model_v3'
    with pytest.raises(ValueError, match='already frozen'):
        develop_and_freeze(rows(), output)
