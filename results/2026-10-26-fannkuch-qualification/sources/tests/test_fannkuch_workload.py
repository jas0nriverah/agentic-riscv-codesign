"""Fannkuch qualification pins, public gate, and candidate-dispatch boundary."""
from __future__ import annotations

from pathlib import Path
import shutil

import pytest
import tarfile

from isaforge import codesign as c, fannkuch_workload as w
from scripts import qualify_fannkuch as q


def public_pool():
    rows = []
    for index in range(w.POOL_SIZE):
        row = {name: 0 for name in w.b.PUBLIC_KEYS}
        row.update(candidate_id=f'candidate_{index:02d}', benchmark='synthetic-public',
            formula='add(in0,slli(in1,2))', size=2, runs=10, places=1,
            saved=10, saved_percent=1., depth=2, tree_op_count=2,
            input_count=2, constant_count=1, unique_constant_count=1,
            max_abs_constant=2, op_add=1, op_slli=1)
        row['latency_features'] = {name: 0 for name in w.b.LATENCY_KEYS}
        row['latency_features'].update(baseline_cycles=10000,
            baseline_instructions=1000, baseline_cpi=10.,
            replacement_execution_fraction=.01, occurrence_size_min=2,
            occurrence_size_max=2, dynamic_software_cycles=100,
            dynamic_custom_cycles=50, estimated_saved_cycles=50,
            estimated_cycle_reduction=.004, estimated_speedup=10000/9950,
            region_custom_instructions=10)
        rows.append(row)
    return rows


def test_source_pins_include_exact_oracle_and_adapter_identity():
    pins = w.verify_source_pins()
    assert pins['commit'] == w.UPSTREAM_COMMIT
    assert pins['adapter_sha256'] == 'b51a5b22d42c94a3a63efff2261713e3e41ad13f51b0ccff987bd245302382e6'
    assert w.upstream_record()['expected_result_u32'] == 1081212944
    assert w.PROTOCOL['unchanged_algorithm'] is True
    assert w.PROTOCOL['unchanged_upstream_source'] is False
    assert w.PROTOCOL['candidate_dispatch_enabled'] is False


def test_source_pin_manifest_tampering_is_rejected(tmp_path, monkeypatch):
    for name in (w.MANIFEST, w.HTML, w.ORACLE, w.EXTRACTED, w.PROGRAM, w.LICENSE):
        destination = tmp_path / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(c.ROOT / name, destination)
    manifest = c.read(tmp_path / w.MANIFEST)
    manifest['upstream']['commit'] = '0' * 40
    (tmp_path / w.MANIFEST).write_text(__import__('json').dumps(manifest))
    monkeypatch.setattr(c, 'ROOT', tmp_path)
    with pytest.raises(ValueError, match='upstream identity'):
        w.verify_source_pins()


def test_coordinated_adapter_and_manifest_hash_change_is_rejected(tmp_path, monkeypatch):
    import hashlib
    for name in (w.MANIFEST, w.HTML, w.ORACLE, w.EXTRACTED, w.PROGRAM, w.LICENSE):
        destination = tmp_path / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(c.ROOT / name, destination)
    adapter = tmp_path / w.PROGRAM
    adapter.write_bytes(adapter.read_bytes() + b'\n/* unreviewed */\n')
    manifest = c.read(tmp_path / w.MANIFEST)
    manifest['adapted_source']['sha256'] = hashlib.sha256(adapter.read_bytes()).hexdigest()
    (tmp_path / w.MANIFEST).write_text(__import__('json').dumps(manifest))
    monkeypatch.setattr(c, 'ROOT', tmp_path)
    with pytest.raises(ValueError, match='independently approved'):
        w.verify_source_pins()


def test_registration_restores_nested_globals_even_when_nested():
    g = w.g
    globals_before = (g.SOURCE, g.WORKLOADS, g.POOL_SIZE, g.NATIVE_LIMITS,
        g.q.SOURCE, g.q.WORKLOADS, g.q.POOL_SIZE,
        g.q.bounded.SOURCE, g.q.bounded.WORKLOADS, g.q.bounded.POOL_SIZE,
        g.q.bounded.campaign.WORKLOADS, g.q.bounded.campaign.POOL_SIZE,
        w.evidence._public)
    with pytest.raises(RuntimeError):
        with w.registration():
            assert g.WORKLOADS == {w.WORKLOAD: '../../fannkuch/fannkuchredux_isaforge.c'}
            assert g.POOL_SIZE == 12 and w.evidence._public is w.public_projection
            with w.registration():
                raise RuntimeError('restore nested state')
    assert globals_before == (g.SOURCE, g.WORKLOADS, g.POOL_SIZE, g.NATIVE_LIMITS,
        g.q.SOURCE, g.q.WORKLOADS, g.q.POOL_SIZE,
        g.q.bounded.SOURCE, g.q.bounded.WORKLOADS, g.q.bounded.POOL_SIZE,
        g.q.bounded.campaign.WORKLOADS, g.q.bounded.campaign.POOL_SIZE,
        w.evidence._public)


