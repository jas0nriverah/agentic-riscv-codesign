"""Saved-point/receipt tests; synthetic byte artifacts, no fitting or model import."""
import ast
import copy
import importlib.util
import json
import math
from pathlib import Path
import sys
import pytest

SOURCE=Path(__file__).resolve().parents[1]/'scripts/audit_v12_results.py'
spec=importlib.util.spec_from_file_location('audit_v12_results',SOURCE);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,allow_nan=False)+'\n');return m.sha(path.read_bytes())


def test_metrics_known_errors_and_exact_boundary_caps():
    value=m.metrics([0,32,65,128],[10.,33.,64.,128.],['a']*4)['pooled']
    assert value['mae_lut4']==3.0 and value['signed_bias_lut4']==2.5
    assert value['zero_mae_lut4']==10.0 and value['maximum_underprediction_lut4']==1.0
    assert value['caps']['32']['false_reject_count']==1
    assert value['caps']['64']['false_accept_count']==1
    assert value['caps']['128']['false_accept_count']==value['caps']['128']['false_reject_count']==0
    assert m.quantile([0,1,2,3],.95)==pytest.approx(2.85)
    assert m.decisions([65],[64.],[66.])['64']=={'raw_accept_log_reject_count':1,'raw_reject_log_accept_count':0,'raw_correct_log_wrong_count':0,'raw_wrong_log_correct_count':1,'count':1}


@pytest.mark.parametrize('bad',[True,float('nan'),float('inf'),-1])
def test_bad_targets_and_predictions_fail(bad):
    with pytest.raises(ValueError):m.metrics([1],[bad],['a'])


def test_points_inverse_zero_order_and_type_contract():
    rows=[{'formula':'synthetic','stratum':'a','lut4_count':0}]
    point={**rows[0],'fold':0,'original_zero':True,'encoded_prediction':math.log1p(10.),'decoded_before_zero':10.,'predicted_lut4':0.}
    assert m.verify_points([point],rows,[True],[0],'log1p')[0]==[0.]
    for key,value in [('decoded_before_zero',9.),('predicted_lut4',10.),('fold',True),('encoded_prediction',True),('target_poison',123),('formula','another')]:
        bad={**point,key:value}
        with pytest.raises(ValueError):m.verify_points([bad],rows,[True],[0],'log1p')


def test_metric_comparison_records_only_bounded_roundoff():
    diffs=m.compare({'mae':1.+math.ulp(1.)},{'mae':1.})
    assert len(diffs)==1 and diffs[0]['path']=='/mae'
    for v in [1,True,1.0001,float('nan')]:
        with pytest.raises(ValueError):m.compare({'mae':v},{'mae':1.})
    with pytest.raises(ValueError):m.loads('{"count":1,"count":2}')


