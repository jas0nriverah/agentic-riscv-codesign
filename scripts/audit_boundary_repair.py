#!/usr/bin/env python3
"""Independent zero-fit median boundary repair audit; no fits or native jobs.

Reconstructs old frozen forests, original-AST routes, exact even-n median,
all ordered points, separate cap events, finite-vector targets and LUT recounts.
"""
from __future__ import annotations
import argparse
from collections import Counter
import itertools
import json
import math
from pathlib import Path
import random
import subprocess
import sys
import zipfile
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
import audit_budget_release as prior
import audit_targeted_coverage as old
read,sha,digest,now=old.read,old.sha,old.digest,old.now
OUT=ROOT/'results/boundary-repair'
TEST=ROOT/'results/boundary-repair-validation'
CAPS=(32,64,128)
CURRENT='incumbent_signed'
RELEASE='budget_release_compound_only'
CANDIDATE='boundary_median'
NAMES=('base',CURRENT,RELEASE,CANDIDATE)
COUNTS={**prior.COUNTS,'consumed-fifth-fresh40':40}
TOL=1e-10


def check_bindings(mapping,root=ROOT):
    for name,value in mapping.items():assert sha(root/name)==value,name


def preserved():
    snap=read(OUT/'auditor-prior-artifacts.json');check_bindings(snap['files'])
    assert subprocess.check_output(['git','submodule','status'],cwd=ROOT).decode().splitlines()==snap['submodules']
    return len(snap['files'])


def receipt(path,body,write=False):
    body={'schema':'independent-boundary-repair-'+path.stem+'-v1','status':'pass','audited_at_utc':now(),**body,'audit_fits':0,'audit_native_jobs':0}
    if write:
        with path.open('x') as f:json.dump(body,f,indent=2,allow_nan=False);f.write('\n')
    else:
        saved=read(path);computed=dict(body)
        for value in (saved,computed):value.pop('audited_at_utc',None)
        assert saved==computed,'Read-only receipt mismatch:'+str(path)
    return body


def identity_audit():
    history=set(read(TEST/'historical-formulas.json'));required=set(read(ROOT/'results/budget-release-data/historical-formulas.json'));aliases=set()
    folders=('selection-validation','targeted-coverage-data','targeted-coverage-validation','budget-preserving-validation','guarded-revision-data','guarded-revision-validation','signed-refinement-data','signed-refinement-validation','budget-release-data','budget-release-validation')
    for name in folders:
        folder=ROOT/'results'/name;required.update(r['formula'] for r in read(folder/'candidates.json'))
        for row in read(folder/'novelty.json')['comparisons']:aliases.update(row['forms'])
    assert required<=history,'Historical inventory omission'
    known=set().union(*(prior.identity_keys(f) for f in history|aliases));seen=set();old_skeletons={old.skeleton(f) for f in history}
    rows=read(TEST/'candidates.json');report=read(TEST/'novelty.json');assert len(rows)==40 and report['status']=='pass'
    assert [r['candidate_id'] for r in report['comparisons']]==[r['candidate_id'] for r in rows]
    for row,evidence in zip(rows,report['comparisons']):
        forms={row['formula'],*evidence['forms']};keys=set().union(*(prior.identity_keys(f) for f in forms))
        assert not keys&known and not keys&seen,row['candidate_id'];seen.update(keys)
        assert old.skeleton(row['formula']) not in old_skeletons,row['candidate_id']
    assert len({r['formula'] for r in rows})==len({r['candidate_id'] for r in rows})==40
    return {'historical_formulas':len(history),'saved_prior_aliases':len(aliases),'known_identity_keys':len(known),'known_or_within_identity_overlaps':0,'historical_original_AST_skeleton_overlaps':0,'fresh_count':40,'templates':dict(Counter(r['template'] for r in rows))}


def panel_sources():
    result=prior.panel_sources();rows=read(ROOT/'results/budget-release-validation/candidates.json');labels=read(ROOT/'results/budget-release-validation/labels.json')
    result['consumed-fifth-fresh40']=({'candidate_ids':[r['candidate_id'] for r in rows],'formulas':[r['formula'] for r in rows],'actual_lut4':[r['lut4'] for r in labels]},read(ROOT/'results/budget-release-validation/features.json'))
    return result


