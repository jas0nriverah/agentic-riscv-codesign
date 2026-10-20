"""Projection contract tests; synthetic fixtures are not processor evidence."""
import json
import sqlite3

import pytest

from isaforge import codesign as c
from isaforge import experiment_ledger as ledger


@pytest.fixture
def evidence(tmp_path, monkeypatch):
    root = tmp_path / 'raw'
    root.mkdir()
    plan = {'schema': 'isaforge-automatic-workload-v1', 'workload': 'fixture',
            'inputs': {}, 'source_bindings': {}, 'configuration': {'isa': 'rv32i'}}
    plan['context_id'] = c.digest(plan)
    c.seal(root / 'plan.json', plan)
    c.write(root / 'discovery/command.log', {'result': 'fixture'})
    command = {'log': 'discovery/command.log', 'log_sha256': c.sha(root / 'discovery/command.log'),
               'argv': ['fixture'], 'elapsed_seconds': 2.0, 'returncode': 0,
               'expected_returncode': 0, 'failure': None}
    c.seal(root / 'commands.json', [command])
    candidate = {'name': 'c1', 'formula': 'add(in0,in1)', 'features': {'operation_count': 2}}
    candidate['candidate_id'] = c.digest([plan['context_id'], candidate['formula']])
    c.seal(root / 'discovery/discovery.json', {'pool': [candidate], 'artifacts': {}})
    for name, cycles in [('baseline', 100), ('c1', 80)]:
        record = {'evaluation_id': 'eval-' + name, 'candidate_id': candidate['candidate_id'] if name == 'c1' else None,
                  'name': name, 'workload': 'fixture', 'performance': {'cycles': cycles, 'instructions': 20},
                  'speedup': 100 / cycles, 'resources': {'lut4_count': 101}, 'added_lut4': 1 if name == 'c1' else 0,
                  'frequency_mhz': 12.0, 'timing_feasible': True, 'elapsed_seconds': 3.0, 'artifacts': {},
                  'routes': [{'seed': 1, 'limiting_internal_fmax_mhz': 15.0, 'internal_timing_pass': True, 'device_fits': True}]}
        c.seal(root / f'measurements/{name}/measurement.json', record)
    audited = []
    monkeypatch.setattr(ledger.workload_audit, 'audit', lambda path: audited.append(path) or {'verified': True})
    return root, tmp_path / 'ledger.sqlite', audited


def test_verified_projection_idempotence_and_deterministic_export(evidence):
    root, db, audited = evidence
    assert ledger.import_evidence(db, root)['imported'] is True
    before = ledger.export(db)
    assert ledger.import_evidence(db, root)['imported'] is False
    assert ledger.export(db) == before
    assert len(audited) == 2
    summary = before['workload_summary'][0]
    assert summary['verified_candidates'] == 1
    assert summary['best_timing_feasible_speedup'] == 1.25
    assert {row['kind'] for row in before['cost_summary']} == {'evaluation_wall', 'native_command'}
    assert sum(row['seconds'] for row in before['cost_summary'] if row['kind'] == 'native_command') == 2
    assert all(row['unit'] == 'seconds' and row['timer_scope'] for row in before['costs'])
    assert len(before['routes']) == 2
    assert before['contexts'][0]['manifest_sha256']


def test_raw_tampering_fails_before_database_creation(evidence):
    root, db, _ = evidence
    (root / 'discovery/command.log').write_text('tampered')
    with pytest.raises(ValueError, match='checksum mismatch'):
        ledger.import_evidence(db, root)
    assert not db.exists()


def test_audit_failure_does_not_modify_database(evidence, monkeypatch):
    root, db, _ = evidence
    ledger.import_evidence(db, root)
    before = db.read_bytes()
    def reject(_):
        raise ValueError('processor evidence failed audit')
    monkeypatch.setattr(ledger.workload_audit, 'audit', reject)
    with pytest.raises(ValueError, match='failed audit'):
        ledger.import_evidence(db, root)
    assert db.read_bytes() == before


def test_resealed_conflict_retains_original_projection(evidence):
    root, db, _ = evidence
    ledger.import_evidence(db, root)
    before = ledger.export(db)
    path = root / 'measurements/c1/measurement.json'
    record = c.unseal(path)
    record['elapsed_seconds'] = 4
    c.seal(path, record)
    with pytest.raises(ValueError, match='different evidence'):
        ledger.import_evidence(db, root)
    assert ledger.export(db) == before


@pytest.mark.parametrize('duplicate', ['candidate', 'command', 'route', 'evaluation'])
def test_duplicate_records_rejected(evidence, duplicate):
    root, db, _ = evidence
    if duplicate == 'candidate':
        path = root / 'discovery/discovery.json'
        record = c.unseal(path)
        record['pool'] *= 2
    elif duplicate == 'command':
        path = root / 'commands.json'
        record = c.unseal(path) * 2
    else:
        path = root / 'measurements/c1/measurement.json'
        record = c.unseal(path)
        if duplicate == 'route':
            record['routes'] *= 2
        else:
            record['evaluation_id'] = 'eval-baseline'
    c.seal(path, record)
    with pytest.raises(ValueError, match='Duplicate'):
        ledger.import_evidence(db, root)
    assert not db.exists()


