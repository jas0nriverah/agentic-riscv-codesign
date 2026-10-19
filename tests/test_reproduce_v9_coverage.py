"""Synthetic replay/write-boundary and evidence integrity tests; no real targets."""
from copy import deepcopy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import zipfile
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('reproduce_v9_coverage', ROOT / 'scripts/reproduce_v9_coverage.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)


def evaluation():
    return {'evaluated_at_utc': '2026-10-15T10:00:00+00:00', 'scope': 'synthetic-only',
            'primary': {'by_program': {'app': {'frozen': {'rmsle': .1, 'mae_lut4': 1.5, 'count': 2}}}}}


def test_only_declared_rmsle_roundoff_and_timestamp_are_accepted():
    ref = evaluation(); actual = deepcopy(ref)
    actual['evaluated_at_utc'] = '2026-10-15T11:00:00+00:00'
    actual['primary']['by_program']['app']['frozen']['rmsle'] = math.nextafter(.1, math.inf)
    result = m.compare_evaluation(ref, actual)
    assert result['status'] == 'pass' and result['accepted_rmsle_roundoff_count'] == 1
    for key, value in [('mae_lut4', math.nextafter(1.5, math.inf)), ('count', 2.), ('rmsle', .1 + 2e-14)]:
        changed = deepcopy(ref); changed['primary']['by_program']['app']['frozen'][key] = value
        assert m.compare_evaluation(ref, changed)['status'] == 'fail'
    changed = deepcopy(ref); changed['scope'] = 'different'
    assert m.compare_evaluation(ref, changed)['status'] == 'fail'


@pytest.mark.parametrize('path', [('provenance', 'rmsle'), ('primary', 'rmsle')])
def test_unknown_rmsle_fields_remain_exact(path):
    ref = evaluation(); actual = deepcopy(ref)
    ref[path[0]] = {path[1]: .1}; actual[path[0]] = {path[1]: math.nextafter(.1, math.inf)}
    assert m.compare_evaluation(ref, actual)['status'] == 'fail'


def test_frozen_arithmetic_writer_can_only_write_fresh_evaluation(tmp_path, monkeypatch):
    fit = tmp_path / 'fit'; fit.mkdir(); output = tmp_path / 'fresh'; output.mkdir()
    published = fit / 'evaluation.json'; published.write_text('preserve frozen result')
    def scoring(root, measurements, given_fit):
        assert given_fit == fit
        m.trainer.write(fit / 'evaluation.json', {'synthetic': True})
        return {'synthetic': True}
    monkeypatch.setattr(m.trainer, 'score', scoring)
    assert m.score_to_fresh(tmp_path, fit, tmp_path, output) == {'synthetic': True}
    assert published.read_text() == 'preserve frozen result'
    assert json.loads((output / 'evaluation.json').read_text()) == {'synthetic': True}
    monkeypatch.setattr(m.trainer, 'score', lambda *args: m.trainer.write(fit / 'other.json', {}))
    with pytest.raises(ValueError, match='Unexpected frozen scorer write'):
        m.score_to_fresh(tmp_path, fit, tmp_path, output)
    assert not (fit / 'other.json').exists()


def test_fit_extraction_normalization_and_native_processes_are_blocked():
    from sklearn.ensemble import ExtraTreesRegressor
    from isaforge import semantic_features_v7
    with m.no_fit_or_native():
        for action in [lambda: ExtraTreesRegressor().fit([[0]], [0]),
                       lambda: m.v6.FeatureExtractor.matrix(None, []),
                       lambda: semantic_features_v7.analyze_modes('add(in0,in1)'),
                       lambda: subprocess.run(['a-native-program-that-must-never-run'])]:
            with pytest.raises(RuntimeError, match='Reproduction forbids'):
                action()


@pytest.fixture
def replay(tmp_path, monkeypatch):
    root = tmp_path / 'evidence'; fit = root / 'fit-attempt-0000'; fit.mkdir(parents=True)
    (root / 'preparation.json').write_text('{}')
    (fit / 'point-freeze.json').write_text('{}')
    ref = evaluation(); (fit / 'evaluation.json').write_text(json.dumps(ref))
    sentinel = root / 'bound.txt'; sentinel.write_text('frozen')
    actual = deepcopy(ref); actual['evaluated_at_utc'] = '2026-10-15T11:00:00+00:00'
    calls = []
    def auth(*args):
        calls.append('authenticate')
        return {'reference': ref, 'measurements': root / 'measurements',
                'bindings': {sentinel: m.sha(sentinel)}, 'feature_archive_members': 2}
    def infer(*args): calls.append('infer'); return {'all_prediction_fields_and_json_types_exact': True}
    def score(root, fit, measurements, output):
        calls.append('score'); m.write(output / 'evaluation.json', actual); return actual
    def audits(*args): calls.append('audit'); return {'independent_metrics_passed': True}
    monkeypatch.setattr(m, 'authenticate', auth); monkeypatch.setattr(m, 'replay_inference', infer)
    monkeypatch.setattr(m, 'score_to_fresh', score); monkeypatch.setattr(m, 'run_audits', audits)
    return root, fit, tmp_path / 'fresh', ref, actual, calls, sentinel


def test_complete_replay_order_and_original_preservation(replay):
    root, fit, output, _, _, calls, sentinel = replay
    before = (fit / 'evaluation.json').read_bytes()
    report = m.reproduce(root, output, fit=fit, skip_figures=True)
    assert report['status'] == 'pass' and report['new_fits'] == report['new_feature_extractions'] == 0
    assert calls == ['authenticate', 'infer', 'score', 'audit']
    assert (fit / 'evaluation.json').read_bytes() == before and sentinel.read_text() == 'frozen'
    assert json.loads((output / 'reproduction.json').read_text()) == report


def test_authentication_failure_precedes_output_or_inference(replay, monkeypatch):
    root, fit, output, _, _, calls, _ = replay
    monkeypatch.setattr(m, 'authenticate', lambda *args: (_ for _ in ()).throw(ValueError('bound source changed')))
    with pytest.raises(ValueError, match='bound source'):
        m.reproduce(root, output, fit=fit, skip_figures=True)
    assert not calls and not output.exists()


def test_real_metric_mismatch_is_retained_and_blocks_success_and_audits(replay):
    root, fit, output, _, actual, calls, _ = replay
    actual['primary']['by_program']['app']['frozen']['mae_lut4'] += 1.
    with pytest.raises(ValueError, match='Frozen arithmetic differs'):
        m.reproduce(root, output, fit=fit, skip_figures=True)
    assert 'audit' not in calls and not (output / 'reproduction.json').exists()
    assert json.loads((output / 'comparison.json').read_text())['incompatible_difference_count'] == 1


def test_existing_output_and_result_destination_are_rejected_without_reads(replay):
    root, fit, output, _, _, calls, _ = replay
    output.mkdir()
    with pytest.raises(ValueError, match='fresh'):
        m.reproduce(root, output, fit=fit, skip_figures=True)
    with pytest.raises(ValueError, match='outside results'):
        m.reproduce(root, root / 'another-result', fit=fit, skip_figures=True)
    assert not calls


def test_optional_figure_receives_validated_evidence_and_fresh_output(replay, monkeypatch):
    root, fit, output, _, _, _, _ = replay; calls = []
    monkeypatch.setitem(sys.modules, 'plot_v9_coverage', SimpleNamespace(run=lambda *a: calls.append(a)))
    assert m.reproduce(root, output, fit=fit)['figures_generated']
    assert calls == [(root, fit, output / 'figures')]


@pytest.fixture
def feature_archive(tmp_path):
    data = b'synthetic cached graph'; name = 'generic/key/graph.json'
    archive = tmp_path / 'feature-evidence.zip'
    with zipfile.ZipFile(archive, 'w') as z: z.writestr(name, data)
    manifest = {'archive': archive.name, 'sha256': m.sha(archive), 'files': [
        {'path': name, 'size': len(data), 'sha256': hashlib.sha256(data).hexdigest()}]}
    (tmp_path / 'feature-evidence.json').write_text(json.dumps(manifest))
    return tmp_path, manifest


def test_feature_archive_authenticates_member_bytes_after_outer_hash_update(feature_archive):
    fit, manifest = feature_archive
    assert m.verify_feature_archive(fit) == 1
    archive = fit / 'feature-evidence.zip'
    with zipfile.ZipFile(archive, 'w') as z: z.writestr(manifest['files'][0]['path'], b'corrupt')
    manifest['sha256'] = m.sha(archive); (fit / 'feature-evidence.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match='member differs'): m.verify_feature_archive(fit)


def test_feature_archive_rejects_traversal_even_with_consistent_hashes(feature_archive):
    fit, manifest = feature_archive; name = '../outside'; data = b'synthetic cached graph'
    with zipfile.ZipFile(fit / 'feature-evidence.zip', 'w') as z: z.writestr(name, data)
    manifest['files'][0]['path'] = name; manifest['sha256'] = m.sha(fit / 'feature-evidence.zip')
    (fit / 'feature-evidence.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match='Unsafe'): m.verify_feature_archive(fit)


def test_all_four_saved_feature_cohorts_compare_diagnostics_too(tmp_path, monkeypatch):
    root = tmp_path / 'evidence'; fit = root / 'fit'; fit.mkdir(parents=True)
    v8_root = tmp_path / 'v8'; v8_root.mkdir(); v6_root = tmp_path / 'v6'; (v6_root / 'corpus/test').mkdir(parents=True)
    monkeypatch.setattr(m.trainer, 'V8', v8_root); monkeypatch.setattr(m.trainer, 'V6', v6_root)
    monkeypatch.setattr(m, 'COUNTS', {k: 1 for k in m.COUNTS})
    def put(path, value): path.write_text(json.dumps(value))
    def feature(formula, columns):
        return {'columns': list(columns), 'records': [{'formula': formula, 'values': [1.] * len(columns)}]}
    rows = {k: [{'formula': k}] for k in m.COUNTS}
    put(v8_root / 'rows.json', rows['applications'])
    put(v8_root / 'features.json', feature('applications', m.v8.columns()))
    put(v6_root / 'corpus/test/candidates.json', rows['v6_test_regression'])
    put(v6_root / 'corpus/test/features.json', feature('v6_test_regression', m.v6.columns()))
    put(root / 'original-training.json', {'rows': rows['original_training_in_sample'], 'values': [[1.] * 336]})
    put(fit / 'coverage-features.json', feature('coverage_training_in_sample', m.v6.columns()))
    params = m.trainer.ExtraTreesRegressor(**m.v6.FIXED_PARAMETERS).get_params()
    def model(count):
        estimator = SimpleNamespace(get_params=lambda: params,
            estimators_=[SimpleNamespace(tree_=SimpleNamespace(n_node_samples=[1713])) for _ in range(300)])
        return SimpleNamespace(training_formula_count=count, kind='mapping_v6', estimator=estimator,
            predict_features=lambda inputs, matrix: [{'formula': r['formula'], 'predicted_lut4': float(matrix[i, 0]),
                                                       'outside_training_feature_ranges': 0} for i, r in enumerate(inputs)])
    monkeypatch.setattr(m.v6, 'load_model', lambda p: model(1713 if p.name == 'mapping-coverage.joblib' else 1665))
    points = {cohort: {name: [{'formula': cohort, 'predicted_lut4': 1., 'outside_training_feature_ranges': 0}]
                      for name in ['frozen', 'augmented']} for cohort in rows}
    put(fit / 'point-predictions.json', points)
    authenticated = {'recipe': {'baseline_model': {'artifact': {'path': 'baseline.joblib'}}},
                     'candidates': rows['coverage_training_in_sample']}
    assert m.replay_inference(root, fit, authenticated)['all_prediction_fields_and_json_types_exact']
    points['v6_test_regression']['augmented'][0]['outside_training_feature_ranges'] = 1
    put(fit / 'point-predictions.json', points)
    with pytest.raises(ValueError, match='v6_test_regression/augmented'):
        m.replay_inference(root, fit, authenticated)
