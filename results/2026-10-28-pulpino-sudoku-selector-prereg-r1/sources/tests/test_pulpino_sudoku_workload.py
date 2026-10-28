from __future__ import annotations

from pathlib import Path
import shutil
import subprocess

import pytest

from isaforge import codesign as c
from isaforge import pulpino_sudoku_workload as workload
from scripts import build_pulpino_sudoku_adapter as builder


def _compiler():
    compiler = shutil.which('cc') or shutil.which('clang')
    assert compiler is not None
    return compiler


def test_source_pin_and_declared_fixed_workload_are_exact():
    record = workload.source_record()
    assert record['commit'] == workload.UPSTREAM_COMMIT
    assert record['fixed_workload']['repetitions'] == 2
    assert record['fixed_workload']['maximum_source_recursion_depth'] == 82
    assert record['files'][workload.UPSTREAM_C]['bytes'] == 5326
    assert record['files'][workload.UPSTREAM_H]['bytes'] == 1096
    assert builder.adapt((c.ROOT / workload.UPSTREAM_C).read_text()).encode() == (
        c.ROOT / workload.ADAPTER).read_bytes()
    assert workload.PARTITION == dict(ram_bytes=8192, program_limit=2304,
        stack_floor=2432, stack_bytes=5760, minimum_guard_bytes=128)
    assert workload.PROTOCOL['candidate_dispatch_enabled'] is False
    assert workload.PROTOCOL['target_candidate_attempts'] == 0


def test_host_adapter_runs_both_solves_and_checks_all_81_cells(tmp_path):
    driver = tmp_path / 'driver.c'
    driver.write_text('''
extern void initialise_benchmark(void), warm_caches(int);
extern int benchmark(void), verify_benchmark(int);
extern int grid_solved[81];
int main(void) {
    initialise_benchmark(); warm_caches(1);
    for (int repeat=0; repeat<2; ++repeat) {
        int result=benchmark();
        if (!verify_benchmark(result)) return 10;
    }
    grid_solved[0] ^= 1;
    if (verify_benchmark(1)) return 11;
    if (verify_benchmark(0)) return 12;
    return 0;
}
''')
    executable = tmp_path / 'sudoku-adapter-host'
    subprocess.run([_compiler(), '-std=gnu17', '-O2', '-fno-builtin',
        str(c.ROOT / workload.ADAPTER), str(driver), '-o', str(executable)],
        check=True, capture_output=True, text=True)
    result = subprocess.run([str(executable)], capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert result.stdout == b''


def test_source_pin_rejects_changed_source(tmp_path, monkeypatch):
    root = tmp_path / 'repo'
    for name in (*workload.FILE_BINDINGS, workload.PIN, workload.LICENSE,
                 workload.ADAPTER):
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(c.ROOT / name, target)
    monkeypatch.setattr(c, 'ROOT', root)
    assert workload.source_record()['fixed_workload']['repetitions'] == 2
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


def test_preparation_copies_exact_source_and_headers_without_native_tools(tmp_path, monkeypatch):
    def prepare_stub(reference, output, name, size, *, program_limit, stack_floor):
        assert name == workload.WORKLOAD and size == 12
        assert (program_limit, stack_floor) == (2304, 2432)
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
    assert (output / 'inputs/upstream/sudokusolver.c').read_bytes() == (
        c.ROOT / workload.UPSTREAM_C).read_bytes()
    assert (output / 'inputs/upstream/sudokusolver.h').read_bytes() == (
        c.ROOT / workload.UPSTREAM_H).read_bytes()
    assert {'program.c', 'upstream/sudokusolver.c',
            'upstream/sudokusolver.h'} <= plan['inputs'].keys()
    assert plan['pulpino_sudoku_protocol']['fixed_solves'] == 2
    assert plan['source_bindings'][workload.ADAPTER] == c.sha(c.ROOT / workload.ADAPTER)
    assert not (output / 'attempt-ledger').exists()
    assert not (output / 'measurements').exists()
    (output / 'inputs/upstream/sudokusolver.h').write_text('changed')
    with pytest.raises(ValueError, match='Bound PULPino Sudoku input differs'):
        workload.validate_inputs(output)


def test_candidate_dispatch_is_denied_before_any_native_operation(tmp_path, monkeypatch):
    evaluator = workload.Evaluator.__new__(workload.Evaluator)
    evaluator.root = tmp_path
    monkeypatch.setattr(workload.g.Evaluator, 'measure',
        lambda *args: pytest.fail('native evaluator must never be called'))
    with pytest.raises(ValueError, match='Candidate dispatch disabled'):
        evaluator.measure('candidate_00')
    assert not list(tmp_path.iterdir())


def test_qualification_cli_and_public_projection_keep_fixed_contract(monkeypatch):
    from scripts import qualify_pulpino_sudoku as qualification
    assert qualification.PHASES == (
        'prepare', 'discover', 'opportunity', 'baseline', 'public', 'freeze')
    command = qualification.phase_command('prepare', Path('/tmp/native'), Path('/tmp/reference'))
    assert command[command.index('-m') + 1] == 'isaforge.pulpino_sudoku_workload'
    assert command[-2:] == ['--reference-root', '/tmp/reference']
    rows = [dict(benchmark='embench-' + workload.WORKLOAD + ':context')]
    monkeypatch.setattr(workload, 'PUBLIC', lambda *args: rows)
    assert workload.public_projection(None, dict(context_id='context'), None, None, None)[0][
        'benchmark'] == workload.GROUP + ':context'


def test_opportunity_requires_both_unchanged_minima_for_the_same_candidate(monkeypatch):
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


def test_only_sealed_false_opportunity_is_classified_as_source_rejection(tmp_path):
    from scripts import qualify_pulpino_sudoku as qualification
    assert qualification.classify_phase_failure('opportunity', tmp_path) == 'failed'
    c.seal(tmp_path / 'opportunity.json', dict(passed=False, measured_candidate_labels_used=False))
    assert qualification.classify_phase_failure('opportunity', tmp_path) == 'rejected'
