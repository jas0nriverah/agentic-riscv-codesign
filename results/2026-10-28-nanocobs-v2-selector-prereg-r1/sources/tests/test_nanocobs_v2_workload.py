from __future__ import annotations

from pathlib import Path
import shutil
import subprocess

import pytest

from isaforge import codesign as c
from isaforge import nanocobs_v2_workload as workload


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
            assert guarded.POOL_SIZE == 30
            assert guarded.WORKLOADS == workload.WORKLOADS
            raise RuntimeError('restoration probe')
    after = (guarded.SOURCE, guarded.WORKLOADS, guarded.POOL_SIZE,
        guarded.NATIVE_LIMITS, guarded.q.WORKLOADS, guarded.q.POOL_SIZE,
        guarded.q.bounded.POOL_SIZE, guarded.q.bounded.campaign.POOL_SIZE,
        workload.evidence._public)
    assert after == before


def test_preparation_copies_source_and_adapter_dependencies_without_native_tools(tmp_path, monkeypatch):
    def prepare_stub(reference, output, name, size, *, program_limit, stack_floor):
        assert name == workload.WORKLOAD and size == 30
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
    from scripts import qualify_nanocobs_v2 as qualification
    assert qualification.PHASES == (
        'prepare', 'discover', 'opportunity', 'baseline', 'public', 'freeze')
    command = qualification.phase_command('prepare', Path('/tmp/native'), Path('/tmp/reference'))
    assert command[command.index('-m') + 1] == 'isaforge.nanocobs_v2_workload'
    assert command[-2:] == ['--reference-root', '/tmp/reference']
    rows = [dict(benchmark='embench-' + workload.WORKLOAD + ':context')]
    monkeypatch.setattr(workload, 'PUBLIC', lambda *args: rows)
    assert workload.public_projection(None, dict(context_id='context', pool_size=30), dict(pool=[{}]), None, None)[0][
        'benchmark'] == workload.GROUP + ':context'


def test_opportunity_accepts_nonempty_even_zero_or_negative_benefit(monkeypatch):
    monkeypatch.setattr(workload, 'source_family_audit', lambda rows: {})
    monkeypatch.setattr(workload.budget, 'occurrence_count', lambda row: row['runs'])
    rows = [dict(candidate_id='negative', runs=1,
                 latency_features=dict(estimated_cycle_reduction=-.01))]
    assert workload.opportunity_gate(rows)['passed']
    assert workload.opportunity_gate(rows)['actual_pool_size'] == 1
    assert not workload.opportunity_gate([])['passed']


def test_only_a_sealed_failed_opportunity_is_classified_as_source_rejection(tmp_path):
    from scripts import qualify_nanocobs_v2 as qualification
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


def test_variable_pool_zero_one_below_cap_and_over_cap(monkeypatch):
    monkeypatch.setattr(workload.latency_features, 'latency_table', lambda _: {})
    monkeypatch.setattr(workload.latency_features, 'instruction_latency', lambda *args: 1)
    for count in (0, 1, 10, 30, 45):
        rows = [dict(name=f'candidate_{i:02d}', formula=str(i),
                     occurrences=[dict(pcs=['0x0'])]) for i in range(count)]
        monkeypatch.setattr(workload.g, '_guarded_extract',
            lambda *args: dict(executable_candidates=rows, executable_formula_count=len(rows)))
        if count == 0:
            with pytest.raises(ValueError, match='No legal calibrated'):
                workload.variable_extract_pool({0:{}}, {}, {}, 30, {})
        else:
            result = workload.variable_extract_pool({0:{}}, {}, {}, 30, {})
            assert len(result['pool']) == min(count, 30)
            assert result['actual_pool_size'] == min(count, 30)
            assert result['eligible_formula_count'] == count
            assert len(set(result['selected_rank_indices'])) == min(count, 30)
            assert result['pool'][0] == rows[0]
            assert result['pool'][-1] == rows[-1]


def test_effective_policy_budget_is_bounded_by_actual_pool():
    assert workload.effective_policy_budget(3, 1) == 1
    assert workload.effective_policy_budget(3, 10) == 3
    assert workload.effective_policy_budget(3, 0) == 0
    with pytest.raises(ValueError):
        workload.effective_policy_budget(0, 10)