_WEIGHTS=None


def points(rows,features):
    global _WEIGHTS
    import numpy as np
    if _WEIGHTS is None:_WEIGHTS=prior.models()
    oldprotocol,b,c,i,current=_WEIGHTS
    assert [r['formula'] for r in features['records']]==rows['formulas']
    oldpoints=prior.compute_points(rows,features,oldprotocol,b,c,i,current)
    columns=oldprotocol['selected_columns'];x=np.asarray([r['values'] for r in features['records']],dtype=float)[:,[features['columns'].index(n) for n in columns]]
    assert len(c.estimator.estimators_)==300
    trees=np.asarray([tree.predict(x) for tree in c.estimator.estimators_]);ordered=np.sort(trees,axis=0)
    medians=((ordered[149]+ordered[150])/2).tolist()
    routes=[{'compound':a,'add_boolean':b,'new_coverage':a or b} for a,b,_ in map(prior.predicates,rows['formulas'])]
    signed=oldpoints[CURRENT];released=oldpoints[RELEASE];result=[];limits=[]
    for inc,rel,median,route in zip(signed,released,medians,routes):
        caps=[cap for cap in CAPS if route['compound'] and inc<=cap<rel and median<=cap]
        result.append(min(caps) if caps else rel);limits.append(caps)
    assert all(inc<=p<=rel for inc,p,rel in zip(signed,result,released))
    details={'forest_medians_lut4':medians,'qualifying_caps_lut4':limits,'tree_predictions_above_cap':{str(cap):np.sum(trees>cap,axis=0).tolist() for cap in CAPS}}
    return {'base':oldpoints['base'],CURRENT:signed,RELEASE:released,CANDIDATE:result},routes,details


def metrics(y,models):return {n:prior.metrics(y,p) for n,p in models.items()}


def accuracy(reference,candidate,strict=False):
    return {k:bool(candidate[k]<reference[k]-TOL if strict else candidate[k]<=reference[k]+TOL) for k in ('mae_lut4','positive_mape_percent')}


def cap_no_worse(reference,candidate,kind):return {str(c):candidate['caps'][str(c)][kind]<=reference['caps'][str(c)][kind] for c in CAPS}



def panel_metrics(y,models):
    m=metrics(y,models);c=m[CANDIDATE];signed=m[CURRENT];release=m[RELEASE]
    m['checks']={'accuracy_no_worse_release':accuracy(release,c),
        'caps':{str(cap):{'false_accept_no_worse_release':c['caps'][str(cap)]['false_accept']<=release['caps'][str(cap)]['false_accept'],'false_reject_no_worse_signed':c['caps'][str(cap)]['false_reject']<=signed['caps'][str(cap)]['false_reject']} for cap in CAPS},
        'maximum_underprediction_no_worse_release':c['maximum_underprediction_lut4']<=release['maximum_underprediction_lut4']+TOL,
        'maximum_underprediction_no_worse_signed':c['maximum_underprediction_lut4']<=signed['maximum_underprediction_lut4']+TOL,
        'pointwise_between_signed_and_release':all(a<=b<=c for a,b,c in zip(models[CURRENT],models[CANDIDATE],models[RELEASE])),
        'events_vs_signed':prior.cap_events(models[CURRENT],models[CANDIDATE],y),
        'events_vs_release':prior.cap_events(models[RELEASE],models[CANDIDATE],y)}
    return m


def passed(checks):
    return all(checks['accuracy_no_worse_release'].values()) and all(all(v.values()) for v in checks['caps'].values()) and checks['maximum_underprediction_no_worse_release'] and checks['maximum_underprediction_no_worse_signed'] and checks['pointwise_between_signed_and_release']