def test_opportunity_gate_requires_both_thresholds_on_same_candidate():
    rows = public_pool()
    rows[0]['latency_features']['estimated_cycle_reduction'] = .005
    rows[0]['runs'] = rows[0]['latency_features']['region_custom_instructions'] = 9
    rows[0]['latency_features']['dynamic_custom_cycles'] = 45
    rows[0]['latency_features']['replacement_execution_fraction'] = .009
    rows[1]['latency_features']['estimated_cycle_reduction'] = .0049
    assert not w.opportunity_gate(rows)['passed']
    rows[1]['latency_features']['estimated_cycle_reduction'] = .005
    assert w.opportunity_gate(rows)['passed']
    rows[1]['speedup'] = 1.01
    with pytest.raises(ValueError, match='non-public'):
        w.opportunity_gate(rows)
    with pytest.raises(ValueError, match='twelve'):
        w.opportunity_gate(public_pool()[:-1])


def test_candidate_dispatch_is_rejected_before_any_gate_or_native_call(tmp_path, monkeypatch):
    evaluator = object.__new__(w.Evaluator)
    evaluator.root = tmp_path
    monkeypatch.setattr(w, 'require_zero_candidates',
        lambda root: (_ for _ in ()).throw(AssertionError('gate ran before dispatch rejection')))
    monkeypatch.setattr(w, 'check_opportunity',
        lambda root: (_ for _ in ()).throw(AssertionError('opportunity ran before dispatch rejection')))
    with pytest.raises(ValueError, match='candidate dispatch disabled'):
        evaluator.measure('candidate_00')


def test_cli_has_only_baseline_qualification_phases(tmp_path):
    for command in ('measure', 'collect', 'fit'):
        with pytest.raises(SystemExit):
            w.main([command, '--root', str(tmp_path)])


def test_generic_guarded_entrypoint_does_not_register_fannkuch():
    with pytest.raises(ValueError, match='registered workload'):
        w.g.check_plan({'workload': w.WORKLOAD, 'pool_size': w.POOL_SIZE})


@pytest.fixture
def qualification(tmp_path, monkeypatch):
    source_root = c.ROOT
    for name in q.SOURCES:
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_root / name, target)
    monkeypatch.setattr(q, 'ROOT', tmp_path)
    monkeypatch.setattr(c, 'ROOT', tmp_path)
    reference = tmp_path / q.REFERENCE
    c.seal(reference / 'plan.json', {'context_id': 'reference'})
    (tmp_path / q.HISTORY).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / q.HISTORY).write_bytes(b'provenance bytes only')
    monkeypatch.setattr(w, 'verify_source_pins', lambda: {})
    output, native = tmp_path / q.OUTPUT, tmp_path / q.NATIVE
    state = dict(reject=None, interrupt=None, drift=None, native_drift=None,
                 artifact=None, calls=[])

    def observe(argv, folder, *, cwd, metadata, timeout_seconds):
        phase = metadata['phase']
        protocol = c.unseal(output / 'protocol.json')
        assert argv == protocol['phase_commands'][phase]
        assert protocol['candidate_dispatch_enabled'] is False
        assert protocol['minimum_calibrated_cycle_reduction'] == .005
        assert protocol['minimum_timed_replacements'] == 10
        assert protocol['pool_size'] == 12
        state['calls'].append(phase)
        native.mkdir(parents=True, exist_ok=True)
        if not (native / 'plan.json').exists():
            source_bindings = {name: protocol['source_bindings'][name]
                for name in w.GATE_SOURCES}
            native_plan = dict(context_id='fannkuch-test', reference_context='reference',
                source_bindings=source_bindings,
                inputs={'program.c': source_bindings[w.PROGRAM]})
            c.seal(native / 'plan.json', native_plan)
            for name in w.GATE_SOURCES:
                destination = native / 'sources' / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(output / 'sources' / name, destination)
            program = native / 'inputs/program.c'
            program.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(output / 'sources' / w.PROGRAM, program)
        if phase == 'freeze':
            c.seal(native / 'evaluation-protocol.json', {
                'pool_names': [f'candidate_{i:02d}' for i in range(12)],
                'maximum_candidate_attempts': 12})
        if phase == state['native_drift']:
            (native / 'sources' / w.SOURCE).write_text('changed native source copy')
        rejected = phase == state['reject']
        if phase == state['artifact']:
            candidate = native / 'attempt-ledger/candidate_00.json'
            candidate.parent.mkdir(parents=True, exist_ok=True)
            candidate.write_text('{}\n')
        record = dict(status='nonzero_exit' if rejected else 'success',
            returncode=int(rejected), durations=dict(monotonic_elapsed_seconds=1.,
            utc_elapsed_seconds=1., clock_disagreement_detected=False))
        c.seal(folder / 'record.json', record)
        if phase == state['drift']:
            (tmp_path / 'docs/fannkuch-adapter-contract-2026-10-26.md').write_text('drifted after phase')
        if phase == state['interrupt']:
            raise KeyboardInterrupt('preserved test interruption')
        return record

    monkeypatch.setattr(q.observed_command, 'run', observe)
    monkeypatch.setattr(q.w, 'validate_inputs', lambda root: {'context_id': 'fannkuch-test'})
    monkeypatch.setattr(q.w, 'check_opportunity', lambda root: {'passed': True})
    return dict(output=output, native=native, reference=reference, state=state)


