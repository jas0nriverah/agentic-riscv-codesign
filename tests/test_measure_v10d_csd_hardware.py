"""V10d synthetic orchestration/integrity tests; no native or area execution."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace
import zipfile
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('measure_v10d_csd_hardware', ROOT / 'scripts/measure_v10d_csd_hardware.py')
m = importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


@pytest.fixture(autouse=True)
def no_native(monkeypatch):
    monkeypatch.setattr(m.subprocess, 'Popen', lambda *a, **k: pytest.fail('Native execution forbidden'))


def fixture_pairs(root):
    pairs = []
    for i in range(32):
        suffix = format(i, '064x')
        arms = {}
        for arm in m.ARMS:
            path = root / 'rtl' / suffix / (arm + '.v');path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('module candidate; /* synthetic ' + arm + ' */ endmodule\n')
            arms[arm] = {'formula': 'synthetic_' + str(i) + '_' + arm, 'rtl': m.record(path, root)}
        proof = root / 'proofs' / (suffix + '.json');m.write(proof, {'source-proof': 'synthetic'})
        mit = root / 'rtl' / suffix / 'miter.v';mit.write_text('synthetic miter')
        pairs.append({'pair_id': 'v10-csd:' + suffix, 'source_candidate_id': 'source-' + str(i),
            'formula': 'synthetic_' + str(i), 'rewritten_formula': arms['csd']['formula'],
            'context': ('direct_product', 'add_after_product', 'sub_before_product', 'masked_sub_before_product')[i % 4],
            'constant_u32': (11, 44, 85, 340, 341, 511, 1364, 2044)[i // 4],
            'operation_count': 2, 'arms': arms, 'proof': m.record(proof, root), 'miter_rtl': m.record(mit, root)})
    return pairs


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    monkeypatch.setattr(m, 'ROOT', tmp_path)
    monkeypatch.setattr(m, 'OLD_ROOT', 'old')
    monkeypatch.setattr(m, 'PRIOR_V9', 'prior.json')
    old = tmp_path / 'old';old.mkdir()
    pairs = fixture_pairs(old)
    tools = {'executables': {'yosys': {'path': '/synthetic/yosys', 'sha256': 'a' * 64, 'version': 'synthetic'},
        'abc': {'path': '/synthetic/yosys-abc', 'sha256': 'b' * 64, 'version': 'synthetic'}}}
    m.write(old / 'pairs.json', pairs);m.write(old / 'tools.json', tools)
    m.write(old / 'source-candidates.json', [{'synthetic': True}])
    m.write(old / 'measurements/completion.json', {'complete': False, 'universal_actual_rtl_pairs_proved': 16, 'fresh_synthesis_jobs_completed': 0})
    prior = [{'formula': pair['formula'], 'ice40_lut4_count': 100, 'ice40_carry_count': 20,
        'rtl_sha256': pair['arms']['original']['rtl']['sha256'], 'tool_sha256': 'a' * 64} for pair in pairs]
    m.write(tmp_path / 'prior.json', prior)
    source = tmp_path / 'synthetic-source.py';source.write_text('# synthetic source\n')
    files = sorted(p for p in old.rglob('*') if p.is_file())
    baseline = {'pairs': m.record(old / 'pairs.json', old), 'tools': m.record(old / 'tools.json', old),
        'files': [m.record(path, old) for path in files]}
    m.write(old / 'preparation.json', baseline)
    monkeypatch.setattr(m, 'OLD_PREPARATION_SHA', m.sha(old / 'preparation.json'))
    inherited = [*files, old / 'preparation.json', tmp_path / 'prior.json']
    monkeypatch.setattr(m, 'baseline_inputs', lambda: (baseline, pairs, inherited))
    monkeypatch.setattr(m, 'required_sources', lambda: [source])
    monkeypatch.setattr(m, 'validate_tools', lambda _: None)
    root = tmp_path / 'new'
    m.prepare(root)
    return root, pairs, tools, prior, source


def put(path, value): path.write_text(json.dumps(value, indent=2) + '\n')


def rebind(root, manifest, path):
    entry = m.record(path, root)
    manifest['files'] = [entry if x['path'] == entry['path'] else x for x in manifest['files']]
    for key in ('pairs', 'recipe', 'tools', 'prior_v9_originals', 'amendment'):
        if manifest[key]['path'] == entry['path']: manifest[key] = entry
    put(root / 'preparation.json', manifest)


def test_prepare_exact_copies_full32_and_no_overwrite(prepared):
    root, pairs, tools, prior, _ = prepared
    manifest, recipe, actual, copied_tools, _ = m.validate_preparation(root)
    assert actual == pairs and copied_tools == tools
    assert m.read(root / 'prior-v9-originals.json') == prior
    assert recipe['frontend_jobs'] == recipe['fresh_synthesis_jobs'] == 64
    assert recipe['frontend_timeout_seconds'] == 60 and recipe['measurement_timeout_seconds_per_arm'] == 360
    assert recipe['all_proofs_before_any_area'] is True and manifest['new_native_jobs'] == 0
    with pytest.raises(ValueError, match='Fresh'): m.prepare(root)
    for pair in pairs:
        for arm in m.ARMS:
            entry = pair['arms'][arm]['rtl']
            assert m.sha(root / entry['path']) == entry['sha256']


@pytest.mark.parametrize('poison', ['source', 'rtl', 'recipe', 'prior', 'missing-closure', 'duplicate-binding', 'pair-filter', 'failed-marker'])
def test_prepared_tamper_and_filter_fail_closed(prepared, poison):
    root, pairs, _, _, source = prepared
    manifest = m.read(root / 'preparation.json')
    if poison == 'source': source.write_text('changed')
    elif poison == 'rtl': (root / pairs[0]['arms']['csd']['rtl']['path']).write_text('changed')
    elif poison == 'recipe':
        path = root / 'recipe.json';value = m.read(path);value['frontend_timeout_seconds'] = 120;put(path, value);rebind(root, manifest, path)
    elif poison == 'prior':
        path = root / 'prior-v9-originals.json';value = m.read(path);value[0]['ice40_lut4_count'] = 0;put(path, value);rebind(root, manifest, path)
    elif poison == 'missing-closure':
        manifest['files'] = [x for x in manifest['files'] if not x['path'].endswith('../old/measurements/completion.json')]
        put(root / 'preparation.json', manifest)
    elif poison == 'duplicate-binding': manifest['files'].append(manifest['files'][0]);put(root / 'preparation.json', manifest)
    elif poison == 'pair-filter':
        path = root / 'pairs.json';put(path, m.read(path)[:-1]);rebind(root, manifest, path)
    else: m.write(root / 'preparation-failure.json', {'failed': True})
    with pytest.raises(ValueError): m.validate_preparation(root)


def test_approval_binds_commit_complete_closure_and_rejects_wrong_root(prepared, monkeypatch):
    root, _, _, _, _ = prepared
    manifest = m.read(root / 'preparation.json')
    approval = root / 'measurement-approval.json'
    review = {'status': 'approved-v10d-csd-hardware-measurements', 'freeze_commit': 'c' * 40,
        'preparation_sha256': m.sha(root / 'preparation.json'), 'recipe_sha256': manifest['recipe']['sha256'],
        'pairs_sha256': manifest['pairs']['sha256'], 'collector_sha256': m.sha(m.__file__),
        'checker_sha256': m.sha(m.algebra.__file__), 'reviewed_at_utc': m.now()}
    m.write(approval, review)
    seen = [];monkeypatch.setattr(m, 'committed', lambda path, commit: seen.append((path, commit)))
    result = m.validate_approval(root, approval)
    assert len(seen) == len(result[-1]) - 1 and all(commit == 'c' * 40 for _, commit in seen)
    with pytest.raises(ValueError): m.validate_approval(root, root / 'wrong.json')
    review['checker_sha256'] = 'd' * 64;put(approval, review)
    with pytest.raises(ValueError, match='release differs'): m.validate_approval(root, approval)


def identity_json():
    return {'modules': {'candidate': {'ports': {'in0': {'direction': 'input', 'bits': list(range(2, 34))},
        'in1': {'direction': 'input', 'bits': list(range(34, 66))}, 'result': {'direction': 'output', 'bits': list(range(2, 34))}}, 'cells': {}}}}


@pytest.mark.parametrize('mode', ['ok', 'timeout', 'missing-json', 'unexpected-input', 'duplicate-json'])
def test_frontend_exact_commands_bytes_metadata_and_failure_retention(prepared, monkeypatch, mode):
    root, pairs, tools, _, _ = prepared
    folder = m.ROOT / 'frontend-case'
    def run(command, log, owner, timeout):
        assert timeout == 60 and command[0] == tools['executables']['yosys']['path']
        script = folder / 'frontend.ys'
        assert script.read_text() == '\n'.join(m.frontend_commands(folder / 'candidate.v', folder / 'word.json')) + '\n'
        assert m.sha(folder / 'candidate.v') == pairs[0]['arms']['original']['rtl']['sha256']
        log.write_text("Parsing Verilog input from `" + str(folder / ('wrong.v' if mode == 'unexpected-input' else 'candidate.v')) + "'\n")
        if mode not in ('timeout', 'missing-json'):
            if mode == 'duplicate-json': (folder / 'word.json').write_text('{"modules":{},"modules":{}}')
            else: m.write(folder / 'word.json', identity_json())
        return {'returncode': None if mode == 'timeout' else 0, 'timed_out': mode == 'timeout', 'elapsed_seconds': 0.1}
    monkeypatch.setattr(m, 'run_owned', run)
    result = m.frontend(root, pairs[0], 'original', folder, tools, None)
    assert result['success'] is (mode == 'ok') and m.read(folder / 'frontend.json') == result
    if mode == 'missing-json': assert result['error'] == 'Successful frontend exit produced no word.json'
    assert m.utc(result['started_at_utc']) <= m.utc(result['completed_at_utc'])
    assert (folder / 'frontend.log').exists()


def test_algebra_wrapper_binds_actual_both_jsons_checker_and_times(prepared, monkeypatch):
    root, pairs, tools, _, _ = prepared
    scratch = m.ROOT / 'scratch';records = {}
    def run(command, log, owner, timeout):
        folder = log.parent;log.write_text("Parsing Verilog input from `" + str(folder / 'candidate.v') + "'\n")
        m.write(folder / 'word.json', identity_json())
        return {'returncode': 0, 'timed_out': False, 'elapsed_seconds': 0.1}
    monkeypatch.setattr(m, 'run_owned', run)
    for arm in m.ARMS:
        folder = scratch / 'frontend' / pairs[0]['pair_id'].split(':')[1] / arm
        records[pairs[0]['pair_id'] + '/' + arm] = m.frontend(root, pairs[0], arm, folder, tools, None)
    result = m.prove_pair(pairs[0], records, scratch)
    assert result['proved'] and result['checker_result']['proved']
    assert result['checker_sha256'] == m.sha(m.algebra.__file__)
    assert all(m.utc(r['completed_at_utc']) <= m.utc(result['started_at_utc']) for r in records.values())
    assert m.read(scratch / 'algebra-proofs' / pairs[0]['pair_id'].split(':')[1] / 'proof.json') == result


class Owner:
    def __init__(self, tools): self.cancelled = False
    def cancel(self): self.cancelled = True


@pytest.mark.parametrize('bad', ['none', 'frontend', 'algebra', 'measurement', 'archive-space'])
def test_full_fixed_phase_order_gate_all32_no_filter_archive_and_single_attempt(prepared, monkeypatch, bad):
    root, pairs, tools, _, _ = prepared
    manifest, recipe, _, _, bindings = m.validate_preparation(root)
    approval = root / 'measurement-approval.json';m.write(approval, {'fixture': True})
    monkeypatch.setattr(m, 'validate_approval', lambda *_: (manifest, recipe, pairs, tools, {'freeze_commit': 'f' * 40}, bindings))
    monkeypatch.setattr(m, 'HardwareWorkers', Owner)
    monkeypatch.setattr(m, 'recheck', lambda *_: None)
    monkeypatch.setattr(m.shutil, 'disk_usage', lambda _: SimpleNamespace(free=3 * 1024**3))
    events = []
    def front(root, pair, arm, folder, tools, owner):
        events.append(('frontend', pair['pair_id'], arm));folder.mkdir(parents=True)
        (folder / 'frontend.log').write_text('retained synthetic frontend')
        result = {'pair_id': pair['pair_id'], 'arm': arm, 'success': not (bad == 'frontend' and pair == pairs[0] and arm == 'csd'),
            'status': 'complete' if bad != 'frontend' else 'failed', 'started_at_utc': m.now(), 'completed_at_utc': m.now()}
        m.write(folder / 'frontend.json', result);return result
    def prove(pair, frontends, scratch):
        assert len([x for x in events if x[0] == 'frontend']) == 64
        events.append(('proof', pair['pair_id']));folder = scratch / 'algebra-proofs' / pair['pair_id'].split(':')[1];folder.mkdir(parents=True)
        success = not ((bad in ('algebra', 'frontend')) and pair == pairs[0])
        result = {'pair_id': pair['pair_id'], 'proved': success, 'error': None if success else 'synthetic rejection',
            'started_at_utc': m.now(), 'completed_at_utc': m.now()}
        m.write(folder / 'proof.json', result);return result
    def measure(root, pair, arm, folder, tools, owner):
        assert len([x for x in events if x[0] == 'proof']) == 32
        assert all(x['proved'] for x in m.read(root / 'measurements/attempt-0000/algebra-proofs.json'))
        assert (root / 'measurements/attempt-0000/measurement-gate.json').is_file()
        events.append(('measure', pair['pair_id'], arm));folder.mkdir(parents=True)
        (folder / 'ice40.log').write_text('retained synthetic area')
        if bad == 'measurement' and pair == pairs[0] and arm == 'original': raise RuntimeError('synthetic measurement failure')
        result = {'pair_id': pair['pair_id'], 'arm': arm, 'lut4_count': 100 if arm == 'original' else 80,
            'carry_count': 20 if arm == 'original' else 25, 'yosys': tools['executables']['yosys'], 'measured_at_utc': m.now()}
        m.write(folder / 'metrics.json', result);return result
    monkeypatch.setattr(m, 'frontend', front);monkeypatch.setattr(m, 'prove_pair', prove);monkeypatch.setattr(m, 'measure_arm', measure)
    if bad == 'archive-space':
        monkeypatch.setattr(m, 'workspace_bytes', lambda *directories: m.MAX_ATTEMPT_BYTES // 2)
    if bad == 'none': m.collect(root, approval)
    else:
        with pytest.raises(ValueError, match='Incomplete V10d'): m.collect(root, approval)
    done = m.read(root / 'measurements/completion.json')
    assert done['complete'] is (bad == 'none')
    assert done['frontend_jobs_completed'] == 64 and done['proof_records'] == 32
    assert done['fresh_synthesis_jobs_completed'] == (64 if bad in ('none', 'archive-space') else 63 if bad == 'measurement' else 0)
    assert (done['measurement_started_at_utc'] is not None) is (bad in ('none', 'measurement', 'archive-space'))
    raw = root / 'measurements/attempt-0000/raw-evidence.zip'
    with zipfile.ZipFile(raw) as archive:
        names = archive.namelist()
        assert len(names) == len(set(names))
        assert sum(n.endswith('/frontend.log') for n in names) == 64
        assert sum('/algebra-proofs/' in n and n.endswith('/proof.json') for n in names) == 32
        assert sum(n.endswith('/measurement-start.json') for n in names) == (64 if bad in ('none', 'measurement', 'archive-space') else 0)
    if bad == 'archive-space':
        assert any(f['phase'] == 'archive-resource-reservation' for f in done['failures'])
        assert not (root / 'measurements/attempt-0000/summary.json').exists()
    if bad == 'none':
        report = m.read(root / 'measurements/attempt-0000/summary.json')
        assert report['lut4']['count'] == 32 and report['lut4']['mean'] == -20 and report['carry_descriptive']['mean'] == 5
        assert report['fresh_original_v9_lut4_disagreements'] == report['fresh_original_v9_carry_disagreements'] == 0
    with pytest.raises(ValueError, match='Single-attempt'): m.collect(root, approval)


def test_per_arm_start_written_before_helper_and_finish_must_follow(prepared, monkeypatch):
    root, pairs, tools, _, _ = prepared
    scratch = m.ROOT / 'scratch';scratch.mkdir();gate = {'measurement_started_at_utc': m.now()};m.write(scratch / 'measurement-gate.json', gate)
    folder = scratch / 'circuits' / pairs[0]['pair_id'].split(':')[1] / 'original'
    def helper(*args):
        path = scratch / 'measurement-start' / pairs[0]['pair_id'].split(':')[1] / 'original.json'
        assert path.is_file() and not folder.exists()
        folder.mkdir(parents=True)
        return {'measured_at_utc': '2000-01-01T00:00:00+00:00'}
    monkeypatch.setattr(m, 'measure_arm', helper)
    with pytest.raises(ValueError, match='completion predates'): m.measured_arm(root, pairs[0], 'original', folder, tools, None, gate, scratch)
    assert (folder / 'measurement-start.json').is_file()


def test_cleanup_error_does_not_mask_primary_resource_error(tmp_path, monkeypatch):
    class BadOwner:
        def cancel(self): raise PermissionError('synthetic cleanup failure')
    monkeypatch.setattr(m, 'guard', lambda *_: (_ for _ in ()).throw(ValueError('primary quota error')))
    failures = []
    with pytest.raises(ValueError, match='primary quota error'):
        m.phase([('job', ())], lambda: 1, {}, 'frontend', tmp_path, tmp_path, BadOwner(), failures)
    assert failures == [{'phase': 'owned-process-cleanup', 'error': "PermissionError('synthetic cleanup failure')"}]


def test_disk_startup_guard_and_owned_archive_paths(prepared, monkeypatch):
    root, pairs, tools, _, _ = prepared
    manifest, recipe, _, _, bindings = m.validate_preparation(root)
    approval = root / 'measurement-approval.json';m.write(approval, {})
    monkeypatch.setattr(m, 'validate_approval', lambda *_: (manifest, recipe, pairs, tools, {'freeze_commit': 'a' * 40}, bindings))
    monkeypatch.setattr(m.shutil, 'disk_usage', lambda _: SimpleNamespace(free=100))
    with pytest.raises(ValueError, match='2GiB free'): m.collect(root, approval)
    assert not (root / 'label-release.json').exists()
    for name in ('/absolute', '../escape', m.PREFIX + 'attempt-0000/../escape', m.PREFIX + 'attempt-0000/x\\y'):
        with pytest.raises(ValueError): m.destination(name, 'attempt-0000')


def test_summary_rejects_dropped_duplicate_unknown_and_reports_drift(prepared):
    _, pairs, tools, prior, _ = prepared
    rows = [{'pair_id': p['pair_id'], 'arm': arm, 'lut4_count': 102 if arm == 'original' else 80, 'carry_count': 20,
        'yosys': tools['executables']['yosys']} for p in pairs for arm in m.ARMS]
    report = m.summary(pairs, rows, prior)
    assert report['fresh_original_v9_lut4_disagreements'] == 32 and report['lut4']['lower'] == 32
    for corrupt in (rows[:-1], [*rows, rows[0]], [dict(rows[0], pair_id='unknown'), *rows[1:]]):
        with pytest.raises(ValueError): m.summary(pairs, corrupt, prior)
