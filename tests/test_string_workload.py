"""Exact new ABI context and scoped delegation; no native tools are invoked."""
import copy
import hashlib
import shutil

import pytest

from isaforge import string_workload as w, codesign as c
from scripts import qualify_string_workload as qualifier


def plan_for():
    g = w.bw.g
    names = (w.SOURCE, w.ORIGINAL_BLIND_SOURCE, w.GUARDED_SOURCE, g.QUALIFIED_SOURCE,
             g.guard.SOURCE, g.attempts.SOURCE, g.EVIDENCE_SOURCE, *g.AUTHENTICATION_SOURCES,
             w.PROGRAM, w.LICENSE)
    plan = dict(workload='levenshtein', pool_size=12, memory_partition=dict(w.PARTITION),
                compiler_flags=list(g.q.bounded.compact.FLAGS), simulation_cycle_limit=g.CYCLE_LIMIT,
                native_limits=dict(w.bw.NATIVE_LIMITS), build_variant={'required_entrypoint': w.SOURCE},
                relocation_guard=dict(g.GUARD_RULE), pool_rule=g.POOL_RULE,
                source_bindings={name: c.sha(c.ROOT / name) for name in names},
                workload_group='beebs-levenshtein', abi_extension=w.abi_extension(),
                upstream=dict(suite='BEEBS', commit=w.UPSTREAM_COMMIT, source=w.PROGRAM,
                              source_sha256=w.PROGRAM_SHA256),
                inputs={'program.c': w.PROGRAM_SHA256,
                        'embench_firmware.c': hashlib.sha256(w.harness_source('levenshtein').encode()).hexdigest()})
    plan['context_id'] = c.digest(plan)
    return plan


def reseal_context(plan):
    plan['context_id'] = c.digest({key: value for key, value in plan.items() if key != 'context_id'})
    return plan


def test_standard_strlen_is_only_external_harness_addition():
    source = (c.ROOT / w.PROGRAM).read_text()
    assert c.sha(c.ROOT / w.PROGRAM) == 'fd1ee0e23bab6db0182b32618bc3622a3ce0399714b662076d053d98fb7193f6'
    assert '#include <string.h>' in source and 'size_t strlen(' not in source
    assert w.harness_source('levenshtein') == w.ORIGINAL_HARNESS('levenshtein') + w.STRLEN_ABI
    assert '#include <stddef.h>' in w.STRLEN_ABI
    assert 'size_t strlen(const char *text)' in w.STRLEN_ABI
    assert w.STRLEN_ABI.count('strlen(') == 1  # no recursive runtime dependency
    assert 'while (*end) ++end;' in w.STRLEN_ABI and 'return (size_t)(end - text);' in w.STRLEN_ABI
    assert w.HELPER_SHA256 == hashlib.sha256(w.STRLEN_ABI.encode()).hexdigest()
    with pytest.raises(ValueError):
        w.harness_source('nettle-arcfour')


def test_nested_registration_captures_original_harness_and_restores_on_failure():
    before = w.bw.SOURCE, w.bw.harness_source
    with pytest.raises(RuntimeError):
        with w.registration():
            assert w.bw.SOURCE == w.SOURCE and w.bw.harness_source is w.harness_source
            with w.registration():
                assert w.bw.harness_source('levenshtein').count(w.STRLEN_ABI) == 1
            raise RuntimeError('failed scope')
    assert (w.bw.SOURCE, w.bw.harness_source) == before


def test_new_plan_accepts_original_source_partition_and_rejects_original_entrypoint():
    plan = plan_for()
    w.check_plan(plan)
    assert plan['pool_size'] == 12 and plan['memory_partition']['program_limit'] == 6400
    assert plan['memory_partition']['stack_floor'] == 6528
    with pytest.raises(ValueError):
        w.bw.check_plan(plan)


