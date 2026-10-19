"""Synthetic V12 leakage, metric, release and exact30-fit orchestration tests."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import pytest
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('develop_v12_target_transform',ROOT/'scripts/develop_v12_target_transform.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


@pytest.fixture(autouse=True)
def no_native_or_real_fit(monkeypatch):
    monkeypatch.setattr(subprocess,'Popen',lambda *a,**k:pytest.fail('Native process forbidden'))
    monkeypatch.setattr(m,'ExtraTreesRegressor',lambda *a,**k:pytest.fail('Real fitting forbidden'))


def toy(count=27):
    rows=[{'formula':f'addi(in0,{i+1})','source':'original1665','development_index':i,'stratum':m.STRATA[i%9],
        'inherited_component':'old-'+str(i),'lut4_count':i%7} for i in range(count)]
    matrix=np.zeros((count,217),dtype='<f4');matrix[:,0]=np.arange(count)+1
    aliases=[[r['formula']] for r in rows]
    return rows,matrix,aliases


def test_no_label_outcome_metadata_changes_grouping_or_folds():
    rows,x,a=toy();groups=m.build_groups(rows,x,a);split=m.assign_folds(rows,groups)
    for i,r in enumerate(rows):r.update(lut4_count=9999-i,residual=-1000,benchmark='outcome poison',predicted_lut4=55)
    assert m.build_groups(rows,x,a)==groups and m.assign_folds(rows,groups)==split and split['feasible'] is True


def test_transitive_identity_old_component_float32_and_context_closure():
    rows,x,a=toy();rows[1]['inherited_component']=rows[0]['inherited_component']
    a[2].append(rows[1]['formula']);x[3]=x[2]
    rows[4]['source']=rows[5]['source']='coverage48';rows[4]['context']=rows[5]['context']='context'
    groups=m.build_groups(rows,x,a)
    assert len(set(groups['row_components'][i] for i in (0,1,2,3)))==1
    assert groups['row_components'][4]==groups['row_components'][5]
    assert {'inherited_V5_component','canonical_original_or_saved_accepted_form','exact_float32_selected_vector','new_coverage_context'}<=set(groups['edge_counts'])
    assert len({groups['row_components'][i] for i in range(6,27)})==21 # skeletons are diagnostic, not unioned


def test_commutative_accepted_alias_cross_original_union():
    rows,x,a=toy();rows[0]['formula']='add(in0,in1)';a[0]=['add(in0,in1)'];rows[1]['formula']='add(in1,in0)';a[1]=['add(in1,in0)']
    g=m.build_groups(rows,x,a);assert g['row_components'][0]==g['row_components'][1]
    assert any(e['reason']=='frozen_commutative_key' and e['members']==[0,1] for e in g['edges'])


def test_float32_effective_collisions_and_signed_zero_normalization():
    full=np.zeros((2,336));full[0,0]=2**24;full[1,0]=2**24+1;full[0,1]=-0.0
    x=m.selected_float32(full,np.arange(217));assert x[0].tobytes()==x[1].tobytes()
    rows,_,a=toy(2);g=m.build_groups(rows,x,a)
    assert g['row_components'][0]==g['row_components'][1] and len(g['float32_collision_classes'])==1


def test_saved_accepted_forms_and_rejected_fallback_poison_excluded():
    r={'formula':'add(in0,in1)','normalized_formula':'add(in0,in1)','v7_modes':{
        mode:{'metadata':{'status':'accepted' if mode=='bit' else 'fallback'},'normalized_formula':'add(in1,in0)' if mode=='bit' else 'invalid poison'} for mode in ('bit','affine','combined')}}
    forms,status=m.saved_new_forms(r)
    assert forms==['add(in0,in1)','add(in1,in0)'] and status['affine']=='fallback'


def test_fixed_group_order_greedy_tie_break_and_train_strata():
    rows,x,a=toy(45);g=m.build_groups(rows,x,a);split=m.assign_folds(rows,g)
    assert split==m.assign_folds(rows,m.build_groups(rows,x,a)) and split['feasible'] is True
    counts=[{} for _ in range(5)];totals=[0]*5
    for c in g['components']:
        expected=min(range(5),key=lambda f:(sum(n*counts[f].get(s,0) for s,n in c['strata'].items()),totals[f],f))
        assert split['component_fold'][c['component_id']]==expected
        for s,n in c['strata'].items():counts[expected][s]=counts[expected].get(s,0)+n
        totals[expected]+=c['row_count']
    assert all(f['training_has_all9strata'] for f in split['folds'])


def test_infeasible_grouping_is_reported_not_weakened():
    rows,x,a=toy();
    for r in rows:r['inherited_component']='one giant component'
    g=m.build_groups(rows,x,a);s=m.assign_folds(rows,g)
    assert len(g['components'])==1 and s['feasible'] is False and s['failure_reason']


def test_log_decode_is_inverse_of_mean_not_mean_of_inverses_zero_override():
    encoded=np.array([(np.log1p(0)+np.log1p(8))/2,np.log1p(100)])
    before,points=m.decode(encoded,'log1p',np.array([False,True]))
    assert np.allclose(before,[2,100]) and np.allclose(points,[2,0]) and points[0]!=4
    assert m.decode(np.array([-1,5]),'raw',np.array([False,False]))[1].tolist()==[0,5]


def test_metrics_zeros_positive_denominators_cap_equality_and_underprediction():
    y=np.array([0,32,33,64,65,128,129]);p=np.array([1,32,32,65,64,129,128]);s=np.array(['workload']*7)
    score=m.metrics(y,p,s)['pooled'];assert score['positive_target_count']==6 and score['zero_target_count']==1 and score['zero_mae_lut4']==1
    assert score['caps']['32']['false_accept_count']==1 and score['caps']['64']['false_accept_count']==score['caps']['64']['false_reject_count']==1
    assert score['maximum_underprediction_lut4']==1 and score['p99_absolute_error_lut4']==1
    d=m.paired_decisions(y,p,y);assert d['64']['raw_wrong_log_correct_count']==2 and d['64']['raw_correct_log_wrong_count']==0


@pytest.fixture
def prepared(tmp_path,monkeypatch):
    monkeypatch.setattr(m,'ROOT',tmp_path);rows,x,a=toy(1713);full=np.zeros((1713,336));zero=np.zeros(1713,dtype=bool);zero[0]=True
    source=tmp_path/'synthetic-source.py';source.write_text('# synthetic source')
    audit_source=tmp_path/'scripts/audit_v12_target_transform.py';audit_source.parent.mkdir();audit_source.write_text('# synthetic auditor')
    data=tmp_path/'synthetic-input.json';m.write(data,{'synthetic':True})
    monkeypatch.setattr(m,'source_paths',lambda:[source,audit_source]);monkeypatch.setattr(m,'runtime',lambda:{'synthetic':True,'files':[{'path':str(source),'sha256':m.sha(source)}]})
    monkeypatch.setattr(m,'load_inputs',lambda:(copy.deepcopy(rows),full.copy(),x.copy(),zero.copy(),copy.deepcopy(a),{'synthetic':True},[data]))
    root=tmp_path/'prepared';m.prepare(root)
    return root,source,data


def test_input_prepare_exact1713_matrix_no_fits_and_no_overwrite(prepared):
    root,source,data=prepared;manifest,fitting,x,g,s,b=m.validate(root)
    assert x.shape==(1713,217) and x.dtype==np.dtype('<f4') and manifest['fits_completed']==0 and manifest['maximum_fits']==30
    assert len(manifest['fit_schedule'])==30 and set((f['seed'],f['view'],f['fold']) for f in manifest['fit_schedule'])==set(m.itertools_product())
    with pytest.raises(ValueError,match='Fresh'):m.prepare(root)


@pytest.mark.parametrize('name',['recipe.json','matrix.npy','groups.json','split.json','fitting.json','source','input'])
def test_prepared_mutations_fail_closed(prepared,name):
    root,source,data=prepared;p=source if name=='source' else data if name=='input' else root/name
    p.write_bytes(p.read_bytes()+b'changed')
    with pytest.raises((ValueError,UnicodeDecodeError)):m.validate(root)


class SpyForest:
    calls=[];fail_on=None
    def __init__(self,**params):self.params=params
    def get_params(self,deep=True):return self.params
    def fit(self,x,y):
        assert x.dtype==np.dtype('<f4') and x.shape[1]==217
        self.mean=float(np.mean(y));self.calls.append((self.params.copy(),x.shape,len(y),float(np.min(y)),float(np.max(y))))
        if self.fail_on==len(self.calls):raise RuntimeError('synthetic fit failure')
        return self
    def predict(self,x):return np.full(len(x),self.mean)


def release(root,monkeypatch):
    review=root/'independent-input-audit.json';m.write(review,{'schema':'isaforge-v12-independent-input-audit-v1','status':'pass','preparation_sha256':m.sha(root/'preparation.json'),
        'audit_source_sha256':m.sha(m.ROOT/'scripts/audit_v12_target_transform.py')})
    approval=root/'fit-approval.json';m.write(approval,{'status':'approved-v12-thirty-fit-comparison','preparation_sha256':m.sha(root/'preparation.json'),
        'runner_sha256':m.sha(m.__file__),'reviewed_at_utc':m.now(),'maximum_fits':30,'freeze_commit':'a'*40,'independent_input_audit':m.record(review,root)})
    monkeypatch.setattr(m.subprocess,'check_output',lambda command,**kw:(m.ROOT/command[-1].split(':',1)[1]).read_bytes())
    monkeypatch.setattr(m,'ExtraTreesRegressor',SpyForest);SpyForest.calls=[];SpyForest.fail_on=None
    monkeypatch.setattr(m.v6,'estimator_fingerprint',lambda e:m.digest({'params':e.params,'mean':e.mean}))
    return approval


def test_exact30_spied_fits_same_columns_seeds_and_roundtrips_no31st(prepared,monkeypatch):
    root,_,_=prepared;approval=release(root,monkeypatch);done=m.fit(root,approval)
    assert done['complete'] is True and done['fits_attempted']==done['fits_completed']==len(SpyForest.calls)==30
    assert all(p['n_estimators']==300 and p['criterion']=='squared_error' and p['n_jobs']==1 for p,*_ in SpyForest.calls)
    assert len(list((root/'fit-attempt-0000/models').glob('*.joblib')))==30
    assert len(list((root/'fit-attempt-0000/predictions').glob('*.json')))==6
    for view in m.VIEWS:
        for seed in m.SEEDS:
            ps=m.read(root/'fit-attempt-0000/predictions'/f'{view}-seed-{seed}.json')
            assert len(ps)==1713 and ps[0]['predicted_lut4']==0 and all(p['fold'] in range(5) for p in ps)
    with pytest.raises(ValueError,match='single fit attempt'):m.fit(root,approval)
    assert len(SpyForest.calls)==30


def test_failed_fit_retains_claim_started_receipt_and_no_retry(prepared,monkeypatch):
    root,_,_=prepared;approval=release(root,monkeypatch);SpyForest.fail_on=3
    with pytest.raises(RuntimeError,match='synthetic fit failure'):m.fit(root,approval)
    done=m.read(root/'fit-attempt-0000/completion.json')
    assert done['complete'] is False and done['fits_attempted']==3 and done['fits_completed']==2
    assert (root/'fit-attempt-0000/receipts/03-start.json').is_file() and (root/'fit-claim.json').is_file()
    with pytest.raises(ValueError,match='single fit attempt'):m.fit(root,approval)


def test_runtime_file_mutation_stops_further_fit_slots(prepared,monkeypatch):
    root,source,_=prepared;approval=release(root,monkeypatch)
    original=SpyForest.fit
    def mutate(self,x,y):
        result=original(self,x,y)
        if len(self.calls)==1:source.write_text('runtime/source changed afterfirstfit')
        return result
    monkeypatch.setattr(SpyForest,'fit',mutate)
    with pytest.raises(ValueError,match='changed'):m.fit(root,approval)
    done=m.read(root/'fit-attempt-0000/completion.json')
    assert done['fits_attempted']==done['fits_completed']==1 and len(SpyForest.calls)==1


def test_review_must_follow_preparation_before_any_fit_claim(prepared,monkeypatch):
    root,_,_=prepared;approval=release(root,monkeypatch);value=m.read(approval);value['reviewed_at_utc']='2000-01-01T00:00:00+00:00'
    approval.write_text(json.dumps(value))
    with pytest.raises(ValueError,match='follow preparation'):m.fit(root,approval)
    assert not (root/'fit-claim.json').exists() and not SpyForest.calls
