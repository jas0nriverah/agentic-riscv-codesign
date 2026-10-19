"""V5 freeze misuse, independent clustered resampling and uncertainty scoring.

Fixtures are artificial protocol records; no V5 holdout labels are read or made.
"""
import importlib.util
import json
from pathlib import Path
import sys

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
spec = importlib.util.spec_from_file_location('evaluate_v5', ROOT / 'scripts/evaluate_v5.py')
ev = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ev)


def save(root, name, data):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))
    return {'path': str(path), 'sha256': ev.sha(path)}


def refresh(root, path):
    """Alter a declared record consistently to test semantic validation, not hashes."""
    manifest = ev.read(root / 'freeze.json')
    for record in manifest['files']:
        if Path(record['path']).resolve() == path.resolve():
            record['sha256'] = ev.sha(path)
    for entry in manifest['models'].values():
        for name in ('artifact', 'schema', 'predictions'):
            if Path(entry[name]['path']).resolve() == path.resolve():
                entry[name]['sha256'] = ev.sha(path)
    save(root, 'freeze.json', manifest)
    release = ev.read(root / 'label-release.json')
    release['freeze_sha256'] = ev.sha(root / 'freeze.json')
    save(root, 'label-release.json', release)
    completion = ev.read(root / 'corpus/test/completion.json')
    completion['release'] = release
    save(root, 'corpus/test/completion.json', completion)


