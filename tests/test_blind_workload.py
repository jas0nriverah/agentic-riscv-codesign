"""Source, ABI and protocol isolation checks; these never run native jobs."""
import copy
import hashlib
import re
import shutil

import pytest

from isaforge import blind_workload as w, codesign as c, guarded_workload as g


PINNED = {
    'aha-compress': '1e9e7929e0466968e1bc069f406597aa7bb1c7e1eeaeb7f4bc593be4510d4af8',
    'ndes': '78d92b71cc0edd3a26ef1a49e2904ac7d6b6dc5ab33d172ab17cb68fdb92d071',
    'nettle-arcfour': '1efb711913921a574cb6092a4e2f996f8514cd1d2fade3c19c9aef6d5787cff7',
    'nettle-md5': '7b8b50fc6ffe75a6e6fa9067a79f502d8cf4a3e5701bfc0ed94de1347b830b2f',
    'levenshtein': 'fd1ee0e23bab6db0182b32618bc3622a3ce0399714b662076d053d98fb7193f6',
}


def source(workload):
    return (c.ROOT / w.program(workload)).read_text()


def integers(text):
    text = re.sub(r'/\*.*?\*/|//[^\n]*', '', text, flags=re.S)
    return [int(token.strip(), 0) for token in text.split(',') if token.strip()]


def array(text, name):
    match = re.search(r'\b' + re.escape(name) + r'\s*\[[^]]*\]\s*=\s*\{([^}]+)\}', text)
    assert match, name
    return integers(match[1])


def plan_for(workload):
    """Minimal real-validator plan: no native artifact or frozen outcome needed."""
    bindings = (w.SOURCE, w.GUARDED_SOURCE, g.QUALIFIED_SOURCE, g.guard.SOURCE,
                g.attempts.SOURCE, g.EVIDENCE_SOURCE, *g.AUTHENTICATION_SOURCES,
                w.program(workload), w.LICENSE)
    return dict(workload=workload, pool_size=12, memory_partition=copy.deepcopy(w.PARTITION),
                compiler_flags=list(g.q.bounded.compact.FLAGS), simulation_cycle_limit=g.CYCLE_LIMIT,
                native_limits=copy.deepcopy(w.NATIVE_LIMITS),
                build_variant={'required_entrypoint': w.SOURCE},
                relocation_guard=copy.deepcopy(g.GUARD_RULE), pool_rule=g.POOL_RULE,
                source_bindings={name: c.sha(c.ROOT / name) for name in bindings},
                workload_group='beebs-' + workload,
                upstream=dict(suite='BEEBS', commit='049ded9f3aeb5591f553879d3a0376b8614e9422',
                              source=w.program(workload), source_sha256=PINNED[workload]),
                inputs={'program.c': PINNED[workload]})


@pytest.mark.parametrize('workload', PINNED)
def test_five_original_sources_and_license_are_pinned(workload):
    assert w.WORKLOADS[workload][1] == PINNED[workload]
    assert c.sha(c.ROOT / w.program(workload)) == PINNED[workload]
    assert 'warm_caches' not in source(workload)
    assert 'verify_benchmark' in source(workload)
    assert c.sha(c.ROOT / w.LICENSE) == '8ceb4b9ee5adedde47b31e975c1d90c73ad27b6b165a1dcd80c7c545eb65b903'


