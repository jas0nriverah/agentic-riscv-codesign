#!/usr/bin/env python3
"""Standard-library V12 saved-point/receipt audit; no model loading or fitting.

This checks saved-point arithmetic and retained receipt/byte provenance. It is
not independent saved-model inference, a replayed training run or fresh transfer.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime,timedelta
import hashlib
import json
import math
from pathlib import Path
import re
import statistics

ROOT=Path(__file__).resolve().parents[1]
SEEDS=(2026101421,2026101422,2026101423)
VIEWS=('raw','log1p')
CAPS=(32,64,128)
STRATA=tuple(sorted(('arithmetic_chain','comparators','constant_shifts','mask_logic','multiplication','parallel_branches','shared_diamond','variable_shifts','workload')))
PARAMETERS={'n_estimators':300,'criterion':'squared_error','min_samples_leaf':1,'max_features':1.0,'n_jobs':1}
FLOAT_ABS_TOLERANCE=1e-12
FLOAT_ULPS=8


def need(value,message):
    if not value:raise ValueError(message)
def sha(data):return hashlib.sha256(data).hexdigest()
def loads(data):
    def unique(items):
        out={}
        for k,v in items:need(k not in out,'Duplicate JSON key');out[k]=v
        return out
    return json.loads(data,object_pairs_hook=unique)
def exact(a,b):
    if type(a) is not type(b):return False
    if type(a) is dict:return set(a)==set(b) and all(exact(a[k],b[k]) for k in a)
    if type(a) is list:return len(a)==len(b) and all(exact(x,y) for x,y in zip(a,b))
    return a==b

def finite(value,nonnegative=True):return type(value) in (int,float) and math.isfinite(value) and (value>=0 or not nonnegative)
def stamp(value):
    need(type(value) is str,'UTC timestamp string required');v=datetime.fromisoformat(value.replace('Z','+00:00'))
    need(v.tzinfo is not None and v.utcoffset()==timedelta(0),'UTC-aware chronology required');return v

def quantile(values,q):
    ordered=sorted(values);h=(len(ordered)-1)*q;lo=math.floor(h);hi=math.ceil(h);fraction=h-lo
    a,b=ordered[lo],ordered[hi]
    return float(a+(b-a)*fraction if fraction<.5 else b-(b-a)*(1-fraction))

def metrics(y,p,strata):
    need(len(y)==len(p)==len(strata)>0 and all(finite(x) for x in y+p),'Complete finite nonnegative scores required')
    def cell(indices):
        truth=[y[i] for i in indices];points=[p[i] for i in indices];n=len(indices);need(n>0,'Nonempty metric cell required')
        errors=[b-a for a,b in zip(truth,points)];ae=[abs(e) for e in errors];positive=[i for i,a in enumerate(truth) if a>0];zeros=[i for i,a in enumerate(truth) if a==0]
        return {'count':n,'mae_lut4':math.fsum(ae)/n,'signed_bias_lut4':math.fsum(errors)/n,
            'rmsle':math.sqrt(math.fsum((math.log1p(b)-math.log1p(a))**2 for a,b in zip(truth,points))/n),
            'positive_target_count':len(positive),'positive_mape_percent':100*math.fsum(ae[i]/truth[i] for i in positive)/len(positive) if positive else None,
            'zero_target_count':len(zeros),'zero_mae_lut4':math.fsum(ae[i] for i in zeros)/len(zeros) if zeros else None,
            'p95_absolute_error_lut4':quantile(ae,.95),'p99_absolute_error_lut4':quantile(ae,.99),
            'worst_absolute_error_lut4':float(max(ae)),'maximum_underprediction_lut4':float(max([0,*(-e for e in errors)])),
            'caps':{str(cap):{'false_accept_count':sum(b<=cap<a for a,b in zip(truth,points)),
                'false_reject_count':sum(a<=cap<b for a,b in zip(truth,points)),
                'actually_feasible_count':sum(a<=cap for a in truth),'actually_infeasible_count':sum(a>cap for a in truth),
                'predicted_feasible_count':sum(b<=cap for b in points),'count':n} for cap in CAPS}}
    by={s:cell([i for i,t in enumerate(strata) if t==s]) for s in sorted(set(strata))}
    return {'pooled':cell(list(range(len(y)))),'by_stratum':by,'macro_stratum_mae_lut4':math.fsum(c['mae_lut4'] for c in by.values())/len(by)}

def decisions(y,raw,log):
    return {str(c):{'raw_accept_log_reject_count':sum(a<=c<b for a,b in zip(raw,log)),
        'raw_reject_log_accept_count':sum(b<=c<a for a,b in zip(raw,log)),
        'raw_correct_log_wrong_count':sum(((a<=c)==(t<=c)) and ((b<=c)!=(t<=c)) for t,a,b in zip(y,raw,log)),
        'raw_wrong_log_correct_count':sum(((a<=c)!=(t<=c)) and ((b<=c)==(t<=c)) for t,a,b in zip(y,raw,log)),
        'count':len(y)} for c in CAPS}


def compare(value,expected,path='',differences=None):
    differences=[] if differences is None else differences
    need(type(value) is type(expected),'JSON type differs at '+path)
    if type(expected) is dict:
        need(set(value)==set(expected),'JSON keys differ at '+path)
        for k in expected:compare(value[k],expected[k],path+'/'+k,differences)
    elif type(expected) is list:
        need(len(value)==len(expected),'JSON length differs at '+path)
        for i,(a,b) in enumerate(zip(value,expected)):compare(a,b,path+'/'+str(i),differences)
    elif type(expected) is float:
        need(math.isfinite(value) and math.isfinite(expected),'Nonfinite score at '+path)
        if value!=expected:
            error=abs(value-expected);limit=max(FLOAT_ABS_TOLERANCE,FLOAT_ULPS*max(math.ulp(value),math.ulp(expected)))
            need(error<=limit,'Score arithmetic differs at '+path);differences.append({'path':path,'saved':value,'recomputed':expected,'absolute_difference':error,'limit':limit})
    else:need(value==expected,'Exact score/count differs at '+path)
    return differences


def verify_points(records,rows,zero,fold_ids,view):
    need(type(records) is list and len(records)==len(rows),'Every OOF row required')
    points=[];decode_differences=[]
    for i,(record,row) in enumerate(zip(records,rows)):
        need(set(record)==set(row)|{'fold','original_zero','encoded_prediction','decoded_before_zero','predicted_lut4'}
            and exact({k:record[k] for k in row},row),'Point whitelist identity/order differs')
        need(type(record['fold']) is int and record['fold']==fold_ids[i] and type(record['original_zero']) is bool and record['original_zero']==zero[i], 'OOF membership/zero override differs')
        encoded,before,point=(record[k] for k in ('encoded_prediction','decoded_before_zero','predicted_lut4'))
        need(all(type(v) is float and finite(v) for v in (encoded,before,point)),'Strict finite nonnegative saved float points required')
        decoded=max(0.0,math.expm1(encoded) if view=='log1p' else encoded)
        limit=4*max(math.ulp(decoded),math.ulp(before))
        need(abs(before-decoded)<=limit,'Wrong inverse transform/ensemble aggregation')
        if before!=decoded:decode_differences.append({'row':i,'absolute_difference':abs(before-decoded),'limit_4ulp':limit})
        need(point==(0.0 if zero[i] else before),'Original-zero override/point differs')
        points.append(point)
    return points,decode_differences


def run(root,*,require_models=False):
    root=Path(root).resolve();snapshots={}
    def data(path):
        path=Path(path).resolve();body=path.read_bytes();digest=sha(body)
        need(path not in snapshots or snapshots[path]==digest,'Input changed during audit');snapshots[path]=digest;return body
    def read(path):return loads(data(path))
    manifest=read(root/'preparation.json');prep_sha=snapshots[root/'preparation.json']
    need(manifest['schema']=='isaforge-v12-target-transform-preparation-v1' and manifest['status']=='prepared-inputs-only'
        and manifest['grouping_feasible'] is True and not (root/'preparation-failure.json').exists(),'Complete frozen input preparation required')
    bindings={}
    for entry in manifest['files']:
        need(set(entry)=={'path','sha256'} and type(entry['path']) is str and not Path(entry['path']).is_absolute(),'Relative preparation binding required')
        path=(root/entry['path']).resolve();need(path.is_relative_to(ROOT) and path not in bindings and sha(data(path))==entry['sha256'],'Prepared bytes/source changed');bindings[path]=entry['sha256']
    approval=read(root/'fit-approval.json');approval_sha=snapshots[root/'fit-approval.json'];claim=read(root/'fit-claim.json')
    need(approval['status']=='approved-v12-thirty-fit-comparison' and approval['preparation_sha256']==prep_sha and exact(approval['maximum_fits'],30)
        and re.fullmatch('[0-9a-f]{40}',approval['freeze_commit']) is not None and approval['runner_sha256']==bindings.get(ROOT/'scripts/develop_v12_target_transform.py'),'Exact thirty-fit release/source required')
    need(exact(claim['maximum_fits'],30) and claim['preparation_sha256']==prep_sha and claim['approval_sha256']==approval_sha
        and stamp(claim['claimed_at_utc'])>=stamp(approval['reviewed_at_utc'])>=stamp(manifest['created_at_utc']),'Fit claim/release chronology differs')
    review_entry=approval['independent_input_audit'];review_path=(root/review_entry['path']).resolve()
    need(review_path.is_relative_to(root) and sha(data(review_path))==review_entry['sha256'],'Independent input review binding differs');review=read(review_path)
    need(review['status']=='pass' and review['preparation_sha256']==prep_sha and review['audit_source_sha256']==bindings.get(ROOT/'scripts/audit_v12_target_transform.py'),'Reviewed input auditor identity differs')
    fitting=read(root/'fitting.json');split=read(root/'split.json');recipe=read(root/'recipe.json');rows=fitting['rows'];zero=fitting['original_zero'];fold_ids=split['fold_ids']
    need(len(rows)==len(zero)==len(fold_ids)==1713 and len({r['formula'] for r in rows})==1713 and set(r['stratum'] for r in rows)==set(STRATA)
        and all(type(z) is bool for z in zero) and all(type(f) is int and f in range(5) for f in fold_ids),'Complete reviewed1713row/fold contract required')
    need(exact(recipe['parameters'],PARAMETERS) and exact(recipe['seeds'],list(SEEDS)) and exact(recipe['target_views'],list(VIEWS))
        and exact(recipe['maximum_fits'],30) and recipe['final_refit'] is False and recipe['smearing'] is False,'Fixed target-scale recipe differs')
    schedule=[{'seed':seed,'view':view,'fold':fold,'fit_index':i+1} for i,(seed,view,fold) in enumerate((s,v,f) for s in SEEDS for v in VIEWS for f in range(5))]
    need(exact(manifest['fit_schedule'],schedule),'Exact fit schedule required')
    out=root/'fit-attempt-0000';done=read(out/'completion.json')
    need(done['schema']=='isaforge-v12-fit-completion-v1' and done['complete'] is True and done['error'] is None
        and all(exact(done[k],30) for k in ('fits_attempted','fits_completed','maximum_fits'))
        and done['preparation_sha256']==prep_sha and done['approval_sha256']==approval_sha and done['runner_sha256']==approval['runner_sha256']
        and all(exact(done[k],0) for k in ('evaluation_target_reads','new_physical_labels','new_feature_extractions','new_solver_queries')),'Complete exact30fit run required')
    names={f'{i:02d}-{suffix}.json' for i in range(1,31) for suffix in ('start','completed')}
    need({p.name for p in (out/'receipts').iterdir()}==names,'Missing/extra fit receipt')
    artifacts=[];previous=stamp(claim['claimed_at_utc']);model_names=set()
    for job in schedule:
        i=job['fit_index'];start=read(out/'receipts'/f'{i:02d}-start.json');end=read(out/'receipts'/f'{i:02d}-completed.json');fold=job['fold']
        training=[j for j,f in enumerate(fold_ids) if f!=fold];validation=[j for j,f in enumerate(fold_ids) if f==fold]
        expected={**job,'parameters':{**PARAMETERS,'random_state':job['seed']},'training_indices':training,'validation_indices':validation,'started_at_utc':start['started_at_utc']}
        need(exact(start,expected) and all(k in end and exact(end[k],v) for k,v in start.items()),'Fit receipt schedule/data/parameters differ')
        need(stamp(start['started_at_utc'])>=previous and stamp(end['completed_at_utc'])>=stamp(start['started_at_utc'])
            and finite(end['elapsed_seconds']) and end['save_load_points_exact'] is True and re.fullmatch('[0-9a-f]{64}',end['estimator_fingerprint']) is not None,'Fit receipt chronology/state differs')
        previous=stamp(end['completed_at_utc']);artifact=end['artifact'];name=f"models/{i:02d}-{job['view']}-seed-{job['seed']}-fold-{fold}.joblib"
        need(artifact['path']==name and re.fullmatch('[0-9a-f]{64}',artifact['sha256']) is not None and type(end['artifact_bytes']) is int and end['artifact_bytes']>0,'Per-fit artifact identity differs')
        model_names.add(Path(name).name);path=out/name;present=path.exists()
        if present:need(sha(data(path))==artifact['sha256'] and path.stat().st_size==end['artifact_bytes'],'Retained model bytes differ from receipt')
        else:need(not require_models,'Required retained model missing')
        artifacts.append({'fit_index':i,'path':name,'sha256':artifact['sha256'],'bytes':end['artifact_bytes'],'present_and_hash_verified':present})
    if (out/'models').exists():need({p.name for p in (out/'models').iterdir()}<=model_names,'Undeclared extra model artifact')
    need(stamp(done['completed_at_utc'])>=previous,'Completion predates last fit')
    expected_names={f'{v}-seed-{s}.json' for s in SEEDS for v in VIEWS}
    for folder in ('predictions','metrics'):need({p.name for p in (out/folder).iterdir()}==expected_names,'Missing/extra saved point/metric view')
    scores={};points={};roundoff=[];decode_roundoff=[];truth=[r['lut4_count'] for r in rows];strata=[r['stratum'] for r in rows]
    for seed in SEEDS:
        for view in VIEWS:
            name=f'{view}-seed-{seed}.json';records=read(out/'predictions'/name)
            point,dr=verify_points(records,rows,zero,fold_ids,view);points[view,seed]=point;decode_roundoff.extend({'view':view,'seed':seed,**d} for d in dr)
            score=metrics(truth,point,strata);scores[view,seed]=score;roundoff.extend(compare(read(out/'metrics'/name),score,'/metrics/'+name))
    differences=[scores['log1p',s]['macro_stratum_mae_lut4']-scores['raw',s]['macro_stratum_mae_lut4'] for s in SEEDS]
    summary=read(out/'summary.json');need(sha(data(out/'summary.json'))==done['summary_sha256'],'Completed summary digest differs')
    expected_summary={'schema':'isaforge-v12-target-transform-comparison-v1','scope':recipe['scope'],'fits_completed':30,
        'primary_log_minus_raw_macro_mae_lut4':{'per_seed':dict(zip(map(str,SEEDS),differences)),'mean':statistics.fmean(differences),'sample_sd_algorithm_seeds':statistics.stdev(differences)},
        'scores':{v:{str(s):scores[v,s] for s in SEEDS} for v in VIEWS},
        'paired_cap_decisions':{str(s):decisions(truth,points['raw',s],points['log1p',s]) for s in SEEDS},
        'promotion':'No automatic promotion or final refit; mean,cap64FA/FR,P99 and maximum-underprediction are separate review endpoints.'}
    roundoff.extend(compare(summary,expected_summary,'/summary'))
    need(all(sha(p.read_bytes())==value for p,value in snapshots.items()),'Evidence mutated during saved-point audit')
    return {'schema':'isaforge-v12-independent-results-audit-v1','status':'pass','complete':True,'preparation_sha256':prep_sha,
        'completion_sha256':snapshots[out/'completion.json'],'audit_source_sha256':sha(Path(__file__).read_bytes()),
        'bound_files_verified':len(bindings),'fit_receipts_verified':30,'saved_point_sets_verified':6,'saved_point_rows_verified':len(rows)*6,
        'primary_recomputed':expected_summary['primary_log_minus_raw_macro_mae_lut4'],'paired_cap_decisions_recomputed':expected_summary['paired_cap_decisions'],
        'artifacts':artifacts,'available_models_hash_verified':sum(a['present_and_hash_verified'] for a in artifacts),'models_not_loaded':True,
        'float_replay_policy':{'score_absolute_tolerance':FLOAT_ABS_TOLERANCE,'score_max_ulps':FLOAT_ULPS,'decode_max_ulps':4,'counts_and_types':'exact'},
        'score_roundoff_differences':roundoff,'decode_libm_roundoff_differences':decode_roundoff,
        'evidence_files':[{'path':str(p.relative_to(ROOT)),'sha256':value} for p,value in sorted(snapshots.items())],
        'independence':'Standard library only; no model loading, sklearn/numpy, native tools, fit or runner-metric imports. Reconstructs all saved-point scores/cap choices and receipt chronology; hashes available model bytes without inference. Not an independent saved-model prediction replay or retraining proof. Fitting-only consumed development, no fresh transfer claim.'}


audit=run
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',type=Path,required=True);parser.add_argument('--output',type=Path);parser.add_argument('--require-models',action='store_true')
    args=parser.parse_args();result=run(args.root,require_models=args.require_models)
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        with args.output.open('x') as stream:json.dump(result,stream,indent=2,allow_nan=False);stream.write('\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('evidence_files','artifacts','score_roundoff_differences','decode_libm_roundoff_differences','paired_cap_decisions_recomputed')},indent=2))
