"""Synthetic sealed studies exercise incremental export without live results."""
from __future__ import annotations
import copy
from pathlib import Path
import pytest
from isaforge import codesign as c
from scripts import export_incremental_selection_corpus as exporter
from test_budgeted_selection import public, measured


def seal_manifest(folder):
    c.seal(folder/'manifest.json',{p.relative_to(folder).as_posix():c.sha(p)
        for p in sorted(folder.rglob('*')) if p.is_file() and p.name not in ('manifest.json','manifest.json.sha256')})


def write_study(root,rel='study',count=2,group='new-group',failed=False):
    folder,prereg = root/rel,root/(rel+'-prereg')
    context_id = rel+'-context'
    context = dict(context_id=context_id,workload_group=group,compiler_flags=['unchanged'],source='real-context')
    c.seal(prereg/'inputs/context.json',context)
    c.seal(prereg/'preregistration.json',dict(historical_rows=156,target_labels_read=0,
        target_labels_observed=0,candidate_attempts_before_fit=0,target_context_id=context_id,
        target_workload=group,family_excluded_training_rows=133))
    seal_manifest(prereg)
    formulas = ['add(in0,in1)','sub(in0,in1)','xor(in0,in1)','or(in0,in1)']
    pubs = [public(c.digest([context_id,f]),f,group+':'+context_id) for f in formulas[:count]]
    names = [f'candidate_{i:02d}' for i in range(count)]
    outcomes = [measured(row) for row in pubs]
    successful = [dict(name=n,candidate_id=r['candidate_id'],measurement_seconds=r['measurement_seconds'],
        speedup=r['speedup'],cycles=r['candidate_cycles'],area_delta_lut4=r['area_delta_lut4'])
        for r,n in zip(outcomes,names)]
    failures = []
    if failed:
        outcomes[-1] = dict(pubs[-1],status='failed',measurement_seconds=2.,error='Unknown infrastructure outcome',
            failure_class='infrastructure_unknown',reference_censored=True)
        successful.pop()
        failures = [dict(name=names[-1],status='failed',elapsed_seconds=2.,
            reference_censored=True,classification='infrastructure_unknown')]
    audit = dict(schema='isaforge-guarded-evidence-v1',context_id=context_id,
        attempt_collection_complete=True,candidate_wall_seconds_complete=True,
        charged_candidate_attempts=count,unattempted=[],outcomes=copy.deepcopy(outcomes),
        public=pubs,pool_names=names,successful=successful,failed_or_interrupted=failures,
        candidate_wall_seconds=2.*count,reference_censored_candidates=names[-1:] if failed else [])
    c.seal(folder/'outcomes.json',outcomes);c.seal(folder/'native-audit.json',audit)
    c.seal(folder/'release.json',dict(preregistration=prereg.relative_to(root).as_posix(),
        preregistration_manifest_sha256=c.sha(prereg/'manifest.json'),target_context_id=context_id,
        prelabel_commit='frozen-before-labels',pool_names=names,
        pool_roster=[dict(name=n,candidate_id=r['candidate_id'],formula=r['formula']) for r,n in zip(pubs,names)]))
    seal_manifest(folder)
    return folder,prereg


def test_successes_and_unknown_failures_preserve_costs_and_actual_context(tmp_path,monkeypatch):
    monkeypatch.setattr(exporter,'ROOT',tmp_path)
    write_study(tmp_path,failed=True)
    rows,failures,context,bindings,metadata = exporter._read_study('study',2,'new-group')
    assert len(rows) == len(failures) == 1
    assert failures[0]['status'] == 'failed' and failures[0]['reference_censored'] is True
    assert 'speedup' not in failures[0]
    assert metadata['candidate_wall_seconds'] == 4.
    assert metadata['prelabel_historical_successes'] == 156
    assert context['source'] == 'real-context' and context['compiler_flags'] == ['unchanged']
    assert 'study-prereg/inputs/context.json' in bindings