def test_original_full_inputs_and_verifiers_are_retained():
    compress = source('aha-compress')
    tests = array(compress, 'test')
    assert len(tests) == 54  # all eighteen input/mask/golden triples
    assert tests[:3] == [0xffffffff, 0x80000000, 1]
    assert tests[-3:] == [0x80000000, 0xf0035555, 0x2000]
    assert re.findall(r'r\s*=\s*compress([1-4])\(test\[i\],\s*test\[i\+1\]\)', compress) == list('1234')
    assert compress.count('if (r != test[i+2])') == 4

    des = source('ndes')
    for field, value in [('inp.l', 35), ('inp.r', 26), ('key.l', 2), ('key.r', 16)]:
        assert re.search(re.escape(field) + r'\s*=\s*KNOWN_VALUE\s*\*\s*' + str(value) + r';', des)
    assert 'exp_l = 2489587893' in des and 'exp_r = 1806503748' in des
    assert 'if (out.l != exp_l)' in des and 'if (out.r != exp_r)' in des

    arc = source('nettle-arcfour')
    assert array(arc, 'key') == list(range(15, -1, -1))
    assert array(arc, 'data') == array(arc, 'exp') == list(range(16))
    assert 'if (result[i] != exp[i])' in arc

    md5 = source('nettle-md5')
    assert array(md5, 'input') == list(range(16)) * 4
    assert array(md5, 'expected') == [0xddaf8815, 0x2149cb8f, 0x9cdd75fd, 0x14a43e27]
    assert 'return ! memcmp (digest, expected, _MD5_DIGEST_LENGTH * sizeof (digest[0]));' in md5

    edit = source('levenshtein')
    assert re.findall(r'"([a-z]+)"', re.search(r'strings\[\].*?\{([^}]+)\}', edit, re.S)[1]) == [
        'srrjngre', 'asfcjnsdkj', 'string', 'msd', 'strings']
    assert 'for(i = 0; i < 5; ++i)' in edit and 'for(j = 0; j < 5; ++j)' in edit
    assert 'int exp = 122;' in edit and 'if (r != exp)' in edit


def globals_snapshot():
    return (g.SOURCE, g.WORKLOADS, g.POOL_SIZE, g.NATIVE_LIMITS, g.q.POOL_SIZE,
            g.q.bounded.POOL_SIZE, g.q.bounded.campaign.POOL_SIZE, w.evidence._public)


def test_nested_registration_restores_every_legacy_global_after_failure():
    before = globals_snapshot()
    with pytest.raises(RuntimeError, match='nested failure'):
        with w.registration('aha-compress'):
            outer = globals_snapshot()
            assert outer[0] == w.SOURCE
            assert set(outer[1]) == {'aha-compress'}
            assert outer[2] == outer[4] == outer[5] == outer[6] == 12
            assert outer[3] == w.NATIVE_LIMITS and outer[3] is not w.NATIVE_LIMITS
            assert outer[7] is w.public_projection
            with w.registration({'workload': 'ndes'}):
                assert set(g.WORKLOADS) == {'ndes'}
                g.NATIVE_LIMITS['commands'] = 1
            assert globals_snapshot() == outer
            assert g.NATIVE_LIMITS is outer[3]
            raise RuntimeError('nested failure')
    assert globals_snapshot() == before
    assert g.WORKLOADS is before[1] and g.NATIVE_LIMITS is before[3]


def test_unknown_registration_cannot_change_global_state():
    before = globals_snapshot()
    with pytest.raises(ValueError):
        with w.registration('unregistered'):
            pytest.fail('unregistered source entered')
    assert globals_snapshot() == before


def rc4_reference(key, data):
    """Independent byte-oriented KSA and PRGA, checked against RFC6229."""
    state = list(range(256))
    j = 0
    for i in range(256):
        j = (j + state[i] + key[i % len(key)]) % 256
        state[i], state[j] = state[j], state[i]
    i = j = 0
    result = []
    for byte in data:
        i = (i + 1) % 256
        j = (j + state[i]) % 256
        state[i], state[j] = state[j], state[i]
        result.append(byte ^ state[(state[i] + state[j]) % 256])
    return bytes(result)


