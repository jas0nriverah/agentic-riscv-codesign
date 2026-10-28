"""Offline countnegative v2 source, variable admission and baseline guards."""
from __future__ import annotations
from pathlib import Path
import shutil
import subprocess

import pytest
from isaforge import codesign as c, countnegative_v2_workload as w
from scripts import qualify_countnegative_v2 as qualification


def test_original_source_checksum_input_partition_and_variable_cap_are_pinned():
    assert w.source_record()['commit'] == w.original.UPSTREAM_COMMIT
    source = (c.ROOT / w.BASE / 'countnegative.c').read_text()
    assert '#define MAXSIZE 20' in source and 'checksum == ( int )0x1778de' in source
    assert w.PARTITION == w.g.q.partition_spec(6400, 6528)
    assert w.POOL_SIZE == 30 and w.PROTOCOL['minimum_legal_candidates'] == 1
    assert 'minimum_calibrated_cycle_reduction' not in w.PROTOCOL
    assert 'minimum_timed_replacements' not in w.PROTOCOL
    assert not w.PROTOCOL['candidate_dispatch_enabled']
    assert 'latency' in w.PROTOCOL['technical_calibration_limit']


@pytest.mark.skipif(shutil.which('cc') is None, reason='host compiler unavailable')
def test_host_original_matrix_and_original_checksum(tmp_path):
    binary = tmp_path / 'countnegative-host'
    subprocess.run([shutil.which('cc'), '-std=gnu11', '-O2', '-Wno-unknown-pragmas',
        '-I', str(c.ROOT / w.BASE), str(c.ROOT / w.PROGRAM),
        str(c.ROOT / 'tests/tacle_countnegative_host_smoke.c'), '-o', str(binary)],
        check=True, capture_output=True)
    assert subprocess.run([str(binary)], timeout=10).returncode == 0


def test_pinned_adapter_rejects_source_change(tmp_path, monkeypatch):
    root = tmp_path / 'repo'
    for name in (w.PROGRAM, w.PROVENANCE, *(w.BASE + n for n in w.original.UPSTREAM)):
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(c.ROOT / name, target)
    monkeypatch.setattr(c, 'ROOT', root)
    assert w.source_record()
    (root / w.PROGRAM).write_text('changed')
    with pytest.raises(ValueError, match='adapter/provenance differs'):
        w.source_record()


def test_nested_registration_restores_every_shared_adapter_on_error():
    def snapshot():
        g = w.g
        return (g.SOURCE, g.WORKLOADS, g.POOL_SIZE, g.NATIVE_LIMITS, g.POOL_RULE,
            g.authenticate_discovery, g.audit, g.q.WORKLOADS, g.q.POOL_SIZE,
            g.q.bounded.POOL_SIZE, g.q.bounded.campaign.POOL_SIZE,
            g.partition.extract_pool, w.evidence._public)
    before = snapshot()
    with pytest.raises(RuntimeError):
        with w.registration():
            assert w.g.SOURCE == w.SOURCE
            assert w.g.partition.extract_pool is w.variable.variable_extract_pool
            assert w.g.authenticate_discovery is w.variable.authenticate_discovery
            with w.registration():
                raise RuntimeError('restore')
    assert snapshot() == before


def test_nonempty_admission_has_no_benefit_or_frequency_minimum():
    row = dict(candidate_id='negative', runs=1,
        latency_features=dict(estimated_cycle_reduction=-.02))
    assert w.opportunity_gate([row])['passed']
    assert w.opportunity_gate([row])['actual_pool_size'] == 1
    assert not w.opportunity_gate([])['passed']


@pytest.mark.parametrize('count', [0, 1, 4, 30, 45])
def test_reused_variable_extractor_accepts_singleton_and_caps_only_for_compute(count, monkeypatch):
    rows = [dict(formula=str(i), occurrences=[dict(pcs=['0x0'])]) for i in range(count)]
    monkeypatch.setattr(w.g, '_guarded_extract', lambda *args:
        dict(executable_candidates=rows, executable_formula_count=count))
    monkeypatch.setattr(w.variable.latency_features, 'latency_table', lambda _: {})
    monkeypatch.setattr(w.variable.latency_features, 'instruction_latency', lambda *args: 1)
    with w.registration():
        if count == 0:
            with pytest.raises(w.variable.NoLegalCandidates):
                w.g.partition.extract_pool({0:{}}, {}, {}, 30, {})
        else:
            result = w.g.partition.extract_pool({0:{}}, {}, {}, 30, {})
            assert result['actual_pool_size'] == min(count, 30)
            assert result['eligible_formula_count'] == count
            assert len(result['pool']) == min(count, 30)


def test_prepare_copies_exact_original_input_and_uses_immutable_cap(tmp_path, monkeypatch):
    def stub(reference, output, workload, cap, *, program_limit, stack_floor):
        assert (workload, cap, program_limit, stack_floor) == (w.WORKLOAD,30,6400,6528)
        inputs = output / 'inputs'
        inputs.mkdir(parents=True)
        shutil.copyfile(c.ROOT / w.PROGRAM, inputs / 'program.c')
        return dict(workload=workload, pool_size=cap, source_bindings={}, context_id='provisional',
            memory_partition=w.PARTITION, inputs={})
    monkeypatch.setattr(w.g, 'prepare', stub)
    monkeypatch.setattr(w.g, 'check_plan', lambda _: None)
    monkeypatch.setattr(w.g, 'validate_runtime_inputs', lambda *args: None)
    output = tmp_path / 'prepared'
    plan = w.prepare(tmp_path / 'reference', output)
    assert w.validate_inputs(output) == plan
    assert plan['pool_size'] == plan['computational_pool_cap'] == 30
    assert (output / 'inputs/countnegative.c').read_bytes() == (c.ROOT / w.BASE / 'countnegative.c').read_bytes()
    (output / 'inputs/countnegative.c').write_text('changed')
    with pytest.raises(ValueError, match='Bound countnegative v2 input differs'):
        w.validate_inputs(output)


def test_candidate_dispatch_rejected_before_native_or_opportunity(tmp_path, monkeypatch):
    evaluator = w.Evaluator.__new__(w.Evaluator)
    evaluator.root = tmp_path
    monkeypatch.setattr(w, 'check_opportunity', lambda *args: pytest.fail('gate reached'))
    monkeypatch.setattr(w.g.Evaluator, 'measure', lambda *args: pytest.fail('native reached'))
    with pytest.raises(ValueError, match='Candidate dispatch disabled'):
        evaluator.measure('candidate_00')
    assert not list(tmp_path.iterdir())


def test_qualifier_reuses_phase_runner_with_new_module_and_restores_driver(monkeypatch):
    donor = qualification.driver
    before = donor.w, donor.SOURCE, donor.SOURCES, donor.phase_command
    def stub(*args):
        assert donor.w is w
        command = donor.phase_command('discover', Path('/native'), Path('/ref'))
        assert command[2] == 'isaforge.countnegative_v2_workload'
        assert set(w.GATE_SOURCES) <= set(donor.SOURCES)
        return {'status':'offline-test'}
    monkeypatch.setattr(donor, 'qualify', stub)
    assert qualification.qualify('/output','/native','/ref')['status'] == 'offline-test'
    assert (donor.w, donor.SOURCE, donor.SOURCES, donor.phase_command) == before