def raw_audit(folder):
    rows=read(folder/'candidates.json');labels=read(folder/'labels.json');features=read(folder/'features.json')
    assert len(rows)==len(labels) and [r['candidate_id'] for r in rows]==[r['candidate_id'] for r in labels]
    manifest=read(folder/'raw-evidence-manifest.json');archive=folder/manifest['archive']
    assert sha(archive)==manifest['archive_sha256'];members={r['path']:r for r in manifest['files']}
    with zipfile.ZipFile(archive) as z:
        assert len(z.namelist())==len(set(z.namelist())) and set(z.namelist())==set(members)
        for name,row in members.items():
            body=z.read(name);assert digest(body)==row['sha256'] and len(body)==row['bytes']
        get=lambda n:z.read('raw/'+n)
        kind='test'
        feature_jobs=[j for j in read(TEST/'feature-completion.json')['native_worker_jobs'] if j['kind']==kind]
        label_jobs=read(folder/'completion.json')['native_worker_jobs']
        for job in feature_jobs+label_jobs:
            phase=job['stage'];directory='verification' if phase=='verify' else phase+'s/'+str(job['index'])
            assert json.loads(get(directory+'/worker.json'))==job
            assert digest(get(directory+'/worker.log'))==job['log_sha256']
        proof=json.loads(get('verification/result.json'));vectors=get('verification/vectors.txt');rtl=get('verification/verification.v').decode()
        assert proof['verified'] and proof['formula_count']==len(rows) and proof['vectors_per_formula']==2148
        assert proof['random_seed']==read(TEST/'plan.json')['proof_random_seed']
        assert digest(vectors)==proof['vectors_sha256'] and digest(rtl.encode())==proof['rtl_sha256']
        assert proof['total_comparisons']==2148*len(rows)
        boundary=[0,1,2,31,32,33,0x7fffffff,0x80000000,0x80000001,2**32-1];rng=random.Random(proof['random_seed'])
        expected=list(itertools.product(boundary,repeat=2))+[(rng.getrandbits(32),rng.getrandbits(32)) for _ in range(2048)]
        parsed=[[int(t,16) for t in line.split()] for line in vectors.decode().splitlines()]
        assert len(parsed)==2148 and [(r[0],r[1]) for r in parsed]==expected
        trees=[old.parse(r['formula']) for r in rows]
        for a,b,*targets in parsed:assert [old.evaluate(t,a,b) for t in trees]==targets
        assert get('verification/verification.log').decode().strip()=='2148 vectors passed'
        for i,(row,label) in enumerate(zip(rows,labels)):
            assert label['status']=='complete' and label['formula']==row['formula']
            assert json.loads(get(f'labels/{i}/result.json'))==label
            net=get(f'labels/{i}/ice40-netlist.json');assert digest(net)==label['netlist_sha256']
            counts=Counter(c['type'] for c in json.loads(net)['modules']['candidate']['cells'].values())
            assert counts['SB_LUT4']==label['lut4'] and counts['SB_CARRY']==label['carry']
            source=get(f'labels/{i}/candidate.v').decode();assert digest(source.encode())==label['rtl_sha256']
            assert source.replace('module candidate(',f'module candidate_{i}(') in rtl
            body=get(f'labels/{i}/metrics.json');assert digest(body)==label['metrics_sha256']
            m=json.loads(body);assert m['ice40_lut4_count']==label['lut4'] and m['ice40_carry_count']==label['carry'] and m['measurement_source']=='rtl_synthesis'
            assert 'synth_ice40 -top candidate' in get(f'labels/{i}/ice40.ys').decode()
            assert json.loads(get(f'features/{i}/result.json'))==features['records'][i]
    return {'archive_sha256':sha(archive),'members_hashed':len(members),'mapped_netlists_recounted':len(rows),'independent_RV32_vector_comparisons':2148*len(rows),'native_job_records_and_logs_authenticated':len(feature_jobs)+len(label_jobs)}



def feature_collisions():
    import numpy as np
    columns=read(ROOT/'results/budget-release/protocol.json')['selected_columns'];oldcols=read(ROOT/'results/feature-comparison/columns.json')
    with np.load(ROOT/'results/feature-comparison/inputs.npz',allow_pickle=False) as data:known={tuple(r) for r in data['x'][:,[oldcols.index(n) for n in columns]]}
    for name in ('selection-validation','targeted-coverage-data','targeted-coverage-validation','budget-preserving-validation','guarded-revision-data','guarded-revision-validation','signed-refinement-data','signed-refinement-validation','budget-release-data','budget-release-validation'):
        payload=read(ROOT/'results'/name/'features.json');matrix=np.asarray([r['values'] for r in payload['records']])[:,[payload['columns'].index(n) for n in columns]];known.update(tuple(r) for r in matrix)
    f=read(TEST/'features.json');matrix=np.asarray([r['values'] for r in f['records']])[:,[f['columns'].index(n) for n in columns]]
    assert matrix.shape==(40,217) and np.isfinite(matrix).all() and (matrix>=0).all()
    return {'prior217_feature_rows_known':len(known),'fresh217_unique':len({tuple(r) for r in matrix}),'fresh_rows_with_prior217_collision':sum(tuple(r) in known for r in matrix),'scope':'Feature equality reported separately from formula and known semantic identity.'}