def test_arcfour_independent_ciphertext_and_outside_counter_check():
    # RFC6229 section2, key0102030405, first sixteen keystream bytes.
    assert rc4_reference(bytes(range(1, 6)), bytes(16)).hex() == 'b2396305f03dc027ccc3524a0a1118a8'
    golden = rc4_reference(bytes(range(15, -1, -1)), bytes(range(16)))
    assert golden.hex() == '084773cb875beefe01a1be8471df1bbc'
    assert hashlib.sha256(golden).hexdigest() == 'ca1bd2b65661d40340ede86f3a6ed3acd9a8b66ecb938dbee53c93a9548c82f4'
    assert bytes(array(w.ARCFOUR_CHECK, 'expected')) == golden
    assert array(w.ARCFOUR_CHECK, 'key') == array(source('nettle-arcfour'), 'key')
    assert array(w.ARCFOUR_CHECK, 'plain') == array(source('nettle-arcfour'), 'data')
    main = w.harness_source('nettle-arcfour').split('int main(void) {', 1)[1]
    assert main.index('uint32_t c1=cycles()') < main.index('int correct=verify_benchmark(result);') < main.index('if (!isaforge_arcfour_check()) correct=0;')
    assert main.count('int result=benchmark();') == 1


@pytest.mark.parametrize('workload', [name for name in PINNED if name != 'nettle-arcfour'])
def test_other_harnesses_are_exact_generic_source_plus_noop_warmup(workload):
    assert w.harness_source(workload) == (c.ROOT / 'hardware/embench_firmware.c').read_text() + w.WARMUP


@pytest.mark.parametrize('workload', PINNED)
def test_valid_plan_requires_adapter_and_rejects_legacy_entrypoint(workload):
    plan = plan_for(workload)
    w.check_plan(plan)
    with pytest.raises(ValueError):
        g.check_plan(plan)


@pytest.mark.parametrize('mutation', [
    lambda p: p.update(workload='jfdctint'),
    lambda p: p.update(pool_size=6),
    lambda p: p.update(pool_size=True),
    lambda p: p.update(memory_partition=g.q.partition_spec(6272, 6400)),
    lambda p: p['upstream'].update(commit='0' * 40),
    lambda p: p['upstream'].update(source='benchmarks/beebs/ndes/libndes.c'),
    lambda p: p['inputs'].update({'program.c': '0' * 64}),
    lambda p: p['source_bindings'].pop(w.GUARDED_SOURCE),
    lambda p: p['source_bindings'].pop(w.LICENSE),
    lambda p: p['native_limits'].update(candidate_attempts=2),
    lambda p: p['native_limits'].update(workers=2),
    lambda p: p['build_variant'].update(required_entrypoint=w.GUARDED_SOURCE),
    lambda p: p.update(compiler_flags=['-O2']),
])
def test_wrong_source_partition_pool_and_runtime_protocol_are_rejected(mutation):
    plan = plan_for('aha-compress')
    mutation(plan)
    with pytest.raises(ValueError):
        w.check_plan(plan)


@pytest.fixture
def input_fixture(tmp_path):
    workload = 'nettle-arcfour'
    inputs = tmp_path / 'inputs'
    inputs.mkdir()
    shutil.copyfile(c.ROOT / w.program(workload), inputs / 'program.c')
    (inputs / 'embench_firmware.c').write_text(w.harness_source(workload))
    plan = plan_for(workload)
    plan['inputs']['embench_firmware.c'] = c.sha(inputs / 'embench_firmware.c')
    c.seal(tmp_path / 'plan.json', plan)
    return tmp_path, plan


def test_validate_inputs_accepts_exact_sources_and_harness(input_fixture):
    root, plan = input_fixture
    assert w.validate_inputs(root) == plan


@pytest.mark.parametrize('edit', [
    lambda text: text.replace('0x08,0x47', '0x09,0x47'),
    lambda text: text.replace('if (!isaforge_arcfour_check()) correct=0;', ''),
    lambda text: text.replace('(void)heat;', 'benchmark();'),
])
def test_resealed_harness_edit_cannot_change_golden_check_or_timed_abi(input_fixture, edit):
    root, plan = input_fixture
    harness = root / 'inputs/embench_firmware.c'
    changed = edit(harness.read_text())
    assert changed != harness.read_text()
    harness.write_text(changed)
    # Even a self-consistent hash cannot authorize a different derivation.
    plan['inputs']['embench_firmware.c'] = c.sha(harness)
    c.seal(root / 'plan.json', plan)
    with pytest.raises(ValueError, match='harness derivation'):
        w.validate_inputs(root)


