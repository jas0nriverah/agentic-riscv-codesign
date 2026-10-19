"""V5 inference contracts, group calibration and trusted artifact portability."""
import json
from pathlib import Path
import shutil

import joblib
import numpy as np
import pytest
from sklearn.ensemble import ExtraTreesRegressor

from isaforge import area_model_v5 as v5
from isaforge.area_model import _versions


def rows(count=2):
    return [{'benchmark': 'fixture', 'candidate_id': str(i), 'formula': 'add(in0,in1)'} for i in range(count)]


def matrix(count=2):
    x = np.zeros((count, len(v5.columns())))
    x[:, v5.columns().index('original_gate_count')] = 1
    return x


def predictor(*, view='dual_semantics', margin=5.):
    x = matrix(4)
    x[:, 0] = [1, 2, 3, 4]
    model = ExtraTreesRegressor(n_estimators=3, random_state=1, n_jobs=1)
    model.fit(x[:, v5.view_indices(view)], [4, 8, 12, 16])
    return v5.V5Predictor(model, view, 'extra_leaf1', v5.columns(), 4,
                          {'upper_margin_lut4': margin, 'assumption': 'fixture group exchangeability'},
                          [0.] * len(v5.columns()), [10.] * len(v5.columns()),
                          {'version': 'fixture', 'executable_sha256': 'f' * 64}, 'training-host/cache')


@pytest.fixture
def artifact(tmp_path):
    path = tmp_path / 'fixture.joblib'
    model = predictor()
    joblib.dump(model, path)
    schema = {'artifact_sha256': v5.sha(path), 'runtime_source_sha256': v5.source_hashes(),
              'versions': _versions(), 'feature_columns': list(v5.columns()), 'view': model.view,
              'configuration': model.configuration, 'frozen_tool': model.frozen_tool,
              'calibration': model.calibration, 'training_formula_count': model.training_formula_count}
    path.with_suffix('.json').write_text(json.dumps(schema))
    return path, schema


def test_feature_views_are_strictly_nested_controls():
    views = [set(v5.view_indices(view)) for view in v5.VIEWS]
    assert all(a < b for a, b in zip(views, views[1:]))
    assert views[-1] == set(range(len(v5.columns())))
    names = v5.columns()
    assert all(names[i].startswith(('sog_', 'original_')) for i in views[1])
    assert not any(names[i].startswith(('normalized_', 'absolute_channel_delta_')) for i in views[1])
    with pytest.raises(ValueError):
        v5.view_indices('invented')


def test_upper_margin_uses_whole_group_maxima_without_row_weighting():
    truth = [100.] * 30 + list(range(1, 9))
    groups = ['large'] * 30 + [f'g{i}' for i in range(8)]
    result = v5.group_upper_margin(truth, np.zeros(len(truth)), groups, alpha=.3)
    assert result['group_count'] == 9
    assert result['rank'] == 7
    assert result['upper_margin_lut4'] == 7


def test_upper_margin_is_unbounded_when_finite_sample_rank_exceeds_groups():
    result = v5.group_upper_margin([5.] * 8, [1.] * 8, [str(i) for i in range(8)], alpha=.1)
    assert result['rank'] == 9 and result['upper_margin_lut4'] is None
    enough = v5.group_upper_margin([5.] * 9, [1.] * 9, [str(i) for i in range(9)], alpha=.1)
    assert enough['rank'] == 9 and enough['upper_margin_lut4'] == 4
    overestimates = v5.group_upper_margin([1.] * 9, [5.] * 9, [str(i) for i in range(9)], alpha=.1)
    assert overestimates['upper_margin_lut4'] == 0


@pytest.mark.parametrize('truth, predictions, groups', [
    ([float('nan')], [0.], ['g']), ([1.], [float('inf')], ['g']),
    ([-1.], [0.], ['g']), ([1.], [-1.], ['g']),
    ([True], [0.], ['g']), ([1.], [False], ['g']),
    ([1.], [0.], ['']), ([1.], [0.], [None]),
    ([True, 1.], [0., 0.], ['g', 'h']), ([1., 1.], [0., 0.], ['g', 1]),
])
def test_invalid_calibration_values_are_rejected(truth, predictions, groups):
    with pytest.raises(ValueError):
        v5.group_upper_margin(truth, predictions, groups)


def test_original_implementation_zero_override_ignores_semantic_zero():
    model = predictor()
    x = matrix()
    x[0, v5.columns().index('original_gate_count')] = 0
    x[0, v5.columns().index('normalized_gate_count')] = 99
    x[1, v5.columns().index('normalized_gate_count')] = 0
    result = model.predict_features(rows(), x)
    assert result[0]['predicted_lut4'] == result[0]['tree_disagreement_lut4'] == 0
    assert result[1]['predicted_lut4'] > 0
    assert result[1]['upper_lut4'] == result[1]['predicted_lut4'] + 5


def test_domain_warning_uses_only_selected_feature_view():
    model = predictor(view='sog_tuned', margin=None)
    x = matrix()
    unused = v5.columns().index('normalized_gate_count')
    x[0, unused] = 100000
    x[1, 0] = 100000
    result = model.predict_features(rows(), x)
    assert result[0]['outside_training_feature_ranges'] == 0
    assert result[1]['outside_training_feature_ranges'] == 1
    assert all(r['upper_lut4'] is None for r in result)
    assert all('exchangeability' in r['uncertainty_scope'] for r in result)


@pytest.mark.parametrize('bad', [float('nan'), float('inf'), -1.])
def test_invalid_inference_features_are_rejected(bad):
    x = matrix()
    x[:, 0] = bad
    with pytest.raises(ValueError):
        predictor().predict_features(rows(), x)