def chronology(final=False):
    features=read(TEST/'feature-completion.json');reports=[features]
    assert old.job_audit(features)['jobs']==40 and Counter(j['stage'] for j in features['native_worker_jobs'])=={'feature':40}
    assert read(TEST/'preflight-audit.json')['audited_at_utc']<read(TEST/'feature-attempt.json')['started_at_utc']
    if final:
        labels=read(TEST/'completion.json');reports.append(labels)
        assert old.job_audit(labels)['jobs']==41 and Counter(j['stage'] for j in labels['native_worker_jobs'])=={'verify':1,'label':40}
        assert read(TEST/'prelabel-audit.json')['audited_at_utc']<read(TEST/'label-attempt.json')['started_at_utc']
        assert max(j['finished_at_utc'] for j in features['native_worker_jobs'])<min(j['started_at_utc'] for j in labels['native_worker_jobs'])
        assert max(j['finished_at_utc'] for j in labels['native_worker_jobs'] if j['stage']=='verify')<min(j['started_at_utc'] for j in labels['native_worker_jobs'] if j['stage']=='label')
        assert read(OUT/'fresh-point-freeze.json')['frozen_at_utc']<min(j['started_at_utc'] for j in labels['native_worker_jobs'])
    events=[event for report in reports for j in report['native_worker_jobs'] for event in ((j['started_at_utc'],1),(j['finished_at_utc'],-1))];active=peak=0
    for _,delta in sorted(events,key=lambda x:(x[0],x[1])):active+=delta;peak=max(peak,active)
    assert active==0 and peak<=2
    total=sum(r['native_elapsed_seconds'] for r in reports);assert total<=300 and math.isclose(reports[-1]['total_native_elapsed_seconds'],total,abs_tol=1e-9)
    return {'native_jobs':sum(len(r['native_worker_jobs']) for r in reports),'total_native_seconds':total,'recorded_worker_peak':peak,'new_fits':0}


def authenticate():
    p=read(OUT/'protocol.json');plan=read(TEST/'plan.json')
    assert p['schema']=='isaforge-boundary-repair-v1' and p['finite_candidates']==[CANDIDATE]
    assert p['planned_fits']==p['maximum_fits']==p['new_training_rows']==p['native_jobs']==0
    assert p['workers']==p['native_threads']==1 and p['existing_forest_training_count']==1825 and p['existing_forest_trees']==300
    assert p['gates']['tolerance']==TOL and p['retained_panels']==COUNTS
    assert p['named_failure_evaluation_only']=={'panel':'consumed-fifth-fresh40','index':12,'cap':128}
    assert p['fresh_compound_indices']==[i for i,r in enumerate(read(TEST/'candidates.json')) if prior.predicates(r['formula'])[0]] and len(p['fresh_compound_indices'])==32
    assert len(set(p['feature_columns']))==336 and len(set(p['selected_columns']))==217
    assert p['policy']['formula']=='Start with frozen budget_release_compound_only. On compound route, find each cap in[32,64,128] for which incumbent_signed<=cap<release AND forest_median<=cap. If any, return smallest qualifying cap; otherwise return release. Outside compound route return release exactly.'
    assert p['policy']['median']=='numpy.median of all300 scalar tree predictions from existing1825forest, on217mappingfeatures; for even300, arithmetic mean of sorted positions149and150 (zero-based). This is not equivalent to strict-majority cap voting.'
    for section in ('sources_sha256','inputs_sha256'):check_bindings(p[section])
    assert plan['schema']=='boundary-repair-fresh40-v1' and plan['training_count']==0 and plan['test_count']==40
    assert plan['policy']=={'total_native_seconds':300,'workers':2,'fits':0,'retries':0,'replacement_candidates':0,'random_vectors':2048,'vectors_per_formula':2148,'caps_lut4':[32,64,128]}
    for section in ('sources','inputs','prior_inventory_sources'):check_bindings(plan[section])
    for tool in read(TEST/'tools.json').values():assert sha(tool['path'])==tool['sha256']
    seal=read(OUT/'policy-freeze.json');assert seal['new_fits']==0 and seal['protocol_sha256']==sha(OUT/'protocol.json') and p['frozen_at_utc']<seal['frozen_at_utc'];check_bindings(seal['files_sha256'],OUT)
    assert not (OUT/'model.joblib').exists() and not (OUT/'run-start.json').exists()
    return p