@pytest.mark.parametrize('tamper', ['success_cost','total_cost','group','audit_row','family'])
def test_tampered_measurement_cost_group_family_or_audit_is_rejected(tmp_path,monkeypatch,tamper):
    monkeypatch.setattr(exporter,'ROOT',tmp_path)
    folder,_ = write_study(tmp_path)
    audit = c.unseal(folder/'native-audit.json')
    outcomes = c.unseal(folder/'outcomes.json')
    if tamper == 'success_cost':
        audit['successful'][0]['measurement_seconds'] += 1
    elif tamper == 'total_cost':
        audit['candidate_wall_seconds'] += 1
    elif tamper == 'group':
        outcomes[0]['workload_group'] = 'wrong-group'
        audit['outcomes'][0] = copy.deepcopy(outcomes[0])
    elif tamper == 'audit_row':
        audit['outcomes'][0]['speedup'] += .1
    elif tamper == 'family':
        outcomes[0]['candidate_family'] = 'fabricated'
        audit['outcomes'][0] = copy.deepcopy(outcomes[0])
    c.seal(folder/'outcomes.json',outcomes);c.seal(folder/'native-audit.json',audit);seal_manifest(folder)
    with pytest.raises(ValueError):
        exporter._read_study('study',2,'new-group')


def test_resealed_fabricated_context_identity_still_rejected(tmp_path,monkeypatch):
    monkeypatch.setattr(exporter,'ROOT',tmp_path)
    folder,prereg = write_study(tmp_path)
    context = c.unseal(prereg/'inputs/context.json');context['context_id'] = 'invented'
    c.seal(prereg/'inputs/context.json',context);seal_manifest(prereg)
    release = c.unseal(folder/'release.json');release['preregistration_manifest_sha256'] = c.sha(prereg/'manifest.json')
    c.seal(folder/'release.json',release);seal_manifest(folder)
    with pytest.raises(ValueError,match='Source context/group identity'):
        exporter._read_study('study',2,'new-group')


def test_failed_unknown_cannot_acquire_fabricated_success_labels(tmp_path,monkeypatch):
    monkeypatch.setattr(exporter,'ROOT',tmp_path)
    folder,_ = write_study(tmp_path,failed=True)
    outcomes = c.unseal(folder/'outcomes.json');outcomes[-1]['speedup'] = 1.2
    audit = c.unseal(folder/'native-audit.json');audit['outcomes'] = copy.deepcopy(outcomes)
    c.seal(folder/'outcomes.json',outcomes);c.seal(folder/'native-audit.json',audit);seal_manifest(folder)
    with pytest.raises(ValueError,match='Failed attempt must not include'):
        exporter._read_study('study',2,'new-group')


def test_collection_adds_base_cumulative_cost_once_and_authenticates_rederivation(tmp_path,monkeypatch):
    monkeypatch.setattr(exporter,'ROOT',tmp_path)
    base_dir = tmp_path/'base';monkeypatch.setattr(exporter,'BASE',base_dir)
    rows = [exporter.base_export._normalise(measured(public('old-'+str(i),benchmark='old:ctx'))) for i in range(156)]
    failures = [dict(public('failed-'+str(i),benchmark='old:ctx'),status='failed',measurement_seconds=2.,error='old failure',
        workload_group='old',source_id='old:ctx',candidate_family=exporter.base_export.family('add(in0,slli(in1,1))'),
        data_use='consumed-development') for i in range(4)]
    base = dict(rows=rows,failed_attempts=failures,contexts={'old:ctx':dict(context_id='ctx',workload_group='old')},
        new_source_contexts=[],successful_labels=156,total_candidate_attempts=160,total_candidate_attempt_wall_seconds=320.)
    c.seal(base_dir/'corpus.json',base);c.seal(base_dir/'provenance.json',{});seal_manifest(base_dir)
    monkeypatch.setattr(exporter.base_export,'authenticate',lambda _: (copy.deepcopy(base),{}))
    monkeypatch.setattr(exporter,'STUDIES',(('four',4,'four-group'),('two',2,'two-group')))
    write_study(tmp_path,'four',4,'four-group');write_study(tmp_path,'two',2,'two-group')
    output = tmp_path/'export'
    result = exporter.export(output)
    assert result['successful_labels'] == 162 and result['failed_attempt_count'] == 4
    assert result['total_candidate_attempts'] == 166
    assert result['incremental_candidate_wall_seconds'] == 12.
    assert result['total_candidate_attempt_wall_seconds'] == 332.
    assert set(result['contexts']) == {'old:ctx','four-group:four-context','two-group:two-context'}
    assert exporter.authenticate(output)[0] == result
    with pytest.raises(ValueError,match='Fresh corpus'):
        exporter.export(output)
    changed = c.unseal(output/'corpus.json');changed['total_candidate_attempt_wall_seconds'] += 1
    c.seal(output/'corpus.json',changed);seal_manifest(output)
    with pytest.raises(ValueError,match='rederived authenticated sources'):
        exporter.authenticate(output)
