"""Independent V13 archive replay fixtures; no native execution or fitting."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import zipfile

import pytest

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('audit_v13_measurements', REPO / 'scripts/audit_v13_measurements.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
ROWS = json.loads((REPO / 'results/2026-10-15-v13-coverage-development/candidates.json').read_bytes())


def dump(value): return (json.dumps(value, indent=2) + '\n').encode()


def test_renderer_all48_matches_existing_generator_without_native():
    from isaforge.rtl import generate_rtl
    for row in ROWS: assert m.original_rtl(row['formula']) == generate_rtl(row['formula']).encode()
    for formula in ('mul(in0,in1)', 'lui(0)', 'add(in0,notreal(in1))'):
        with pytest.raises(ValueError): m.original_rtl(formula)


def vectors():
    formulas = sorted(r['formula'] for r in ROWS); trees = [m.oracle.parse(f) for f in formulas]
    lines = [' '.join(f'{v:08x}' for v in [a, b, *[m.oracle.evaluate(t, a, b) for t in trees]]) for a, b in m.input_pairs()]
    return ('\n'.join(lines) + '\n').encode()


@pytest.fixture(scope='module')
def vector_data(): return vectors()


def test_all103104_expected_outputs(vector_data):
    assert m.verify_vectors(vector_data, sorted(r['formula'] for r in ROWS)) == 103104


@pytest.mark.parametrize('poison', ['output', 'seed', 'short', 'shape'])
def test_expected_vector_poison(vector_data, poison):
    lines = vector_data.decode().splitlines()
    if poison == 'short': lines.pop()
    elif poison == 'shape': lines[0] = lines[0] + ' 00000000'
    else:
        words = lines[0].split(); words[2 if poison == 'output' else 0] = 'ffffffff'; lines[0] = ' '.join(words)
    with pytest.raises(ValueError): m.verify_vectors(('\n'.join(lines) + '\n').encode(), sorted(r['formula'] for r in ROWS))


def recovery_fixture(repo, root, tools, save, monkeypatch):
    previous = repo / m.FAILED_ROOT; stage = previous / 'measurements/attempt-0000'
    for n in m.INPUT_FILES:
        if not (root / n).exists(): save(root / n, {})
        p = previous / n; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes((root / n).read_bytes())
    old = {'complete': False, 'failures': [{'error': 'SYNTHETIC missing cstdint'}], 'new_physical_measurements': 0, 'verified_comparisons': 0, 'new_estimator_fits': 0}
    save(previous / 'measurements/completion.json', old); save(stage / 'completion.json', old)
    monkeypatch.setattr(m, 'FAILED_COMPLETION_SHA', m.sha(stage / 'completion.json'))
    (stage / 'raw-evidence.zip').write_bytes(b'SYNTHETIC preserved failed archive')
    monkeypatch.setattr(m, 'FAILED_ARCHIVE_SHA', m.sha(stage / 'raw-evidence.zip'))
    save(stage / 'raw-evidence.json', {'complete': False, 'archive_sha256': m.FAILED_ARCHIVE_SHA, 'completion_sha256': m.FAILED_COMPLETION_SHA})
    for n in ('labels', 'unique-measurements', 'verification'): save(stage / (n + '.json'), [])
    for n in ('measurement-plan', 'measurement-tools', 'measurement-approval', 'label-release'): save(previous / (n + '.json'), {})
    amendment = {'schema': 'isaforge-v13b-prelabel-recovery-v1', 'source_root': m.FAILED_ROOT, 'source_freeze_commit': '6d7721e89104fac0f9fe255b81b2f0f6c3b021a5',
                 'failed_completion_sha256': m.FAILED_COMPLETION_SHA, 'failed_raw_archive_sha256': m.FAILED_ARCHIVE_SHA}
    save(root / 'recovery-amendment.json', amendment)
    diagnosis = repo / 'generated/v13-sdk-preflight'; probe = repo / 'generated/v13b-sdk-preflight/attempt-0000'
    diagnosis.mkdir(parents=True); probe.mkdir(parents=True)
    (diagnosis / 'probe.cpp').write_text('SYNTHETIC header probe')
    runs = []
    for name in ('frozen_env', 'explicit_sdk', 'shim_first'):
        (diagnosis / (name + '.log')).write_text('SYNTHETIC ' + name)
        runs.append({'name': name, 'returncode': 1 if name == 'frozen_env' else 0, 'executable_returncode': 0, 'log_sha256': m.sha(diagnosis / (name + '.log'))})
    save(diagnosis / 'report.json', {'runs': runs, 'source_sha256': m.sha(diagnosis / 'probe.cpp')})
    (probe / 'probe.cpp').write_text('SYNTHETIC owner header probe')
    (probe / 'collector-source.py').write_bytes((repo / 'scripts/measure_v13b_coverage.py').read_bytes()); save(probe / 'tools.json', tools)
    runs = []
    for name in ('build', 'run'):
        (probe / (name + '.log')).write_text('SYNTHETIC ' + name); runs.append({'name': name, 'returncode': 0, 'log_sha256': m.sha(probe / (name + '.log'))})
    save(probe / 'report.json', {'schema': 'isaforge-v13b-sdk-header-preflight-v1', 'complete': True, 'error': None, 'runs': runs,
         'environment': tools['environment'], 'tools_sha256': m.sha(probe / 'tools.json'), 'collector_source_sha256': m.sha(probe / 'collector-source.py'),
         'source_sha256': m.sha(probe / 'probe.cpp'), 'rtl_comparisons': 0, 'physical_labels': 0, 'estimator_fits': 0, 'completed_at_utc': '2026-10-15T00:00:00+00:00'})
    return [p for p in previous.rglob('*') if p.is_file()] + [root / 'recovery-amendment.json'] + [p for d in (diagnosis, probe) for p in d.iterdir() if p.is_file()]


def make_fixture(tmp_path, monkeypatch, vector_data, poison=None, profile='v13'):
    repo = tmp_path / 'repo'; root = repo / 'result'; stage = root / 'measurements/attempt-0000'; stage.mkdir(parents=True)
    monkeypatch.setattr(m, 'ROOT', repo)
    def save(path, value):
        path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(dump(value))
    def bind(path): return {'path': str(path.relative_to(root)) if path.is_relative_to(root) else '../' + str(path.relative_to(repo)), 'sha256': m.sha(path)}
    for path in ('scripts/measure_' + profile + '_coverage.py', 'tests/test_measure_' + profile + '_coverage.py', 'isaforge/v4_validation.py'):
        p = repo / path; p.parent.mkdir(parents=True, exist_ok=True); p.write_text('SYNTHETIC source\n')
    tool = {'path': '/synthetic/yosys', 'sha256': 'a' * 64, 'version': 'SYNTHETIC'}
    abc = {'path': '/synthetic/yosys-abc', 'sha256': 'b' * 64, 'version': 'SYNTHETIC'}
    data = {'path': '/synthetic/data', 'files': [{'path': 'ice40/cells_sim.v', 'sha256': 'c' * 64, 'bytes': 1}]}
    historical = {'executables': {'yosys': tool, 'abc': abc}, 'yosys_data': data}
    save(repo / m.BASE_TOOLS, historical); monkeypatch.setattr(m, 'BASE_TOOLS_SHA', m.sha(repo / m.BASE_TOOLS))
    tools = {'schema': 'isaforge-' + profile + '-coverage-tools-v1', 'inherited_inventory': {'path': m.BASE_TOOLS, 'sha256': m.BASE_TOOLS_SHA}, **historical}
    if profile == 'v13b': tools.update(sdk={'path': '/SYNTHETIC/MacOSX.sdk'}, environment={'SDKROOT': '/SYNTHETIC/MacOSX.sdk'})
    save(root / 'measurement-tools.json', tools); save(root / 'candidates.json', ROWS); save(root / 'recipe.json', {})
    sources = [repo / ('scripts/measure_' + profile + '_coverage.py'), repo / ('tests/test_measure_' + profile + '_coverage.py'), repo / 'isaforge/v4_validation.py']
    prep = {'schema': 'isaforge-v13-coverage-preparation-v1', 'status': 'prepared-inputs-only', 'created_at_utc': '2026-10-15T00:00:00+00:00',
            'files': [bind(p) for p in [root / 'candidates.json', root / 'recipe.json', *sources]]}
    save(root / 'preparation.json', prep)
    recovery_paths = recovery_fixture(repo, root, tools, save, monkeypatch) if profile == 'v13b' else []
    policy = {'seed': m.SEED, 'random_vectors': 2048, 'boundary_vectors': 100, 'total_vectors': 2148, 'workers': 2,
              'worker_timeout_seconds': 360, 'candidate_count': 48, 'retries': 0, 'replacement_candidates': 0, 'new_estimator_fits': 0, 'original_rtl_only': True}
    plan = {'schema': 'isaforge-' + profile + '-coverage-measurement-plan-v1', 'status': 'prepared-no-native-jobs', 'created_at_utc': '2026-10-15T00:00:01+00:00',
            **{n + '_sha256': m.sha(root / (n + '.json')) for n in ('preparation', 'recipe', 'candidates')},
            'tools': {'path': 'measurement-tools.json', 'sha256': m.sha(root / 'measurement-tools.json')}, 'policy': policy,
            'files': [bind(p) for p in [root / 'preparation.json', root / 'candidates.json', root / 'recipe.json', *sources, repo / m.BASE_TOOLS, *recovery_paths]]}
    if profile == 'v13b': plan['recovery_amendment_sha256'] = m.sha(root / 'recovery-amendment.json')
    save(root / 'measurement-plan.json', plan)
    approval = {'status': 'approved-' + profile + '-coverage-measurements', **{n + '_sha256': m.sha(root / (n.replace('_', '-') + '.json')) for n in ('preparation', 'recipe', 'candidates', 'measurement_plan')},
                'tools_sha256': m.sha(root / 'measurement-tools.json'), 'collector_sha256': m.sha(sources[0]), 'collector_tests_sha256': m.sha(sources[1]),
                'freeze_commit': 'd' * 40, 'reviewed_at_utc': '2026-10-15T00:00:02+00:00'}
    if profile == 'v13b': approval['recovery_amendment_sha256'] = m.sha(root / 'recovery-amendment.json')
    save(root / 'measurement-approval.json', approval)
    release = {'schema': 'isaforge-' + profile + '-coverage-label-release-v1', **{k: v for k, v in approval.items() if k.endswith('_sha256') and k != 'collector_tests_sha256'},
               'policy': policy, 'approval_sha256': m.sha(root / 'measurement-approval.json'), 'freeze_commit': approval['freeze_commit'], 'released_at_utc': '2026-10-15T00:00:03+00:00'}
    save(root / 'label-release.json', release)
    members = {n + '.json': (root / (n + '.json')).read_bytes() for n in ('preparation', 'recipe', 'candidates', 'measurement-plan', 'measurement-tools', 'measurement-approval', 'label-release')}
    for path in sources: members['sources/' + path.relative_to(repo).as_posix()] = path.read_bytes()
    for path in recovery_paths: members['recovery-evidence/' + path.relative_to(repo).as_posix()] = path.read_bytes()
    formulas = sorted(r['formula'] for r in ROWS)
    proof = {'verified': True, 'formula_count': 48, 'vectors_per_formula': 2148, 'total_comparisons': 103104, 'random_seed': m.SEED,
             'v4_validation_override_sha256': m.sha(sources[2]), 'signed_overflow_workaround_applied': False,
             'rtl_sha256': m.digest(m.verification_rtl(formulas)), 'vectors_sha256': m.digest(vector_data)}
    members['verification/batch-0000/verification.v'] = m.verification_rtl(formulas)
    members['verification/batch-0000/vectors.txt'] = vector_data
    members['verification/batch-0000/verification.log'] = b'2148 vectors passed\n'
    if poison == 'runtime': members['verification/batch-0000/verification.log'] = b'2147 vectors passed\n'
    members['verification-0000-worker.result.json'] = dump(proof)
    gate = {'verified_at_utc': '2026-10-15T00:00:04+00:00', 'comparison_count': 103104, 'verification_sha256': m.digest(json.dumps(proof, sort_keys=True).encode())}
    members['verification-gate.json'] = dump(gate)
    metrics = []; by_formula = {}
    for index, formula in enumerate(formulas):
        folder = 'circuits/' + m.digest(formula.encode())[:20] + '/'; absolute = '/SYNTHETIC/generated/' + profile + '-coverage-measurements/attempt-0000/' + folder
        members[folder + 'candidate.v'] = m.original_rtl(formula)
        members[folder + 'ice40.ys'] = (f'read_verilog "{absolute}candidate.v"\nsynth_ice40 -top candidate\ncheck -assert\nwrite_json "{absolute}ice40-netlist.json"\nstat\n').encode()
        members[folder + 'ice40.log'] = (f'Running ABC command: "<yosys-exe-dir>/yosys-abc" -s test\nParsing Verilog input from `{absolute}candidate.v\'\nParsing Verilog input from `/synthetic/bin/../data/ice40/cells_sim.v\'\n').encode()
        members[folder + 'ice40-netlist.json'] = dump({'modules': {'candidate': {'cells': {'lut': {'type': 'SB_LUT4'}, 'carry': {'type': 'SB_CARRY'}}}}})
        metric = {'formula': formula, 'tool': 'SYNTHETIC', 'tool_sha256': tool['sha256'], 'measurement_source': 'rtl_synthesis', 'measured_at_utc': '2026-10-15T00:00:06+00:00',
                  'ice40_cell_types': {'SB_LUT4': 1, 'SB_CARRY': 1}, 'ice40_lut4_count': 1, 'ice40_carry_count': 1,
                  **{key: m.digest(members[folder + name]) for name, key in [('candidate.v', 'rtl_sha256'), ('ice40.ys', 'script_sha256'), ('ice40.log', 'log_sha256'), ('ice40-netlist.json', 'netlist_sha256')]},
                  'command': ['/synthetic/yosys', '-s', absolute + 'ice40.ys'], 'abc_invocations': [{'path': abc['path'], 'sha256': abc['sha256']}],
                  'data_invocations': {'ice40/cells_sim.v': {'sha256': 'c' * 64, 'resolved_path': '/synthetic/data/ice40/cells_sim.v', 'logged_paths': ['/synthetic/bin/../data/ice40/cells_sim.v']}}}
        if index == 0 and poison == 'recount': metric['ice40_lut4_count'] = 2
        if index == 0 and poison == 'abc': metric['abc_invocations'][0]['sha256'] = 'f' * 64
        if index == 0 and poison == 'recipe':
            members[folder + 'ice40.ys'] = members[folder + 'ice40.ys'].replace(b'synth_ice40 -top', b'synth_ice40 -abc9 -top'); metric['script_sha256'] = m.digest(members[folder + 'ice40.ys'])
        if index == 0 and poison == 'rtl':
            members[folder + 'candidate.v'] += b'// mutated\n'; metric['rtl_sha256'] = m.digest(members[folder + 'candidate.v'])
        worker = {k: v for k, v in metric.items() if k not in ('tool_sha256', 'abc_invocations', 'data_invocations')}
        members[folder + 'measurement.json'] = dump(metric); members[folder + 'metrics.json'] = dump(worker); members[folder + 'worker.result.json'] = dump(worker)
        start = {'formula': formula, 'started_at_utc': '2026-10-15T00:00:05+00:00', 'verification_gate_sha256': m.digest(members['verification-gate.json'])}
        if index == 0 and poison == 'chronology': start['started_at_utc'] = '2026-10-15T00:00:03+00:00'
        members[folder + 'measurement-start.json'] = dump(start); metrics.append(metric); by_formula[formula] = metric
    labels = [{**copy.deepcopy(row), 'lut4_count': by_formula[row['formula']]['ice40_lut4_count'], 'carry_count': 1, 'rtl_sha256': by_formula[row['formula']]['rtl_sha256'],
               'measurement_source': 'rtl_synthesis', 'correctness_verified': True} for row in ROWS]
    if poison == 'order': labels.reverse()
    if poison == 'identity': labels[0]['parameters']['POISON'] = True
    labels = copy.deepcopy(labels)
    for name, body in [('labels', labels), ('unique-measurements', metrics), ('verification', [proof])]: save(stage / (name + '.json'), body)
    done = {'schema': 'isaforge-' + profile + '-coverage-measurements-v1', 'attempt': m.ATTEMPT, 'complete': True, 'failures': [], 'candidate_count': 48,
            'new_physical_measurements': 48, 'verified_comparisons': 103104, 'verification_seed': m.SEED, 'vectors_per_formula': 2148, 'workers': 2,
            'verification_batch_sizes': [48], 'original_rtl_only': True, 'legacy_measurements_reused': False, 'new_estimator_fits': 0,
            'freeze_commit': approval['freeze_commit'], **{k: v for k, v in release.items() if k.endswith('_sha256')}, 'release_sha256': m.sha(root / 'label-release.json'),
            **{key: m.sha(stage / (name + '.json')) for name, key in [('labels', 'labels_sha256'), ('unique-measurements', 'unique_measurements_sha256'), ('verification', 'verification_sha256')]},
            'scratch_directory': 'generated/' + profile + '-coverage-measurements/attempt-0000', 'completed_at_utc': '2026-10-15T00:00:07+00:00'}
    if poison == 'count': done['new_physical_measurements'] = True
    save(stage / 'completion.json', done); save(root / 'measurements/completion.json', done)
    for name in ('labels', 'unique-measurements', 'verification', 'completion'): members['stage/' + name + '.json'] = (stage / (name + '.json')).read_bytes()
    archive = stage / 'raw-evidence.zip'
    with zipfile.ZipFile(archive, 'x', zipfile.ZIP_DEFLATED) as raw:
        for name, data in members.items(): raw.writestr(name, data)
    save(stage / 'raw-evidence.json', {'schema': 'isaforge-' + profile + '-coverage-raw-evidence-v1', 'archive': archive.name, 'archive_sha256': m.sha(archive), 'complete': True,
         'attempt': m.ATTEMPT, 'compiler_objects_included': False, 'completion_sha256': m.sha(stage / 'completion.json'),
         'files': [{'path': n, 'sha256': m.digest(d), 'size': len(d)} for n, d in members.items()]})
    return root


def test_full48_independent_archive_replay_no_subprocess(tmp_path, monkeypatch, vector_data):
    root = make_fixture(tmp_path, monkeypatch, vector_data)
    def forbidden(*args, **kwargs): raise AssertionError('Native/subprocess prohibited')
    monkeypatch.setattr(subprocess, 'Popen', forbidden)
    result = m.run(root)
    assert result['status'] == 'pass' and result['complete'] is True
    assert result['independent_expected_outputs_recomputed'] == 103104
    assert result['netlists_recounted'] == result['original_rtl_identities_checked'] == 48
    assert result['completion_sha256'] == m.sha(root / 'measurements/completion.json')


def test_v13b_explicit_recovery_profile_full48(tmp_path, monkeypatch, vector_data):
    root = make_fixture(tmp_path, monkeypatch, vector_data, profile='v13b')
    report = m.run(root)
    assert report['measurement_profile'] == 'v13b' and report['prelabel_recovery']['same_prepared_input_files'] == 6
    assert report['independent_expected_outputs_recomputed'] == 103104


@pytest.mark.parametrize('poison', ['input', 'preflight', 'snapshot', 'old-label'])
def test_v13b_recovery_semantic_poison(tmp_path, monkeypatch, vector_data, poison):
    root = make_fixture(tmp_path, monkeypatch, vector_data, profile='v13b'); repo = root.parent
    if poison == 'input': (root / 'coverage-diagnostics.json').write_text('{"changed":true}')
    elif poison == 'preflight':
        path = repo / 'generated/v13b-sdk-preflight/attempt-0000/report.json'; proof = m.read(path); proof['complete'] = False; path.write_bytes(dump(proof))
    elif poison == 'snapshot': (repo / 'generated/v13b-sdk-preflight/attempt-0000/collector-source.py').write_text('POISON')
    else:
        previous = repo / m.FAILED_ROOT; old = m.read(previous / 'measurements/completion.json'); old['new_physical_measurements'] = 1
        for path in (previous / 'measurements/completion.json', previous / 'measurements/attempt-0000/completion.json'): path.write_bytes(dump(old))
        monkeypatch.setattr(m, 'FAILED_COMPLETION_SHA', m.sha(previous / 'measurements/completion.json'))
    plan = m.read(root / 'measurement-plan.json')
    # Reauthenticate modified evidence: rejection must come from semantic checks.
    bindings = {(root / e['path']).resolve(): m.sha((root / e['path']).resolve()) for e in plan['files']}
    with pytest.raises(ValueError): m.validate_recovery(root, plan, m.read(root / 'measurement-tools.json'), bindings)


@pytest.mark.parametrize('poison', ['runtime', 'recount', 'abc', 'recipe', 'rtl', 'chronology', 'order', 'count', 'identity'])
def test_reauthenticated_archive_semantic_poison(tmp_path, monkeypatch, vector_data, poison):
    root = make_fixture(tmp_path, monkeypatch, vector_data, poison)
    with pytest.raises(ValueError): m.run(root)


def test_oracle_pin_rejects_changes(tmp_path, monkeypatch):
    path = tmp_path / 'oracle.py'; path.write_text('raise AssertionError("untrusted")')
    monkeypatch.setattr(m, 'ORACLE', path)
    with pytest.raises(ValueError, match='Pinned'): m.oracle_module()