def test_qualification_runs_fixed_order_and_archives_without_candidate_labels(qualification):
    f = qualification
    result = q.qualify(f['output'], f['native'], f['reference'])
    assert result['status'] == 'accepted' and result['target_candidate_attempts'] == 0
    assert f['state']['calls'] == list(q.PHASES)
    assert (f['output'] / 'raw.tar.gz').is_file()
    assert c.unseal(f['output'] / 'manifest.json')['raw.tar.gz'] == c.sha(f['output'] / 'raw.tar.gz')
    with pytest.raises(ValueError, match='Fresh'):
        q.qualify(f['output'], f['native'], f['reference'])


@pytest.mark.parametrize('phase', ['discover', 'opportunity'])
def test_rejected_qualification_stops_and_preserves_archive(qualification, phase):
    f = qualification
    f['state']['reject'] = phase
    result = q.qualify(f['output'], f['native'], f['reference'])
    assert result['status'] == 'rejected'
    assert f['state']['calls'] == list(q.PHASES)[:q.PHASES.index(phase) + 1]
    assert 'baseline' not in f['state']['calls']
    assert (f['output'] / 'raw.tar.gz').is_file()


def test_interruption_preserves_partial_archive(qualification):
    f = qualification
    f['state']['interrupt'] = 'discover'
    with pytest.raises(KeyboardInterrupt):
        q.qualify(f['output'], f['native'], f['reference'])
    assert f['state']['calls'] == ['prepare', 'discover']
    assert c.unseal(f['output'] / 'qualification.json')['status'] == 'interrupted'
    assert (f['output'] / 'raw.tar.gz').is_file()


def test_source_drift_before_prepare_is_rejected_before_phase_runs(qualification, monkeypatch):
    f = qualification
    original = q.verify_outer_snapshot
    changed = False

    def drift_then_check(output, protocol):
        nonlocal changed
        if not changed:
            changed = True
            (q.ROOT / 'docs/fannkuch-adapter-contract-2026-10-26.md').write_text('drifted before prepare')
        return original(output, protocol)

    monkeypatch.setattr(q, 'verify_outer_snapshot', drift_then_check)
    with pytest.raises(ValueError, match='Live qualification source changed'):
        q.qualify(f['output'], f['native'], f['reference'])
    assert f['state']['calls'] == []
    assert c.unseal(f['output'] / 'qualification.json')['status'] == 'failed'


def test_source_drift_between_phases_fails_and_archives(qualification):
    f = qualification
    f['state']['drift'] = 'discover'
    with pytest.raises(ValueError, match='Live qualification source changed'):
        q.qualify(f['output'], f['native'], f['reference'])
    assert f['state']['calls'] == ['prepare', 'discover']
    assert c.unseal(f['output'] / 'qualification.json')['status'] == 'failed'
    assert (f['output'] / 'raw.tar.gz').is_file()


def test_native_source_archive_drift_is_rejected(qualification):
    f = qualification
    f['state']['native_drift'] = 'prepare'
    with pytest.raises(ValueError, match='Prepared native plan/source archive differs'):
        q.qualify(f['output'], f['native'], f['reference'])
    assert f['state']['calls'] == ['prepare']
    assert c.unseal(f['output'] / 'qualification.json')['status'] == 'failed'
    assert (f['output'] / 'raw.tar.gz').is_file()


def test_candidate_artifact_violation_is_archived_and_count_not_claimed(qualification):
    f = qualification
    f['state']['artifact'] = 'discover'
    with pytest.raises(ValueError, match='zero candidate attempts'):
        q.qualify(f['output'], f['native'], f['reference'])
    record = c.unseal(f['output'] / 'qualification.json')
    assert record['status'] == 'failed'
    assert record['target_candidate_attempts'] is None
    assert record['candidate_attempt_count_status'].startswith('uncertified')
    with tarfile.open(f['output'] / 'raw.tar.gz', 'r:gz') as archive:
        assert any(name.endswith('attempt-ledger/candidate_00.json')
                   for name in archive.getnames())


def test_frozen_pool_remains_non_authorizing(qualification):
    f = qualification
    result = q.qualify(f['output'], f['native'], f['reference'])
    assert result['status'] == 'accepted'
    protocol = c.unseal(f['output'] / 'protocol.json')
    assert protocol['pool_freeze_is_candidate_authorization'] is False
    evaluator = object.__new__(w.Evaluator)
    evaluator.root = f['native']
    with pytest.raises(ValueError, match='dispatch disabled'):
        evaluator.measure('candidate_00')
    w.require_zero_candidates(f['native'])