@pytest.fixture
def prepared(tmp_path,monkeypatch):
    monkeypatch.setattr(m,'ROOT',tmp_path)
    root=tmp_path/'results'/'SYNTHETIC';out=root/'fit-attempt-0000'
    root.mkdir(parents=True)
    runner=tmp_path/'scripts/develop_v12_target_transform.py';runner.parent.mkdir();runner.write_text('# SYNTHETIC ONLY\n')
    input_audit=tmp_path/'scripts/audit_v12_target_transform.py';input_audit.write_text('# SYNTHETIC ONLY\n')
    rows=[{'formula':f'SYNTHETIC_{i}','stratum':m.STRATA[i%9],'lut4_count':i%150} for i in range(1713)]
    zero=[i%150==0 for i in range(1713)];folds=[i%5 for i in range(1713)]
    recipe={'parameters':m.PARAMETERS,'seeds':list(m.SEEDS),'target_views':list(m.VIEWS),'maximum_fits':30,'final_refit':False,'smearing':False,'scope':'SYNTHETIC fixture only'}
    write(root/'fitting.json',{'rows':rows,'original_zero':zero});write(root/'split.json',{'fold_ids':folds});write(root/'recipe.json',recipe)
    schedule=[{'seed':s,'view':v,'fold':f,'fit_index':i+1} for i,(s,v,f) in enumerate((s,v,f) for s in m.SEEDS for v in m.VIEWS for f in range(5))]
    files=[{'path':str(p.relative_to(root)) if p.is_relative_to(root) else '../../'+str(p.relative_to(tmp_path)),'sha256':m.sha(p.read_bytes())} for p in [runner,input_audit,root/'fitting.json',root/'split.json',root/'recipe.json']]
    prep=write(root/'preparation.json',{'schema':'isaforge-v12-target-transform-preparation-v1','status':'prepared-inputs-only','grouping_feasible':True,'created_at_utc':'2026-01-01T00:00:00Z','files':files,'fit_schedule':schedule})
    review=write(root/'review.json',{'status':'pass','preparation_sha256':prep,'audit_source_sha256':m.sha(input_audit.read_bytes())})
    approval=write(root/'fit-approval.json',{'status':'approved-v12-thirty-fit-comparison','preparation_sha256':prep,'runner_sha256':m.sha(runner.read_bytes()),'maximum_fits':30,'freeze_commit':'a'*40,'reviewed_at_utc':'2026-01-01T00:00:01Z','independent_input_audit':{'path':'review.json','sha256':review}})
    write(root/'fit-claim.json',{'maximum_fits':30,'preparation_sha256':prep,'approval_sha256':approval,'claimed_at_utc':'2026-01-01T00:00:02Z'})
    for j in schedule:
        i=j['fit_index'];start={**j,'parameters':{**m.PARAMETERS,'random_state':j['seed']},'training_indices':[k for k,f in enumerate(folds) if f!=j['fold']],'validation_indices':[k for k,f in enumerate(folds) if f==j['fold']],'started_at_utc':f'2026-01-01T00:{i:02d}:00Z'}
        write(out/'receipts'/f'{i:02d}-start.json',start)
        name=f"models/{i:02d}-{j['view']}-seed-{j['seed']}-fold-{j['fold']}.joblib";model=out/name;model.parent.mkdir(exist_ok=True);model.write_bytes(b'SYNTHETIC NOT A MODEL')
        write(out/'receipts'/f'{i:02d}-completed.json',{**start,'completed_at_utc':f'2026-01-01T00:{i:02d}:01Z','elapsed_seconds':1.,'estimator_fingerprint':'b'*64,'artifact':{'path':name,'sha256':m.sha(model.read_bytes())},'artifact_bytes':model.stat().st_size,'save_load_points_exact':True})
    truth=[r['lut4_count'] for r in rows];strata=[r['stratum'] for r in rows];scores={v:{} for v in m.VIEWS};points={}
    for s in m.SEEDS:
        for v in m.VIEWS:
            records=[]
            for i,r in enumerate(rows):
                encoded=float(r['lut4_count']+2) if v=='raw' else math.log1p(r['lut4_count']+1)
                before=encoded if v=='raw' else math.expm1(encoded)
                records.append({**r,'fold':folds[i],'original_zero':zero[i],'encoded_prediction':encoded,'decoded_before_zero':before,'predicted_lut4':0. if zero[i] else before})
            name=f'{v}-seed-{s}.json';write(out/'predictions'/name,records);p=[r['predicted_lut4'] for r in records];points[v,s]=p
            scores[v][str(s)]=m.metrics(truth,p,strata);write(out/'metrics'/name,scores[v][str(s)])
    differences=[scores['log1p'][str(s)]['macro_stratum_mae_lut4']-scores['raw'][str(s)]['macro_stratum_mae_lut4'] for s in m.SEEDS]
    summary={'schema':'isaforge-v12-target-transform-comparison-v1','scope':recipe['scope'],'fits_completed':30,'primary_log_minus_raw_macro_mae_lut4':{'per_seed':dict(zip(map(str,m.SEEDS),differences)),'mean':m.statistics.fmean(differences),'sample_sd_algorithm_seeds':m.statistics.stdev(differences)},'scores':scores,'paired_cap_decisions':{str(s):m.decisions(truth,points['raw',s],points['log1p',s]) for s in m.SEEDS},'promotion':'No automatic promotion or final refit; mean,cap64FA/FR,P99 and maximum-underprediction are separate review endpoints.'}
    summary_sha=write(out/'summary.json',summary)
    write(out/'completion.json',{'schema':'isaforge-v12-fit-completion-v1','complete':True,'error':None,'fits_attempted':30,'fits_completed':30,'maximum_fits':30,'preparation_sha256':prep,'approval_sha256':approval,'runner_sha256':m.sha(runner.read_bytes()),'summary_sha256':summary_sha,'completed_at_utc':'2026-01-01T01:00:00Z','evaluation_target_reads':0,'new_physical_labels':0,'new_feature_extractions':0,'new_solver_queries':0})
    return root


