"""Synthetic approved-worker/archive contracts; no native tools or real labels."""
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import zipfile
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('measure_v9_coverage', ROOT / 'scripts/measure_v9_coverage.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)


def test_no_native_access_or_release_before_parent_approval(tmp_path, monkeypatch):
    monkeypatch.setattr(m, 'validate_approval', lambda *_: (_ for _ in ()).throw(ValueError('No parent approval')))
    monkeypatch.setattr(m.shutil, 'which', lambda *_: pytest.fail('No native tool before approval'))
    with pytest.raises(ValueError, match='parent approval'):
        m.collect(tmp_path, tmp_path / 'measurement-approval.json')
    assert not (tmp_path / 'label-release.json').exists()


@pytest.mark.parametrize('workers,attempt', [(1, 'attempt-0000'), (True, 'attempt-0000'), (2, '../escape'), (2, 'attempt-1')])
def test_fixed_worker_and_attempt_contract(tmp_path, workers, attempt):
    with pytest.raises(ValueError):
        m.collect(tmp_path, tmp_path / 'measurement-approval.json', workers=workers, attempt=attempt)


def test_completed_result_is_immutable_before_other_reads(tmp_path, monkeypatch):
    m.write(tmp_path / 'measurements/completion.json', {'complete': True})
    monkeypatch.setattr(m, 'validate_approval', lambda *_: pytest.fail('Must stop at complete gate'))
    with pytest.raises(ValueError, match='immutable'):
        m.collect(tmp_path, tmp_path / 'measurement-approval.json')


@pytest.fixture
def review(tmp_path, monkeypatch):
    monkeypatch.setattr(m, 'ROOT', tmp_path)
    root = tmp_path / 'result'; root.mkdir()
    manifest = {'prepared_at_utc': '2026-10-15T10:00:00+00:00',
                'recipe': {'sha256': 'b' * 64}, 'candidates': {'sha256': 'c' * 64}}
    m.write(root / 'preparation.json', manifest)
    source = tmp_path / 'approved.py'; source.write_bytes(b'approved-source')
    monkeypatch.setattr(m, 'prepared_inputs', lambda *_: (manifest, {}, [], {source: m.sha(source)}))
    value = {'status': 'approved-v9-coverage-measurements', 'preparation_sha256': m.sha(root / 'preparation.json'),
             'recipe_sha256': 'b' * 64, 'candidates_sha256': 'c' * 64, 'collector_sha256': m.sha(m.__file__),
             'freeze_commit': 'a' * 40, 'reviewed_at_utc': '2026-10-15T10:01:00+00:00'}
    path = root / 'measurement-approval.json'; m.write(path, value)
    return root, path, value, source


def test_git_committed_input_bytes_required(review, monkeypatch):
    root, path, _, source = review
    monkeypatch.setattr(m.subprocess, 'run', lambda *a, **k: SimpleNamespace(returncode=0, stdout=source.read_bytes()))
    assert m.validate_approval(root, path)[3]['freeze_commit'] == 'a' * 40
    monkeypatch.setattr(m.subprocess, 'run', lambda *a, **k: SimpleNamespace(returncode=0, stdout=b'changed'))
    with pytest.raises(ValueError, match='committed bytes'):
        m.validate_approval(root, path)


@pytest.mark.parametrize('field,value', [('status', 'unapproved'), ('freeze_commit', 'HEAD'),
    ('collector_sha256', 'wrong'), ('preparation_sha256', 'wrong'), ('candidates_sha256', 'wrong'),
    ('recipe_sha256', 'wrong'), ('reviewed_at_utc', '2026-10-15T09:59:00+00:00')])
def test_stale_or_incomplete_review_blocks_before_git_or_native(review, monkeypatch, field, value):
    root, path, review_value, _ = review; review_value[field] = value; m.write(path, review_value)
    monkeypatch.setattr(m.subprocess, 'run', lambda *a, **k: pytest.fail('Invalid approval must precede Git'))
    with pytest.raises(ValueError):
        m.validate_approval(root, path)
    assert not (root / 'label-release.json').exists()


@pytest.fixture
def workers(tmp_path, monkeypatch):
    monkeypatch.setattr(m, 'ROOT', tmp_path); monkeypatch.setattr(m, 'COUNT', 2)
    root = tmp_path / 'result'; root.mkdir()
    source = tmp_path / 'source.py'; source.write_bytes(b'frozen source')
    helper = tmp_path / 'isaforge/v4_validation.py'; helper.parent.mkdir(); helper.write_bytes(b'frozen proof helper')
    executable = tmp_path / 'yosys'; executable.write_bytes(b'synthetic executable never run')
    tool = {'version': 'SYNTHETIC_ONLY', 'executable_sha256': m.sha(executable)}
    candidates = [{'formula': 'add(in0,in1)', 'id': 'one'}, {'formula': 'xor(in0,in1)', 'id': 'two'}]
    manifest = {'recipe': {'sha256': 'b' * 64}, 'candidates': {'sha256': 'c' * 64}}
    m.write(root / 'preparation.json', manifest); approval = root / 'measurement-approval.json'; m.write(approval, {'synthetic': True})
    monkeypatch.setattr(m, 'validate_approval', lambda *_: (manifest, {'frozen_tool': tool}, candidates,
                          {'freeze_commit': 'a' * 40}, {source: m.sha(source)}))
    monkeypatch.setattr(m.shutil, 'which', lambda *_: str(executable))
    monkeypatch.setattr(m.subprocess, 'check_output', lambda *a, **k: tool['version'])
    state = {'calls': [], 'verify_bad': False, 'map_bad': None, 'mutate_source': False, 'wrong_rtl': None}
    def fake(payload, log, owner):
        state['calls'].append(payload)
        folder = Path(payload['folder']); folder.mkdir(parents=True)
        Path(log).parent.mkdir(parents=True, exist_ok=True); Path(log).write_text('synthetic worker log')
        if payload['kind'] == 'verify':
            (folder / 'verification.v').write_text(m.verification_source(payload['formulas']))
            (folder / 'vectors.txt').write_text('synthetic vectors; no RTL execution')
            return {'verified': not state['verify_bad'], 'formula_count': 2, 'vectors_per_formula': 2148,
                    'total_comparisons': 4296, 'random_seed': state.get('proof_seed', m.VERIFY_SEED),
                    'v4_validation_override_sha256': m.sha(helper), 'rtl_sha256': m.sha(folder / 'verification.v'),
                    'vectors_sha256': m.sha(folder / 'vectors.txt')}
        formula = payload['formula']
        if formula == state['map_bad']: raise RuntimeError('synthetic synthesis failure')
        (folder / 'candidate.v').write_text('wrong original' if formula == state['wrong_rtl'] else m.generate_rtl(formula))
        (folder / 'ice40.ys').write_text('synthetic script'); (folder / 'ice40.log').write_text('synthetic map log')
        m.write(folder / 'ice40-netlist.json', {'modules': {'candidate': {'cells': {'one': {'type': 'SB_LUT4'}}}}})
        value = {'formula': formula, 'tool': tool['version'], 'measurement_source': 'rtl_synthesis',
                 'ice40_lut4_count': state.get('metric_lut', 1), 'ice40_carry_count': 0, 'ice40_cell_types': {'SB_LUT4': 1},
                 'rtl_sha256': hashlib.sha256(m.generate_rtl(formula).encode()).hexdigest()}
        for name, key in [('ice40.ys', 'script_sha256'), ('ice40.log', 'log_sha256'), ('ice40-netlist.json', 'netlist_sha256')]:
            value[key] = m.sha(folder / name)
        if state['mutate_source']: source.write_text('changed during workers')
        if state.get('mutate_binary'): executable.write_bytes(b'changed during workers')
        return value
    monkeypatch.setattr(m, 'run_owned', fake)
    return root, approval, state, executable


def test_complete_fresh_original_batch_archive_and_no_recollection(workers, monkeypatch):
    root, approval, state, _ = workers
    done = m.collect(root, approval)
    assert done['complete'] and done['unique_original_formulas'] == 2
    assert done['verification_seed'] == 2026101519 and done['verification_batch_sizes'] == [2]
    assert done['legacy_measurements_reused'] is False and done['new_estimator_fits'] == 0
    calls = state['calls']; assert calls[0]['kind'] == 'verify'
    assert calls[0]['seed'] == 2026101519
    assert Counter(c['formula'] for c in calls if c['kind'] == 'map') == Counter(['add(in0,in1)', 'xor(in0,in1)'])
    archive = m.verify_archive(root)
    with zipfile.ZipFile(archive) as z:
        assert any(n.endswith('/candidate.v') for n in z.namelist())
        assert any(n.endswith('/worker.log') for n in z.namelist())
    monkeypatch.setattr(m, 'validate_approval', lambda *_: pytest.fail('Completed cohort cannot run again'))
    with pytest.raises(ValueError, match='immutable'):
        m.collect(root, approval, attempt='attempt-0001')


def test_failed_formula_is_charged_once_retained_and_never_replaced(workers):
    root, approval, state, _ = workers; state['map_bad'] = 'xor(in0,in1)'
    with pytest.raises(RuntimeError, match='Incomplete'):
        m.collect(root, approval)
    done = m.read(root / 'measurements/completion.json')
    assert not done['complete'] and done['new_physical_measurements'] == 1
    assert len([c for c in state['calls'] if c['kind'] == 'map']) == 2
    assert done['failures'][0]['formula'] == 'xor(in0,in1)'
    assert m.verify_archive(root, attempt='attempt-0000').is_file()
    with pytest.raises(ValueError, match='Fresh coverage attempt'):
        m.collect(root, approval)


def test_failed_verification_prevents_every_map_and_retains_raw_logs(workers):
    root, approval, state, _ = workers; state['verify_bad'] = True
    with pytest.raises(RuntimeError, match='Incomplete'):
        m.collect(root, approval)
    assert [c['kind'] for c in state['calls']] == ['verify']
    assert m.read(root / 'measurements/completion.json')['new_physical_measurements'] == 0
    assert m.verify_archive(root, attempt='attempt-0000').is_file()


def test_changed_source_during_collection_blocks_completion(workers):
    root, approval, state, _ = workers; state['mutate_source'] = True
    with pytest.raises(RuntimeError, match='Incomplete'):
        m.collect(root, approval)
    assert any(f['stage'] == 'provenance' for f in m.read(root / 'measurements/completion.json')['failures'])


@pytest.mark.parametrize('resource', [2, True])
def test_wrong_or_boolean_resource_count_cannot_override_raw_netlist(workers, resource):
    root, approval, state, _ = workers; state['metric_lut'] = resource
    with pytest.raises(RuntimeError, match='Incomplete'):
        m.collect(root, approval)
    assert m.read(root / 'measurements/completion.json')['unique_original_formulas'] == 0


def test_wrong_verification_seed_blocks_mapping(workers):
    root, approval, state, _ = workers; state['proof_seed'] = 99
    with pytest.raises(RuntimeError, match='Incomplete'):
        m.collect(root, approval)
    assert [c['kind'] for c in state['calls']] == ['verify']


def test_native_binary_change_during_collection_blocks_completion(workers):
    root, approval, state, _ = workers; state['mutate_binary'] = True
    with pytest.raises(RuntimeError, match='Incomplete'):
        m.collect(root, approval)
    assert any('Yosys binary changed' in f['error'] for f in m.read(root / 'measurements/completion.json')['failures'])


def test_wrong_generated_original_rtl_is_rejected(workers):
    root, approval, state, _ = workers; state['wrong_rtl'] = 'xor(in0,in1)'
    with pytest.raises(RuntimeError, match='Incomplete'):
        m.collect(root, approval)
    done = m.read(root / 'measurements/completion.json')
    assert done['unique_original_formulas'] == 1 and 'original RTL' in done['failures'][0]['error']


def test_changed_native_binary_blocks_before_release_or_workers(workers):
    root, approval, state, executable = workers; executable.write_bytes(b'changed binary')
    with pytest.raises(ValueError, match='binary/version'):
        m.collect(root, approval)
    assert not state['calls'] and not (root / 'label-release.json').exists()


def test_raw_member_digest_rechecked_even_with_updated_archive_hash(workers):
    root, approval, _, _ = workers; m.collect(root, approval)
    archive = root / 'measurements/raw-evidence.zip'; manifest_path = archive.with_suffix('.json')
    manifest = m.read(manifest_path)
    with zipfile.ZipFile(archive) as z: members = {i.filename: z.read(i) for i in z.infolist()}
    members[next(iter(members))] = b'poisoned member'
    with zipfile.ZipFile(archive, 'w') as z:
        for name, data in members.items(): z.writestr(name, data)
    manifest['archive_sha256'] = m.sha(archive); m.write(manifest_path, manifest)
    with pytest.raises(ValueError, match='archived member'):
        m.verify_archive(root)


def test_completed_label_mutation_is_rejected_during_archive_validation(workers):
    root, approval, _, _ = workers; m.collect(root, approval)
    (root / 'measurements/attempt-0000/labels.json').write_text('[]\n')
    with pytest.raises(ValueError, match='output changed'):
        m.verify_archive(root)


@pytest.mark.parametrize('name', ['../escape', '/tmp/escape', 'generated/v9-coverage-measurements/attempt-0000/../escape',
                                  'generated/v9-coverage-measurements/attempt-0001/data', 'generated/v8-measurements/attempt-0000/data',
                                  'generated/v9-coverage-measurements/attempt-0000/a\\b'])
def test_archive_paths_confined_to_exact_attempt(tmp_path, name):
    with pytest.raises(ValueError): m.destination(name, tmp_path, 'attempt-0000')


def test_archive_symlink_escape_is_rejected(tmp_path):
    outside = tmp_path / 'outside'; outside.mkdir()
    repository = tmp_path / 'repo'; repository.mkdir()
    (repository / 'generated').symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match='escapes'):
        m.destination(m.PREFIX + 'attempt-0000/data', repository, 'attempt-0000')
    assert not list(outside.iterdir())