@pytest.mark.parametrize('change', ['helper', 'harness', 'old_binding', 'new_binding', 'context', 'source', 'pool', 'partition'])
def test_self_consistent_manifest_cannot_authorize_a_different_abi(change):
    plan = plan_for()
    if change == 'helper': plan['abi_extension']['helper_sha256'] = '0' * 64
    elif change == 'harness': plan['inputs']['embench_firmware.c'] = '0' * 64
    elif change == 'old_binding': plan['source_bindings'].pop(w.ORIGINAL_BLIND_SOURCE)
    elif change == 'new_binding': plan['source_bindings'][w.SOURCE] = '0' * 64
    elif change == 'source': plan['inputs']['program.c'] = '0' * 64
    elif change == 'pool': plan['pool_size'] = 6
    elif change == 'partition': plan['memory_partition'] = w.bw.g.q.partition_spec(6272, 6400)
    if change != 'context': reseal_context(plan)
    else: plan['context_id'] = '0' * 64
    with pytest.raises(ValueError): w.check_plan(plan)


def test_exact_original_inputs_and_helper_are_required_on_disk(tmp_path):
    plan = plan_for()
    inputs = tmp_path / 'inputs'; inputs.mkdir()
    shutil.copyfile(c.ROOT / w.PROGRAM, inputs / 'program.c')
    harness = inputs / 'embench_firmware.c'; harness.write_text(w.harness_source('levenshtein'))
    c.seal(tmp_path / 'plan.json', plan)
    assert w.validate_inputs(tmp_path) == plan
    harness.write_text(w.ORIGINAL_HARNESS('levenshtein'))
    with pytest.raises(ValueError, match='harness derivation'): w.validate_inputs(tmp_path)


def test_prepare_rebinds_original_adapter_and_recomputes_context(tmp_path, monkeypatch):
    initial = plan_for()
    initial.pop('abi_extension')
    initial['source_bindings'].pop(w.ORIGINAL_BLIND_SOURCE)
    reseal_context(initial)

    def prepare(reference, output, workload):
        assert workload == 'levenshtein' and w.bw.SOURCE == w.SOURCE
        inputs = output / 'inputs'; inputs.mkdir()
        shutil.copyfile(c.ROOT / w.PROGRAM, inputs / 'program.c')
        (inputs / 'embench_firmware.c').write_text(w.bw.harness_source(workload))
        return copy.deepcopy(initial)

    monkeypatch.setattr(w.bw, 'prepare', prepare)
    plan = w.prepare('unused-reference', tmp_path)
    assert plan['context_id'] != initial['context_id']
    assert plan['inputs']['program.c'] == w.PROGRAM_SHA256
    assert plan['source_bindings'][w.ORIGINAL_BLIND_SOURCE] == c.sha(c.ROOT / w.ORIGINAL_BLIND_SOURCE)
    assert (tmp_path / 'sources' / w.ORIGINAL_BLIND_SOURCE).is_file()
    assert w.validate_inputs(tmp_path) == plan


def test_audit_pack_and_baseline_delegate_with_only_scoped_registration(monkeypatch):
    monkeypatch.setattr(w, 'validate_inputs', lambda root: plan_for())
    before = w.bw.SOURCE, w.bw.harness_source

    def delegate(*args, **kwargs):
        assert w.bw.SOURCE == w.SOURCE and w.bw.harness_source is w.harness_source
        return 'unchanged-evidence'

    monkeypatch.setattr(w.bw, 'audit', delegate)
    monkeypatch.setattr(w.bw, 'pack', delegate)
    assert w.audit('root') == w.pack('root', 'snapshot') == 'unchanged-evidence'
    assert (w.bw.SOURCE, w.bw.harness_source) == before


def test_renewed_qualification_scopes_new_module_and_amends_before_sealing(tmp_path):
    original = qualifier.original
    before = (original.ROOT, original.SOURCE, original.SOURCES, original.workload, original.phase_command, original.c)
    output = tmp_path / 'new'
    amendment = dict(reason='Only missing strlen ABI support', prior_manifest_sha256='a' * 64)
    with pytest.raises(RuntimeError):
        with qualifier.registration(output, amendment):
            assert original.workload is w
            assert original.phase_command('discover', 'root', 'ref')[2] == 'isaforge.string_workload'
            assert w.ORIGINAL_BLIND_SOURCE in original.SOURCES and w.SOURCE in original.SOURCES
            original.c.seal(output / 'protocol.json', {'order': ['levenshtein']})
            sealed = c.unseal(output / 'protocol.json')
            assert sealed['qualification_amendment'] == amendment
            assert sealed['schema'] == 'isaforge-levenshtein-strlen-qualification-v1'
            raise RuntimeError('restore')
    assert (original.ROOT, original.SOURCE, original.SOURCES, original.workload, original.phase_command, original.c) == before