def test_full_synthetic_receipts_saved_points_and_optional_models(prepared):
    result=m.run(prepared,require_models=True)
    assert result['saved_point_rows_verified']==10278 and result['fit_receipts_verified']==30
    assert result['available_models_hash_verified']==30 and result['models_not_loaded'] is True
    next((prepared/'fit-attempt-0000/models').iterdir()).unlink()
    assert m.run(prepared)['available_models_hash_verified']==29
    with pytest.raises(ValueError,match='model missing'):m.run(prepared,require_models=True)


@pytest.mark.parametrize('poison',['receipt_missing','overlap','chronology','model','point','metric_count','extra_points','completion_bool','review','summary_reauthenticated'])
def test_contract_corruptions_fail_closed(prepared,poison):
    out=prepared/'fit-attempt-0000'
    if poison=='receipt_missing':(out/'receipts/01-start.json').unlink()
    elif poison in ('overlap','chronology'):
        p=out/'receipts/01-start.json';v=json.loads(p.read_text())
        if poison=='overlap':v['training_indices'].append(v['validation_indices'][0])
        else:v['started_at_utc']='2025-01-01T00:00:00Z'
        write(p,v)
        end=out/'receipts/01-completed.json';completed=json.loads(end.read_text())
        completed.update({k:v[k] for k in ('training_indices','started_at_utc')})
        write(end,completed)
    elif poison=='model':next((out/'models').iterdir()).write_bytes(b'POISON')
    elif poison=='point':
        p=out/f'predictions/raw-seed-{m.SEEDS[0]}.json';v=json.loads(p.read_text());v[1]['predicted_lut4']+=1.;write(p,v)
    elif poison=='metric_count':
        p=out/f'metrics/raw-seed-{m.SEEDS[0]}.json';v=json.loads(p.read_text());v['pooled']['caps']['64']['false_accept_count']+=1;write(p,v)
    elif poison=='extra_points':write(out/'predictions/extra.json',[])
    elif poison=='completion_bool':
        p=out/'completion.json';v=json.loads(p.read_text());v['fits_completed']=True;write(p,v)
    elif poison=='review':write(prepared/'review.json',{'status':'pass','POISON':True})
    elif poison=='summary_reauthenticated':
        p=out/'summary.json';v=json.loads(p.read_text());v['paired_cap_decisions'][str(m.SEEDS[0])]['64']['raw_correct_log_wrong_count']+=1;digest=write(p,v)
        p=out/'completion.json';v=json.loads(p.read_text());v['summary_sha256']=digest;write(p,v)
    with pytest.raises(ValueError):m.run(prepared)


def test_only_standard_library_imports_and_no_execution_api():
    tree=ast.parse(SOURCE.read_text());names=[]
    for n in ast.walk(tree):
        if isinstance(n,ast.Import):names.extend(v.name.split('.')[0] for v in n.names)
        elif isinstance(n,ast.ImportFrom):names.append((n.module or '').split('.')[0])
    assert set(names)<=set(sys.stdlib_module_names)|{'__future__'}
    assert not set(names)&{'subprocess','pickle','joblib','numpy','sklearn','os'}
