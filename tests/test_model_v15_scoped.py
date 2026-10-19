"""Fixed input-only V15 routing; synthetic frozen models, no inference/native jobs."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('model_v15_scoped', ROOT/'scripts/model_v15_scoped.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)


@pytest.fixture(autouse=True)
def forbid_jobs(monkeypatch):
    monkeypatch.setattr(subprocess, 'Popen', lambda *a, **k: pytest.fail('Native process forbidden'))
    monkeypatch.setattr(m.frozen, 'load_model', lambda *a, **k: pytest.fail('Actual model load forbidden'))
    monkeypatch.setattr(m.frozen.FeatureExtractor, 'matrix', lambda *a, **k: pytest.fail('Feature extraction forbidden'))


@pytest.mark.parametrize('formula', [
    'mul(in0,1)', 'mul(in1,2047)', 'mul(31,in0)', 'mul(in0,addi(0,7))', 'mul(addi(0,159),xor(in0,in1))',
    'xor(mul(in0,addi(0,47)),in1)', 'add(in0,mul(in1,127))',
])
def test_exact_positive_constant_low_multiply_coverage(formula):
    assert m.route(formula) == {'source_model': 'V9', 'coverage_classes': ['constant-low-multiply']}


@pytest.mark.parametrize('formula', [
    'mul(in0,in1)', 'mul(in0,-7)', 'mul(in0,0)', 'mul(in0,2048)', 'mul(in0,addi(0,-7))',
    'mul(in0,addi(0,0))', 'mul(in0,addi(0,2048))', 'mul(in0,addi(in1,7))',
    'mul(in0,add(3,4))', 'mul(in0,sub(8,1))', 'mul(in0,lui(1))',
    'mulh(in0,addi(0,7))', 'mulhu(in0,31)', 'mulhsu(in0,31)',
    'add(in0,in1)', 'xor(in0,in1)', 'srai(in0,31)', 'sub(in0,srai(in1,31))',
    'sub(srli(in0,2),srai(in1,31))', 'sub(srai(in0,32),srai(in1,31))',
    'sub(srai(in0,-1),srai(in1,31))', 'sub(srai(in0,2),srai(in1,30))',
    'sub(srai(7,2),srai(in1,31))', 'sub(srai(in0,2),srai(addi(0,7),31))',
])
def test_unsupported_negative_and_nonconstant_cases_fall_back(formula):
    assert m.route(formula) == {'source_model': 'V6', 'coverage_classes': []}


@pytest.mark.parametrize('formula', [
    'sub(srai(in0,0),srai(in0,31))', 'sub(srai(in0,31),srai(in1,31))',
    'sub(srai(add(in0,in1),2),srai(in1,31))',
    'sub(srai(xor(in0,in1),4),srai(sub(in0,in1),31))',
    'xor(sub(srai(in0,8),srai(in1,31)),in0)',
])
def test_signed_shift_coverage_allows_different_input_expressions(formula):
    assert m.route(formula) == {'source_model': 'V9', 'coverage_classes': ['signed-shift-difference']}


def test_both_classes_and_whitespace_use_original_ast():
    assert m.route(' sub( srai(mul(in0,7),2), srai(in1,31)) ') == {
        'source_model': 'V9', 'coverage_classes': ['constant-low-multiply', 'signed-shift-difference']}
    with pytest.raises(ValueError): m.route('evil(in0,7)')


def points(rows, value):
    return [dict({k: row[k] for k in ('candidate_id','formula','benchmark') if k in row}, predicted_lut4=float(value+i),
                 upper_lut4=None, calibration_status='uncalibrated', model='mapping_v6',
                 routed_expert='mapping_v6', tree_disagreement_lut4=.25,
                 outside_training_feature_ranges=i, uncertainty_scope='unchanged frozen metadata')
            for i, row in enumerate(rows)]


def test_selected_points_and_v6_fallback_are_exact_and_metadata_independent():
    rows = [{'candidate_id': 'a', 'formula': 'mul(in0,in1)', 'labels': 999},
            {'candidate_id': 'b', 'formula': 'mul(in0,31)', 'predictions': 999},
            {'candidate_id': 'c', 'formula': 'sub(srai(in0,2),srai(in1,31))', 'error': 999}]
    v6, v9 = points(rows, 10), points(rows, 20)
    selected, routes = m.combine_points(rows, v6, v9)
    assert selected == [v6[0], v9[1], v9[2]]
    assert [r['source_model'] for r in routes] == ['V6', 'V9', 'V9']
    for row in rows: row.update(labels=-1, predictions=-1, error=-1, candidate_id='changed')
    assert [m.route(row['formula']) for row in rows] == [{k:r[k] for k in ('source_model','coverage_classes')} for r in routes]
    selected[0]['predicted_lut4'] = 99
    assert v6[0]['predicted_lut4'] == 10


@pytest.mark.parametrize('poison', ['short', 'order', 'negative', 'nan', 'bool', 'calibrated'])
def test_combination_rejects_invalid_or_calibrated_points(poison):
    rows = [{'formula': 'add(in0,in1)'}, {'formula': 'mul(in0,7)'}]
    v6, v9 = points(rows, 1), points(rows, 2)
    if poison == 'short': v9.pop()
    elif poison == 'order': v9.reverse()
    elif poison == 'negative': v9[0]['predicted_lut4'] = -1
    elif poison == 'nan': v9[0]['predicted_lut4'] = float('nan')
    elif poison == 'bool': v9[0]['predicted_lut4'] = True
    else: v9[0]['calibration_status'] = 'calibrated'
    with pytest.raises(ValueError): m.combine_points(rows, v6, v9)


@pytest.fixture
def synthetic_pair(tmp_path, monkeypatch):
    monkeypatch.setattr(m, 'ROOT', tmp_path)
    definitions = {}; events = []
    rows = [{'candidate_id': 'a', 'formula': 'add(in0,in1)'}, {'candidate_id': 'b', 'formula': 'mul(in0,31)'}]
    for name, count in [('V6',1665), ('V9',1713)]:
        path = tmp_path/(name+'.joblib'); path.write_text('SYNTHETIC '+name)
        definitions[name] = (path.name, m.sha(path), count)
    monkeypatch.setattr(m, 'MODELS', definitions)
    def load(path):
        name = path.stem; events.append(('load',name))
        def predict(observed, x):
            events.append(('predict',name))
            assert observed == rows and x.shape == (2,336)
            result = points(rows, 10 if name == 'V6' else 20)
            # Frozen original-zero override is preserved, never recomputed by routing.
            result[0]['predicted_lut4'] = 0.
            return result
        return SimpleNamespace(kind='mapping_v6', training_formula_count=definitions[name][2],
                               calibration={'status':'uncalibrated','upper_margin_lut4':None},
                               frozen_tool={'version':'SYNTHETIC'}, predict_features=predict)
    monkeypatch.setattr(m.frozen, 'load_model', load)
    return rows, events


def test_exact_pair_no_fit_full336_and_original_zero_preserved(synthetic_pair):
    rows, events = synthetic_pair
    models, routes = m.predict_models(rows, np.zeros((2,336)))
    assert events == [('load','V6'),('predict','V6'),('load','V9'),('predict','V9')]
    assert models['V15'] == [models['V6'][0], models['V9'][1]] and models['V15'][0]['predicted_lut4'] == 0
    assert routes[0]['source_model'] == 'V6'


@pytest.mark.parametrize('poison', ['shape','nan','negative','artifact'])
def test_invalid_matrix_or_artifact_fails_before_model_prediction(synthetic_pair, poison):
    rows, events = synthetic_pair; x = np.zeros((2,336))
    if poison == 'shape': x = np.zeros((2,217))
    elif poison == 'nan': x[0,0] = float('nan')
    elif poison == 'negative': x[0,0] = -1
    else: (m.ROOT/'V6.joblib').write_text('POISON')
    with pytest.raises(ValueError): m.predict_models(rows, x)
    assert events == []


def test_cached_feature_cli_result_binds_inputs_gate_and_exact_points(synthetic_pair, tmp_path):
    rows, events = synthetic_pair
    row_path, feature_path, output = [tmp_path/name for name in ('rows.json','features.json','output.json')]
    row_path.write_text(json.dumps(rows))
    data = {'columns':list(m.frozen.columns()), 'records':[dict(row,values=[0.]*336) for row in rows]}
    feature_path.write_text(json.dumps(data))
    result = m.run(row_path, feature_path, output)
    assert result == json.loads(output.read_text())
    assert result['gate'] == m.GATE and result['rows_sha256'] == m.sha(row_path) and result['features_sha256'] == m.sha(feature_path)
    assert result['models']['V15'] == [result['models']['V6'][0],result['models']['V9'][1]]
    assert result['fits'] == result['native_jobs'] == result['calibration_jobs'] == 0
    with pytest.raises(ValueError, match='Fresh'): m.run(row_path,feature_path,output)


@pytest.mark.parametrize('poison', ['columns','order','id','width','bool'])
def test_cached_features_require_exact_original336_alignment(poison):
    rows = [{'candidate_id':'a','formula':'add(in0,in1)'}, {'candidate_id':'b','formula':'mul(in0,7)'}]
    data = {'columns':list(m.frozen.columns()), 'records':[dict(row,values=[0.]*336) for row in rows]}
    if poison == 'columns': data['columns'].reverse()
    elif poison == 'order': data['records'].reverse()
    elif poison == 'id': data['records'][0]['candidate_id'] = 'changed'
    elif poison == 'width': data['records'][0]['values'].pop()
    else: data['records'][0]['values'][0] = True
    with pytest.raises(ValueError): m.cached_matrix(rows,data)
