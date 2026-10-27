"""Synthetic metadata only: no archived labels, fitted artifacts or native tools."""
import builtins
import copy
import importlib.metadata
import json
from pathlib import Path
import subprocess

import pytest

from scripts import prepare_md5_heldout_controller as w


@pytest.fixture(autouse=True)
def forbid_native_models_and_real_results(monkeypatch):
    def forbidden(*args,**kwargs):
        raise AssertionError('Native/model action forbidden')
    monkeypatch.setattr(subprocess,'run',forbidden)
    monkeypatch.setattr(subprocess,'Popen',forbidden)
    original_import=builtins.__import__
    def checked_import(name,*args,**kwargs):
        assert not name.startswith('isaforge'), 'Runtime/model imports forbidden'
        return original_import(name,*args,**kwargs)
    monkeypatch.setattr(builtins,'__import__',checked_import)
    original_open=Path.open
    def checked_open(path,*args,**kwargs):
        assert not path.resolve().is_relative_to(w.ROOT/'results'), 'Real evidence access forbidden in tests'
        assert not any(part in ('measurements','attempt-ledger','model','models') for part in path.parts)
        return original_open(path,*args,**kwargs)
    monkeypatch.setattr(Path,'open',checked_open)
    monkeypatch.setattr(importlib.metadata,'version',lambda name:'synthetic-version')


def save(path,value,sidecar=True):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes(w.encoded(value)+b'\n')
    if sidecar:path.with_name(path.name+'.sha256').write_text(w.sha(path)+'\n')


@pytest.fixture
def fixture(tmp_path,monkeypatch):
    root=tmp_path;prereg=root/w.PREREG;certdir=root/w.CERTS
    prereg.mkdir(parents=True);certdir.mkdir()
    source_texts={name:'# synthetic dependency\n' for name in w.RECIPE_SOURCES}
    source_texts['isaforge/budgeted_selection.py']='POLICIES='+repr(w.EXPECTED_POLICIES[:10])+"\nGP_SETTINGS=dict(alpha=1e-4,optimizer=None)\n"
    source_texts['isaforge/tacle_workload.py']='POLICIES=(*b.POLICIES, '+', '.join(repr(x) for x in w.EXPECTED_POLICIES[10:14])+')\n'
    source_texts['isaforge/finite_selection.py']='MYOPIC="fixed_joint_myopic"\nLOOKAHEAD="fixed_joint_lookahead"\nFALLBACK="fixed_joint_heuristic_fallback"\nPOLICIES=(MYOPIC,LOOKAHEAD,FALLBACK)\nSETTINGS=dict(fantasy_draws=128)\n'
    source_texts['scripts/g723_selection_campaign.py']='POLICIES=[*OLD_POLICIES,*f.POLICIES]\n'
    source_texts['isaforge/model.py']='class M:\n def __init__(self,seed=0,ensemble_size=20): pass\n def fit(self): raise AssertionError("Must never execute")\n'
    for name,text in source_texts.items():
        path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)
    script=root/w.SOURCE;script.parent.mkdir(parents=True,exist_ok=True);script.write_text('# synthetic builder identity\n')
    context='archived-synthetic-context'
    roster=[dict(name=f'candidate_{i:02d}',formula=f'add(in0,slli(in1,{i+1}))') for i in range(12)]
    save(prereg/'roster.json',roster,False);monkeypatch.setattr(w,'ROSTER_SHA256',w.sha(prereg/'roster.json'))
    protocol=dict(candidate_dispatch_enabled=False,new_pool_labels=0,historical_md5_labels_excluded=True,
                  eligibility_pending=True,existing_context_id=context)
    save(prereg/'preregistration.json',protocol,False)
    save(prereg/'artifact-manifest.json',{name:w.sha(prereg/name) for name in ('roster.json','preregistration.json')},False)
    audit=dict(roster={'file_sha256':w.ROSTER_SHA256},cohort_amendment=dict(
        retained_fitting_rows=28,retained_training_ids=[f'synthetic-training-{i}' for i in range(28)],
        retained_group_count=7,retained_target_workload_rows=0,remaining_roster_family_overlap=False,
        retained_public_identity_digest='synthetic-public-identity'),source_bindings={
            name:w.sha(root/name) for name in ('isaforge/budgeted_selection.py','isaforge/finite_selection.py')})
    save(prereg/'independent-cohort-audit.json',audit);monkeypatch.setattr(w,'AUDIT_SHA256',w.sha(prereg/'independent-cohort-audit.json'))
    save(prereg/'cross-context-identity-audit-v2.json',{'authorization':dict(
        bounded_identity_membership_gate='passed',candidate_dispatch=False,new_pool_labels=0)})
    certs=[]
    for row in roster:
        assembly=row['name']+'.S';(certdir/assembly).write_text('# synthetic emitted assembly\n')
        certs.append(dict(**row,candidate_id=w.digest([context,row['formula']]),
            assembly=assembly,assembly_sha256=w.sha(certdir/assembly),
            relocation_check={'safe':True},lowering_check={'passed':True,'blocks':1,'comparisons':64}))
    certificate=dict(status='offline_certificates_complete_eligibility_pending',context_id=context,
        candidate_dispatch_enabled=False,new_pool_labels=0,eligibility_pending=True,
        roster_file_sha256=w.ROSTER_SHA256,roster_codesign_digest=w.digest(roster),certificates=certs)
    save(certdir/'certificates.json',certificate);monkeypatch.setattr(w,'CERTIFICATE_SHA256',w.sha(certdir/'certificates.json'))
    save(certdir/'artifact-manifest.json',{p.name:w.sha(p) for p in certdir.iterdir() if p.is_file()})
    return dict(root=root,prereg=prereg,certdir=certdir,output=prereg/'controller-preparation-test',
                audit=audit,certificate=certificate)


