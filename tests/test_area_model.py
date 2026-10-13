"""Leakage barriers, model persistence, and formula-only LUT4 prediction."""
import json

import numpy as np
import pytest

from isaforge import area_model
from isaforge.area_model import (AREA_FEATURE_COLUMNS, area_feature_matrix, benchmark_split,
                                 evaluate_and_train, load_area_model, save_area_model, train_area_model)
from isaforge.features import IMMEDIATE_OPERATIONS, OPERATIONS, parse_formula
from isaforge.rtl import evaluate_formula


def fixture_rows():
    # Compact fixtures exercise contracts, not predictive performance evidence.
    rows = []
    for index, benchmark in enumerate(('a', 'b', 'c')):
        for offset in range(1, 5):
            rows.append({'benchmark': benchmark, 'candidate_id': f'{benchmark}-{offset}',
                         'formula': f'add(slli(in0,{offset+index*4}),in1)',
                         'lut4_count': 32 - offset - index*4, 'measurement_source': 'rtl_synthesis'})
        rows.append({'benchmark': benchmark, 'candidate_id': f'{benchmark}-zero',
                     'formula': f'xor(addi(in0,{index}),addi(in0,{index}))',
                     'lut4_count': 0, 'measurement_source': 'rtl_synthesis'})
    return rows


def test_features_ignore_measured_outcomes_and_trace_frequency():
    a = {'formula': 'add(slli(in0,2),in1)', 'lut4_count': 30, 'generic_cell_count': 151, 'runs': 8}
    b = {**a, 'lut4_count': 99999, 'generic_cell_count': -17, 'generic_logic_depth': 7, 'runs': 900000}
    np.testing.assert_array_equal(area_feature_matrix([a]), area_feature_matrix([b]))
    assert not any('lut' in name or 'generic' in name or 'runs' in name for name in AREA_FEATURE_COLUMNS)


def test_static_features_detect_constant_and_shared_logic():
    x = area_feature_matrix([{'formula': 'xor(addi(in0,1),addi(in0,1))'}])[0]
    feature = dict(zip(AREA_FEATURE_COLUMNS, x))
    assert feature['output_is_constant'] == 1
    assert feature['output_known_zero_bits'] == 32
    assert feature['repeated_subexpression_count'] == 1


def test_abstract_known_bits_are_sound_on_all_supported_operations():
    rng = np.random.default_rng(42)
    formulas = [f'{op}(4096)' if op == 'lui' else f'{op}(in0,-1)'
                if op in IMMEDIATE_OPERATIONS else f'{op}(in0,in1)' for op in OPERATIONS]
    formulas += ['sra(ori(in0,-2147483648),in1)', 'slt(andi(in0,31),32)',
                 'add(andi(in0,15),andi(in1,15))', 'sub(andi(in0,15),andi(in1,15))',
                 'srli(slli(sll(in0,addi(in1,-11)),12),12)']
    for formula in formulas:
        root = parse_formula(formula)
        zeros, ones = area_model._known_bits(root)
        assert zeros & ones == 0
        for a, b in rng.integers(0, 2**32, size=(100, 2), dtype=np.uint64):
            result = evaluate_formula(root, int(a), int(b))
            assert result & zeros == 0
            assert result & ones == ones


def test_split_excludes_identical_formulas_across_benchmarks():
    rows = fixture_rows()
    rows.append({**rows[0], 'benchmark': 'c', 'candidate_id': 'c-duplicate'})
    train, test, excluded = benchmark_split(rows, 'a')
    assert excluded == 1
    assert not {row['formula'] for row in train} & {row['formula'] for row in test}
    assert all(row['benchmark'] != 'a' for row in train)


@pytest.mark.parametrize('name', list(area_model.MODEL_CONFIGS))
def test_estimator_family_can_train_and_predict_nonnegative(name):
    model = train_area_model(fixture_rows(), name, 0)
    predictions = model.predict([{'formula': 'add(slli(in0,5),in1)'}])
    assert len(predictions) == 1
    assert np.isfinite(predictions[0]['predicted_lut4'])
    assert predictions[0]['predicted_lut4'] >= 0


def test_persisted_model_roundtrip_and_tamper_detection(tmp_path):
    rows = fixture_rows()
    model = train_area_model(rows, 'extra_trees_log', 0)
    paths = save_area_model(model, tmp_path)
    loaded = load_area_model(paths['model_path'])
    assert loaded.predict(rows) == model.predict(rows)
    schema = tmp_path / 'area-model.json'
    data = json.loads(schema.read_text())
    data['feature_columns'] = ['lut4_count']
    schema.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='schema'):
        load_area_model(paths['model_path'])


def test_nested_evaluation_and_final_fit_have_distinct_scopes(tmp_path, monkeypatch):
    monkeypatch.setattr(area_model, 'MODEL_CONFIGS', {
        name: options for name, options in area_model.MODEL_CONFIGS.items() if name in ('mean', 'ridge_log')})
    rows = fixture_rows()
    report = evaluate_and_train(rows, tmp_path)
    assert report['pooled_metrics']['sample_count'] == len(rows)
    assert report['pooled_metrics']['nonzero_lut4_metrics']['sample_count'] == 12
    assert len(report['folds']) == 3
    for fold in report['folds']:
        assert fold['held_out_benchmark'] not in fold['train_benchmarks']
        assert fold['held_out_benchmark'] not in {
            item['held_out_benchmark'] for item in fold['inner_selection']['folds']}
        assert fold['inner_selection']['selection_reason'] == 'minimum pooled inner benchmark-held-out RMSLE'
    final = load_area_model(report['model_path'])
    assert final.training_formula_count == len(rows)
    assert (tmp_path / 'evaluation.json').is_file()


def test_rejects_synthetic_or_inconsistent_labels():
    rows = fixture_rows()
    with pytest.raises(ValueError, match='rtl_synthesis'):
        train_area_model([{**rows[0], 'measurement_source': 'synthetic'}])
    with pytest.raises(ValueError, match='inconsistent'):
        train_area_model([rows[0], {**rows[0], 'benchmark': 'other', 'lut4_count': 800}])
    with pytest.raises(ValueError, match='nonnegative'):
        train_area_model([{**rows[0], 'lut4_count': -1}])