def frozen_bindings():
    files=[OUT/n for n in ('protocol.json','policy-freeze.json','development-predictions.json','development-metrics.json','auditor-prior-artifacts.json','goal-at-freeze.json')]+[TEST/n for n in ('plan.json','candidates.json','novelty.json','historical-formulas.json','tools.json')]
    return {str(p.relative_to(ROOT)):sha(p) for p in files}


def preflight(write=False):
    p=authenticate();count=preserved();identities=identity_audit()
    if write:assert not any((TEST/n).exists() for n in ('labels.json','features.json','label-attempt.json','feature-attempt.json'))
    return receipt(TEST/'preflight-audit.json',{'bindings':frozen_bindings(),'scientific_artifacts_preserved':count,'identity_audit':identities,
        'reviewed_policy':p['policy'],'reviewed_gates':p['gates'],'finite_candidates':[CANDIDATE],'new_fits':0,
        'new_features_labels_and_attempts_absent_at_receipt':True,'policy_development_selection_cohort_frozen_before_features_or_labels':True},write)



def development():
    authenticate();saved=read(OUT/'development-predictions.json');saved_metrics=read(OUT/'development-metrics.json');computed={};fields=0
    assert set(saved)==set(COUNTS)
    for name,(row,features) in panel_sources().items():
        assert len(row['actual_lut4'])==COUNTS[name]
        for key,value in row.items():assert saved[name][key]==value,(name,key)
        models,routes,details=points(row,features)
        assert models==saved[name]['models'] and routes==saved[name]['routes'],name
        for key,value in details.items():assert saved[name][key]==value,(name,key)
        computed[name]=panel_metrics(row['actual_lut4'],models);fields+=old.compare_metric(saved_metrics['panels'][name],computed[name])
    def subgroup(panel,folder,template):
        rows=read(ROOT/'results'/folder/'candidates.json');indices=[i for i,r in enumerate(rows) if r['template']==template];assert len(indices)==4
        payload=saved[panel];return panel_metrics([payload['actual_lut4'][i] for i in indices],{n:[values[i] for i in indices] for n,values in payload['models'].items()})
    named={'arithmetic_stress32':computed['arithmetic-stress'],
        'signed_dual_arithmetic4':subgroup('consumed-second-fresh32','budget-preserving-validation','signed_dual_arithmetic'),
        'signed_add_boolean4':subgroup('consumed-third-fresh40','guarded-revision-validation','heldout_signed_variable_add_boolean'),
        'compound_signed_add_xor4':subgroup('consumed-fourth-fresh40','signed-refinement-validation','heldout_compound_signed_add_xor'),
        'fifth_compound_signed_add_xor4':subgroup('consumed-fifth-fresh40','budget-release-validation','heldout_compound_signed_add_xor'),
        'fifth_compound_signed_xordata_addxor4':subgroup('consumed-fifth-fresh40','budget-release-validation','heldout_compound_signed_xordata_addxor')}
    for name,m in named.items():fields+=old.compare_metric(saved_metrics['named_regressions'][name],m)
    row=saved['consumed-fifth-fresh40'];i=12;assert row['actual_lut4'][i]==125 and row['models'][RELEASE][i]>128
    failure={'candidate_id':row['candidate_ids'][i],'formula':row['formulas'][i],'actual_lut4':row['actual_lut4'][i],
        'signed_lut4':row['models'][CURRENT][i],'release_lut4':row['models'][RELEASE][i],'repaired_lut4':row['models'][CANDIDATE][i],
        'median_lut4':row['forest_medians_lut4'][i],'repaired_at_cap128':row['models'][CANDIDATE][i]<=128}
    assert failure==saved_metrics['named_failure']
    retained=all(passed(m['checks']) for m in computed.values());prior_fixes=all(passed(m['checks']) for m in named.values())
    untouched=all(row['models'][CANDIDATE][i]==row['models'][RELEASE][i] for row in saved.values() for i,r in enumerate(row['routes']) if not r['compound'])
    gate={'all_nine_retained_panels_pass':retained,'all_prior_named_subgroups_preserved':prior_fixes,'named_failure_repaired':failure['repaired_at_cap128'],
        'outside_compound_exactly_release':untouched,'development_gate_passed':retained and prior_fixes and failure['repaired_at_cap128'] and untouched}
    gates={CANDIDATE:gate};selected=CANDIDATE if gate['development_gate_passed'] else None
    assert gates==saved_metrics['gates'] and saved_metrics['selected_candidate']==selected and saved_metrics['evaluated_candidate']==CANDIDATE
    changes=[]
    for panel,row in saved.items():
        for i,(r,p) in enumerate(zip(row['models'][RELEASE],row['models'][CANDIDATE])):
            if r!=p:changes.append({'panel':panel,'candidate_id':row['candidate_ids'][i],'formula':row['formulas'][i],'actual_lut4':row['actual_lut4'][i],'release_lut4':r,'repaired_lut4':p,'median_lut4':row['forest_medians_lut4'][i]})
    return {'panels':computed,'named_regressions':named,'named_failure':failure,'gates':gates,'selected_candidate':selected,'evaluated_candidate':CANDIDATE,'numeric_fields_compared':fields,'development_points_replayed':sum(COUNTS.values())*4,'changed_points':changes}