@pytest.fixture
def bundle(tmp_path):
    candidates = [{'benchmark': f'b{i}', 'candidate_id': f'id{i}',
        'formula': f'xor(addi(in0,{i+3000}),in1)', 'stratum': f's{(i % 128)//16}',
        'evaluation_scope': ev.SCOPES[i//128]} for i in range(256)]
    development = [{'formula': f'addi(in0,{i+10000})', 'lut4_count': 1,
        'stratum': f's{i%8}', 'benchmark': 'fixture', 'measurement_source': 'rtl_synthesis',
        'correctness_verified': True} for i in range(2057)]
    components = {r['formula']: f'd{i%100}' for i, r in enumerate(development)}
    components.update({r['formula']: f't{i//2}' for i, r in enumerate(candidates)})
    fit_indices = [i for i in range(2057) if i % 100 < 80]
    sources = {'v5_corpus.py': ev.sha(ROOT/'isaforge/v5_corpus.py')}
    test_record = save(tmp_path, 'corpus/test/candidates.json', candidates)
    records = [test_record, save(tmp_path, 'development-data.json', development),
        save(tmp_path, 'development-features.json', {'records': [
            {'formula': r['formula'], 'values': [i], 'normalized_formula': r['formula']}
            for i, r in enumerate(development)]}),
        save(tmp_path, 'test-features.json', {'records': [
            {'formula': r['formula'], 'values': [i+10000], 'normalized_formula': r['formula']}
            for i, r in enumerate(candidates)]}),
        save(tmp_path, 'input-seal.json', {'status': 'sealed', 'cross_cohort_component_count': 0,
            'components': components, 'development_formula_count': 2057, 'test_formula_count': 256}),
        save(tmp_path, 'test-clusters.json', {'definition': 'artificial fixture clusters',
            'component_by_formula': {r['formula']: components[r['formula']] for r in candidates}}),
        save(tmp_path, 'split.json', {'fit_indices': fit_indices,
            'calibration_indices': [i for i in range(2057) if i%100 >= 80],
            'component_by_formula': {r['formula']: components[r['formula']] for r in development}}),
        save(tmp_path, 'training-start.json', {'dataset_sources': [],
            'started_at_utc': '2026-10-14T00:30:00Z',
            'sources': sources}),
        save(tmp_path, 'development-evaluation.json', {'fixture': True}),
        save(tmp_path, 'corpus/test/freeze.json', {'schema': 'isaforge-v5-input-freeze-v1',
            'frozen_at_utc': '2026-10-14T00:00:00Z', 'candidate_sha256': test_record['sha256']}),
        save(tmp_path, 'corpus/development/verification.json', {'verified': True}),
        save(tmp_path, 'corpus/development/completion.json', {'complete': True})]
    for path in [ROOT/'scripts/evaluate_v5.py', ROOT/'scripts/evaluate_v4.py',
                 ROOT/'scripts/train_v5.py', ROOT/'scripts/measure_v5.py', ROOT/'docs/v5-protocol.md',
                 ROOT/'isaforge/v5_corpus.py']:
        records.append({'path': str(path), 'sha256': ev.sha(path)})
    models = {}
    for name in ev.MODELS:
        prediction = [{**r, 'predicted_lut4': 1., 'upper_lut4': 2.} for r in candidates]
        artifact = save(tmp_path, f'models/{name}.joblib', {'fixture': True})
        models[name] = {'frozen_at_utc': '2026-10-14T01:00:00Z',
            'predictions': save(tmp_path, f'predictions/{name}.json', prediction),
            'artifact': artifact,
            'schema': save(tmp_path, f'models/{name}.json', {'fixture': True,
                'artifact_sha256': artifact['sha256'], 'runtime_source_sha256': sources,
                'view': name, 'training_formula_count': len(fit_indices),
                'calibration': {'upper_margin_lut4': 1.}})}
    manifest = {'schema': 'isaforge-v5-freeze-v1', 'frozen_at_utc': '2026-10-14T02:00:00Z',
        'models': models, 'files': records, 'test_candidate_sha256': test_record['sha256'],
        'primary': 'unseen_compositions macro-stratum MAE',
        'primary_comparison': 'dual_semantics minus sog_tuned', 'test_labels_read': False}
    save(tmp_path, 'freeze.json', manifest)
    release = {'freeze_sha256': ev.sha(tmp_path/'freeze.json'),
        'candidate_sha256': ev.sha(tmp_path/'corpus/test/candidates.json'),
        'authorized_after_freeze': True, 'released_at_utc': '2026-10-14T03:00:00Z'}
    save(tmp_path, 'label-release.json', release)
    dataset = save(tmp_path, 'corpus/test/dataset.json', [{**r, 'lut4_count': 1,
        'measurement_source': 'rtl_synthesis', 'correctness_verified': True} for r in candidates])
    verification = save(tmp_path, 'corpus/test/verification.json', {'fixture': True})
    save(tmp_path, 'corpus/test/completion.json', {'complete': True, 'measured_count': 256,
        'failures': [], 'candidate_sha256': test_record['sha256'],
        'dataset_sha256': dataset['sha256'], 'verification_sha256': verification['sha256'],
        'release': release, 'collector_sha256': ev.sha(ROOT/'scripts/measure_v5.py')})
    return tmp_path


def test_freeze_validation_does_not_access_sealed_labels(bundle):
    (bundle/'corpus/test/dataset.json').unlink()
    (bundle/'label-release.json').unlink()
    ev.validate_freeze(bundle)


def test_tampered_prediction_blocks_validation_before_any_label_read(bundle):
    (bundle/'predictions/dual_semantics.json').write_text('[]')
    (bundle/'label-release.json').unlink()
    with pytest.raises(ValueError, match='Frozen file changed'):
        ev.evaluate(bundle)


@pytest.mark.parametrize('filename', ['input-seal.json', 'split.json', 'development-data.json',
                                     'development-features.json', 'test-features.json', 'test-clusters.json'])
def test_critical_protocol_record_cannot_be_omitted_from_freeze(bundle, filename):
    manifest = ev.read(bundle/'freeze.json')
    manifest['files'] = [r for r in manifest['files'] if Path(r['path']).name != filename]
    save(bundle, 'freeze.json', manifest)
    with pytest.raises(ValueError):
        ev.validate_freeze(bundle)


@pytest.mark.parametrize('bad', [True, '2', -1., float('nan'), float('inf')])
def test_upper_bounds_require_nonboolean_finite_numeric_or_explicit_unbounded(bundle, bad):
    path = bundle/'predictions/dual_semantics.json'
    data = ev.read(path)
    data[0]['upper_lut4'] = bad
    save(bundle, str(path.relative_to(bundle)), data)
    refresh(bundle, path)
    with pytest.raises(ValueError):
        ev.validate_freeze(bundle)


def test_development_duplicate_formulas_cannot_pass_count_check(bundle):
    path = bundle/'development-data.json'
    rows = ev.read(path)
    rows[1]['formula'] = rows[0]['formula']
    save(bundle, str(path.relative_to(bundle)), rows)
    refresh(bundle, path)
    with pytest.raises(ValueError):
        ev.validate_freeze(bundle)


def test_calibration_cannot_share_a_fitting_component(bundle):
    path = bundle/'split.json'
    split = ev.read(path)
    development = ev.read(bundle/'development-data.json')
    fitting = development[split['fit_indices'][0]]['formula']
    calibrated = development[split['calibration_indices'][0]]['formula']
    split['component_by_formula'][calibrated] = split['component_by_formula'][fitting]
    save(bundle, 'split.json', split)
    refresh(bundle, path)
    with pytest.raises(ValueError, match='Calibration component leakage'):
        ev.validate_freeze(bundle)


def test_label_release_must_follow_entire_prediction_bundle(bundle):
    release = ev.read(bundle/'label-release.json')
    release['released_at_utc'] = '2026-10-14T02:00:00Z'
    save(bundle, 'label-release.json', release)
    with pytest.raises(ValueError, match='valid release after model freeze'):
        ev.evaluate(bundle)


def test_missing_or_failed_measurement_cannot_be_scored_as_complete(bundle):
    completion = ev.read(bundle/'corpus/test/completion.json')
    completion['measured_count'] = 255
    save(bundle, 'corpus/test/completion.json', completion)
    with pytest.raises(ValueError, match='incomplete'):
        ev.evaluate(bundle)


@pytest.mark.parametrize('field, invalid', [
    ('artifact_sha256', 'changed'), ('runtime_source_sha256', {'wrong': 'hash'}),
    ('view', 'sog_tuned'), ('training_formula_count', 2057),
])
def test_model_schema_must_agree_with_frozen_training_and_artifact(bundle, field, invalid):
    path = bundle/'models/dual_semantics.json'
    schema = ev.read(path)
    schema[field] = invalid
    save(bundle, str(path.relative_to(bundle)), schema)
    refresh(bundle, path)
    with pytest.raises(ValueError, match='schema disagrees'):
        ev.validate_freeze(bundle)


def test_candidate_hash_in_release_must_match_frozen_pool(bundle):
    release = ev.read(bundle/'label-release.json')
    release['candidate_sha256'] = 'different'
    save(bundle, 'label-release.json', release)
    with pytest.raises(ValueError, match='valid release'):
        ev.evaluate(bundle)


@pytest.mark.parametrize('field', ['release', 'collector_sha256'])
def test_completion_requires_same_release_and_frozen_collector(bundle, field):
    completion = ev.read(bundle/'corpus/test/completion.json')
    completion[field] = {'different': True} if field == 'release' else 'changed'
    save(bundle, 'corpus/test/completion.json', completion)
    with pytest.raises(ValueError, match='Measurement provenance'):
        ev.evaluate(bundle)


def test_incomplete_test_cluster_partition_cannot_be_scored(bundle):
    path = bundle/'test-clusters.json'
    clusters = ev.read(path)
    clusters['component_by_formula'].pop(next(iter(clusters['component_by_formula'])))
    save(bundle, str(path.relative_to(bundle)), clusters)
    refresh(bundle, path)
    with pytest.raises(ValueError, match='cluster partition incomplete'):
        ev.evaluate(bundle)


def test_incomplete_test_cluster_partition_blocks_freeze_with_labels_sealed(bundle):
    path = bundle/'test-clusters.json'
    clusters = ev.read(path)
    clusters['component_by_formula'].pop(next(iter(clusters['component_by_formula'])))
    save(bundle, str(path.relative_to(bundle)), clusters)
    refresh(bundle, path)
    (bundle/'corpus/test/dataset.json').unlink()
    (bundle/'label-release.json').unlink()
    with pytest.raises(ValueError, match='cluster partition incomplete'):
        ev.validate_freeze(bundle)


def test_cluster_partition_tamper_rejected_before_label_access(bundle):
    (bundle/'test-clusters.json').write_text('{}')
    (bundle/'label-release.json').unlink()
    with pytest.raises(ValueError, match='Frozen file changed'):
        ev.evaluate(bundle)


@pytest.mark.parametrize('filename, field, stamp', [
    ('corpus/test/freeze.json', 'frozen_at_utc', '2026-10-14T01:00:00Z'),
    ('training-start.json', 'started_at_utc', '2026-10-14T03:00:00Z'),
])
def test_candidate_and_training_chronology_must_precede_models(bundle, filename, field, stamp):
    path = bundle/filename
    record = ev.read(path)
    record[field] = stamp
    save(bundle, filename, record)
    refresh(bundle, path)
    with pytest.raises(ValueError, match='chronology'):
        ev.validate_freeze(bundle)


def test_upper_bound_cannot_be_finite_when_frozen_margin_is_unbounded(bundle):
    path = bundle/'models/dual_semantics.json'
    schema = ev.read(path)
    schema['calibration']['upper_margin_lut4'] = None
    save(bundle, str(path.relative_to(bundle)), schema)
    refresh(bundle, path)
    with pytest.raises(ValueError, match='upper prediction bound'):
        ev.validate_freeze(bundle)


def test_cluster_bootstrap_preserves_cross_stratum_clusters_and_macro_weighting():
    # Both clusters span both strata. Treating rows independently would yield
    # other bootstrap support; macro weighting also differs from pooled MAE.
    d = np.array([0., 0., 10., 20., 20., 30.])
    strata = np.array(['a', 'a', 'b', 'a', 'a', 'b'])
    clusters = np.array(['first'] * 3 + ['second'] * 3)
    score = ev.paired_clusters(d, strata, clusters, replicates=1000)
    assert score['macro_stratum_mae_difference_lut4'] == 15.
    assert score['descriptive_cluster_bootstrap_95_interval'] == [5., 25.]
    assert score['cluster_count'] == 2
    assert score['attempts'] == 1000
    assert score['empty_stratum_draws_rejected'] == 0
    assert score == ev.paired_clusters(d, strata, clusters, replicates=1000)


def test_single_cluster_difference_is_retained_even_when_new_model_loses():
    score = ev.paired_clusters(np.array([3., 9.]), np.array(['a', 'b']),
                              np.array(['one', 'one']), replicates=10)
    assert score['macro_stratum_mae_difference_lut4'] == 6.
    assert score['descriptive_cluster_bootstrap_95_interval'] == [6., 6.]


def test_empty_stratum_draws_are_redrawn_with_their_number_reported():
    score = ev.paired_clusters(np.array([1., 3.]), np.array(['a', 'b']),
                              np.array(['one', 'two']), replicates=100)
    assert score['macro_stratum_mae_difference_lut4'] == 2.
    assert score['descriptive_cluster_bootstrap_95_interval'] == [2., 2.]
    assert score['attempts'] > score['replicates']
    assert score['empty_stratum_draws_rejected'] == score['attempts']-score['replicates']


def test_all_empty_stratum_draws_fail_closed_at_declared_attempt_limit(monkeypatch):
    class InvalidDraws:
        def integers(self, low, high, size):
            return np.zeros(size, dtype=int)
    monkeypatch.setattr(ev.np.random, 'default_rng', lambda seed: InvalidDraws())
    with pytest.raises(ValueError, match='Insufficient nonempty-stratum'):
        ev.paired_clusters(np.array([1., 3.]), np.array(['a', 'b']),
                           np.array(['one', 'two']), replicates=10)


@pytest.mark.parametrize('d,s,c,reps', [
    ([], [], [], 10), ([1.], ['a', 'b'], ['g'], 10),
    ([float('nan')], ['a'], ['g'], 10), ([float('inf')], ['a'], ['g'], 10),
    ([1.], ['a'], ['g'], 0), ([1.], ['a'], ['g'], True),
])
def test_invalid_cluster_bootstrap_inputs_are_rejected(d, s, c, reps):
    with pytest.raises(ValueError):
        ev.paired_clusters(np.array(d), np.array(s), np.array(c), replicates=reps)


def test_upper_coverage_distinguishes_rows_complete_components_and_infinite_bounds(bundle, monkeypatch):
    # Only one row misses. It makes its two-row component fail as a whole.
    path = bundle/'corpus/test/dataset.json'
    rows = ev.read(path)
    rows[0]['lut4_count'] = 3
    save(bundle, str(path.relative_to(bundle)), rows)
    completion = ev.read(bundle/'corpus/test/completion.json')
    completion['dataset_sha256'] = ev.sha(path)
    save(bundle, 'corpus/test/completion.json', completion)
    path = bundle/'predictions/original_graph.json'
    rows = ev.read(path)
    for row in rows:
        row['upper_lut4'] = None
    save(bundle, str(path.relative_to(bundle)), rows)
    refresh(bundle, path)
    path = bundle/'models/original_graph.json'
    schema = ev.read(path)
    schema['calibration']['upper_margin_lut4'] = None
    save(bundle, str(path.relative_to(bundle)), schema)
    refresh(bundle, path)
    # Cluster resampling has independent substantive tests above.
    monkeypatch.setattr(ev, 'paired_clusters', lambda *a, **kw: {'fixture': True})
    report = ev.evaluate(bundle)
    upper = report['models']['dual_semantics']['by_scope']['known_families']['upper_bound']
    assert upper['candidate_coverage'] == 127/128
    assert upper['whole_component_coverage'] == 63/64
    assert upper['finite_fraction'] == 1.
    unbounded = report['models']['original_graph']['by_scope']['known_families']['upper_bound']
    assert unbounded['candidate_coverage'] == unbounded['whole_component_coverage'] == 1.
    assert unbounded['finite_fraction'] == 0.
    assert unbounded['mean_upper_minus_target_lut4'] is None
    assert report['primary_comparison'] == 'dual_semantics minus sog_tuned'
    assert len(report['models']['dual_semantics']['candidate_errors']) == 256
