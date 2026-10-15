"""Replay publication contracts, using synthetic evaluations without real targets."""
import copy
import importlib.util
import json
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
def test_reference_arithmetic_type_or_nested_timestamp_changes_fail(replay, key, value):
    root, output, reference, actual, _ = replay
    reference['scores'][key] = value
    (root / 'evaluation.json').write_text(json.dumps(reference))
    with pytest.raises(ValueError, match='differs from published'):
        m.reproduce(root, output, skip_figures=True)
    assert (output / 'evaluation.json').is_file()
    assert not (output / 'reproduction.json').exists()


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
