"""Replay publication contracts, using synthetic evaluations without real targets."""
import copy
import importlib.util
import json
import math
from pathlib import Path
import sys
import types
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'scripts')]
spec = importlib.util.spec_from_file_location('reproduce_v8_applications', ROOT / 'scripts/reproduce_v8_applications.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


@pytest.fixture
def replay(tmp_path, monkeypatch):
    root = tmp_path / 'published'
    root.mkdir()
    reference = {
        'schema': 'SYNTHETIC_ONLY', 'evaluated_at_utc': '2026-10-15T10:00:00+00:00',
        'provenance': {'point_freeze_sha256': 'a' * 64},
        'scores': {'primary': 1.5, 'complete': True, 'nested_timestamp': 'frozen-time'},
    }
    reference_path = root / 'evaluation.json'
    reference_path.write_text(json.dumps(reference))
    actual = copy.deepcopy(reference)
    actual['evaluated_at_utc'] = '2026-10-15T11:00:00+00:00'
    calls = []
    def score(given_root, output):
        calls.append((given_root, output))
        output.write_text(json.dumps(actual))
        return actual
    monkeypatch.setattr(m.scorer, 'score', score)
    return root, tmp_path / 'fresh-replay', reference, actual, calls


def test_authenticated_replay_allows_only_evaluation_time_to_change(replay):
    root, output, reference, actual, calls = replay
    before = (root / 'evaluation.json').read_bytes()
    report = m.reproduce(root, output, skip_figures=True)
    assert calls == [(root, output / 'evaluation.json')]
    assert report['status'] == 'pass'
    assert report['published_evaluation_sha256'] != report['reproduced_evaluation_sha256']
    assert report['point_freeze_sha256'] == 'a' * 64
    assert report['new_estimator_fits'] == 0 and report['fresh_target_generation'] is False
    assert json.loads((output / 'reproduction.json').read_text()) == report
    assert (root / 'evaluation.json').read_bytes() == before


@pytest.mark.parametrize('key,value', [('primary', 9.0), ('complete', 1), ('nested_timestamp', 'changed')])
def test_reference_arithmetic_type_or_nested_timestamp_changes_fail(replay, key, value, capsys):
    root, output, reference, actual, _ = replay
    reference['scores'][key] = value
    (root / 'evaluation.json').write_text(json.dumps(reference))
    with pytest.raises(ValueError, match='differs from published'):
        m.reproduce(root, output, skip_figures=True)
    assert (output / 'evaluation.json').is_file()
    assert not (output / 'reproduction.json').exists()
    mismatch = json.loads((output / 'mismatch.json').read_text())
    assert mismatch['difference_count'] == 1
    assert mismatch['differences'][0]['path'] == '/scores/' + key
    assert json.loads(capsys.readouterr().err) == mismatch


def test_replay_preserves_existing_output_without_scoring(replay):
    root, output, _, _, calls = replay
    output.mkdir()
    retained = output / 'retained.json'
    retained.write_text('preserve')
    with pytest.raises(ValueError, match='fresh directory'):
        m.reproduce(root, output, skip_figures=True)
    assert retained.read_text() == 'preserve' and not calls


def test_approval_failure_precedes_published_evaluation_read(replay, monkeypatch):
    root, output, _, _, _ = replay
    def blocked(*args):
        raise ValueError('committed approval blocked')
    monkeypatch.setattr(m.scorer, 'score', blocked)
    monkeypatch.setattr(Path, 'read_text', lambda *args, **kwargs: pytest.fail('No published result read before approval'))
    with pytest.raises(ValueError, match='committed approval blocked'):
        m.reproduce(root, output, skip_figures=True)
    assert not (output / 'reproduction.json').exists()


@pytest.mark.parametrize('timestamp', [None, '2026-10-15T10:00:00'])
def test_missing_or_timezone_free_timestamp_is_not_silently_ignored(replay, timestamp):
    root, output, reference, _, _ = replay
    if timestamp is None:
        del reference['evaluated_at_utc']
    else:
        reference['evaluated_at_utc'] = timestamp
    (root / 'evaluation.json').write_text(json.dumps(reference))
    with pytest.raises(ValueError):
        m.reproduce(root, output, skip_figures=True)


def test_optional_plots_use_only_the_verified_reproduced_evaluation(replay, monkeypatch):
    root, output, _, _, _ = replay
    calls = []
    monkeypatch.setitem(sys.modules, 'plot_v8_applications', types.SimpleNamespace(run=lambda *args, **kwargs: calls.append((args, kwargs))))
    report = m.reproduce(root, output)
    assert calls == [((output / 'evaluation.json', output / 'figures'), {'root': root})]
    assert report['figures_generated'] is True


def test_unpublished_evaluation_does_not_create_output(replay):
    root, output, _, _, calls = replay
    (root / 'evaluation.json').unlink()
    with pytest.raises(ValueError, match='Published V8'):
        m.reproduce(root, output, skip_figures=True)
    assert not output.exists() and not calls


def test_one_ulp_diagnostic_reports_the_exact_field_without_accepting_it(replay):
    root, output, _, actual, _ = replay
    actual['scores']['primary'] = math.nextafter(1.5, math.inf)
    with pytest.raises(ValueError, match='differs from published'):
        m.reproduce(root, output, skip_figures=True)
    report = json.loads((output / 'mismatch.json').read_text())
    difference = report['differences'][0]
    assert difference['expected'] == 1.5
    assert difference['actual'] == actual['scores']['primary']
    assert difference['numeric_difference']['absolute'] == math.ulp(1.5)
    assert difference['numeric_difference']['ulps'] == 1.0
    assert not (output / 'reproduction.json').exists()


def test_diagnostics_bound_output_but_count_every_mismatch():
    report = m.difference_report({'values': list(range(1000))}, {'values': list(range(1, 1001))}, limit=2)
    assert report['difference_count'] == 1000
    assert report['reported_difference_count'] == 2 and report['truncated']
    assert [d['path'] for d in report['differences']] == ['/values/0', '/values/1']
    assert len(json.dumps(report)) < 2000


def test_diagnostic_paths_preserve_types_structure_and_nested_timestamps():
    expected = {'x/y~z': [True], 'missing': {'large': list(range(1000))},
                'evaluated_at_utc': 'ignored', 'nested': {'evaluated_at_utc': 'before'}}
    actual = {'x/y~z': [1, 2], 'extra': False,
              'evaluated_at_utc': 'different', 'nested': {'evaluated_at_utc': 'after'}}
    report = m.difference_report(expected, actual)
    by_path = {d['path']: d for d in report['differences']}
    assert report['difference_count'] == 5
    assert by_path['/x~1y~0z']['reason'] == 'list_length'
    assert by_path['/x~1y~0z/0']['reason'] == 'type'
    assert by_path['/missing']['expected']['length'] == 1
    assert by_path['/nested/evaluated_at_utc']['actual'] == 'after'
    assert '/evaluated_at_utc' not in by_path


@pytest.mark.parametrize('limit', [0, 1001, True])
def test_diagnostic_limit_is_bounded(limit):
    with pytest.raises(ValueError, match='Diagnostic limit'):
        m.difference_report({}, {}, limit=limit)


def test_declared_rmsle_roundoff_is_recorded_while_preserving_published_bytes(replay):
    root, output, reference, actual, _ = replay
    reference['scores']['mapping_v6'] = {'by_program': {'fft': {'rmsle': 0.030547051812597762}}}
    actual['scores']['mapping_v6'] = {'by_program': {'fft': {'rmsle': 0.030547051812597856}}}
    reference_path = root / 'evaluation.json'
    reference_path.write_text(json.dumps(reference))
    before = reference_path.read_bytes()
    report = m.reproduce(root, output, skip_figures=True)
    assert report['status'] == 'pass' and report['accepted_rmsle_roundoff_count'] == 1
    roundoff = json.loads((output / 'roundoff.json').read_text())
    assert roundoff['status'] == 'pass' and roundoff['incompatible_difference_count'] == 0
    assert roundoff['differences'][0]['numeric_difference']['ulps'] == 27
    assert reference_path.read_bytes() == before
    assert not (output / 'mismatch.json').exists()


@pytest.mark.parametrize('metric,expected,actual', [
    ('rmsle', 0.1, 0.1 + 2e-14),
    ('rmsle', 0, 0.0),
    ('rmsle', -1e-16, 0.0),
    ('mae_lut4', 0.1, math.nextafter(0.1, math.inf)),
])
def test_rmsle_tolerance_cannot_hide_larger_drift_types_invalid_values_or_mae(metric, expected, actual):
    def value(x):
        return {'scores': {'mapping_v6': {'by_program': {'fft': {metric: x}}}}}
    report = m.difference_report(value(expected), value(actual), rmsle_roundoff=True)
    assert report['status'] == 'fail'
    assert report['accepted_rmsle_roundoff_count'] == 0
    assert report['incompatible_difference_count'] == 1


def test_unknown_rmsle_paths_and_provenance_remain_exact():
    for expected, actual in [
        ({'scores': {'unknown_model': {'by_program': {'fft': {'rmsle': .1}}}}},
         {'scores': {'unknown_model': {'by_program': {'fft': {'rmsle': math.nextafter(.1, math.inf)}}}}}),
        ({'provenance': {'rmsle': .1}}, {'provenance': {'rmsle': math.nextafter(.1, math.inf)}}),
    ]:
        report = m.difference_report(expected, actual, rmsle_roundoff=True)
        assert report['status'] == 'fail' and report['incompatible_difference_count'] == 1


def test_unreported_incompatible_fields_still_block_acceptance():
    expected = {'scores': {'mapping_v6': {'by_program': {'fft': {'rmsle': .1}}}}, 'z': 1}
    actual = copy.deepcopy(expected)
    actual['scores']['mapping_v6']['by_program']['fft']['rmsle'] = math.nextafter(.1, math.inf)
    actual['z'] = 2
    report = m.difference_report(expected, actual, limit=1, rmsle_roundoff=True)
    assert report['truncated'] and report['differences'][0]['accepted_rmsle_roundoff']
    assert report['accepted_rmsle_roundoff_count'] == 1 and report['incompatible_difference_count'] == 1
    assert report['status'] == 'fail'
