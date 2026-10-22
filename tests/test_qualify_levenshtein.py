"""Qualification orchestration checks; every subprocess/native phase is mocked."""
from pathlib import Path
import shutil
import tarfile

import pytest

from isaforge import codesign as c
from scripts import qualify_levenshtein as q


@pytest.fixture
def fixture(tmp_path, monkeypatch):
    original = q.ROOT
    for name in q.SOURCES:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(original / name, path)
    monkeypatch.setattr(q, 'ROOT', tmp_path)
    reference = tmp_path / q.REFERENCE
    c.seal(reference / 'plan.json', {'context_id': 'preserved-reference'})
    native, output = tmp_path / q.NATIVE, tmp_path / q.OUTPUT
    calls = []
    control = dict(fail_phase=None, interrupt_phase=None)

    def run(argv, folder, *, cwd, metadata, timeout_seconds):
        phase = metadata['phase']
        # Immutable declaration/source snapshots must exist before the first dispatch.
        protocol = c.unseal(output / 'protocol.json')
        assert metadata['protocol_sha256'] == c.sha(output / 'protocol.json')
        assert argv == protocol['phase_commands'][phase]
        assert cwd == tmp_path and timeout_seconds == 3600
        assert protocol['order'] == ['levenshtein']
        assert all(c.sha(output / 'sources' / name) == digest for name, digest in protocol['source_bindings'].items())
        assert not list((native / 'attempt-ledger').glob('candidate_*.json'))
        calls.append(phase)
        folder.mkdir(parents=True)
        (folder / 'stdout.txt').write_text('native stdout')
        (folder / 'stderr.txt').write_text('native stderr')
        interrupted = phase == control['interrupt_phase']
        failed = phase == control['fail_phase']
        record = dict(status='interrupted' if interrupted else 'nonzero_exit' if failed else 'success',
                      returncode=None if interrupted else 1 if failed else 0,
                      start={'utc_ns': 0, 'monotonic_before_ns': 0, 'monotonic_after_ns': 1},
                      end={'utc_ns': 2000000000, 'monotonic_before_ns': 1999999999, 'monotonic_after_ns': 2000000001},
                      durations=dict(monotonic_elapsed_seconds=2.0, utc_elapsed_seconds=2.0,
                                     clock_disagreement_detected=False))
        c.seal(folder / 'record.json', record)
        native.mkdir(exist_ok=True)
        c.seal(native / 'plan.json', {'workload': 'levenshtein', 'context_id': 'fresh-context'})
        (native / 'obj_dir').mkdir(exist_ok=True)
        (native / 'obj_dir/simulator').write_text('uncommitted build product')
        if phase == 'freeze':
            c.seal(native / 'evaluation-protocol.json', dict(
                pool_names=['candidate_' + str(i) for i in range(12)], maximum_candidate_attempts=12))
        if interrupted:
            raise KeyboardInterrupt('mocked interrupt')
        return record

    monkeypatch.setattr(q.observed_command, 'run', run)
    monkeypatch.setattr(q.workload, 'validate_inputs', lambda root: c.unseal(Path(root) / 'plan.json'))
    return dict(native=native, output=output, reference=reference, calls=calls, control=control)


def qualify(f):
    return q.qualify(f['output'], f['native'], f['reference'])