def test_only_zero_label_preparation_and_all_seventeen_policies(fixture):
    f=fixture;value=w.build(f['root'],f['output'])
    assert [p['policy'] for p in value['policies']]==list(w.EXPECTED_POLICIES)
    assert value['dispatch'] is False and value['measurement_authorization'] is False
    assert value['candidate_dispatch_enabled'] is False and value['model_artifacts_created'] is False
    assert value['model_fits']==value['model_predictions']==value['new_pool_labels']==value['native_jobs']==0
    assert value['primary']['area_delta_lut4']==64 and value['primary']['budget']==3
    assert value['primary']['clock_mhz']==12. and value['comparisons']['seeds_are_dependent']
    assert value['collection_contract']['maximum_unique_candidate_attempts']==12
    assert value['fitting_contract']['rows']==28 and value['fitting_contract']['groups']==7
    assert len(value['id_remap'])==12
    assert all(r['preparation_candidate_id']==w.digest([value['preparation_context_id'],r['formula']]) and
               r['preparation_candidate_id']!=r['archived_candidate_id'] for r in value['id_remap'])
    manifest=json.loads((f['output']/'artifact-manifest.json').read_text())
    assert all(w.sha(f['output']/name)==hashed for name,hashed in manifest.items())
    assert sorted(p.name for p in f['output'].iterdir())==sorted([
        'README.md','artifact-manifest.json','artifact-manifest.json.sha256',
        *[name+suffix for name in ('controller-contract.json','id-remap.json','recipe-source-snapshots.json')
          for suffix in ('','.sha256')]])


def test_refuses_existing_and_outside_output(fixture):
    f=fixture
    with pytest.raises(ValueError,match='Fresh direct'):w.build(f['root'],f['root']/'outside')
    w.build(f['root'],f['output'])
    with pytest.raises(ValueError,match='Fresh direct'):w.build(f['root'],f['output'])


@pytest.mark.parametrize('path',('roster.json','independent-cohort-audit.json.sha256'))
def test_changed_evidence_stops_before_package(fixture,path):
    f=fixture;(f['prereg']/path).write_text('changed')
    with pytest.raises((ValueError,json.JSONDecodeError)):w.build(f['root'],f['output'])
    assert not f['output'].exists()


def test_changed_emitted_assembly_stops_before_package(fixture):
    f=fixture;(f['certdir']/'candidate_00.S').write_text('changed')
    with pytest.raises(ValueError,match='assembly changed'):w.build(f['root'],f['output'])
    assert not f['output'].exists()


def test_changed_audited_recipe_stops_without_importing_or_fitting(fixture):
    f=fixture
    with (f['root']/'isaforge/budgeted_selection.py').open('a') as stream:stream.write('# changed\n')
    with pytest.raises(ValueError,match='Audited recipe source changed'):w.build(f['root'],f['output'])
    assert not f['output'].exists()


def test_changed_policy_composition_stops_before_package(fixture):
    f=fixture;(f['root']/'isaforge/tacle_workload.py').write_text('POLICIES=("other",)\n')
    with pytest.raises(ValueError,match='policy declaration changed'):w.build(f['root'],f['output'])
    assert not f['output'].exists()


def test_contract_keeps_budget_specific_endpoints_and_update_semantics(fixture):
    f=fixture;value=w.build(f['root'],f['output'])
    definitions={row['policy']:row for row in value['policies']}
    assert definitions['hybrid_gp_adapt_count_semantic']['update'].startswith('dynamic')
    assert definitions['fixed_joint_lookahead']['update'].startswith('fixed-initial')
    assert 'independent B1/B2/B3' in definitions['fixed_joint_lookahead']['endpoint_execution']
    assert 'prefixes' in definitions['merit']['endpoint_execution']
    assert value['reference']['censored'].endswith('complete-pool optimality.')
    assert value['collection_contract']['retries']==0