def fresh_points():
    p=authenticate();saved=read(OUT/'fresh-predictions.json');rows=read(TEST/'candidates.json');features=read(TEST/'features.json')
    assert saved['candidate_ids']==[r['candidate_id'] for r in rows] and saved['formulas']==[r['formula'] for r in rows]
    models,routes,details=points(saved,features);assert saved['models']==models and saved['routes']==routes
    for key,value in details.items():assert saved[key]==value,key
    seal=read(OUT/'fresh-point-freeze.json');assert seal['fresh_labels_present'] is False and seal['new_fits']==0
    for key,path in [('protocol_sha256',OUT/'protocol.json'),('policy_freeze_sha256',OUT/'policy-freeze.json'),('predictions_sha256',OUT/'fresh-predictions.json'),('features_sha256',TEST/'features.json'),('candidates_sha256',TEST/'candidates.json')]:assert seal[key]==sha(path)
    bridge=read(TEST/'point-freeze.json');assert bridge['target_label_jobs']==0;check_bindings(bridge['bindings'])
    dev=development();assert saved['selected_candidate']==dev['selected_candidate'] and saved['evaluated_candidate']==CANDIDATE
    assert read(OUT/'policy-freeze.json')['frozen_at_utc']<read(TEST/'feature-attempt.json')['started_at_utc']
    assert read(TEST/'feature-completion.json')['completed_at_utc']<seal['frozen_at_utc']
    return saved,dev


def prelabel(write=False):
    authenticate();count=preserved();preflight(False);jobs=chronology();saved,dev=fresh_points()
    if write:assert not any((TEST/n).exists() for n in ('labels.json','label-attempt.json'))
    files=[OUT/n for n in ('fresh-point-freeze.json','fresh-predictions.json')]+[TEST/n for n in ('point-freeze.json','features.json','feature-completion.json')]
    return receipt(TEST/'prelabel-audit.json',{'bindings':{**frozen_bindings(),**{str(p.relative_to(ROOT)):sha(p) for p in files}},
        'scientific_artifacts_preserved':count,'fresh_labels_and_attempts_absent_at_receipt':True,'fresh_predictions_replayed':160,'fresh_tree_predictions_replayed':12000,
        'development':dev,'cached_inference':cached_inference(saved),'feature_collisions':feature_collisions(),'native_accounting_to_date':jobs,'fixed_weights_and_all_points_before_fresh_labels':True},write)