def test_declares_then_runs_only_five_phases_and_archives_zero_attempts(fixture):
    f = fixture
    result = qualify(f)
    assert result['accepted'] is True and result['status'] == 'accepted'
    assert f['calls'] == list(q.PHASES)
    assert result['target_candidate_attempts'] == 0 and len(result['pool_names']) == 12
    assert result['recorded_subprocess_monotonic_seconds'] == result['recorded_subprocess_utc_seconds'] == 10
    protocol = c.unseal(f['output'] / 'protocol.json')
    assert protocol['pool_size'] == 12 and protocol['memory_partition']['stack_floor'] == 6528
    assert protocol['upstream']['source_sha256'] == q.PROGRAM_SHA256
    assert protocol['verifier']['original_aggregate_sum'] == 122
    assert protocol['independently_computed_distances'] == [list(row) for row in q.EXPECTED_DISTANCES]
    assert '--workload' in protocol['phase_commands']['prepare']
    assert all('--candidate' not in argv for argv in protocol['phase_commands'].values())
    archive = c.unseal(f['output'] / 'archive-manifest.json')
    assert all('obj_dir' not in entry['path'].split('/') for entry in archive['files'])
    with tarfile.open(f['output'] / 'raw.tar.gz') as stream:
        assert 'evaluation-protocol.json' in stream.getnames()
        assert 'obj_dir/simulator' not in stream.getnames()
    manifest = c.unseal(f['output'] / 'manifest.json')
    assert manifest['protocol.json'] == c.sha(f['output'] / 'protocol.json')
    assert manifest['qualification.json'] == c.sha(f['output'] / 'qualification.json')


@pytest.mark.parametrize('phase', q.PHASES)
def test_terminal_failure_stops_without_retry_or_fallback_and_preserves_logs(fixture, phase):
    f = fixture
    f['control']['fail_phase'] = phase
    result = qualify(f)
    assert not result['accepted'] and result['status'] == 'rejected' and result['failed_phase'] == phase
    assert f['calls'] == list(q.PHASES[:q.PHASES.index(phase) + 1])
    assert result['commands'][-1]['record']['returncode'] == 1
    assert (f['output'] / result['commands'][-1]['observation'] / 'stderr.txt').read_text() == 'native stderr'
    assert (f['output'] / 'archive-manifest.json').exists()
    assert c.unseal(f['output'] / 'qualification.json')['accepted'] is False


def test_interrupt_retains_observed_terminal_receipt_then_rethrows(fixture):
    f = fixture
    f['control']['interrupt_phase'] = 'public'
    with pytest.raises(KeyboardInterrupt, match='mocked interrupt'):
        qualify(f)
    result = c.unseal(f['output'] / 'qualification.json')
    assert result['status'] == 'interrupted' and result['failed_phase'] == 'public'
    assert result['commands'][-1]['record']['status'] == 'interrupted'
    assert result['recorded_subprocess_monotonic_seconds'] == 8.0
    assert (f['output'] / 'manifest.json').exists() and (f['output'] / 'raw.tar.gz').exists()


@pytest.mark.parametrize('existing', ['output', 'native'])
def test_existing_directory_cannot_be_overwritten_or_retried(fixture, existing):
    f = fixture
    f[existing].mkdir(parents=True)
    with pytest.raises(ValueError, match='Fresh'):
        qualify(f)
    assert f['calls'] == []


def test_wrong_reference_or_modified_source_blocks_dispatch(fixture):
    f = fixture
    with pytest.raises(ValueError, match='Exact preserved'):
        q.qualify(f['output'], f['native'], f['reference'].parent)
    source = q.ROOT / q.PROGRAM
    source.write_text(source.read_text().replace('int exp = 122;', 'int exp = 121;'))
    with pytest.raises(ValueError, match='Pinned original source'):
        qualify(f)
    assert f['calls'] == [] and not f['output'].exists()


def test_nonqualification_phase_and_paid_artifacts_are_rejected(tmp_path):
    with pytest.raises(ValueError, match='five declared'):
        q.phase_command('measure', tmp_path, tmp_path)
    c.seal(tmp_path / 'attempt-ledger/candidate_00.json', {'status': 'failed'})
    with pytest.raises(ValueError, match='zero candidate attempts'):
        q.zero_candidate_attempts(tmp_path)


def test_independent_edit_distances_cover_every_original_pair():
    distances = q.reference_distances()
    assert len(distances) == 5 and all(len(row) == 5 for row in distances)
    assert sum(map(sum, distances)) == 122
    assert all(distances[i][i] == 0 for i in range(5))
    assert all(distances[i][j] == distances[j][i] for i in range(5) for j in range(5))
