"""Synthetic recovered-feature admission/inference tests; no native or real model work."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import zipfile

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('predict_v11e_transfer', ROOT/'scripts/predict_v11e_transfer.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


@pytest.fixture(autouse=True)
def no_actual_jobs(monkeypatch):
    monkeypatch.setattr(subprocess, 'Popen', lambda *a, **k: pytest.fail('Actual process forbidden'))
    monkeypatch.setattr(m.v6, 'load_model', lambda *a, **k: pytest.fail('Actual model load forbidden'))
    monkeypatch.setattr(m.v6.FeatureExtractor, 'matrix', lambda *a, **k: pytest.fail('Feature extraction forbidden'))
    monkeypatch.setattr(m.frozen.replay, 'replay_feature_record', lambda *a, **k: pytest.fail('Unmocked raw replay forbidden'))
    monkeypatch.setattr(m.native_tools, 'validate_tools', lambda t: None)


@pytest.fixture
def recovered(tmp_path, monkeypatch):
    monkeypatch.setattr(m, 'ROOT', tmp_path)
    monkeypatch.setattr(m.frozen.inputs, 'ROOT', tmp_path)
    monkeypatch.setattr(m.packaging, 'ROOT', tmp_path)
    source = tmp_path/'results/original'
    recovery = tmp_path/'results/recovery'
    original = tmp_path/'results/inputs'
    root = tmp_path/'results/inference'
    script = tmp_path/'scripts/adapter.py'
    script.parent.mkdir()
    script.write_text('SYNTHETIC adapter source')
    audit_source = tmp_path/'scripts/audit_v11d_feature_packaging.py'
    audit_source.write_text('SYNTHETIC auditor source')
    audit_tests = tmp_path/'tests/test_audit_v11d_feature_packaging.py'
    audit_tests.parent.mkdir()
    audit_tests.write_text('SYNTHETIC auditor tests')
    monkeypatch.setattr(m, 'sources', lambda: [script])
    candidates = [{'candidate_id': 'id:'+str(i), 'formula': formula}
                  for i, formula in enumerate(('add(in0,in1)', 'xor(in0,in1)'))]
    members = [{'program': program, 'family': family, 'canonical_count': 1 if program != 'recursion' else 0}
               for program, family in m.inputs.FAMILIES.items()]
    data = {'columns': list(m.v6.columns()), 'records': [dict(c, values=[0.]*336) for c in candidates]}
    for row in data['records']:
        row['values'][0] = 1.
    tools = {'environment': {'PATH': 'SYNTHETIC'}, 'inherited_inventory': {'path': 'inventory.json'}}
    runtime = {'python': 'SYNTHETIC', 'versions': {}, 'files': []}
    p = {'input_root': '../inputs', 'input_preparation_sha256': 'b'*64,
         'columns': data['columns'], 'selected_columns': list(m.v6.mapping_columns()),
         'selected_indices': m.v6.mapping_indices().tolist(), 'frozen_tool': {'version': 'SYNTHETIC'},
         'feature_source_sha256': m.v6.source_hashes()}
    for path, value in [(source/'feature-plan.json', p), (source/'features/completion.json', {'complete': False}),
                        (source/'features/attempt-0000/features.json', data),
                        (source/'features/attempt-0000/replay/result.json', {'native_channels': 4}),
                        (source/'archive-failure/terminal-observation.json', {'schema': 'isaforge-v11d-archive-terminal-observation-v1', 'observed_terminal_at_utc': '2026-10-16T00:00:00+00:00'}),
                        (source/'runtime.json', runtime), (original/'candidates.json', candidates), (original/'memberships.json', members)]:
        m.write(path, value)
    models = {}
    definitions = {}
    for name, count in [('V6', 1665), ('V9', 1713)]:
        path = tmp_path/f'models/{name}.joblib'
        path.parent.mkdir(exist_ok=True)
        path.write_text('SYNTHETIC '+name)
        models[name] = {'artifact': m.record(path, tmp_path)}
        definitions[name] = (path.relative_to(tmp_path).as_posix(), m.sha(path), count)
    monkeypatch.setattr(m.inputs, 'MODELS', definitions)
    m.write(original/'predictors.json', models)
    recovery.mkdir(parents=True)
    with zipfile.ZipFile(recovery/'raw-evidence.zip', 'x') as archive:
        archive.write(source/'features/attempt-0000/features.json', 'features.json')
    m.write(recovery/'raw-evidence.json', {'archive_sha256': m.sha(recovery/'raw-evidence.zip'), 'files': []})
    done = {'original_completion_remains_false': True, 'completed_at_utc': '2026-10-16T01:00:00+00:00'}
    m.write(recovery/'completion.json', done)
    m.write(recovery/'packaging-plan.json', {'original_root': source.relative_to(tmp_path).as_posix(),
            'sources': [m.packaging.record(path) for path in (audit_source, audit_tests)]})
    audit = tmp_path/'results/review.json'
    review = {'schema': 'isaforge-v11d-independent-feature-packaging-audit-v1', 'status': 'pass', 'complete': True,
              'audited_at_utc': '2026-10-16T02:00:00+00:00', 'audit_source': m.record(audit_source, tmp_path),
              'auditor_sha256': m.sha(audit_source), 'tests_sha256': m.sha(audit_tests),
              'shared_helper_sha256': m.sha(m.packaging.__file__), 'original_runner_sha256': m.FROZEN_SHA,
              'records': 2, 'full_columns': 336, 'selected_columns': 217, 'native_channels': 4,
              'original_completion_remains_false': True, 'scope': 'SYNTHETIC admission'}
    review.update({k: 0 for k in ('new_native_jobs','new_features','new_models_loaded','new_predictions','new_labels','new_fits')})
    for key, path in [('completion_sha256', recovery/'completion.json'), ('archive_sha256', recovery/'raw-evidence.zip'),
                      ('manifest_sha256', recovery/'raw-evidence.json'), ('original_completion_sha256', source/'features/completion.json'),
                      ('features_sha256', source/'features/attempt-0000/features.json'), ('packaging_plan_sha256', recovery/'packaging-plan.json'),
                      ('original_feature_plan_sha256', source/'feature-plan.json'), ('replay_sha256', source/'features/attempt-0000/replay/result.json')]:
        review[key] = m.sha(path)
    m.write(audit, review)
    source_bound = [source/'feature-plan.json', source/'features/completion.json', source/'features/attempt-0000/features.json', source/'runtime.json', original/'candidates.json', original/'memberships.json', original/'predictors.json']
    source_bound += [tmp_path/entry['artifact']['path'] for entry in models.values()]
    recovery_bound = list(recovery.iterdir())
    def source_gate(path):
        assert path == source
        return copy.deepcopy(p), copy.deepcopy(candidates), copy.deepcopy(models), copy.deepcopy(tools), {path: m.sha(path) for path in source_bound}
    def recovery_gate(path):
        assert path == recovery
        return copy.deepcopy(done), copy.deepcopy(data), {path: m.sha(path) for path in recovery_bound}
    monkeypatch.setattr(m.frozen, 'validate', source_gate)
    monkeypatch.setattr(m.packaging, 'validate_recovery', recovery_gate)
    monkeypatch.setattr(m.frozen, 'runtime', lambda: copy.deepcopy(runtime))
    monkeypatch.setattr(m.frozen, 'tools_bindings', lambda t: {})
    return SimpleNamespace(source=source, recovery=recovery, root=root, original=original, audit=audit,
                           review=review, data=data, candidates=candidates, members=members, models=models, tools=tools, script=script)


def prepare(state):
    return m.prepare(state.source, state.recovery, state.audit, m.sha(state.audit), state.root)


def release(state, monkeypatch):
    monkeypatch.setattr(m, 'git_freeze', lambda *a: None)
    p = m.read(state.root/'inference-plan.json')
    value = {'status': 'approved-v11e-recovered-feature-frozen-predictions',
             'inference_plan_sha256': m.sha(state.root/'inference-plan.json'), 'runner_sha256': m.sha(m.__file__),
             'tests_sha256': m.sha(Path(__file__)), 'candidate_count': 2, 'maximum_predictions': 4,
             'recovery_completion_sha256': p['feature_admission']['recovery_completion']['sha256'],
             'features_sha256': p['feature_admission']['features']['sha256'], 'reviewed_at_utc': m.now(), 'freeze_commit': 'a'*40}
    # The source-bound test filename is rooted at m.ROOT in synthetic fixtures.
    target = m.ROOT/'tests/test_predict_v11e_transfer.py'
    target.write_bytes(Path(__file__).read_bytes())
    value['tests_sha256'] = m.sha(target)
    m.write(state.root/'prediction-approval.json', value)
    return state.root/'prediction-approval.json'


def result_for(state):
    p = m.read(state.root/'inference-plan.json'); a = p['feature_admission']
    return {'schema': 'isaforge-v11e-frozen-point-predictions-v1', 'candidate_count': 2,
            'models': {name: [dict(c, predicted_lut4=0., upper_lut4=None, calibration_status='uncalibrated') for c in state.candidates] for name in ('V6', 'V9')},
            'inference_plan_sha256': m.sha(state.root/'inference-plan.json'), 'features_sha256': a['features']['sha256'],
            'recovery_completion_sha256': a['recovery_completion']['sha256'], 'source_failed_completion_sha256': a['source_failed_completion']['sha256'],
            'input_preparation_sha256': p['input_preparation_sha256'], 'membership_sha256': m.sha(state.original/'memberships.json'),
            'predictor_manifest_sha256': m.sha(state.original/'predictors.json'), 'runner_sha256': m.sha(m.__file__),
            'raw_replay_records': 2, 'raw_replay_native_channels': 4}


def fake_worker(state, monkeypatch, poison=None):
    def worker(root, bindings, tools):
        stage = root/'predictions/attempt-0000'; stage.mkdir(parents=True)
        (stage/'worker.log').write_text('SYNTHETIC owned worker')
        value = result_for(state)
        if poison == 'replay': value['raw_replay_native_channels'] = 5
        if poison == 'negative': value['models']['V9'][0]['predicted_lut4'] = -1
        if poison == 'provenance': value['features_sha256'] = 'f'*64
        m.write(stage/'result.json', value)
        m.write(stage/'worker.json', {'schema': 'isaforge-v11e-prediction-worker-v1', 'action': 'inference-worker',
                'complete': True, 'primary_error': None, 'returncode': 0, 'cleanup_errors': [], 'remaining_owned_children': [],
                'runner_sha256': m.sha(m.__file__), 'log_sha256': m.sha(stage/'worker.log'),
                'command': [sys.executable, str(Path(m.__file__).resolve()), 'inference-worker', '--root', str(root), '--payload', json.dumps({'claim_sha256': m.sha(root/'prediction-claim.json')})],
                'timeout_seconds': 300, 'elapsed_seconds': .1, 'started_at_utc': m.now(), 'completed_at_utc': m.now()})
        return value
    monkeypatch.setattr(m, 'run_worker', worker)


def test_prepare_validate_preserves_failed_original_and_has_no_jobs(recovered):
    p = prepare(recovered)
    _, c, members, _, _, _, bindings = m.validate(recovered.root)
    assert len(c) == 2 and len(members) == 6 and p['raw_replay_native_channels'] == 4
    assert len(p['columns']) == 336 and len(p['selected_columns']) == 217
    assert all(v == 0 for v in p['calls'].values()) and recovered.script in bindings
    assert m.read(recovered.source/'features/completion.json') == {'complete': False}
    assert not (recovered.root/'features').exists() and not (recovered.root/'predictions').exists()


@pytest.mark.parametrize('poison', ['audit-digest', 'audit-count', 'audit-scope', 'failed-completion', 'source', 'plan-scope', 'replay-count', 'binding-bytes'])
def test_admission_and_seal_reject_changed_evidence(recovered, poison):
    if poison in ('source', 'plan-scope', 'replay-count', 'binding-bytes'):
        p = prepare(recovered)
        if poison == 'source': recovered.script.write_text('POISON')
        elif poison == 'plan-scope': p['calls']['labels'] = 1; m.write(recovered.root/'inference-plan.json', p)
        elif poison == 'binding-bytes': p['files'][0]['bytes'] += 1; m.write(recovered.root/'inference-plan.json', p)
        else: p['raw_replay_native_channels'] = 5; m.write(recovered.root/'inference-plan.json', p)
        with pytest.raises(ValueError): m.validate(recovered.root)
    else:
        if poison == 'failed-completion': m.write(recovered.source/'features/completion.json', {'complete': True})
        elif poison == 'audit-count': recovered.review['records'] = 1; m.write(recovered.audit, recovered.review)
        elif poison == 'audit-scope': recovered.review['new_labels'] = 1; m.write(recovered.audit, recovered.review)
        digest = 'a'*64 if poison == 'audit-digest' else m.sha(recovered.audit)
        with pytest.raises(ValueError): m.prepare(recovered.source, recovered.recovery, recovered.audit, digest, recovered.root)
        assert not recovered.root.exists()


@pytest.mark.parametrize('poison', [None, 'negative', 'provenance', 'replay'])
def test_full_pair_freeze_and_failures_remain_closed(recovered, monkeypatch, poison):
    prepare(recovered); approval = release(recovered, monkeypatch); fake_worker(recovered, monkeypatch, poison)
    if poison is not None:
        with pytest.raises(ValueError): m.predict(recovered.root, approval)
        assert m.read(recovered.root/'predictions/completion.json')['complete'] is False
        with pytest.raises((ValueError, FileNotFoundError)): m.validate_point_freeze(recovered.root)
    else:
        assert m.predict(recovered.root, approval)['complete']
        f, c, members, bindings = m.validate_point_freeze(recovered.root)
        assert f['candidate_count'] == 2 and f['prediction_count'] == 4 and len(members) == 6
        assert recovered.root/'point-freeze.json' in bindings
        assert f['feature_admission']['original_completion_remains_false'] is True
        with pytest.raises(ValueError, match='fresh inference-only'): m.predict(recovered.root, approval)
    assert m.read(recovered.source/'features/completion.json')['complete'] is False


def test_worker_replays_before_loading_exact_pair_and_uses_full336(recovered, monkeypatch):
    prepare(recovered)
    p = m.read(recovered.root/'inference-plan.json')
    approval = release(recovered, monkeypatch)
    m.write(recovered.root/'prediction-claim.json', {'runner_sha256': m.sha(m.__file__), 'inference_plan_sha256': m.sha(recovered.root/'inference-plan.json'),
            'approval_sha256': m.sha(approval), 'maximum_predictions': 4, 'claimed_at_utc': m.now()})
    events = []
    def replay(archive, row, tool, root):
        events.append('replay')
        assert tool == p['frozen_tool'] and root == str(recovered.source)
        return row['values'], {row['candidate_id']+':a', row['candidate_id']+':b'}
    monkeypatch.setattr(m.frozen.replay, 'replay_feature_record', replay)
    class Model:
        kind = 'mapping_v6'; calibration = {'status': 'uncalibrated'}; frozen_tool = p['frozen_tool']
        def __init__(self, count): self.training_formula_count = count
        def predict_features(self, rows, x):
            events.append('predict')
            assert rows == recovered.candidates and x.shape == (2, 336)
            return [dict(row, predicted_lut4=0., upper_lut4=None, calibration_status='uncalibrated') for row in rows]
    def load(path):
        assert events[:2] == ['replay', 'replay']
        events.append('load-'+path.stem)
        return Model(m.inputs.MODELS[path.stem][2])
    monkeypatch.setattr(m.v6, 'load_model', load)
    m.inference_worker(recovered.root, {'claim_sha256': m.sha(recovered.root/'prediction-claim.json')})
    assert events == ['replay', 'replay', 'load-V6', 'predict', 'load-V9', 'predict']
    assert m.read(recovered.root/'predictions/attempt-0000/result.json')['raw_replay_native_channels'] == 4


def test_incomplete_raw_replay_blocks_model_loading(recovered, monkeypatch):
    prepare(recovered)
    approval = release(recovered, monkeypatch)
    m.write(recovered.root/'prediction-claim.json', {'runner_sha256': m.sha(m.__file__), 'inference_plan_sha256': m.sha(recovered.root/'inference-plan.json'),
            'approval_sha256': m.sha(approval), 'maximum_predictions': 4, 'claimed_at_utc': m.now()})
    monkeypatch.setattr(m.frozen.replay, 'replay_feature_record', lambda *a: ([], {'same:a', 'same:b', 'extra:c', 'extra:d', 'extra:e'}))
    with pytest.raises(ValueError, match='Complete raw336'):
        m.inference_worker(recovered.root, {'claim_sha256': m.sha(recovered.root/'prediction-claim.json')})


def test_synthetic_worker_failure_keeps_receipt_and_cleanup(recovered, monkeypatch):
    prepare(recovered)
    m.write(recovered.root/'prediction-claim.json', {'synthetic': True})
    class Process:
        returncode = 1
        def poll(self): return 1
    process = Process(); removed = []
    class Owner:
        def __init__(self, environment): assert environment == recovered.tools['environment']
        def launch(self, command, stream): return process
        def remove(self, p): removed.append(p)
    monkeypatch.setattr(m.frozen, 'Owner', Owner)
    monkeypatch.setattr(m.frozen, 'clean', lambda p: ([], []))
    with pytest.raises(ValueError, match='Owned inference worker failed'):
        m.run_worker(recovered.root, {}, recovered.tools)
    assert removed == [process]
    receipt = m.read(recovered.root/'predictions/attempt-0000/worker.json')
    assert receipt['complete'] is False and receipt['returncode'] == 1 and receipt['cleanup_errors'] == []


def test_unreviewed_outside_path_cannot_bypass_git(recovered, monkeypatch, tmp_path):
    prepare(recovered)
    external = tmp_path.parent/'outside-inference.py'; external.write_text('SYNTHETIC outside source')
    monkeypatch.setattr(m.frozen, 'local_payloads', lambda b: set())
    monkeypatch.setattr(m, 'recovered_local_payloads', lambda *a: set())
    with pytest.raises(ValueError, match='outside-repository'):
        m.git_freeze(recovered.root, {external: m.sha(external)}, 'a'*40)


@pytest.mark.parametrize('poison', ['missing-approval', 'claim-scope', 'approval-scope'])
def test_direct_worker_cannot_bypass_release(recovered, monkeypatch, poison):
    prepare(recovered)
    approval = release(recovered, monkeypatch)
    claim = {'runner_sha256': m.sha(m.__file__), 'inference_plan_sha256': m.sha(recovered.root/'inference-plan.json'),
             'approval_sha256': m.sha(approval), 'maximum_predictions': 4, 'claimed_at_utc': m.now()}
    if poison == 'claim-scope': claim['maximum_predictions'] = 2
    if poison == 'approval-scope':
        value = m.read(approval); value['maximum_predictions'] = 2; m.write(approval, value); claim['approval_sha256'] = m.sha(approval)
    m.write(recovered.root/'prediction-claim.json', claim)
    if poison == 'missing-approval': approval.unlink()
    with pytest.raises((ValueError, FileNotFoundError)):
        m.inference_worker(recovered.root, {'claim_sha256': m.sha(recovered.root/'prediction-claim.json')})


def test_only_exact_archive_backed_worker_receipts_and_caches_may_be_local(recovered):
    prepare(recovered)
    stage = recovered.source/'features/attempt-0000'
    partial = stage/'raw-evidence.zip'; partial.write_bytes(b'SYNTHETIC partial ZIP')
    cache = stage/'cache/key/graph.json'; m.write(cache, {'synthetic': True})
    receipt = stage/'workers/0/worker.json'; m.write(receipt, {'synthetic': True})
    control = stage/'replay/worker.json'; m.write(control, {'synthetic': True})
    unexpected = stage/'workers/0/extra.py'; unexpected.write_text('SYNTHETIC unreviewed source')
    paths = [cache, receipt, control, unexpected]
    entries = [{'member': path.relative_to(stage).as_posix(), **m.packaging.record(path)} for path in paths]
    m.write(recovered.recovery/'packaging-plan.json', {'original_partial_archive': m.packaging.record(partial), 'members': entries})
    archive_sha = m.sha(recovered.recovery/'raw-evidence.zip')
    m.write(recovered.recovery/'completion.json', {'archive_sha256': archive_sha})
    manifest = {'archive_sha256': archive_sha, 'files': [{'path': e['member'], 'sha256': e['sha256'], 'bytes': e['bytes']} for e in entries]}
    m.write(recovered.recovery/'raw-evidence.json', manifest)
    bindings = {path: m.sha(path) for path in [*paths, partial, recovered.recovery/'raw-evidence.zip']}
    allowed = m.recovered_local_payloads(recovered.root, bindings)
    assert cache in allowed and receipt in allowed and partial in allowed
    assert control not in allowed and unexpected not in allowed
    manifest['files'][1]['sha256'] = 'f'*64
    m.write(recovered.recovery/'raw-evidence.json', manifest)
    with pytest.raises(ValueError, match='archive-backed'):
        m.recovered_local_payloads(recovered.root, bindings)
