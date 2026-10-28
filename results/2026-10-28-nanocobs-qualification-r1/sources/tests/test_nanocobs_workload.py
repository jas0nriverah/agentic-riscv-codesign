from __future__ import annotations

from pathlib import Path
import shutil
import subprocess

import pytest

from isaforge import codesign as c
from isaforge import nanocobs_workload as workload


def _compiler():
    compiler = shutil.which('cc') or shutil.which('clang')
    assert compiler is not None
    return compiler


def test_pinned_source_and_full_original_probe_are_exact():
    record = workload.source_record()
    assert record['commit'] == workload.UPSTREAM_COMMIT
    assert record['fixed_cases'] == 8215
    assert workload.WORKLOADS[workload.WORKLOAD] == str(c.ROOT / workload.UPSTREAM_C)
    assert workload.PARTITION == dict(ram_bytes=8192, program_limit=6400,
        stack_floor=6528, stack_bytes=1664, minimum_guard_bytes=128)
    assert workload.PROTOCOL['candidate_dispatch_enabled'] is False
    assert 'shared source bugs' in record['common_mode_limitation']


def test_host_adapter_full_probe_and_checker(tmp_path):
    driver = tmp_path / 'driver.c'
    driver.write_text('''
#include "adapter.c"
int main(void) {
    initialise_benchmark();
    int r = benchmark();
    if (!verify_benchmark(r) || passed != 8215) return 10;
    if (verify_benchmark(1)) return 11;
    ++failed;
    if (verify_benchmark(0)) return 12;
    --failed; --passed;
    if (verify_benchmark(0)) return 13;
    return 0;
}
''')
    executable = tmp_path / 'nanocobs-host'
    subprocess.run([_compiler(), '-std=c99', '-Os', '-DCOBS_SWAR_WORD_BITS=32',
        '-I', str(c.ROOT / 'benchmarks/nanocobs'), str(driver),
        str(c.ROOT / workload.UPSTREAM_C),
        str(c.ROOT / 'benchmarks/nanocobs/upstream/tests/cobs_ref.c'),
        '-o', str(executable)], check=True, capture_output=True, text=True)
    result = subprocess.run([str(executable)], capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert result.stdout == b''


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
        shutil.copyfile(c.ROOT / workload.UPSTREAM_C, inputs / 'program.c')
        shutil.copyfile(c.ROOT / 'hardware/embench_firmware.c', inputs / 'embench_firmware.c')
        return dict(workload=name, pool_size=size, memory_partition=workload.PARTITION,
            compiler_flags=workload.PROTOCOL['compiler_flags'], source_bindings={},
            inputs={}, context_id='provisional')

    monkeypatch.setattr(workload.g, 'prepare', prepare_stub)
    output = tmp_path / 'prepared'
    plan = workload.prepare(tmp_path / 'reference', output)
    assert workload.validate_inputs(output) == plan
    assert (output / 'inputs/program.c').read_bytes() == (c.ROOT / workload.UPSTREAM_C).read_bytes()
    assert {'program.c', 'adapter.c', 'upstream/cobs.c', 'upstream/tests/cobs_ref.c',
            'upstream/tests/qemu/probe.c'} <= plan['inputs'].keys()
    assert plan['nanocobs_protocol']['fixed_cases'] == 8215
    assert plan['source_bindings'][workload.ADAPTER] == c.sha(c.ROOT / workload.ADAPTER)
    assert not (output / 'attempt-ledger').exists()
    assert not (output / 'measurements').exists()
    (output / 'inputs/upstream/tests/cobs_ref.c').write_text('changed')
    with pytest.raises(ValueError, match='Bound nanocobs input differs'):
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
    from scripts import qualify_nanocobs as qualification
    assert qualification.PHASES == (
        'prepare', 'discover', 'opportunity', 'baseline', 'public', 'freeze')
    command = qualification.phase_command('prepare', Path('/tmp/native'), Path('/tmp/reference'))
    assert command[command.index('-m') + 1] == 'isaforge.nanocobs_workload'
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
    from scripts import qualify_nanocobs as qualification
    assert qualification.classify_phase_failure('opportunity', tmp_path) == 'failed'
    c.seal(tmp_path / 'opportunity.json', dict(passed=False, measured_candidate_labels_used=False))
    assert qualification.classify_phase_failure('opportunity', tmp_path) == 'rejected'


def test_source_pin_rejects_modified_reference(tmp_path, monkeypatch):
    root = tmp_path / 'repo'
    for name in (*workload.FILE_BINDINGS, workload.PIN, workload.ADAPTER):
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(c.ROOT / name, target)
    monkeypatch.setattr(c, 'ROOT', root)
    assert workload.source_record()['fixed_cases'] == 8215
    reference = root / 'benchmarks/nanocobs/upstream/tests/cobs_ref.c'
    reference.write_bytes(reference.read_bytes() + b'\n')
    with pytest.raises(ValueError, match='upstream bytes differ'):
        workload.source_record()


def test_link_composition_is_fixed_for_c_original_marked_and_candidate_and_fixtures(tmp_path, monkeypatch):
    from types import SimpleNamespace
    evaluator = workload.Evaluator.__new__(workload.Evaluator)
    evaluator.inputs = tmp_path / 'inputs'
    evaluator.partition = workload.PARTITION
    evaluator.plan = dict(compiler_flags=workload.COMPILER_FLAGS)
    evaluator.tools = dict(gcc='gcc', objcopy='objcopy', objdump='objdump', nm='nm')
    commands = []
    def run(argv, log):
        commands.append(argv)
        if argv[0] == 'objcopy':
            Path(argv[-1]).write_bytes(b'')
        return ''
    evaluator.runner = SimpleNamespace(run=run)
    monkeypatch.setattr(workload.g.q.bounded, 'validate_isa',
        lambda disassembly: dict(custom_static_sites=0))
    monkeypatch.setattr(workload.g.q, 'memory_symbols', lambda *args: (3408, 3000))
    monkeypatch.setattr(workload.g.q, 'memory_image', lambda *args: '')
    fixed = [evaluator.inputs / 'adapter.c', evaluator.inputs / 'upstream/tests/cobs_ref.c']
    for i, source in enumerate(('program.c', 'marked.S', 'candidate_00.S', 'fixture.S')):
        evaluator.compile_program(tmp_path / str(i), Path(source), fixture=i == 3)
        compile_command = commands[-4]
        assert compile_command[0] == 'gcc'
        assert Path(source) in compile_command
        assert all((path in compile_command) == (i != 3) for path in fixed)
        assert evaluator.inputs / 'upstream/cobs.c' not in compile_command
        assert evaluator.inputs / 'upstream/tests/qemu/probe.c' not in compile_command
        assert '-DCOBS_SWAR_WORD_BITS=32' in compile_command