def test_input_arithmetic_edit_is_rejected_without_trusting_manifest(input_fixture):
    root, _ = input_fixture
    program = root / 'inputs/program.c'
    program.write_text(program.read_text().replace('0xf,0xe', '0xe,0xe'))
    with pytest.raises(ValueError, match='Unchanged full benchmark source'):
        w.validate_inputs(root)


def test_public_projection_retains_identity_and_rejects_cross_source_rows(monkeypatch):
    original = [{'benchmark': 'embench-ndes:ctx', 'candidate_id': 'candidate-1'}]
    monkeypatch.setattr(w, 'PUBLIC', lambda *args: copy.deepcopy(original))
    result = w.public_projection(None, {'workload': 'ndes', 'context_id': 'ctx'}, None, None, None)
    assert result == [{'benchmark': 'beebs-ndes:ctx', 'candidate_id': 'candidate-1'}]
    assert original[0]['benchmark'] == 'embench-ndes:ctx'
    with pytest.raises(ValueError, match='projection'):
        w.public_projection(None, {'workload': 'aha-compress', 'context_id': 'ctx'}, None, None, None)


@pytest.fixture
def released_evaluator(tmp_path, monkeypatch):
    evaluator = object.__new__(w.Evaluator)
    evaluator.root = tmp_path
    evaluator.plan = dict(workload='ndes', context_id='frozen-context')
    c.seal(tmp_path / 'evaluation-protocol.json', {'pool_names': ['candidate_0000']})
    release = dict(schema='isaforge-blind-cohort-v1-release', zero_candidate_attempts=True,
                   target_labels_observed=0, targets={'beebs-ndes': dict(
                       context_id='frozen-context', native_order=['candidate_0000'],
                       evaluation_protocol_sha256=c.sha(tmp_path / 'evaluation-protocol.json'))})
    calls = []

    def measured(self, name):
        calls.append((name, g.SOURCE, g.POOL_SIZE))
        return {'dispatched': name}

    monkeypatch.setattr(g.Evaluator, 'measure', measured)
    return evaluator, release, calls


@pytest.mark.parametrize('mutation', [
    lambda release: release.update(schema='old-release'),
    lambda release: release.update(zero_candidate_attempts=False),
    lambda release: release.update(target_labels_observed=1),
    lambda release: release.update(target_labels_observed=False),
    lambda release: release['targets'].clear(),
    lambda release: release['targets']['beebs-ndes'].update(context_id='different-context'),
    lambda release: release['targets']['beebs-ndes'].update(native_order=['candidate_0001']),
    lambda release: release['targets']['beebs-ndes'].update(evaluation_protocol_sha256='0' * 64),
])
def test_mismatched_release_stops_before_candidate_dispatch(released_evaluator, mutation):
    evaluator, release, calls = released_evaluator
    mutation(release)
    c.seal(evaluator.root / 'release.json', release)
    with pytest.raises(ValueError, match='zero-attempt cohort release'):
        evaluator.measure('candidate_0000')
    assert calls == []


def test_exact_release_dispatches_in_scoped_context_and_baseline_needs_no_release(released_evaluator):
    evaluator, release, calls = released_evaluator
    before = globals_snapshot()
    assert evaluator.measure('baseline') == {'dispatched': 'baseline'}
    c.seal(evaluator.root / 'release.json', release)
    assert evaluator.measure('candidate_0000') == {'dispatched': 'candidate_0000'}
    assert calls == [('baseline', w.SOURCE, 12), ('candidate_0000', w.SOURCE, 12)]
    assert globals_snapshot() == before
