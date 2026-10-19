"""Independent synthetic trainer-boundary tests; no native tools or ML fits."""
from copy import deepcopy
from pathlib import Path
import sys

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import measure_v9_coverage as collector
import prepare_v9_coverage as preparer
import train_v9_coverage as trainer


def put(path, value):
    trainer.write(path, value)
    return path


def evidence(tmp_path, monkeypatch):
    root = tmp_path / 'prepared'
    root.mkdir()
    for name in ('preparation.json', 'recipe.json', 'candidates.json'):
        put(root / name, {'synthetic': name})
    stage = root / 'measurements/attempt-0000'
    stage.mkdir(parents=True)
    labels = [{'formula': f'coverage-{i}', 'lut4_count': i} for i in range(48)]
    put(stage / 'labels.json', labels)
    tool = {'version': 'synthetic-tool', 'executable_sha256': 'a'*64}
    done = {'schema': 'isaforge-v9-coverage-measurements-v1', 'complete': True, 'failures': [],
            'attempt': 'attempt-0000', 'candidate_count': 48, 'unique_original_formulas': 48,
            'preparation_sha256': trainer.sha(root/'preparation.json'),
            'recipe_sha256': trainer.sha(root/'recipe.json'),
            'candidates_sha256': trainer.sha(root/'candidates.json'), 'frozen_tool': tool,
            'verification_seed': 2026101519, 'vectors_per_formula': 2148, 'workers': 2,
            'original_rtl_only': True, 'legacy_measurements_reused': False,
            'new_estimator_fits': 0, 'new_physical_measurements': 48,
            'labels_sha256': trainer.sha(stage/'labels.json')}
    put(stage/'completion.json', done)
    put(root/'measurements/completion.json', done)
    put(root/'measurements/raw-evidence.json', {'synthetic': True})
    (root/'measurements/raw-evidence.zip').write_bytes(b'synthetic archive; verified separately by collector tests')
    monkeypatch.setattr(collector, 'verify_archive', lambda _: root/'measurements/raw-evidence.zip')
    review = {'measurement_completion_sha256': trainer.sha(root/'measurements/completion.json'),
              'labels_sha256': trainer.sha(stage/'labels.json')}
    return root, stage, {'frozen_tool': tool}, review, done, labels


def replace(path, value):
    path.unlink()
    put(path, value)


def test_valid_measurement_boundary_and_recheck_catches_later_mutation(tmp_path, monkeypatch):
    root, stage, recipe, review, _, expected = evidence(tmp_path, monkeypatch)
    labels, bindings = trainer.measurement_inputs(root, stage, recipe, review)
    assert labels == expected
    assert stage/'labels.json' in bindings
    (stage/'labels.json').write_text('[]\n')
    with pytest.raises(ValueError, match='changed during run'):
        trainer.recheck(bindings)


@pytest.mark.parametrize('field,value', [
    ('preparation_sha256', '0'*64), ('recipe_sha256', '0'*64), ('candidates_sha256', '0'*64),
    ('frozen_tool', {'version': 'other', 'executable_sha256': 'a'*64}),
    ('verification_seed', 1), ('vectors_per_formula', 2147), ('workers', 1),
    ('unique_original_formulas', 47), ('candidate_count', 47), ('new_physical_measurements', 47),
    ('original_rtl_only', False), ('legacy_measurements_reused', True), ('new_estimator_fits', 1),
    ('complete', 1), ('failures', [{'formula': 'failed'}])])
def test_measurement_identity_contract_rejects_wrong_evidence_before_archive(tmp_path, monkeypatch, field, value):
    root, stage, recipe, review, done, _ = evidence(tmp_path, monkeypatch)
    done[field] = value
    replace(stage/'completion.json', done)
    replace(root/'measurements/completion.json', done)
    review['measurement_completion_sha256'] = trainer.sha(root/'measurements/completion.json')
    monkeypatch.setattr(collector, 'verify_archive', lambda _: pytest.fail('Bad evidence reached archive stage'))
    with pytest.raises(ValueError):
        trainer.measurement_inputs(root, stage, recipe, review)


@pytest.mark.parametrize('field', ['measurement_completion_sha256', 'labels_sha256'])
def test_fit_release_cannot_substitute_other_measurements(tmp_path, monkeypatch, field):
    root, stage, recipe, review, _, _ = evidence(tmp_path, monkeypatch)
    review[field] = '0'*64
    with pytest.raises(ValueError, match='release must bind'):
        trainer.measurement_inputs(root, stage, recipe, review)