def test_incomplete_context_preserves_failures_without_labels(evidence):
    root, db, audited = evidence
    commands = c.unseal(root / 'commands.json')
    commands[0].update(returncode=1, failure='compile failed')
    c.seal(root / 'commands.json', commands)
    c.write(root / 'measurements/c1/attempt-000/failure.json', {'error': 'overflow', 'elapsed_seconds': 5})
    ledger.import_evidence(db, root, incomplete=True)
    result = ledger.export(db)
    assert not audited
    assert result['measurements'] == result['candidates'] == []
    assert len(result['failures']) == 2
    assert {row['authentication'] for row in result['failures']} == {'observed_unsealed_file', 'sealed_command_receipt'}
    assert {row['kind'] for row in result['costs']} == {'native_command', 'failed_attempt_wall'}
    assert result['workload_summary'][0]['status'] == 'incomplete'


@pytest.mark.parametrize('value', [-1, float('nan'), True])
def test_invalid_cost_rejected(evidence, value):
    root, db, _ = evidence
    path = root / 'commands.json'
    records = c.unseal(path)
    records[0]['elapsed_seconds'] = value
    path.write_text(json.dumps(records))
    (root / 'commands.json.sha256').write_text(c.sha(path))
    with pytest.raises(ValueError, match='elapsed|Non-finite'):
        ledger.import_evidence(db, root)
    assert not db.exists()


def test_duplicate_json_keys_rejected(evidence):
    root, db, _ = evidence
    path = root / 'commands.json'
    path.write_text('[{"log":"a","log":"b"}]')
    (root / 'commands.json.sha256').write_text(c.sha(path))
    with pytest.raises(ValueError, match='Duplicate JSON key'):
        ledger.import_evidence(db, root)


def test_path_escape_rejected(evidence):
    root, db, _ = evidence
    commands = c.unseal(root / 'commands.json')
    commands[0]['log'] = '../outside.log'
    c.seal(root / 'commands.json', commands)
    with pytest.raises(ValueError, match='escapes'):
        ledger.import_evidence(db, root)


def test_export_and_summary_are_read_only(evidence, capsys):
    root, db, _ = evidence
    ledger.import_evidence(db, root)
    before = db.read_bytes()
    ledger.main(['summary', '--db', str(db)])
    result = json.loads(capsys.readouterr().out)
    assert result['workload_summary'][0]['candidates'] == 1
    assert db.read_bytes() == before


def test_partitioned_plan_uses_guarded_audit(evidence, monkeypatch):
    import sys
    import types
    root, db, audited = evidence
    plan = c.unseal(root / 'plan.json')
    plan['memory_partition'] = {'fixture': True}
    del plan['context_id']
    plan['context_id'] = c.digest(plan)
    c.seal(root / 'plan.json', plan)
    # Stop at audit dispatch; these fixture candidate identities are deliberately stale.
    def guarded(_):
        raise ValueError('guarded stack audit called')
    monkeypatch.setitem(sys.modules, 'isaforge.partitioned_workload', types.SimpleNamespace(audit=guarded))
    with pytest.raises(ValueError, match='guarded stack'):
        ledger.import_evidence(db, root)
    assert not audited and not db.exists()


def test_incomplete_without_receipts_is_metadata_only(evidence):
    root, db, _ = evidence
    (root / 'commands.json').unlink()
    (root / 'commands.json.sha256').unlink()
    ledger.import_evidence(db, root, incomplete=True)
    result = ledger.export(db)
    assert result['costs'] == result['measurements'] == []
    assert json.loads(result['contexts'][0]['audit_json'])['command_receipts_present'] is False


def test_historical_source_snapshot_is_checked(evidence):
    root, db, _ = evidence
    snapshot = root / 'sources/old_source.py'
    snapshot.parent.mkdir()
    snapshot.write_text('# old source\n')
    plan = c.unseal(root / 'plan.json')
    plan['source_bindings'] = {'old_source.py': c.sha(snapshot)}
    del plan['context_id']
    plan['context_id'] = c.digest(plan)
    c.seal(root / 'plan.json', plan)
    ledger.import_evidence(db, root, incomplete=True)
    assert any(row['path'] == 'sources/old_source.py' for row in ledger.export(db)['source_files'])
    snapshot.write_text('# altered\n')
    with pytest.raises(ValueError, match='checksum mismatch'):
        ledger.import_evidence(db, root, incomplete=True)


@pytest.mark.parametrize('field,value', [('cycles', True), ('frequency_mhz', 100), ('timing_feasible', 'yes')])
def test_malformed_verified_record_rejected(evidence, field, value):
    root, db, _ = evidence
    path = root / 'measurements/c1/measurement.json'
    record = c.unseal(path)
    if field == 'cycles':
        record['performance'][field] = value
    else:
        record[field] = value
    c.seal(path, record)
    with pytest.raises(ValueError, match='Invalid cycle|Unsupported clock'):
        ledger.import_evidence(db, root)
    assert not db.exists()
