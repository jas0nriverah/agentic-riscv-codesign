"""Countnegative source pin and baseline-only qualification guardrails."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

import pytest

from isaforge import codesign as c, tacle_countnegative_workload as w
from scripts import qualify_tacle_countnegative as q


def public_pool():
    return c.unseal(c.ROOT / 'results/2026-10-22-expanded-history-verified/experiments/expanded/beebs-ndes/controls11/model/public.json')


def test_original_source_and_archive_provenance_are_pinned():
    record = json.loads((c.ROOT / w.PROVENANCE).read_text())
    assert record['archive_sha256'] == 'de14a15d3623fb800ad0d056282d83ac8a69d2af7964b88bdf318215c4117626'
    assert record['commit'] == w.UPSTREAM_COMMIT
    assert record['directory'] == 'bench/kernel/countnegative'
    assert set(record['files']) == set(w.UPSTREAM)
    for name, digest in w.UPSTREAM.items():
        raw = (c.ROOT / w.BASE / name).read_bytes()
        assert c.sha(c.ROOT / w.BASE / name) == digest == record['files'][name]['sha256']
        assert record['files'][name]['bytes'] == len(raw)
        assert record['files'][name]['git_blob_sha1'] == hashlib.sha1(
            b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
    source = (c.ROOT / w.BASE / 'countnegative.c').read_text()
    adapter = (c.ROOT / w.PROGRAM).read_text()
    assert '#define MAXSIZE 20' in source
    assert 'checksum == ( int )0x1778de' in source
    assert 'countnegative_main();' in adapter
    assert 'return result == 0 && countnegative_return() == 0;' in adapter


def test_fixed_source_contract_and_group_are_new():
    assert w.WORKLOAD == 'countnegative' and w.GROUP == 'tacle-countnegative'
    assert w.POOL_SIZE == 12
    assert w.PARTITION == w.g.q.partition_spec(6400, 6528)
    assert w.PROTOCOL['minimum_calibrated_cycle_reduction'] == .005
    assert w.PROTOCOL['minimum_timed_replacements'] == 10
    corpus = c.unseal(c.ROOT / q.HISTORY)
    assert w.GROUP not in corpus['independent_workload_groups']
    assert set(w.prior.semantic.SOURCES).issubset(w.GATE_SOURCES)
    assert set(w.GATE_SOURCES).issubset(q.SOURCES)


@pytest.mark.skipif(shutil.which('cc') is None, reason='host C compiler unavailable')
def test_host_adapter_runs_original_matrix_checksum(tmp_path):
    executable = tmp_path / 'countnegative-host-smoke'
    subprocess.run([
        shutil.which('cc'), '-std=gnu11', '-O2', '-Wno-unknown-pragmas',
        '-I', str(c.ROOT / w.BASE),
        str(c.ROOT / w.PROGRAM),
        str(c.ROOT / 'tests/tacle_countnegative_host_smoke.c'),
        '-o', str(executable),
    ], check=True, capture_output=True, text=True)
    result = subprocess.run([str(executable)], check=False)
    assert result.returncode == 0


def test_registration_restores_all_shared_globals_even_when_nested():
    g = w.g
    before = (g.SOURCE, g.WORKLOADS, g.POOL_SIZE, g.NATIVE_LIMITS,
              g.q.POOL_SIZE, g.q.bounded.POOL_SIZE,
              g.q.bounded.campaign.POOL_SIZE, w.evidence._public)
    with pytest.raises(RuntimeError, match='restore'):
        with w.registration():
            assert g.SOURCE == w.SOURCE and g.POOL_SIZE == 12
            assert g.WORKLOADS == {w.WORKLOAD: '../../tacle/countnegative/isaforge_adapter.c'}
            with w.registration():
                raise RuntimeError('restore')
    after = (g.SOURCE, g.WORKLOADS, g.POOL_SIZE, g.NATIVE_LIMITS,
             g.q.POOL_SIZE, g.q.bounded.POOL_SIZE,
             g.q.bounded.campaign.POOL_SIZE, w.evidence._public)
    assert after == before


def test_opportunity_gate_keeps_the_fixed_twelve_pool_and_joint_threshold():
    public = public_pool()
    for row in public:
        row['latency_features']['estimated_cycle_reduction'] = 0.0
        row['runs'] = row['latency_features']['region_custom_instructions'] = 1
        row['latency_features']['dynamic_custom_cycles'] = 5
        row['latency_features']['replacement_execution_fraction'] = 1 / row['latency_features']['baseline_instructions']
    public[0]['latency_features']['estimated_cycle_reduction'] = .005
    public[1]['runs'] = public[1]['latency_features']['region_custom_instructions'] = 10
    public[1]['latency_features']['dynamic_custom_cycles'] = 50
    public[1]['latency_features']['replacement_execution_fraction'] = 10 / public[1]['latency_features']['baseline_instructions']
    assert not w.opportunity_gate(public)['passed']
    public[0]['runs'] = public[0]['latency_features']['region_custom_instructions'] = 10
    public[0]['latency_features']['dynamic_custom_cycles'] = 50
    public[0]['latency_features']['replacement_execution_fraction'] = 10 / public[0]['latency_features']['baseline_instructions']
    assert w.opportunity_gate(public)['passed']
    public[0]['speedup'] = 2.0
    with pytest.raises(ValueError, match='non-public'):
        w.opportunity_gate(public)
    with pytest.raises(ValueError, match='twelve'):
        w.opportunity_gate(public_pool()[:-1])


def test_candidate_dispatch_is_disabled_for_zero_label_qualification(tmp_path, monkeypatch):
    evaluator = object.__new__(w.Evaluator)
    evaluator.root = tmp_path
    calls = []
    monkeypatch.setattr(w, 'check_opportunity', lambda root: calls.append('gate'))
    monkeypatch.setattr(w.g.Evaluator, 'measure', lambda self, name: calls.append('native'))
    with pytest.raises(ValueError, match='dispatch disabled'):
        evaluator.measure('candidate_00')
    assert calls == []
    evaluator.measure('baseline')
    assert calls == ['gate', 'native']


def test_qualification_uses_baseline_only_phases_and_charges_no_candidates(tmp_path):
    argv = q.phase_command('prepare', tmp_path / 'native', tmp_path / 'reference')
    assert argv[1:4] == ['-m', 'isaforge.tacle_countnegative_workload', 'prepare']
    assert argv[-2:] == ['--reference-root', str(tmp_path / 'reference')]
    assert '--reference-root' not in q.phase_command('discover', tmp_path / 'native', tmp_path / 'reference')
    with pytest.raises(ValueError, match='phase'):
        q.phase_command('measure', tmp_path / 'native', tmp_path / 'reference')
    c.seal(tmp_path / 'attempt-ledger/candidate_00.json', {})
    with pytest.raises(ValueError, match='zero candidate'):
        q.zero(tmp_path)


@pytest.fixture
def qualification_fixture(tmp_path, monkeypatch):
    for name in q.SOURCES:
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(q.ROOT / name, target)
    monkeypatch.setattr(q, 'ROOT', tmp_path)
    reference = tmp_path / q.REFERENCE
    c.seal(reference / 'plan.json', {'context_id': 'reference'})
    c.seal(tmp_path / q.HISTORY, {'independent_workload_groups': ['consumed']})
    output, native = tmp_path / q.OUTPUT, tmp_path / q.NATIVE
    calls = []
    reject_at = {'phase': None}

    def observe(argv, folder, *, cwd, metadata, timeout_seconds):
        phase = metadata['phase']
        protocol = c.unseal(output / 'protocol.json')
        assert argv == protocol['phase_commands'][phase]
        assert protocol['pool_size'] == 12
        assert protocol['minimum_calibrated_cycle_reduction'] == .005
        assert protocol['minimum_timed_replacements'] == 10
        assert metadata['protocol_sha256'] == c.sha(output / 'protocol.json')
        calls.append(phase)
        c.seal(native / 'plan.json', {'context_id': 'countnegative'})
        if phase == 'freeze':
            c.seal(native / 'evaluation-protocol.json', {
                'pool_names': [f'candidate_{i:02d}' for i in range(12)],
                'maximum_candidate_attempts': 12})
        rejected = phase == reject_at['phase']
        record = dict(status='nonzero_exit' if rejected else 'success', returncode=int(rejected),
            durations=dict(monotonic_elapsed_seconds=1.0, utc_elapsed_seconds=1.0,
                           clock_disagreement_detected=False))
        c.seal(folder / 'record.json', record)
        return record

    monkeypatch.setattr(q.observed_command, 'run', observe)
    monkeypatch.setattr(q.w, 'validate_inputs', lambda root: c.unseal(Path(root) / 'plan.json'))
    monkeypatch.setattr(q.w, 'check_opportunity', lambda root: {'passed': True})
    return dict(output=output, native=native, reference=reference, calls=calls, reject_at=reject_at)


def test_synthetic_accepted_qualification_freezes_exact_pool(qualification_fixture):
    fixture = qualification_fixture
    result = q.qualify(fixture['output'], fixture['native'], fixture['reference'])
    assert result['status'] == 'accepted' and result['target_candidate_attempts'] == 0
    assert fixture['calls'] == list(q.PHASES)
    assert (fixture['output'] / 'raw.tar.gz').is_file()
    assert c.unseal(fixture['output'] / 'manifest.json')['raw.tar.gz'] == c.sha(fixture['output'] / 'raw.tar.gz')
    with pytest.raises(ValueError, match='Fresh'):
        q.qualify(fixture['output'], fixture['native'], fixture['reference'])


@pytest.mark.parametrize('phase', ['discover', 'opportunity'])
def test_first_rejection_is_preserved_without_routed_baseline(qualification_fixture, phase):
    fixture = qualification_fixture
    fixture['reject_at']['phase'] = phase
    result = q.qualify(fixture['output'], fixture['native'], fixture['reference'])
    assert result['status'] == 'rejected' and result['accepted'] == {}
    assert fixture['calls'] == list(q.PHASES)[:q.PHASES.index(phase) + 1]
    assert 'baseline' not in fixture['calls']
    assert (fixture['output'] / 'raw.tar.gz').is_file()
