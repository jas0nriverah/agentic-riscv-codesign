"""Synthetic saved artifacts and inference spies only; never train or run hardware."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import numpy as np
import pytest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('replay_v13_models',ROOT/'scripts/replay_v13_models.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def write(p,value):
    p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(value)+'\n')
def rec(p,root):return {'path':str(p.relative_to(root)),'sha256':m.sha(p)}

class SyntheticForest:
    loads=[]
    def __init__(self,**params):self.params=params;self.offset=0.;self.estimators_=[None]*300;self.n_features_in_=217
    def get_params(self,deep=True):return self.params
    def predict(self,x):return x[:,0].astype(float)*.25+self.offset
    def fit(self,*a,**k):raise AssertionError('No fitting in replay tests')

def fingerprint(model):return hashlib.sha256(json.dumps([model.params,model.offset],sort_keys=True).encode()).hexdigest()

@pytest.fixture
def study(tmp_path,monkeypatch):
    monkeypatch.setattr(m,'ROOT',tmp_path)
    runner=tmp_path/'scripts/develop_v13_coverage.py';runner.parent.mkdir();runner.write_text('SYNTHETIC trainer')
    helper=tmp_path/'isaforge/area_model_v6.py';helper.parent.mkdir();helper.write_text('SYNTHETIC fingerprint')
    root=tmp_path/'study';fit=root/'fitting';attempt=fit/'fit-attempt-0000';fit.mkdir(parents=True)
    rows=[{'formula':f'addi(in0,{i})','cohort':'original1713' if i<1713 else 'coverage48','lut4_count':i%100} for i in range(1761)]
    zero=np.zeros(1761,dtype=bool);zero[0]=True
    write(fit/'fitting.json',{'rows':rows,'original_zero':zero.tolist()})
    matrix=np.zeros((1761,217),dtype='<f4');matrix[:,0]=np.arange(1761)+1;np.save(fit/'matrix.npy',matrix)
    ids=np.arange(1761)%5
    write(fit/'split.json',{'fold_ids':ids.tolist(),'folds':[{'training_indices':np.flatnonzero(ids!=f).tolist(),'control_training_indices':np.flatnonzero((ids!=f)&(np.arange(1761)<1713)).tolist(),'validation_indices':np.flatnonzero(ids==f).tolist()} for f in range(5)]})
    write(fit/'groups.json',{})
    runtime={'python':'SYNTHETIC','packages':{},'files':[]};write(fit/'runtime.json',runtime);monkeypatch.setattr(m,'runtime',lambda:copy.deepcopy(runtime))
    recipe={'seeds':list(m.SEEDS),'views':list(m.VIEWS),'parameters':m.PARAMETERS,'folds':5,'maximum_fits':30,'target_transform':'none','final_refit':False};write(fit/'recipe.json',recipe)
    schedule=[{'fit_index':i+1,'seed':s,'view':v,'fold':f} for i,(s,v,f) in enumerate((s,v,f) for s in m.SEEDS for v in m.VIEWS for f in range(5))]
    paths=[fit/n for n in ('fitting.json','matrix.npy','groups.json','split.json','runtime.json','recipe.json')]
    prep={'schema':'isaforge-v13-matched-coverage-preparation-v1','status':'prepared-inputs-only','rows':1761,'old_rows':1713,'new_rows':48,'selected_columns':217,'fit_schedule':schedule,
          'files':[{'path':str(p.relative_to(fit)) if p.is_relative_to(fit) else str(Path('..')/'..'/p.relative_to(tmp_path)),'sha256':m.sha(p)} for p in [*paths,runner,helper]]}
    # fit is tmp/study/fitting, external sources use ../../scripts and ../../isaforge.
    write(fit/'preparation.json',prep)
    approval={'status':'approved-v13-thirty-matched-coverage-fits','preparation_sha256':m.sha(fit/'preparation.json'),'runner_sha256':m.sha(runner),'maximum_fits':30}
    write(fit/'fit-approval.json',approval);write(fit/'fit-claim.json',{'maximum_fits':30,'approval_sha256':m.sha(fit/'fit-approval.json'),'preparation_sha256':m.sha(fit/'preparation.json')})
    for seed in m.SEEDS:
        for view in m.VIEWS:
            encoded=matrix[:,0].astype(float)*.25+(1 if view=='augmented' else 0);before=np.maximum(encoded,0);points=before.copy();points[zero]=0
            write(attempt/'predictions'/f'{view}-seed-{seed}.json',[{**row,'fold':int(ids[i]),'original_zero':bool(zero[i]),'encoded_prediction':float(encoded[i]),'decoded_before_zero':float(before[i]),'predicted_lut4':float(points[i])} for i,row in enumerate(rows)])
    for job in schedule:
        i,view,seed,fold=(job[k] for k in ('fit_index','view','seed','fold'));model=SyntheticForest(**m.PARAMETERS,random_state=seed);model.offset=1 if view=='augmented' else 0
        path=attempt/'models'/f'{i:02d}-{view}-seed-{seed}-fold-{fold}.joblib';write(path,{'params':model.params,'offset':model.offset})
        start={**job,'parameters':model.params,'training_indices':np.flatnonzero((ids!=fold)&((np.arange(1761)<1713) if view=='control' else True)).tolist(),'validation_indices':np.flatnonzero(ids==fold).tolist()}
        write(attempt/'receipts'/f'{i:02d}-start.json',start)
        write(attempt/'receipts'/f'{i:02d}-completed.json',{**start,'save_load_points_exact':True,'artifact':rec(path,attempt),'artifact_bytes':path.stat().st_size,'estimator_fingerprint':fingerprint(model)})
    write(attempt/'summary.json',{'SYNTHETIC':True})
    write(attempt/'completion.json',{'schema':'isaforge-v13-matched-fit-completion-v1','complete':True,'error':None,'fits_attempted':30,'fits_completed':30,'maximum_fits':30,'preparation_sha256':m.sha(fit/'preparation.json'),
          'summary_sha256':m.sha(attempt/'summary.json'),'approval_sha256':m.sha(fit/'fit-approval.json'),'runner_sha256':m.sha(runner)})
    SyntheticForest.loads=[]
    def load(path):
        value=m.read(path);model=SyntheticForest(**value['params']);model.offset=value['offset'];SyntheticForest.loads.append(str(path));return model
    monkeypatch.setattr(m,'ExtraTreesRegressor',SyntheticForest);monkeypatch.setattr(m,'estimator_fingerprint',fingerprint);monkeypatch.setattr(m.joblib,'load',load)
    return root,fit,attempt

def test_complete30_models_replay10566_points_without_fit(study):
    root,fit,attempt=study;r=m.run(root)
    assert r['models_loaded']==len(SyntheticForest.loads)==30 and r['heldout_points_compared']==10566
    assert r['all_row_coverage_exactly_once'] and r['new_fits']==0 and r['points_per_seed_view']==1761
    assert r['original_rows_per_seed_view']==1713 and r['coverage_rows_per_seed_view']==48

def test_incomplete_stops_before_model_load(study):
    root,fit,a=study;p=a/'completion.json';v=m.read(p);v['complete']=False;write(p,v)
    with pytest.raises(ValueError,match='Complete exact30'):m.run(root)
    assert not SyntheticForest.loads

@pytest.mark.parametrize('poison',['missing','bytes','training','fingerprint','params','forecast','zero','extra_model','extra_receipt'])
def test_adversarial_saved_evidence(study,poison):
    root,fit,a=study;p=a/'receipts/01-completed.json';receipt=m.read(p);artifact=a/receipt['artifact']['path']
    if poison=='missing':artifact.unlink()
    elif poison=='bytes':artifact.write_bytes(b'wrong')
    elif poison in ('training','fingerprint','params'):
        if poison=='training':receipt['training_indices'].append(1713)
        elif poison=='fingerprint':receipt['estimator_fingerprint']='f'*64
        else:receipt['parameters']['random_state']+=1
        write(p,receipt)
    elif poison in ('forecast','zero'):
        p=a/'predictions'/f'control-seed-{m.SEEDS[0]}.json';v=m.read(p);v[0 if poison=='zero' else 2]['predicted_lut4']+=1;write(p,v)
    elif poison=='extra_model':(a/'models/extra.joblib').write_bytes(b'extra')
    else:write(a/'receipts/extra.json',{})
    with pytest.raises(ValueError):m.run(root)

@pytest.mark.parametrize('encoded,zero,expected', [([-2,3],[False,False],[0,3]),([2,3],[True,False],[0,3])])
def test_raw_decode_and_zero(encoded,zero,expected):
    before,points=m.decoded_points(encoded,'control',np.asarray(zero));assert points.tolist()==expected

def test_no_fit_guard_restores_method():
    original=m.ExtraTreesRegressor.fit
    with m.no_fitting():
        with pytest.raises(RuntimeError,match='never fit'):m.ExtraTreesRegressor().fit([],[])
    assert m.ExtraTreesRegressor.fit is original