def cached_inference(saved):
    path=OUT/'cached-inference-check.json';cache=read(path)
    assert cache['model']==CANDIDATE and cache['selected_candidate']==saved['selected_candidate'] and cache['development_eligible']==(saved['selected_candidate'] is not None)
    assert cache['fits']==cache['native_jobs']==0 and cache['calibration_status']=='uncalibrated' and cache['upper_lut4'] is None
    for key in ('candidate_ids','formulas','models','routes','forest_medians_lut4','qualifying_caps_lut4','tree_predictions_above_cap'):assert cache[key]==saved[key],key
    assert cache['predicted_lut4']==saved['models'][CANDIDATE]
    assert cache['protocol_sha256']==sha(OUT/'protocol.json') and cache['features_sha256']==sha(TEST/'features.json') and cache['candidates_sha256']==sha(TEST/'candidates.json')
    return {'artifact_sha256':sha(path),'predictions_replayed':40,'all_four_models_and_median_details_replayed':True,'fits':0,'native_jobs':0,'source':'cached features only'}



def decision_cases(saved,actual,rows):
    result={}
    for reference in (CURRENT,RELEASE):
        caps={}
        for cap in CAPS:
            feasible=sum(y<=cap for y in actual);cases=[]
            for i,(oldpoint,newpoint,y) in enumerate(zip(saved['models'][reference],saved['models'][CANDIDATE],actual)):
                if (oldpoint<=cap)==(newpoint<=cap):continue
                cases.append({'candidate_id':saved['candidate_ids'][i],'formula':saved['formulas'][i],'template':rows[i]['template'],
                    'actual_lut4':y,'reference_lut4':oldpoint,'repaired_lut4':newpoint,'forest_median_lut4':saved['forest_medians_lut4'][i],
                    'event':('corrected_false_reject' if y<=cap else 'new_false_accept') if newpoint<=cap else ('new_false_reject' if y<=cap else 'corrected_false_accept')})
            caps[str(cap)]={'actual_feasible':feasible,'actual_infeasible':len(actual)-feasible,'changed_decisions':cases}
        result[reference]=caps
    return result