def test_registration_restores_all_variable_pool_adapters():
    def snapshot():
        return (workload.g.partition.extract_pool, workload.g.authenticate_discovery,
                workload.g.POOL_RULE, workload.g.q.bounded.compact.FLAGS, workload.g.audit)
    before = snapshot()
    with pytest.raises(RuntimeError):
        with workload.registration():
            assert workload.g.partition.extract_pool is workload.variable_extract_pool
            assert workload.g.authenticate_discovery is workload.authenticate_discovery
            assert workload.g.audit is workload.audit
            raise RuntimeError('restore')
    assert snapshot() == before


def test_audit_uses_authenticated_variable_baseline_and_ledger(tmp_path, monkeypatch):
    monkeypatch.setattr(workload, 'baseline_public',
        lambda root: ([{}], dict(context_id='context'), dict(workload='nanocobs')))
    monkeypatch.setattr(workload.g.attempts, 'read_attempt',
        lambda *args: dict(status='success'))
    assert workload.audit(tmp_path)['actual_pool_size'] == 1
    with workload.registration():
        assert workload.g.adapter_for_plan.__module__ == 'isaforge.guarded_workload'
        assert workload.g.audit is workload.audit


def test_sealed_zero_legal_rejection_is_explicit_and_plan_bound(tmp_path):
    from scripts import qualify_nanocobs_v2 as qualification
    c.seal(tmp_path / 'plan.json', dict(context_id='context'))
    rejection = dict(passed=False, source_level_rejection=True, context_id='context',
        plan_sha256=c.sha(tmp_path / 'plan.json'), extraction=dict(actual_pool_size=0))
    c.seal(tmp_path / 'discovery-rejection.json', rejection)
    assert qualification.classify_phase_failure('discover', tmp_path) == 'rejected'
    rejection['context_id'] = 'changed'
    c.seal(tmp_path / 'discovery-rejection.json', rejection)
    assert qualification.classify_phase_failure('discover', tmp_path) == 'failed'


def test_authenticator_rederives_actual_count_and_rejects_metadata_tamper(tmp_path, monkeypatch):
    folder = tmp_path / 'discovery/attempt-000'
    (folder / 'marked').mkdir(parents=True)
    (folder / 'original').mkdir()
    (folder / 'profile').mkdir()
    for name in ('program.s', 'marked.S', 'marked/symbols.txt',
                 'marked/disassembly.txt', 'marked/firmware.hex', 'original/firmware.hex'):
        (folder / name).write_text('')
    c.write(folder / 'profile/simulation.json', {})
    c.write(tmp_path / 'inputs/latency-calibration.json', {})
    plan = dict(context_id='context', workload=workload.WORKLOAD,
                pool_size=30, memory_partition=workload.PARTITION)
    found = dict(context_id='context', workload=workload.WORKLOAD,
        baseline_image='discovery/attempt-000/marked/firmware.hex',
        profile='discovery/attempt-000/profile/simulation.json',
        memory_check={}, baseline_performance={}, pool=[], executable_candidates=[],
        actual_pool_size=0)
    monkeypatch.setattr(workload.g, 'authenticate_plan', lambda _: plan)
    monkeypatch.setattr(workload.w, 'verify_cache', lambda *args: found)
    monkeypatch.setattr(workload.lowering, 'mark_assembly', lambda _: ('', []))
    monkeypatch.setattr(workload.lowering, 'map_sites', lambda *args: {})
    monkeypatch.setattr(workload.lowering, 'read_program', lambda _: {})
    monkeypatch.setattr(workload.q, 'validate_memory', lambda *args, **kwargs: {})
    monkeypatch.setattr(workload.w, 'validate_execution', lambda _: {})
    monkeypatch.setattr(workload, 'variable_extract_pool', lambda *args:
        dict(pool=[{}], executable_candidates=[{}], actual_pool_size=1))
    with pytest.raises(ValueError, match='metadata differs: actual_pool_size'):
        workload.authenticate_discovery(tmp_path)
