from __future__ import annotations

from pathlib import Path
import shutil
import subprocess

from isaforge import codesign as c
from isaforge import tiny_regex_workload as workload


def test_source_pin_and_fixed_suite_contract_are_exact():
    record = workload.source_record()
    assert record['fixed_cases'] == 76
    assert record['commit'] == workload.UPSTREAM_COMMIT
    assert record['files'][workload.UPSTREAM_TEST]['bytes'] == 8053
    assert workload.PARTITION == {
        'ram_bytes': 8192, 'program_limit': 6400, 'stack_floor': 6528,
        'stack_bytes': 1664, 'minimum_guard_bytes': 128,
    }
    assert workload.PROTOCOL['target_candidate_attempts'] == 0
    assert workload.PROTOCOL['candidate_dispatch_enabled'] is False


def test_host_adapter_passes_all_unchanged_upstream_vectors(tmp_path: Path):
    compiler = shutil.which('cc') or shutil.which('clang')
    assert compiler is not None
    runner = tmp_path / 'runner.c'
    runner.write_text('''
extern unsigned long isaforge_tiny_regex_case_count(void);
extern int benchmark(void);
extern int verify_benchmark(int);
int main(void) {
    if (isaforge_tiny_regex_case_count() != 76) return 10;
    int failures = benchmark();
    return verify_benchmark(failures) ? 0 : 11;
}
''')
    executable = tmp_path / 'tiny-regex-host'
    subprocess.run([
        compiler, '-std=c99', '-O2', '-fno-builtin',
        '-I', str(c.ROOT / 'benchmarks/tiny-regex/include'),
        '-I', str(c.ROOT / 'benchmarks/tiny-regex/upstream'),
        str(c.ROOT / workload.ADAPTER), str(runner), '-o', str(executable),
    ], check=True, capture_output=True, text=True)
    subprocess.run([str(executable)], check=True, capture_output=True, text=True)


def test_registration_restores_shared_pipeline_globals():
    from isaforge import guarded_workload as guarded

    before = (guarded.SOURCE, guarded.WORKLOADS, guarded.POOL_SIZE,
              guarded.NATIVE_LIMITS, guarded.q.WORKLOADS,
              guarded.q.POOL_SIZE, guarded.q.bounded.POOL_SIZE,
              guarded.q.bounded.campaign.POOL_SIZE)
    with workload.registration():
        assert guarded.SOURCE == workload.SOURCE
        assert guarded.WORKLOADS == workload.WORKLOADS
        assert guarded.POOL_SIZE == workload.POOL_SIZE == 12
        assert guarded.q.WORKLOADS == workload.WORKLOADS
    after = (guarded.SOURCE, guarded.WORKLOADS, guarded.POOL_SIZE,
             guarded.NATIVE_LIMITS, guarded.q.WORKLOADS,
             guarded.q.POOL_SIZE, guarded.q.bounded.POOL_SIZE,
             guarded.q.bounded.campaign.POOL_SIZE)
    assert after == before


def test_source_family_audit_classifies_formula_overlap_without_claiming_independence():
    history = c.unseal(c.ROOT / workload.HISTORY)
    known_formula = history['rows'][0]['formula']
    audit = workload.source_family_audit([
        {'candidate_id': 'candidate-test', 'formula': known_formula},
    ])
    assert audit['historical_verified_labels'] == 122
    assert audit['historical_workload_groups'] == 14
    assert audit['target_candidate_count'] == 1
    assert 'Descriptive formula-tree overlap only' in audit['interpretation']
    assert audit['overlapping_operation_families']
    assert audit['overlap_candidate_ids'] == ['candidate-test']


def test_qualification_commands_are_bounded_and_baseline_only():
    from scripts import qualify_tiny_regex as qualification

    assert qualification.PHASES == (
        'prepare', 'discover', 'opportunity', 'baseline', 'public', 'freeze')
    assert workload.PROTOCOL['candidate_dispatch_enabled'] is False
    command = qualification.phase_command(
        'prepare', Path('/tmp/native'), Path('/tmp/reference'))
    assert command[command.index('prepare') + 1:] == [
        '--root', '/tmp/native', '--reference-root', '/tmp/reference']