def test_stage_root_completion_and_path_are_both_required(tmp_path, monkeypatch):
    root, stage, recipe, review, done, _ = evidence(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match='Exact completed measurement stage'):
        trainer.measurement_inputs(root, root/'different-stage', recipe, review)
    changed = deepcopy(done);changed['workers'] = 1
    replace(stage/'completion.json', changed)
    with pytest.raises(ValueError, match='Stage/root'):
        trainer.measurement_inputs(root, stage, recipe, review)


def test_query_identity_in_scoring_includes_benchmark_and_candidate_id():
    rows = [{'formula': 'add(in0,in1)', 'benchmark': 'app', 'candidate_id': 'one'}]
    for field in ('benchmark', 'candidate_id'):
        prediction = {**rows[0], 'predicted_lut4': 32.}
        prediction[field] = 'wrong'
        with pytest.raises(ValueError, match='identity'):
            trainer.paired_metrics(rows, {'add(in0,in1)': 32}, {'frozen': [prediction]})


@pytest.mark.parametrize('fault', ['extra_prediction', 'duplicate_program_formula'])
def test_application_macro_rejects_extra_points_or_duplicate_formula_weights(fault):
    rows = [{'formula': 'add(in0,in1)', 'benchmark': 'app', 'candidate_id': 'one'},
            {'formula': 'sub(in0,in1)', 'benchmark': 'app', 'candidate_id': 'two'}]
    programs = [{'benchmark': 'app', 'family': 'F', 'primary_family': True}]
    points = {name: [{**row, 'predicted_lut4': 31.} for row in rows] for name in ('frozen', 'augmented')}
    if fault == 'extra_prediction':
        for values in points.values():
            values.append({'formula': 'xor(in0,in1)', 'benchmark': 'unknown', 'candidate_id': 'extra', 'predicted_lut4': 999.})
    else:
        duplicate = {**rows[0], 'candidate_id': 'duplicate'}
        rows.append(duplicate)
        for values in points.values():
            values.append({**duplicate, 'predicted_lut4': 31.})
    with pytest.raises(ValueError):
        trainer.application_metrics(rows, programs, {'add(in0,in1)': 32, 'sub(in0,in1)': 32}, points)