def final_audit(write=False):
    protocol=authenticate();count=preserved();prelabel(False);jobs=chronology(True);saved,dev=fresh_points()
    labels=read(TEST/'labels.json');rows=read(TEST/'candidates.json');assert saved['candidate_ids']==[r['candidate_id'] for r in labels]
    actual=[r['lut4'] for r in labels];m=panel_metrics(actual,saved['models']);scored=read(OUT/'fresh-metrics.json');fields=old.compare_metric(scored['models'],m)
    indices=protocol['fresh_compound_indices'];compound=panel_metrics([actual[i] for i in indices],{n:[p[i] for i in indices] for n,p in saved['models'].items()})
    fields+=old.compare_metric(scored['fresh_compound_subgroup'],compound);assert scored['fresh_compound_count']==len(indices)==32
    changed=sum(a!=b for a,b in zip(saved['models'][CANDIDATE],saved['models'][RELEASE]))
    checks={'fresh_modified_prediction_count':changed,'fresh_repair_exercised':changed>=1,'strictly_better_signed':accuracy(m[CURRENT],m[CANDIDATE],True),
        'retained_style':m['checks'],'compound_subset_passes':passed(compound['checks']),
        'strictly_fewer_false_accept_cap_events_than_signed':sum(m[CANDIDATE]['caps'][str(c)]['false_accept'] for c in CAPS)<sum(m[CURRENT]['caps'][str(c)]['false_accept'] for c in CAPS),
        'outside_compound_exactly_release':all(saved['models'][CANDIDATE][i]==saved['models'][RELEASE][i] for i,r in enumerate(saved['routes']) if not r['compound'])}
    fresh_pass=checks['fresh_repair_exercised'] and all(checks['strictly_better_signed'].values()) and passed(checks['retained_style']) and checks['compound_subset_passes'] and checks['strictly_fewer_false_accept_cap_events_than_signed'] and checks['outside_compound_exactly_release']
    eligible=fresh_pass and dev['selected_candidate']==CANDIDATE
    gates={CANDIDATE:{'checks':checks,'fresh_gate_passed':fresh_pass,'development_gate_passed':dev['gates'][CANDIDATE]['development_gate_passed'],'eligible':eligible}}
    assert gates==scored['gates'] and scored['scoped_experimental_eligibility']==eligible and scored['selected_candidate']==dev['selected_candidate']
    assert scored['fresh_labels_sha256']==sha(TEST/'labels.json') and scored['fresh_point_freeze_sha256']==sha(OUT/'fresh-point-freeze.json') and scored['fits']==scored['native_jobs']==0
    templates={}
    for template in sorted({r['template'] for r in rows}):
        ix=[i for i,r in enumerate(rows) if r['template']==template];assert len(ix)==4
        templates[template]=panel_metrics([actual[i] for i in ix],{n:[p[i] for i in ix] for n,p in saved['models'].items()})
    tradeoffs=[]
    groups={**{'consumed:'+k:v for k,v in dev['panels'].items()},**{'named:'+k:v for k,v in dev['named_regressions'].items()},'fresh40':m,'fresh_compound32':compound,**{'fresh-template:'+k:v for k,v in templates.items()}}
    for panel,values in groups.items():
        for reference in ('base',CURRENT,RELEASE):
            for metric in ('mae_lut4','positive_mape_percent','maximum_underprediction_lut4'):
                if values[CANDIDATE][metric]>values[reference][metric]+TOL:tradeoffs.append({'panel':panel,'reference':reference,'metric':metric,'reference_value':values[reference][metric],'candidate_value':values[CANDIDATE][metric],'increase':values[CANDIDATE][metric]-values[reference][metric]})
    body={'protocol_sha256':sha(OUT/'protocol.json'),'auditor_sha256':sha(Path(__file__)),'scientific_artifacts_preserved':count,'old_data_scripts_models_figures_unchanged':True,
        'new_fits':0,'new_training_rows':0,'fresh_count':40,'native_accounting':jobs,'identity_audit':identity_audit(),'feature_collisions':feature_collisions(),
        'raw_evidence':raw_audit(TEST),'cached_inference':cached_inference(saved),'development':dev,'fresh':m,'fresh_compound_subgroup':compound,
        'fresh_template_metrics_descriptive':templates,'fresh_gates':gates,'selected_candidate':dev['selected_candidate'],'evaluated_candidate':CANDIDATE,'scoped_experimental_eligibility':eligible,
        'fresh_modified_prediction_count':changed,'repair_transfer_exercised':changed>=1,'fresh_cap_decision_cases':decision_cases(saved,actual,rows),
        'accuracy_and_tail_regressions_all_comparisons':tradeoffs,'fresh_numeric_fields_compared':fields,'fresh_predictions_replayed':160,'all_predictions_replayed':sum(COUNTS.values())*4+160,
        'tree_predictions_replayed':(sum(COUNTS.values())+40)*300,'median_replay_implementation':'Sort300tree predictions and average positions149/150; independent of runner numpy.median call.',
        'policy_and_cohort_before_features_or_labels':True,'fixed_weights_and_all_points_before_test_labels':True,
        'false_acceptance_sum_unit':'circuit-budget events; per-cap feasible/infeasible denominators and changed-case IDs reported separately',
        'mathematical_bounds':{'formula':'incumbent_signed<=boundary_median<=budget_release_compound_only','consequences':'Versus release, lowering can only reduce FR and increase FA; versus signed, upward predictions can only reduce FA and increase FR. Thus separate no-worse cap gates permit no newFA against release and no newFR against signed, without count offsets.'},
        'limitations':['Single development-informed policy combining fivefixed300treeforests, manual originalASTroute and exactfixedcaps; not calibrated uncertainty or universal safety.','Finite identity/composition screens and40targetedsyntheticcircuits do not establish application independence, CPU performance, timing or power.','OriginalRTL finitevectors andmappedcellrecounts are not universal equivalence or mappednetlist functional proof.','Zerochangedfreshpoints means the boundaryrepair itself is unexercised and cannot satisfy the predeclared transfer gate, even if inherited release accuracy improves.']}
    return receipt(OUT/'audit.json',body,write)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('command',choices=('preflight','prelabel','final'),nargs='?',default='final');parser.add_argument('--write-receipt',action='store_true');args=parser.parse_args()
    result=globals()[{'final':'final_audit'}.get(args.command,args.command)](args.write_receipt)
    print(json.dumps({'status':result['status'],'receipt_created':args.write_receipt,'audit_fits':0,'audit_native_jobs':0,**{k:result[k] for k in ('selected_candidate','scoped_experimental_eligibility','native_accounting','fresh_predictions_replayed') if k in result}},indent=2))
