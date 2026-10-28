from __future__ import annotations

from pathlib import Path
import shutil
import subprocess

import pytest

from isaforge import codesign as c
from isaforge import pulpino_hanoi_workload as workload


def _compiler():
    compiler = shutil.which('cc') or shutil.which('clang')
    assert compiler is not None
    return compiler


def test_pinned_source_and_extracted_recursive_algorithm_are_exact():
    record = workload.source_record()
    assert record['commit'] == workload.UPSTREAM_COMMIT
    assert record['fixed_workload']['maximum_source_recursion_depth'] == 12
    assert record['files'][workload.UPSTREAM_C]['bytes'] == 1847
    assert workload.PARTITION == dict(ram_bytes=8192, program_limit=6400,
        stack_floor=6528, stack_bytes=1664, minimum_guard_bytes=128)
    assert workload.PROTOCOL['candidate_dispatch_enabled'] is False
    assert workload.PROTOCOL['target_candidate_attempts'] == 0


def test_host_adapter_runs_original_twelve_plate_input_and_rejects_bad_results(tmp_path):
    driver = tmp_path / 'driver.c'
    driver.write_text('''
#include "adapter.c"
int main(void) {
    for (int repeat = 0; repeat < 2; ++repeat) {
        int result = benchmark();
        if (!verify_benchmark(result)) return 10;
        if (verify_benchmark(0)) return 11;
    }
    B[0] ^= 1;
    if (verify_benchmark(1)) return 12;
    return 0;
}
''')
    executable = tmp_path / 'hanoi-adapter-host'
    subprocess.run([_compiler(), '-std=gnu17', '-O2', '-fno-builtin',
        '-I', str(c.ROOT / 'benchmarks/pulpino-hanoi'), str(driver),
        '-o', str(executable)], check=True, capture_output=True, text=True)
    result = subprocess.run([str(executable)], capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert result.stdout == b''


def test_source_pin_rejects_changed_upstream_or_adapter(tmp_path, monkeypatch):
    root = tmp_path / 'repo'
    for name in (*workload.FILE_BINDINGS, workload.PIN, workload.LICENSE,
                 workload.ADAPTER, workload.ALGORITHM):
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(c.ROOT / name, target)
    monkeypatch.setattr(c, 'ROOT', root)
    assert workload.source_record()['fixed_workload']['maximum_source_recursion_depth'] == 12
    source = root / workload.UPSTREAM_C
    source.write_bytes(source.read_bytes() + b'\n')
    with pytest.raises(ValueError, match='upstream bytes differ'):
        workload.source_record()


def test_registration_restores_shared_pipeline_globals_after_error():
    guarded = workload.g
    before = (guarded.SOURCE, guarded.WORKLOADS, guarded.POOL_SIZE,
        guarded.NATIVE_LIMITS, guarded.q.WORKLOADS, guarded.q.POOL_SIZE,
        guarded.q.bounded.POOL_SIZE, guarded.q.bounded.campaign.POOL_SIZE,
        workload.evidence._public)
    with pytest.raises(RuntimeError):
        with workload.registration():
            assert guarded.SOURCE == workload.SOURCE
            assert guarded.POOL_SIZE == 12
            assert guarded.WORKLOADS == workload.WORKLOADS
            raise RuntimeError('restoration probe')
    after = (guarded.SOURCE, guarded.WORKLOADS, guarded.POOL_SIZE,
        guarded.NATIVE_LIMITS, guarded.q.WORKLOADS, guarded.q.POOL_SIZE,
        guarded.q.bounded.POOL_SIZE, guarded.q.bounded.campaign.POOL_SIZE,
        workload.evidence._public)
    assert after == before


def test_preparation_copies_source_and_adapter_dependencies_without_native_tools(tmp_path, monkeypatch):
    def prepare_stub(reference, output, name, size, *, program_limit, stack_floor):
        assert name == workload.WORKLOAD and size == 12
        assert (program_limit, stack_floor) == (6400, 6528)
        inputs = output / 'inputs'
        inputs.mkdir(parents=True)
        shutil.copyfile(c.ROOT / workload.ADAPTER, inputs / 'program.c')
        shutil.copyfile(c.ROOT / 'hardware/embench_firmware.c', inputs / 'embench_firmware.c')
        return dict(workload=name, pool_size=size, memory_partition=workload.PARTITION,
            compiler_flags=workload.PROTOCOL['compiler_flags'], source_bindings={},
            inputs={}, context_id='provisional')

    monkeypatch.setattr(workload.g, 'prepare', prepare_stub)
    output = tmp_path / 'prepared'
    plan = workload.prepare(tmp_path / 'reference', output)
    assert workload.validate_inputs(output) == plan
    assert (output / 'inputs/upstream/towerofhanoi.c').read_bytes() == (
        c.ROOT / workload.UPSTREAM_C).read_bytes()
    assert (output / 'inputs/algorithm.c').read_bytes() == (
        c.ROOT / workload.ALGORITHM).read_bytes()
    assert {'program.c', 'algorithm.c', 'upstream/towerofhanoi.c',
            'upstream/LICENSE'} <= plan['inputs'].keys()
    assert plan['pulpino_hanoi_protocol']['plate_count'] == 12
    assert plan['source_bindings'][workload.ADAPTER] == c.sha(c.ROOT / workload.ADAPTER)
    assert not (output / 'attempt-ledger').exists()
    assert not (output / 'measurements').exists()
    (output / 'inputs/upstream/towerofhanoi.c').write_text('changed')
    with pytest.raises(ValueError, match='Bound PULPino Hanoi input differs'):
        workload.validate_inputs(output)


def test_candidate_dispatch_is_denied_before_native_operation(tmp_path, monkeypatch):
    evaluator = workload.Evaluator.__new__(workload.Evaluator)
    evaluator.root = tmp_path
    monkeypatch.setattr(workload.g.Evaluator, 'measure',
        lambda *args: pytest.fail('native evaluator must not run'))
    with pytest.raises(ValueError, match='Candidate dispatch disabled'):
        evaluator.measure('candidate_00')
    assert not list(tmp_path.iterdir())


def test_qualification_cli_and_public_projection_keep_fixed_contract(monkeypatch):
    from scripts import qualify_pulpino_hanoi as qualification
    assert qualification.PHASES == (
        'prepare', 'discover', 'opportunity', 'baseline', 'public', 'freeze')
    command = qualification.phase_command('prepare', Path('/tmp/native'), Path('/tmp/reference'))
    assert command[command.index('-m') + 1] == 'isaforge.pulpino_hanoi_workload'
    assert command[-2:] == ['--reference-root', '/tmp/reference']
    rows = [dict(benchmark='embench-' + workload.WORKLOAD + ':context')]
    monkeypatch.setattr(workload, 'PUBLIC', lambda *args: rows)
    assert workload.public_projection(None, dict(context_id='context'), None, None, None)[0][
        'benchmark'] == workload.GROUP + ':context'


def test_opportunity_keeps_both_unchanged_minima_on_the_same_candidate(monkeypatch):
    monkeypatch.setattr(workload, 'source_family_audit', lambda rows: {})
    monkeypatch.setattr(workload.budget, 'occurrence_count', lambda row: row['runs'])
    rows = [dict(candidate_id='fast-but-rare', runs=9,
                 latency_features=dict(estimated_cycle_reduction=.006)),
            dict(candidate_id='frequent-but-small', runs=100,
                 latency_features=dict(estimated_cycle_reduction=.004))]
    gate = workload.opportunity_gate(rows)
    assert not gate['passed']
    assert not gate['measured_candidate_labels_used']
    assert gate['target_candidate_attempts'] == 0
    rows.append(dict(candidate_id='both', runs=10,
                     latency_features=dict(estimated_cycle_reduction=.005)))
    assert workload.opportunity_gate(rows)['qualifying_candidate_ids'] == ['both']


def test_only_a_sealed_failed_opportunity_is_classified_as_source_rejection(tmp_path):
    from scripts import qualify_pulpino_hanoi as qualification
    assert qualification.classify_phase_failure('opportunity', tmp_path) == 'failed'
    c.seal(tmp_path / 'opportunity.json', dict(passed=False, measured_candidate_labels_used=False))
    assert qualification.classify_phase_failure('opportunity', tmp_path) == 'rejected'


def test_discovery_diagnosis_requires_fixed_candidate_count_without_relaxing_guards():
    from scripts.diagnose_pulpino_hanoi_discovery import classify_candidate_counts
    assert classify_candidate_counts(raw=3, executable=3, relocation_safe=0,
        calibrated=0, required=12) == 'source_rejected_no_relocation_safe_candidates'
    assert classify_candidate_counts(raw=15, executable=12, relocation_safe=11,
        calibrated=11, required=12) == 'source_rejected_candidate_pool_too_small'
    assert classify_candidate_counts(raw=15, executable=15, relocation_safe=13,
        calibrated=12, required=12) == 'pool_size_gate_passed'