def mock_training_case(tmp_path, monkeypatch, corrupt_roundtrip=False):
    root, stage, recipe, review, _, _ = evidence(tmp_path, monkeypatch)
    fake_repo = tmp_path/'repository'
    fake_repo.mkdir()
    v8, v6 = fake_repo/'v8', fake_repo/'v6'
    monkeypatch.setattr(trainer, 'ROOT', fake_repo)
    monkeypatch.setattr(trainer, 'V8', v8)
    monkeypatch.setattr(trainer, 'V6', v6)
    candidates = [{'formula': f'coverage-{i}'} for i in range(48)]
    monkeypatch.setattr(preparer, 'validate_preparation', lambda _: ({}, recipe, candidates))
    original = {'columns': list(trainer.v8.columns()),
        'rows': [{'formula': f'old-{i}', 'lut4_count': 0} for i in range(1665)],
        'values': np.zeros((1665, 455)).tolist(), 'training_provenance': {'synthetic': True},
        'frozen_tool': recipe['frozen_tool']}
    put(v8/'training/training-data.json', original)
    artifact = v8/'baseline.joblib';artifact.write_bytes(b'synthetic baseline')
    put(v8/'point-freeze.json', {'models': {'mapping_v6': {
        'artifact': {'path': artifact.name, 'sha256': trainer.sha(artifact)},
        'predictions': {'path': 'frozen-points.json'}}}})
    app_rows = [{'formula': f'app-{i}', 'benchmark': 'app', 'candidate_id': str(i)} for i in range(152)]
    regression_rows = [{'formula': f'regression-{i}'} for i in range(192)]
    put(v8/'rows.json', app_rows)
    put(v8/'programs.json', [{'benchmark': 'app', 'family': 'F', 'primary_family': True}])
    put(v8/'features.json', {'columns': list(trainer.v8.columns()),
        'records': [{'formula': r['formula'], 'values': [0.]*455} for r in app_rows]})
    put(v6/'corpus/test/candidates.json', regression_rows)
    put(v6/'corpus/test/features.json', {'columns': list(trainer.v6.columns()),
        'records': [{'formula': r['formula'], 'values': [0.]*336} for r in regression_rows]})
    put(v8/'frozen-points.json', [{**r, 'predicted_lut4': 0.} for r in app_rows])
    state = {'fit_calls': 0, 'extract_calls': 0, 'read_paths': [], 'models': []}
    original_read = trainer.read
    def guarded_read(path):
        path = Path(path).resolve()
        state['read_paths'].append(path)
        if path.is_relative_to(v8/'measurements') or path.is_relative_to(v6/'corpus/test/attempt-0000'):
            pytest.fail('Historical evaluation targets were opened during train')
        return original_read(path)
    monkeypatch.setattr(trainer, 'read', guarded_read)
    class Extractor:
        def __init__(self, cache, **_):
            self.cache = cache
        def matrix(self, inputs, workers):
            state['extract_calls'] += 1
            assert inputs == candidates and workers == 2
            self.cache.mkdir(parents=True)
            return np.zeros((48, 336)), [{'formula': r['formula'], 'values': [0.]*336} for r in inputs]
    monkeypatch.setattr(trainer.v6, 'FeatureExtractor', Extractor)
    class Estimator:
        def __init__(self, **parameters):
            assert parameters == trainer.v6.FIXED_PARAMETERS
        def fit(self, x, y):
            state['fit_calls'] += 1
            assert (root/'fit-claim.json').exists()
            assert x.shape == (1713, 217) and y.shape == (1713,)
            assert np.array_equal(y[:1665], np.zeros(1665))
            assert np.array_equal(y[-48:], np.arange(48))
            return self  # A spy, never an actual ML fit.
    monkeypatch.setattr(trainer, 'ExtraTreesRegressor', Estimator)
    class Model:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)
            self.corrupt = False
        def predict_features(self, inputs, values):
            return [{**{k: r[k] for k in ('formula', 'benchmark', 'candidate_id') if k in r},
                     'predicted_lut4': 0., 'upper_lut4': None,
                     'tree_disagreement_lut4': 1. if self.corrupt else 0.} for r in inputs]
    baseline = Model(kind='mapping_v6', training_formula_count=1665,
                     training_provenance=original['training_provenance'], frozen_tool=recipe['frozen_tool'])
    monkeypatch.setattr(trainer.v6, 'V6Predictor', Model)
    def save(model, path):
        path.parent.mkdir(parents=True)
        path.write_bytes(b'synthetic augmented artifact')
        put(path.with_suffix('.json'), {})
        state['models'].append(model)
        return {'artifact': path, 'schema': path.with_suffix('.json')}
    def load(path):
        if Path(path) == artifact:
            return baseline
        model = deepcopy(state['models'][-1]);model.corrupt = corrupt_roundtrip
        return model
    monkeypatch.setattr(trainer.v6, 'save_model', save)
    monkeypatch.setattr(trainer.v6, 'load_model', load)
    review.update(status='approved-one-coverage-fit', preparation_sha256=trainer.sha(root/'preparation.json'),
                  training_runner_sha256=trainer.sha(trainer.__file__))
    review_path = put(root/'fit-review.json', review)
    return root, stage, review_path, state


def test_mock_fit_once_freezes_all_points_without_historical_targets(tmp_path, monkeypatch):
    root, stage, review, state = mock_training_case(tmp_path, monkeypatch)
    output = root/'fit-attempt-0000'
    result = trainer.train(root, stage, review, output)
    assert state['fit_calls'] == state['extract_calls'] == 1
    assert set(result) == {'applications', 'v6_test_regression', 'original_training_in_sample', 'coverage_training_in_sample'}
    assert len(result['applications']['augmented']) == 152
    assert len(result['v6_test_regression']['augmented']) == 192
    assert trainer.read(output/'point-freeze.json')['evaluation_target_files_opened'] is False
    with pytest.raises(ValueError, match='already claimed'):
        trainer.train(root, stage, review, root/'another-output')
    assert state['fit_calls'] == state['extract_calls'] == 1


def test_roundtrip_checks_diagnostics_and_retains_failed_single_fit_claim(tmp_path, monkeypatch):
    root, stage, review, state = mock_training_case(tmp_path, monkeypatch, corrupt_roundtrip=True)
    output = root/'fit-attempt-0000'
    with pytest.raises(ValueError, match='any field'):
        trainer.train(root, stage, review, output)
    assert state['fit_calls'] == 1
    assert (root/'fit-claim.json').exists()
    assert not (output/'point-freeze.json').exists()
    with pytest.raises(ValueError, match='already claimed'):
        trainer.train(root, stage, review, root/'another-output')