@pytest.mark.parametrize('bad', [float('nan'), float('inf'), -1.])
def test_invalid_upper_margins_are_rejected(bad):
    with pytest.raises(ValueError):
        predictor(margin=bad).predict_features(rows(), matrix())


def test_feature_extraction_ignores_labels_and_retains_portable_sog_context(monkeypatch, tmp_path):
    seen = []

    class Graph:
        def __init__(self, cache, *, frozen_tool=None):
            self.cache_dir = Path(cache)
            self.tool = {'version': 'fixture', 'executable_sha256': 'f' * 64}

        def matrix(self, candidate_rows, workers):
            features = np.zeros((len(candidate_rows), len(v5.GRAPH_COLUMNS)))
            return features, [{'formula': r['formula'], 'normalized_formula': r['formula'],
                               'cache_hit': True, 'original': {'cache_key': 'original'},
                               'normalized': {'cache_key': 'normalized'}} for r in candidate_rows]

    class SOG:
        def __init__(self, cache, *, frozen_tool=None):
            self.cache_dir = Path(cache)
            seen.append(frozen_tool)

        def key(self, formula):
            return formula, 'sog'

        def matrix(self, candidate_rows, workers):
            return np.zeros((len(candidate_rows), len(v5.SOG_COLUMNS)))

    monkeypatch.setattr(v5, 'GraphExtractor', Graph)
    monkeypatch.setattr(v5, 'SOGExtractor', SOG)
    monkeypatch.setattr(v5, 'feature_dict', lambda formula: dict.fromkeys(v5.FEATURE_NAMES, 0.))
    monkeypatch.setattr(v5, 'sha', lambda path: 'fixture-manifest-hash')
    clean = rows(1)[0]
    poisoned = {**clean, 'benchmark': 'other', 'candidate_id': 'other', 'lut4_count': float('nan'),
                'carry_count': 9999, 'correctness_verified': False, 'speedup': -1, 'stratum': 'other'}
    a, records_a = v5.FeatureExtractor(tmp_path / 'train').matrix([clean])
    b, records_b = v5.FeatureExtractor(tmp_path / 'replay', frozen_tool={'version': 'fixture', 'executable_sha256': 'f' * 64}).matrix([poisoned])
    assert np.array_equal(a, b)
    assert records_a == records_b
    assert not {'lut4_count', 'carry_count', 'correctness_verified', 'speedup', 'stratum'} & set(records_a[0])
    assert seen[0] == seen[1]
    assert seen[0]['executable'] == 'yosys'


def test_real_trusted_artifact_load_preserves_predictions_and_overrides_cache(artifact, tmp_path):
    path, _ = artifact
    original = joblib.load(path)
    loaded = v5.load_model(path, tmp_path / 'restored')
    assert loaded.predict_features(rows(), matrix()) == original.predict_features(rows(), matrix())
    assert loaded.cache_root == str((tmp_path / 'restored').resolve())
    assert v5.load_model(path).cache_root == str(path.parent / 'cache')


@pytest.mark.skipif(shutil.which('yosys') is None, reason='Yosys is not installed')
def test_actual_both_channel_cache_relocation_needs_no_yosys(monkeypatch, tmp_path):
    import isaforge.graph_features_v5 as graph_module
    import isaforge.masterrtl_baseline as sog_module

    inputs = [rows(1)[0], {**rows(1)[0], 'candidate_id': 'zero', 'formula': 'xor(in0,in0)'}]
    extractor = v5.FeatureExtractor(tmp_path / 'training')
    expected, _ = extractor.matrix(inputs, workers=1)
    moved = tmp_path / 'relocated'
    shutil.copytree(extractor.cache_root, moved)

    def absent(*args, **kwargs):
        raise RuntimeError('No Yosys available in relocated environment')

    monkeypatch.setattr(graph_module, 'tool_identity', absent)
    monkeypatch.setattr(sog_module, 'tool_identity', absent)
    restored = v5.FeatureExtractor(moved, frozen_tool=extractor.graph.tool)
    actual, _ = restored.matrix(inputs, workers=1)
    np.testing.assert_array_equal(actual, expected)
    model = predictor()
    model.frozen_tool = extractor.graph.tool
    model.cache_root = str(moved)
    predictions = model.predict(inputs)
    assert predictions == model.predict_features(inputs, expected)
    assert predictions[1]['predicted_lut4'] == 0


@pytest.mark.parametrize('field', ['artifact_sha256', 'runtime_source_sha256', 'versions'])
def test_source_artifact_environment_mismatch_rejected_before_unpickling(artifact, monkeypatch, field):
    path, schema = artifact
    schema[field] = 'tampered' if field == 'artifact_sha256' else {'tampered': 'value'}
    path.with_suffix('.json').write_text(json.dumps(schema))
    monkeypatch.setattr(joblib, 'load', lambda *a: pytest.fail('Mismatch must be rejected before unpickling'))
    with pytest.raises(ValueError):
        v5.load_model(path)


@pytest.mark.parametrize('field, value', [
    ('feature_columns', ['invented']), ('view', 'sog_tuned'), ('configuration', 'xgb_raw_d3'),
    ('training_formula_count', 999), ('calibration', {'upper_margin_lut4': 999., 'assumption': 'invented'}),
    ('frozen_tool', {'version': 'different', 'executable_sha256': 'different'}),
])
def test_schema_and_artifact_metadata_mismatch_rejected(artifact, field, value):
    path, schema = artifact
    schema[field] = value
    path.with_suffix('.json').write_text(json.dumps(schema))
    with pytest.raises(ValueError):
        v5.load_model(path)
