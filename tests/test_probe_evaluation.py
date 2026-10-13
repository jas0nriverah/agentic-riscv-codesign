import pytest
from isaforge.probe_evaluation import score_probe


def example():
    candidates=[dict(benchmark='probe',candidate_id=str(i),formula=f'addi(in0,{i})',stratum='arithmetic') for i in [1,2]]
    measured=[dict(r,lut4_count=y,correctness_verified=True,measurement_source='rtl_synthesis') for r,y in zip(candidates,[0,10])]
    pred=[dict(r,predicted_lut4=p) for r,p in zip(candidates,[2,12])]
    return candidates,measured,{'model':pred}


def test_zero_targets_reported_separately_from_percentage_error():
    c,m,p=example(); result=score_probe([],c,m,p)['models']['model']['pooled']
    assert result['mae_lut4']==2
    assert result['positive_mape_percent']==20
    assert result['positive_mape_count']==1
    assert result['zero_target_mae_lut4']==2


@pytest.mark.parametrize('problem',['missing','duplicate','formula','unverified','negative','overlap'])
def test_probe_refuses_invalid_or_leaky_comparisons(problem):
    c,m,p=example();training=[]
    if problem=='missing':p['model'].pop()
    if problem=='duplicate':p['model'].append(p['model'][0])
    if problem=='formula':p['model'][0]['formula']='in0'
    if problem=='unverified':m[0]['correctness_verified']=False
    if problem=='negative':p['model'][0]['predicted_lut4']=-1
    if problem=='overlap':training=[c[0]]
    with pytest.raises(ValueError):score_probe(training,c,m,p)


def frozen_record(tmp_path):
    import hashlib,json
    from pathlib import Path
    from datetime import datetime,timezone
    from isaforge.area_model import _validated_rows
    from isaforge.probe_evaluation import validate_model_freezes
    row={'benchmark':'old','candidate_id':'old-id','formula':'xor(in0,in1)','lut4_count':32,'measurement_source':'rtl_synthesis'}
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    artifact=tmp_path/'model.joblib';artifact.write_bytes(b'test artifact; never unpickled')
    artifact.with_suffix('.json').write_text(json.dumps({'artifact_sha256':sha(artifact),'training_formula_count':1}))
    pred=tmp_path/'prediction.json';pred.write_text('[]')
    pred.with_suffix('.timing.json').write_text(json.dumps({'model_sha256':sha(artifact),'candidate_sha256':'candidate-digest'}))
    source=Path(__import__('isaforge.probe_evaluation',fromlist=['__file__']).__file__)
    record={'frozen_at_utc':datetime.now(timezone.utc).isoformat(),'training_dataset_sha256':hashlib.sha256(json.dumps(_validated_rows([row]),sort_keys=True,separators=(',',':')).encode()).hexdigest(),
            'unique_formula_count':1,'runtime_source_sha256':{source.name:sha(source)},'artifacts':{'model':{'model_path':str(artifact),'artifact_sha256':sha(artifact)}}}
    path=tmp_path/'freeze.json';path.write_text(json.dumps(record))
    return [row],path,{'model':pred},record,artifact


def test_release_gate_validates_every_frozen_comparator(tmp_path):
    from isaforge.probe_evaluation import validate_model_freezes
    rows,path,preds,record,artifact=frozen_record(tmp_path)
    assert len(validate_model_freezes(rows,[path],preds,'candidate-digest'))==1


@pytest.mark.parametrize('tamper',['timestamp','dataset','artifact','source','missing_model','sidecar'])
def test_release_gate_rejects_mismatched_freezes(tmp_path,tamper):
    import json
    from isaforge.probe_evaluation import validate_model_freezes
    rows,path,preds,record,artifact=frozen_record(tmp_path)
    if tamper=='timestamp':record.pop('frozen_at_utc')
    if tamper=='dataset':record['training_dataset_sha256']='different'
    if tamper=='artifact':artifact.write_bytes(b'changed')
    if tamper=='source':record['runtime_source_sha256']['probe_evaluation.py']='different'
    if tamper=='missing_model':preds={}
    if tamper=='sidecar':next(iter(preds.values())).with_suffix('.timing.json').write_text('{}')
    path.write_text(json.dumps(record))
    with pytest.raises(ValueError):validate_model_freezes(rows,[path],preds,'candidate-digest')
