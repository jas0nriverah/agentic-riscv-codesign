"""Synthetic complete-pool seals; native/model inference/target access forbidden."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import types
import pytest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('prepare_v11_model_comparison',ROOT/'scripts/prepare_v11_model_comparison.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

@pytest.fixture(autouse=True)
def no_native(monkeypatch):
    monkeypatch.setattr(subprocess,'Popen',lambda *a,**k:pytest.fail('Native execution forbidden'))
    import joblib
    monkeypatch.setattr(joblib,'load',lambda *a,**k:pytest.fail('Model loading forbidden'))

@pytest.fixture
def recovered(tmp_path,monkeypatch):
    monkeypatch.setattr(m,'ROOT',tmp_path);root=tmp_path/'results/recovery';root.mkdir(parents=True)
    formulas={'ammunition':['add(in0,in1)'],'audiobeam':['add(in1,in0)'],'pm':['xor(in0,in1)'],
        'fmref':['add(in0,in1)'],'fac':['sub(in0,in1)'],'recursion':[]};records={};completed=[]
    for name,family in m.FAMILIES.items():
        rows=[{'formula':f,'occurrences':[{'symbols':['SYNTHETIC-helper'],'pcs':['0x100']}]} for f in formulas[name]]
        p=root/'original'/f'{name}.json';m.write(p,rows)
        records[name]={'family':family,'status':'complete' if rows else 'empty','candidate_count':len(rows),'candidate_file':m.record(p,root)}
        completed.extend({**r,'benchmark':name,'family':family} for r in rows)
    m.write(root/'run/attempt-0000/completed-rows.json',completed)
    return root,records

def test_full_memberships_cross_program_originals_and_empty_preserved(recovered):
    root,records=recovered;before=copy.deepcopy(records);members,candidates,copies=m.pool(root,records)
    assert records==before and len(members)==6 and len(candidates)==4 and sum(r['canonical_count'] for r in members)==5
    shared=next(r for r in candidates if r['formula']=='add(in0,in1)');assert shared['programs']==['ammunition','fmref'] and len(shared['families'])==2
    assert members[-1]['program']=='recursion' and members[-1]['status']=='empty' and members[-1]['canonical_ids']==[]
    assert len({r['candidate_id'] for r in candidates})==4 and all(p.is_file() for p in copies.values())

@pytest.mark.parametrize('poison',['missing','extra','family','failed','badcount','duplicate','noncanonical','familyempty','recursionfilled','wrongcompleted','boolcount'])
def test_pool_fail_closed(recovered,poison):
    root,r=recovered
    if poison=='missing':r.pop('pm')
    elif poison=='extra':r['foreign']=copy.deepcopy(r['pm'])
    elif poison=='family':r['pm']['family']='integer-recurrences'
    elif poison=='failed':r['pm']['status']='failure-retained'
    elif poison=='badcount':r['pm']['candidate_count']=2
    elif poison=='boolcount':r['pm']['candidate_count']=True
    elif poison=='wrongcompleted':(root/'run/attempt-0000/completed-rows.json').write_text('[]')
    else:
        name='pm' if poison!='recursionfilled' else 'recursion';p=root/r[name]['candidate_file']['path']
        rows=m.read(p)
        if poison=='duplicate':rows+=copy.deepcopy(rows)
        elif poison=='noncanonical':rows[0]['formula']='add( in0, in1 )'
        elif poison=='familyempty':rows=[];r[name]['status']='empty'
        else:rows=[{'formula':'or(in0,in1)'}];r[name]['status']='complete'
        p.write_text(json.dumps(rows));r[name]['candidate_count']=len(rows);r[name]['candidate_file']=m.record(p,root)
    with pytest.raises(ValueError):m.pool(root,r)

def test_saved_accepted_modes_only_and_commutative_diagnostic(recovered):
    original='add(in0,in1)';poison='xor(in0,in1)'
    row={'formula':original,'normalized_formula':original,'v7_modes':{k:{'normalized_formula':poison,'metadata':{'status':'fallback'}} for k in ('bit','affine','combined')}}
    assert m.accepted_forms(row)=={original}
    row['v7_modes']['bit']['metadata']['status']='accepted';assert m.accepted_forms(row)=={original,poison}
    _,candidates,_=m.pool(*recovered)
    d=m.overlap(candidates,{original:{original},'or(in0,in1)':{'or(in0,in1)'}},{'V6':{original},'V9':{original,'or(in0,in1)'}})
    commuted=next(r for r in d['records'] if r['formula']=='add(in1,in0)')
    assert not commuted['pre_reservation_canonical_seen'] and commuted['pre_reservation_matches']['saved_accepted_form']==[]
    assert commuted['training_overlap']['V6']['declared_alias_originals']==[original]
    different=next(r for r in d['records'] if r['formula']==poison)
    assert not different['training_overlap']['V6']['declared_alias_originals']

def test_budget_is_full_unique_pool_and_not_authorization():
    d=m.budget(257,420);assert d['unique_original_mappings']==257 and d['rtl_output_comparisons']==552036
    assert d['verification_batches']==3 and d['timeout_envelope_seconds_excluding_packaging']==360*(3+129)
    assert d['maximum_cold_feature_channels']==771 and d['target_jobs_released']==d['feature_jobs_released']==d['fits_released']==0

def test_accepted_identity_chain_closes_training_familiarity_without_filtering():
    a='add(add(in0,in1),in0)';b='add(slli(in0,1),in1)';c='sub(add(slli(in0,2),in1),slli(in0,1))'
    candidates=[{'formula':c,'candidate_id':m.identifier(c)}];before=copy.deepcopy(candidates)
    d=m.overlap(candidates,{a:{a,b},b:{b,c}},{'V6':{a},'V9':{a,b}});r=d['records'][0]
    assert candidates==before and len(d['records'])==1
    assert r['pre_reservation_matches']['saved_accepted_form']==[b]
    assert r['training_overlap']['V6']['declared_alias_originals']==[]
    assert r['training_overlap']['V6']['accepted_identity_component_originals']==[a]
    assert r['training_overlap']['V9']['accepted_identity_component_originals']==sorted([a,b])
    assert d['accepted_identity_components']['count']==1

def test_fallback_and_skeleton_are_not_identity_edges():
    a='add(add(in0,in1),in0)';b='add(slli(in0,1),in1)';c='sub(add(slli(in0,2),in1),slli(in0,1))'
    saved={'formula':b,'normalized_formula':b,'v7_modes':{k:{'normalized_formula':c,'metadata':{'status':'fallback'}} for k in ('bit','affine','combined')}}
    d=m.overlap([{'formula':c,'candidate_id':m.identifier(c)}],{a:{a,b},b:m.accepted_forms(saved)},{'V6':{a}})
    assert d['records'][0]['training_overlap']['V6']['accepted_identity_component_originals']==[]
    # Same ordered operator structure with different immediates is not equality.
    x='slli(in0,1)';y='slli(in0,2)'
    d=m.overlap([{'formula':y,'candidate_id':m.identifier(y)}],{x:{x},y:{y}},{'V6':{x}});r=d['records'][0]
    assert x in r['pre_reservation_matches']['ordered_skeleton']
    assert r['training_overlap']['V6']['accepted_identity_component_originals']==[]
    assert d['accepted_identity_components']['count']==2

@pytest.fixture
def authenticated(recovered,monkeypatch):
    root,records=recovered;stage=root/'run/attempt-0000';m.write(root/'preparation.json',{'scope':'SYNTHETIC'})
    m.write(stage/'evidence-manifest.json',{});(stage/'metadata.zip').write_bytes(b'SYNTHETIC archive')
    done={'schema':'isaforge-v11c-recovery-completion-v1','complete':True,'failures':[],'completed_at_utc':'2026-01-01T00:00:00+00:00'}
    m.write(root/'completion.json',done);m.write(stage/'completion.json',done);m.write(stage/'programs.json',records)
    source=m.ROOT/'audit.py';source.write_text('SYNTHETIC auditor')
    report={'schema':'isaforge-v11c-independent-recovery-audit-v1','status':'pass','complete':True,'source_sha256':m.sha(source),
        'preparation_sha256':m.sha(root/'preparation.json'),'completion_sha256':m.sha(root/'completion.json'),'evidence_manifest_sha256':m.sha(stage/'evidence-manifest.json'),
        'program_count':6,'reused_program_count':4,'recovered_program_count':2,'labels_predictions_features_fits':0,
        'audited_at_utc':'2026-01-01T00:01:00+00:00','programs':{n:{'status':r['status'],'candidate_count':r['candidate_count']} for n,r in records.items()},
        'unique_canonical_formulas':4,'program_formula_rows':5,'independence':'SYNTHETIC shared helpers; not fully independent parser'}
    path=root/'independent-result-audit.json';m.write(path,report)
    audit=types.SimpleNamespace(__file__=str(source),inputs=lambda r:{'bindings':{},'plan':{}},verify_package=lambda r,d:({},{}),verify_outcomes=lambda r,p:None)
    monkeypatch.setitem(sys.modules,'audit_v11c_recovery',audit)
    return root,records,path,report,audit

@pytest.mark.parametrize('poison',['digest','partial','source','scope','completion','manifest','omittedoutcome','count','boolcount','boolzero','floattopcount','chronology'])
def test_audit_authentication_poisons(authenticated,poison):
    root,records,path,report,audit=authenticated
    if poison=='digest':digest='f'*64
    else:
        if poison=='partial':report['complete']=False
        elif poison=='source':report['source_sha256']='f'*64
        elif poison=='scope':report['labels_predictions_features_fits']=1
        elif poison=='completion':report['completion_sha256']='f'*64
        elif poison=='manifest':report['evidence_manifest_sha256']='f'*64
        elif poison=='omittedoutcome':report['programs'].pop('recursion')
        elif poison=='count':report['programs']['pm']['candidate_count']=99
        elif poison=='boolcount':report['programs']['fac']['candidate_count']=True
        elif poison=='boolzero':report['programs']['recursion']['candidate_count']=False
        elif poison=='floattopcount':report['program_count']=6.0
        else:report['audited_at_utc']='2025-01-01T00:00:00+00:00'
        path.write_text(json.dumps(report));digest=m.sha(path)
    with pytest.raises(ValueError):m.authenticate_recovery(root,path,digest)

def test_full_preparation_byte_copies_source_seal_and_no_outputs(authenticated,monkeypatch):
    root,records,path,report,audit=authenticated;source=m.ROOT/'new-source.py';source.write_text('SYNTHETIC source')
    monkeypatch.setattr(m,'sources',lambda:[source]);aliases={'add(in0,in1)':{'add(in0,in1)'}}
    monkeypatch.setattr(m,'historical_inputs',lambda:(aliases,{'V6':set(aliases),'V9':set(aliases)},{'SYNTHETIC':'metadata-only'},{}))
    output=m.ROOT/'results/comparison';result=m.prepare(root,path,m.sha(path),output)
    assert result['status']=='prepared-inputs-only' and result['unique_canonical_originals']==4 and result['program_formula_memberships']==5
    assert result['audit_independence']==report['independence'] and all(v==0 for v in result['calls'].values())
    for name,r in records.items():assert (output/'original-candidate-files'/(name+'.json')).read_bytes()==(root/r['candidate_file']['path']).read_bytes()
    for r in result['files']:assert m.sha(output/r['path'])==r['sha256']
    assert {p.name for p in output.iterdir()}=={'original-candidate-files','memberships.json','candidates.json','overlap.json','pre-reservation-reference.json','predictors.json','proposed-budget.json','preparation.json'}
    with pytest.raises(ValueError,match='Fresh separate'):m.prepare(root,path,m.sha(path),output)

@pytest.fixture
def history(tmp_path,monkeypatch):
    monkeypatch.setattr(m,'ROOT',tmp_path);root=tmp_path/m.V9;root.mkdir(parents=True)
    formulas=[f'add(in0,lui({i}))' for i in range(1,2882)]
    prior=[{'formula':f,'accepted_forms':[f]} for f in formulas];new=[{'formula':f'add(in0,lui({i}))'} for i in range(3000,3048)]
    identities=[{'formula':r['formula'],'normalized_formula':r['formula'],'v7_modes':{k:{'normalized_formula':r['formula'],'metadata':{'status':'accepted'}} for k in ('bit','affine','combined')}} for r in new]
    columns=['input'+str(i) for i in range(336)];selected=columns[:217];runtime=tmp_path/'isaforge/source.py';runtime.parent.mkdir();runtime.write_text('SYNTHETIC runtime')
    feature=tmp_path/'results/2026-10-14-v5/development-features.json';m.write(feature,{'records':[{'formula':f} for f in formulas]})
    recipe={'feature_columns':columns,'selected_columns':selected,'fixed_parameters':{'n_estimators':300},'frozen_tool':{'executable_sha256':'SYNTHETIC'},'baseline_model':{'schema':{}}}
    models={};schemas={}
    for name,count in [('V6',1665),('V9',1713)]:
        artifact=tmp_path/f'models/{name}.joblib';artifact.parent.mkdir(exist_ok=True);artifact.write_bytes(('SYNTHETIC '+name).encode());models[name]=(str(artifact.relative_to(tmp_path)),m.sha(artifact),count)
        schema={'schema':'isaforge-v6-model-v1','artifact_sha256':m.sha(artifact),'kind':'mapping_v6','training_formula_count':count,'calibration':{'status':'uncalibrated'},
            'feature_columns':columns,'mapping_columns':selected,'configuration':recipe['fixed_parameters'],'frozen_tool':recipe['frozen_tool'],'runtime_source_sha256':{'source.py':m.sha(runtime)},
            'training_provenance':{'development_features_sha256':m.sha(feature),'fit_indices':list(range(1665))}}
        m.write(artifact.with_suffix('.json'),schema);schemas[name]=artifact.with_suffix('.json')
    recipe['baseline_model']['schema']['sha256']=m.sha(schemas['V6']);point=root/'fit-attempt-0000/point-freeze.json';m.write(point,{'schema_sha256':m.sha(schemas['V9'])});monkeypatch.setattr(m,'V9_POINT_SHA',m.sha(point));monkeypatch.setattr(m,'MODELS',models)
    for name,value in [('consumed-input-ledger.json',{'records':prior}),('candidates.json',new),('identity-analysis.json',identities),('recipe.json',recipe)]:m.write(root/name,value)
    files=[root/n for n in ('consumed-input-ledger.json','candidates.json','identity-analysis.json','recipe.json')];m.write(root/'preparation.json',{'files':[m.record(p,root) for p in files]});monkeypatch.setattr(m,'V9_PREP_SHA',m.sha(root/'preparation.json'))
    return root,models,schemas,feature

def test_exact2929_and_training_sets_without_opening_targets(history,monkeypatch):
    root,models,schemas,feature=history;original=m.read;opened=[]
    def reader(path):
        opened.append(Path(path));assert Path(path).name not in ('original-training.json','development-data.json','evaluation.json','point-predictions.json','labels.json')
        return original(path)
    monkeypatch.setattr(m,'read',reader);aliases,training,records,b=m.historical_inputs()
    assert len(aliases)==2929 and len(training['V6'])==1665 and len(training['V9'])==1713
    assert all(p.with_suffix('.joblib') not in opened for p in schemas.values()) and feature in opened
    assert records['V6']['point_only'] and records['V9']['training_formula_count']==1713

@pytest.mark.parametrize('poison',['artifactmissing','artifactbytes','metadata','runtime','featurebytes','identitymissing'])
def test_historical_identity_failure_closed(history,poison):
    root,models,schemas,feature=history
    if poison=='artifactmissing':(m.ROOT/models['V6'][0]).unlink()
    elif poison=='artifactbytes':(m.ROOT/models['V6'][0]).write_bytes(b'POISON')
    elif poison=='metadata':schemas['V6'].write_text('{}')
    elif poison=='runtime':(m.ROOT/'isaforge/source.py').write_text('POISON')
    elif poison=='featurebytes':feature.write_text('{}')
    else:(root/'identity-analysis.json').write_text('[]')
    with pytest.raises((ValueError,FileNotFoundError)):m.historical_inputs()
