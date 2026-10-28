from __future__ import annotations

from pathlib import Path
import shutil
import subprocess

import pytest

from isaforge import codesign as c
from isaforge import llvm_queens_workload as workload


def _compiler():
    compiler = shutil.which('cc') or shutil.which('clang')
    assert compiler is not None
    return compiler


def _compile_adapter(tmp_path, body):
    runner = tmp_path / 'runner.c'
    runner.write_text(body)
    executable = tmp_path / 'queens-host'
    subprocess.run([
        _compiler(), '-std=c99', '-O2', '-fno-builtin',
        '-I', str(c.ROOT / 'benchmarks/llvm-queens/include'),
        str(c.ROOT / workload.ADAPTER), str(runner), '-o', str(executable),
    ], check=True, capture_output=True, text=True)
    return executable


def test_source_pin_and_original_fixed_workload_are_exact():
    record = workload.source_record()
    assert record['commit'] == workload.UPSTREAM_COMMIT
    assert record['fixed_workload']['solves'] == 5000
    assert record['files'][workload.UPSTREAM_C]['bytes'] == 3946
    assert record['files'][workload.REFERENCE]['bytes'] == 299
    assert workload.PARTITION == dict(ram_bytes=8192, program_limit=6400,
        stack_floor=6528, stack_bytes=1664, minimum_guard_bytes=128)
    assert workload.PROTOCOL['candidate_dispatch_enabled'] is False
    assert workload.PROTOCOL['target_candidate_attempts'] == 0


def test_original_host_stdout_and_exit_match_pinned_reference(tmp_path):
    executable = tmp_path / 'original-queens'
    subprocess.run([_compiler(), '-std=c99', '-Os', '-fno-builtin',
        str(c.ROOT / workload.UPSTREAM_C), '-o', str(executable)],
        check=True, capture_output=True)
    result = subprocess.run([str(executable)], capture_output=True, timeout=30)
    assert result.returncode == 0
    assert result.stderr == b''
    assert result.stdout + b'exit 0\n' == (c.ROOT / workload.REFERENCE).read_bytes()


def test_host_adapter_retains_original_workload_and_verifies_output(tmp_path):
    executable = _compile_adapter(tmp_path, '''
extern int benchmark(void), verify_benchmark(int);
extern unsigned int isaforge_queens_output_calls(void);
extern unsigned int isaforge_queens_output_errors(void);
int main(void) {
    for (int trial = 0; trial < 2; ++trial) {
        int result = benchmark();
        if (!verify_benchmark(result)) return 10;
        if (isaforge_queens_output_calls() != 100) return 11;
        if (isaforge_queens_output_errors() != 0) return 12;
        if (verify_benchmark(-1)) return 13;
    }
    return 0;
}
''')
    result = subprocess.run([str(executable)], capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert result.stdout == b''


def test_output_oracle_rejects_failure_missing_extra_reordered_and_unknown_text(tmp_path):
    executable = _compile_adapter(tmp_path, '''
extern void isaforge_queens_reset_output(void);
extern int isaforge_queens_printf(const char *, ...);
extern int isaforge_queens_output_valid(void), verify_benchmark(int);
static void sequence(int first, int last) {
    for (int value = first; value <= last; ++value)
        isaforge_queens_printf("%d\\n", value);
}
int main(void) {
    isaforge_queens_reset_output(); sequence(1, 100);
    if (!verify_benchmark(0)) return 1;
    isaforge_queens_printf(" Error in Queens.\\n");
    if (verify_benchmark(0)) return 2;
    isaforge_queens_reset_output(); sequence(1, 99);
    if (isaforge_queens_output_valid()) return 3;
    sequence(100, 101);
    if (isaforge_queens_output_valid()) return 4;
    isaforge_queens_reset_output(); sequence(1, 98);
    isaforge_queens_printf("%d\\n", 100); isaforge_queens_printf("%d\\n", 99);
    if (isaforge_queens_output_valid()) return 5;
    isaforge_queens_reset_output(); sequence(1, 100);
    isaforge_queens_printf("unexpected");
    if (isaforge_queens_output_valid()) return 6;
    isaforge_queens_reset_output();
    if (verify_benchmark(0)) return 7;
    return 0;
}
''')
    result = subprocess.run([str(executable)], capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr


def test_source_pin_rejects_changed_source_or_reference(tmp_path, monkeypatch):
    root = tmp_path / 'repo'
    for name in (*workload.FILE_BINDINGS, workload.PIN, workload.LICENSE):
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(c.ROOT / name, target)
    monkeypatch.setattr(c, 'ROOT', root)
    assert workload.source_record()['fixed_workload']['solves'] == 5000
    source = root / workload.UPSTREAM_C
    source.write_bytes(source.read_bytes() + b'\n')
    with pytest.raises(ValueError, match='upstream bytes differ'):
        workload.source_record()
    source.write_bytes(source.read_bytes()[:-1])
    reference = root / workload.REFERENCE
    reference.write_bytes(reference.read_bytes().replace(b'exit 0', b'exit 1'))
    with pytest.raises(ValueError, match='upstream bytes differ'):
        workload.source_record()


def test_registration_restores_shared_pipeline_globals_after_error():
    from isaforge import guarded_workload as guarded
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
    assert (output / 'inputs/upstream/Queens.c').read_bytes() == (c.ROOT / workload.UPSTREAM_C).read_bytes()
    assert {'stdlib.h', 'stdio.h', 'upstream/Queens.c',
            'upstream/Queens.reference_output'} <= plan['inputs'].keys()
    assert plan['llvm_queens_protocol']['fixed_solves'] == 5000
    assert plan['source_bindings'][workload.ADAPTER] == c.sha(c.ROOT / workload.ADAPTER)
    assert not (output / 'attempt-ledger').exists()
    assert not (output / 'measurements').exists()
    (output / 'inputs/stdio.h').write_text('changed header')
    with pytest.raises(ValueError, match='Bound llvm-queens input differs'):
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
    from scripts import qualify_llvm_queens as qualification
    assert qualification.PHASES == (
        'prepare', 'discover', 'opportunity', 'baseline', 'public', 'freeze')
    command = qualification.phase_command('prepare', Path('/tmp/native'), Path('/tmp/reference'))
    assert command[command.index('-m') + 1] == 'isaforge.llvm_queens_workload'
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
    from scripts import qualify_llvm_queens as qualification
    assert qualification.classify_phase_failure('opportunity', tmp_path) == 'failed'
    c.seal(tmp_path / 'opportunity.json', dict(passed=False, measured_candidate_labels_used=False))
    assert qualification.classify_phase_failure('opportunity', tmp_path) == 'rejected'
