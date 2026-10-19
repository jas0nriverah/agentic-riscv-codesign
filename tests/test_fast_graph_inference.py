"""Exact selected-channel adapter and strict-loader delegation contracts."""
from types import SimpleNamespace

import numpy as np
import pytest
from sklearn.ensemble import ExtraTreesRegressor

from isaforge import fast_graph_inference as fast


@pytest.fixture
def extraction(monkeypatch):
    calls = {'original': [], 'sog': []}
    class Graph:
        def __init__(self, cache, frozen_tool):
            self.tool = frozen_tool
        def _channel(self, formula):
            calls['original'].append(formula)
            return {'feature_values': list(range(1, len(fast.CHANNEL_COLUMNS)+1))}
        def extract(self, formula):
            pytest.fail('Normalization/dual extraction must never be called')
    class SOG:
        def __init__(self, cache, frozen_tool):
            assert frozen_tool['executable'] == 'yosys'
        def matrix(self, rows, workers):
            calls['sog'].extend(r['formula'] for r in rows)
            return np.full((len(rows), len(fast.SOG_COLUMNS)), 3.)
    monkeypatch.setattr(fast, 'GraphExtractor', Graph)
    monkeypatch.setattr(fast, 'SOGExtractor', SOG)
    monkeypatch.setattr(fast.v5, 'feature_dict', lambda *a: pytest.fail('Unused semantic features must not be computed'))
    return calls


def test_adapter_retains_every_selected_feature_and_zeros_only_unused_columns(extraction, tmp_path):
    captured = []
    def predict(rows, matrix):
        captured.append(matrix)
        return rows
    model = SimpleNamespace(view='original_graph', cache_root=str(tmp_path),
                            frozen_tool={'version': 'fixture'}, predict_features=predict)
    rows = [{'formula': 'add(in0,in1)'}, {'formula': ' add(in0, in1) ', 'lut4_count': float('nan')}]
    result = fast.FastOriginalGraphPredictor(model, workers=2).predict(rows)
    assert result == rows
    assert extraction['original'] == extraction['sog'] == ['add(in0,in1)']
    matrix = captured[0]
    assert matrix.shape == (2, len(fast.v5.columns()))
    assert np.array_equal(matrix[0], matrix[1])
    selected = fast.v5.view_indices('original_graph')
    unused = sorted(set(range(matrix.shape[1]))-set(selected))
    assert not matrix[:, unused].any()
    assert np.array_equal(matrix[0, :len(fast.SOG_COLUMNS)], np.full(len(fast.SOG_COLUMNS), 3.))
    assert np.array_equal(matrix[0, selected[len(fast.SOG_COLUMNS):]], np.arange(1, len(fast.CHANNEL_COLUMNS)+1))
    assert matrix[0, fast.v5.columns().index('original_gate_count')] == 1.


@pytest.mark.parametrize('view', ['sog_tuned', 'dual_graph', 'dual_semantics'])
def test_other_views_are_rejected(view):
    with pytest.raises(ValueError, match='only the frozen original_graph'):
        fast.FastOriginalGraphPredictor(SimpleNamespace(view=view))


@pytest.mark.parametrize('workers', [0, 5, True, 1.5])
def test_worker_contract(workers):
    with pytest.raises(ValueError, match='Workers must'):
        fast.FastOriginalGraphPredictor(SimpleNamespace(view='original_graph'), workers=workers)


def test_strict_loader_is_used_and_its_rejection_cannot_be_bypassed(monkeypatch):
    def reject(path, cache):
        raise ValueError('frozen source mismatch')
    monkeypatch.setattr(fast.v5, 'load_model', reject)
    with pytest.raises(ValueError, match='frozen source mismatch'):
        fast.load_model('model.joblib', 'cache')


def test_empty_rows_do_not_construct_hardware_extractors(monkeypatch):
    monkeypatch.setattr(fast, 'GraphExtractor', lambda *a, **k: pytest.fail('Empty rows must not extract'))
    assert fast.FastOriginalGraphPredictor(SimpleNamespace(view='original_graph')).predict([]) == []


def test_real_frozen_predictor_contract_preserves_upper_dispersion_domain_and_zero(extraction, monkeypatch, tmp_path):
    names = fast.v5.columns()
    indices = fast.v5.view_indices('original_graph')
    x = np.zeros((4, len(names)))
    x[:, 0] = [1, 2, 3, 4]
    x[:, names.index('original_gate_count')] = 1
    estimator = ExtraTreesRegressor(n_estimators=3, n_jobs=1, random_state=13)
    estimator.fit(x[:, indices], [4, 8, 12, 16])
    model = fast.v5.V5Predictor(estimator, 'original_graph', 'extra_leaf1', names, 4,
        {'upper_margin_lut4': 5., 'assumption': 'fixture'}, [0.]*len(names), [10.]*len(names),
        {'version': 'fixture'}, str(tmp_path))
    original_channel = fast.GraphExtractor._channel
    def channel(self, formula):
        return {'feature_values': [0.]*len(fast.CHANNEL_COLUMNS)} if formula == 'xor(in0,in0)' else original_channel(self, formula)
    monkeypatch.setattr(fast.GraphExtractor, '_channel', channel)
    rows = [{'benchmark': 'fixture', 'candidate_id': str(i), 'formula': f}
            for i, f in enumerate(('add(in0,in1)', 'xor(in0,in0)'))]
    full = np.full((2, len(names)), 1000000.)
    full[:, :len(fast.SOG_COLUMNS)] = 3.
    full[0, indices[len(fast.SOG_COLUMNS):]] = np.arange(1, len(fast.CHANNEL_COLUMNS)+1)
    full[1, indices[len(fast.SOG_COLUMNS):]] = 0.
    expected = model.predict_features(rows, full)
    actual = fast.FastOriginalGraphPredictor(model).predict(rows)
    assert actual == expected
    assert actual[1]['predicted_lut4'] == actual[1]['tree_disagreement_lut4'] == 0.
    assert actual[1]['upper_lut4'] == 5.
    assert actual[0]['outside_training_feature_ranges'] > 0


def test_cold_benchmark_cannot_reuse_existing_cache(tmp_path):
    with pytest.raises(ValueError, match='absent cache root'):
        fast.benchmark('model', 'candidates', 'expected', tmp_path)
