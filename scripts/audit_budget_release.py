#!/usr/bin/env python3
"""Independent budget release evidence audit. Read-only unless --write-receipt.

No fits or synthesis. Replays retained model points, independent AST predicates,
RV32 vectors, mapped LUT/carry counts, cohort identities and complete-panel gates.
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
import audit_targeted_coverage as old
read,sha,digest,now=old.read,old.sha,old.digest,old.now
OUT=ROOT/'results/budget-release'
TRAIN=ROOT/'results/budget-release-data'
TEST=ROOT/'results/budget-release-validation'
CAPS=(32,64,128)
POLICIES=('budget_release','budget_release_compound_only')
ABLATION='release1793_uncapped'
CURRENT='incumbent_signed'
PREVIOUS='previous_guarded'
TOL=1e-10
COUNTS={'research-baselines':192,'application-transfer':327,'arithmetic-stress':32,
        'selection-validation':40,'consumed-first-fresh40':40,'consumed-second-fresh32':32,'consumed-third-fresh40':40,'consumed-fourth-fresh40':40}


def check_bindings(mapping,root=ROOT):
    for name,value in mapping.items():assert sha(root/name)==value,name


def preserved():
    snapshot=read(OUT/'auditor-prior-artifacts.json')
    check_bindings(snapshot['files'])
    check_bindings(read(OUT/'auditor-prior-docs-artifacts.json')['files'])
    assert subprocess.check_output(['git','submodule','status'],cwd=ROOT).decode().splitlines()==snapshot['submodules']
    return len(snapshot['files'])


def guard(base,scoped):
    assert len(base)==len(scoped)
    assert all(math.isfinite(v) and v>=0 for v in (*base,*scoped))
    result=[min(max(b,s),next((c for c in CAPS if b<=c),math.inf)) for b,s in zip(base,scoped)]
    assert all(p>=b for b,p in zip(base,result))
    assert all((p<=c)==(b<=c) for b,p in zip(base,result) for c in CAPS)
    return result


def route(formula,abstain=False):
    tree=old.parse(formula); ns=list(old.nodes(tree)); ops={n[0] for n in ns if isinstance(n,tuple)}
    variable=any(isinstance(n,tuple) and n[0] in ('sll','srl','sra') and
                 any(v in ('in0','in1') for v in old.nodes(n[1][1])) for n in ns)
    mixed=bool(ops&{'add','addi','sub'}) and bool(ops&{'xor','xori'}) and not ops&{'mul','mulh','mulhu','mulhsu'}
    return bool((variable or mixed) and not (abstain and mixed and 'srai' in ops and not variable))


def metrics(y,p):
    result=old.metrics(y,p)
    for c in CAPS:result['caps'][str(c)].update(actual_accept=sum(v<=c for v in y),predicted_accept=sum(v<=c for v in p))
    return result



def decision_changes(actual,reference,candidate,ids):
    assert len(actual)==len(reference)==len(candidate)==len(ids)
    assert all(n>=c for c,n in zip(reference,candidate))
    result={}
    for cap in CAPS:
        feasible=sum(y<=cap for y in actual)
        corrected=[ids[i] for i,(y,c,n) in enumerate(zip(actual,reference,candidate)) if c<=cap<y and n>cap]
        newfr=[ids[i] for i,(y,c,n) in enumerate(zip(actual,reference,candidate)) if y<=cap and c<=cap<n]
        priorfr=[ids[i] for i,(y,c) in enumerate(zip(actual,reference)) if y<=cap<c]
        assert all(candidate[i]>cap for i,(y,c) in enumerate(zip(actual,reference)) if y<=cap<c)
        result[str(cap)]={'actual_feasible':feasible,'actual_infeasible':len(actual)-feasible,
            'corrected_false_acceptance_ids':corrected,'new_false_rejection_ids':newfr,'prior_false_rejection_count':len(priorfr),
            'new_false_rejection_count':len(newfr),'corrected_false_acceptance_count':len(corrected)}
    return result



def accuracy(reference,candidate,strict=False):
    return {k:bool(candidate[k]<reference[k]-TOL if strict else candidate[k]<=reference[k]+TOL) for k in ('mae_lut4','positive_mape_percent')}


def cap_events(reference,candidate,y):
    return {str(c):{'actual_accept':sum(a<=c for a in y),'actual_reject':sum(a>c for a in y),
        'corrected_false_accept':sum(r<=c<n and a>c for r,n,a in zip(reference,candidate,y)),
        'new_false_accept':sum(n<=c<r and a>c for r,n,a in zip(reference,candidate,y)),
        'corrected_false_reject':sum(n<=c<r and a<=c for r,n,a in zip(reference,candidate,y)),
        'new_false_reject':sum(r<=c<n and a<=c for r,n,a in zip(reference,candidate,y))} for c in CAPS}


def panel_metrics(y,models):
    m={n:metrics(y,values) for n,values in models.items()};m['checks']={}
    for n in POLICIES:
        m['checks'][n]={'accuracy_no_worse_current':accuracy(m[CURRENT],m[n]),
            'caps_no_worse_current':{str(c):{k:m[n]['caps'][str(c)][k]<=m[CURRENT]['caps'][str(c)][k] for k in ('false_accept','false_reject')} for c in CAPS},
            'pointwise_at_least_current':all(v>=r for v,r in zip(models[n],models[CURRENT])),
            'maximum_underprediction_no_worse_current':m[n]['maximum_underprediction_lut4']<=m[CURRENT]['maximum_underprediction_lut4']+TOL,
            'cap_events':cap_events(models[CURRENT],models[n],y)}
    return m


def no_worse(base,candidate):
    return all(candidate[k]<=base[k]+TOL for k in ('mae_lut4','positive_mape_percent','maximum_underprediction_lut4')) and all(candidate['caps'][str(c)][k]<=base['caps'][str(c)][k] for c in CAPS for k in ('false_accept','false_reject'))

def identity_keys(formula):
    from isaforge.features import parse_formula
    from isaforge.structural_features_v4 import normalize_formula as v4
    from isaforge.structural_features_v5 import normalize_formula as v5
    from isaforge.v5_corpus import equivalence_key
    forms={parse_formula(formula).canonical()}
    for normalize in (v4,v5):
        for value in tuple(forms):
            try:forms.add(parse_formula(normalize(value)).canonical())
            except ValueError:pass
    result={('formula',f) for f in forms}|{('commutative',equivalence_key(f)) for f in forms}
    result.update(('formula',normalize(f)) for f in forms for normalize in (v4,v5))
    return result


def identity_audit():
    history=set(read(TRAIN/'historical-formulas.json'))
    required=set(read(ROOT/'results/budget-preserving-validation/historical-formulas.json'))
    aliases=set()
    for folder in ('selection-validation','targeted-coverage-data','targeted-coverage-validation','budget-preserving-validation','guarded-revision-data','guarded-revision-validation','signed-refinement-data','signed-refinement-validation'):
        path=ROOT/'results'/folder
        required.update(r['formula'] for r in read(path/'candidates.json'))
        for row in read(path/'novelty.json')['comparisons']:aliases.update(row['forms'])
    assert required<=history,'Historical inventory omits known prior formulas'
    known=set().union(*(identity_keys(f) for f in history|aliases));seen=set();reports={};skeletons={}
    for name,folder,count in (('train',TRAIN,32),('test',TEST,40)):
        rows=read(folder/'candidates.json');report=read(folder/'novelty.json')
        assert len(rows)==count and report['status']=='pass'
        assert [r['candidate_id'] for r in report['comparisons']]==[r['candidate_id'] for r in rows]
        skeletons[name]={old.skeleton(r['formula']) for r in rows}
        for row,evidence in zip(rows,report['comparisons']):
            forms=set(evidence['forms'])|{row['formula']};current=set().union(*(identity_keys(f) for f in forms))
            assert not current&known and not current&seen,row['candidate_id']
            seen.update(current)
        reports[name]={'count':count,'templates':dict(Counter(r['template'] for r in rows))}
    historical_skeletons={old.skeleton(f) for f in history}
    assert not (skeletons['train']|skeletons['test'])&historical_skeletons,'Historical constant-erased AST composition overlap'
    assert not skeletons['train']&skeletons['test'],'Cross-cohort constant-erased AST composition overlap'
    joint=read(TRAIN/'candidates.json')+read(TEST/'candidates.json')
    assert len({r['candidate_id'] for r in joint})==len({r['formula'] for r in joint})==72
    return {'historical_formulas':len(history),'saved_prior_aliases':len(aliases),'known_identity_keys':len(known),
            'all_prior280_cohort_cases_and_saved_aliases_included':True,'known_or_joint_identity_overlaps':0,'train_test_composition_overlap':0,'cohorts':reports}


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
        kind='train' if folder==TRAIN else 'test'
        feature_jobs=[j for j in read(TRAIN/'feature-completion.json')['native_worker_jobs'] if j['kind']==kind]
        label_jobs=read(folder/'completion.json')['native_worker_jobs']
        for job in feature_jobs+label_jobs:
            phase=job['stage'];directory='verification' if phase=='verify' else phase+'s/'+str(job['index'])
            assert json.loads(get(directory+'/worker.json'))==job
            assert digest(get(directory+'/worker.log'))==job['log_sha256']
        proof=json.loads(get('verification/result.json'));vectors=get('verification/vectors.txt');rtl=get('verification/verification.v').decode()
        assert proof['verified'] and proof['formula_count']==len(rows) and proof['vectors_per_formula']==2148
        assert proof['random_seed']==read(TRAIN/'plan.json')['proof_random_seeds'][kind]
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


def receipt(path,body,write=False):
    body={'schema':'independent-budget-release-'+path.stem+'-v1','status':'pass','audited_at_utc':now(),**body,'audit_fits':0,'audit_native_jobs':0}
    if write:
        with path.open('x') as stream:json.dump(body,stream,indent=2,allow_nan=False);stream.write('\n')
    else:
        saved=read(path);actual=dict(body)
        for payload in (saved,actual):payload.pop('audited_at_utc',None)
        assert saved==actual,'Read-only replay differs from frozen receipt: '+str(path)
    return body


def feature_collisions(protocol):
    import numpy as np
    selected=protocol['selected_columns'];oldcols=read(ROOT/'results/feature-comparison/columns.json')
    with np.load(ROOT/'results/feature-comparison/inputs.npz',allow_pickle=False) as data:
        known={tuple(v) for v in data['x'][:,[oldcols.index(n) for n in selected]]}
    for name in ('targeted-coverage-data','targeted-coverage-validation','budget-preserving-validation','guarded-revision-data','guarded-revision-validation','signed-refinement-data','signed-refinement-validation'):
        payload=read(ROOT/'results'/name/'features.json')
        values=np.asarray([r['values'] for r in payload['records']])[:,[payload['columns'].index(n) for n in selected]]
        known.update(tuple(v) for v in values)
    values={}
    for name,folder in (('train',TRAIN),('test',TEST)):
        payload=read(folder/'features.json')
        matrix=np.asarray([r['values'] for r in payload['records']])[:,[payload['columns'].index(n) for n in selected]]
        assert np.isfinite(matrix).all() and (matrix>=0).all()
        values[name]=matrix
    return {'new_train_rows_with_prior217_feature_collision':sum(tuple(v) in known for v in values['train']),
            'new_test_rows_with_prior217_feature_collision':sum(tuple(v) in known for v in values['test']),
            'test_rows_with_new_training217_collision':sum(tuple(v) in {tuple(x) for x in values['train']} for v in values['test']),
            'train_unique217':len({tuple(v) for v in values['train']}),'test_unique217':len({tuple(v) for v in values['test']}),
            'scope':'Feature equality reported separately from formula/known semantic identity.'}


def panel_sources():
    result={}
    for name in ('research-baselines','application-transfer','arithmetic-stress','selection-validation'):
        folder=ROOT/'results'/name
        if name=='selection-validation':
            rows=read(folder/'labels.json');y=[r['lut4'] for r in rows];ids=[r['candidate_id'] for r in rows]
        else:
            rows=read(folder/'observations.json')['rows'];y=[r['measured_lut4'] for r in rows];ids=[r['id'] for r in rows]
        result[name]=({'candidate_ids':ids,'formulas':[r['formula'] for r in rows],'actual_lut4':y},read(folder/'features.json'))
    for name,folder in (('consumed-first-fresh40','targeted-coverage-validation'),('consumed-second-fresh32','budget-preserving-validation'),('consumed-third-fresh40','guarded-revision-validation'),('consumed-fourth-fresh40','signed-refinement-validation')):
        path=ROOT/'results'/folder;rows=read(path/'candidates.json');labels=read(path/'labels.json')
        assert [r['candidate_id'] for r in rows]==[r['candidate_id'] for r in labels]
        result[name]=({'candidate_ids':[r['candidate_id'] for r in rows],'formulas':[r['formula'] for r in rows],
                       'actual_lut4':[r['lut4'] for r in labels]},read(path/'features.json'))
    return result


def predict(features,model,selected):
    import numpy as np
    names=features['columns'];matrix=np.asarray([r['values'] for r in features['records']])
    assert np.isfinite(matrix).all() and (matrix>=0).all()
    p=np.maximum(model.estimator.predict(matrix[:,[names.index(n) for n in selected]]),0)
    p[matrix[:,names.index('original_gate_count')]==0]=0
    return p.tolist()


def predicates(formula):
    ns=list(old.nodes(old.parse(formula)));ops={n[0] for n in ns if isinstance(n,tuple)}
    bearing=lambda tree:any(v in ('in0','in1') for v in old.nodes(tree))
    variable_signed=[n for n in ns if isinstance(n,tuple) and n[0]=='sra' and bearing(n[1][1])]
    compound=any({'addi','xori'}<={x[0] for x in old.nodes(n[1][0]) if isinstance(x,tuple)} for n in variable_signed)
    add_boolean=bool(variable_signed) and {'add','xor'}<=ops and bool(ops&{'and','or'}) and not bool(ops&{'sub','mul','mulh','mulhu','mulhsu'})
    repair=bool(ops&{'sra','srai'}) and 'sub' in ops and bool(ops&{'xor','xori'})
    return compound,add_boolean,repair


def compute_points(rows,features,protocol,base,candidate,old1729,current1761):
    import joblib
    import audit_signed_refinement as previous
    oldprotocol=read(ROOT/'results/signed-refinement/protocol.json')
    model1793=joblib.load(ROOT/'results/signed-refinement/model.joblib')
    oldpoints=previous.compute_points(rows,features,oldprotocol,base,model1793,old1729,current1761)
    incumbent=oldpoints['signed_refinement'];raw=predict(features,candidate,protocol['selected_columns'])
    masks=[predicates(f) for f in rows['formulas']]
    primary=[max(c,n) if compound or boolean else c for c,n,(compound,boolean,_) in zip(incumbent,raw,masks)]
    fallback=[max(c,n) if compound else c for c,n,(compound,boolean,_) in zip(incumbent,raw,masks)]
    return {'base':oldpoints['base'],PREVIOUS:oldpoints['incumbent_current'],
            CURRENT:incumbent,POLICIES[0]:primary,POLICIES[1]:fallback,
            ABLATION:[max(c,n) if compound or boolean else c for c,n,(compound,boolean,_) in zip(incumbent,predict(features,model1793,protocol['selected_columns']),masks)]}

def authenticate():
    p=read(OUT/'protocol.json');assert p['schema']=='isaforge-budget-release-v1'
    assert p['original_training_count']==1665 and p['new_training_count']==32 and p['total_training_count']==1825
    assert p['planned_fits']==p['maximum_fits']==1 and p['maximum_fit_seconds']<=120 and p['workers']==p['native_threads']==1 and p['native_jobs']==0
    assert p['configuration']=={'n_estimators':300,'min_samples_leaf':1,'max_features':1.0,'n_jobs':1,'random_state':2026101401}
    assert p['retained_panels']==COUNTS and p['consumed_evaluation_rows_used_for_fitting']==0
    assert len(set(p['selected_columns']))==217 and len(set(p['feature_columns']))==336
    assert p['gates']['tolerance']==TOL
    assert p['prior_extra_training_count']==128
    assert p['fresh_compound_indices']==[i for i,r in enumerate(read(TEST/'candidates.json')) if predicates(r['formula'])[0]]
    assert p['policies']['primary']=='On signed-refinement compound OR add_boolean original-AST route, p=max(incumbent_signed,new1825_raw); incumbent_signed elsewhere.'
    assert p['policies']['fallback']=='On signed-refinement compound original-AST route only, p=max(incumbent_signed,new1825_raw); incumbent_signed elsewhere.'
    for section in ('sources_sha256','inputs_sha256'):check_bindings(p[section])
    plan=read(TRAIN/'plan.json');assert read(TEST/'plan.json')==plan
    assert plan['schema']=='budget-release-joint32train40test-v1'
    assert plan['policy']=={'total_native_seconds':300,'training_native_seconds':180,'workers':2,'fits':0,'retries':0,'replacement_candidates':0,'random_vectors':2048,'vectors_per_formula':2148,'caps_lut4':[32,64,128]}
    for section in ('sources','inputs','prior_inventory_sources'):check_bindings(plan[section])
    for row in read(TRAIN/'tools.json').values():assert sha(row['path'])==row['sha256']
    return p

def frozen_bindings():
    paths=[OUT/'protocol.json',OUT/'auditor-prior-artifacts.json',TRAIN/'plan.json',TRAIN/'historical-formulas.json',TRAIN/'tools.json']
    paths += [folder/name for folder in (TRAIN,TEST) for name in ('candidates.json','novelty.json')]
    return {str(p.relative_to(ROOT)):sha(p) for p in paths}


def preflight(write=False):
    authenticate();count=preserved();identities=identity_audit()
    if write:
        assert not any((folder/name).exists() for folder in (TRAIN,TEST) for name in ('labels.json','label-attempt.json'))
        assert not (TRAIN/'feature-attempt.json').exists() and not (OUT/'run-start.json').exists()
    return receipt(TRAIN/'preflight-audit.json',{'bindings':frozen_bindings(),'scientific_artifacts_preserved':count,
        'identity_audit':identities,'new_labels_and_attempts_absent_at_receipt':True,'policy_and_both_cohorts_frozen_before_jobs':True},write)


def pretrain(write=False):
    p=authenticate();preserved();preflight(False)
    done=read(TRAIN/'feature-completion.json');jobs=old.job_audit(done)
    assert jobs['jobs']==72 and Counter((j['kind'],j['stage']) for j in done['native_worker_jobs'])=={('train','feature'):32,('test','feature'):40}
    assert done['native_elapsed_seconds']==done['total_native_elapsed_seconds']<=180
    assert read(TRAIN/'preflight-audit.json')['audited_at_utc']<read(TRAIN/'feature-attempt.json')['started_at_utc']
    if write:assert not any((f/'labels.json').exists() or (f/'label-attempt.json').exists() for f in (TRAIN,TEST))
    return receipt(TRAIN/'pretrain-audit.json',{'bindings':{**frozen_bindings(),**{str(x.relative_to(ROOT)):sha(x) for x in (TRAIN/'feature-completion.json',TRAIN/'features.json',TEST/'features.json')}},
        'feature_jobs':jobs['jobs'],'feature_native_seconds':done['native_elapsed_seconds'],'feature_collision_audit':feature_collisions(p),
        'both_cohorts_and_policy_before_training_labels':True,'new_labels_absent_at_receipt':True},write)


def models():
    import joblib
    import numpy as np
    p=authenticate();freeze=read(OUT/'model-freeze.json')
    assert freeze['protocol_sha256']==sha(OUT/'protocol.json') and freeze['fits_completed']==1 and freeze['wall_seconds']<=120
    assert read(TRAIN/'completion.json')['completed_at_utc']<read(OUT/'run-start.json')['started_at_utc']<freeze['frozen_at_utc']
    check_bindings(freeze['files_sha256'],OUT)
    candidate=joblib.load(OUT/'model.joblib');base=joblib.load(ROOT/'models/base/model.joblib');inc=joblib.load(ROOT/'results/targeted-coverage/model.joblib');current=joblib.load(ROOT/'results/guarded-revision/model.joblib')
    assert candidate.training_formula_count==1825 and candidate.kind=='mapping_v6' and candidate.calibration['status']=='uncalibrated' and candidate.calibration['upper_margin_lut4'] is None
    assert read(OUT/'model.json')['artifact_sha256']==sha(OUT/'model.joblib')
    provenance=candidate.training_provenance
    assert provenance['protocol_sha256']==sha(OUT/'protocol.json') and provenance['original_count']==1665 and provenance['new_training_count']==32 and provenance['consumed_evaluation_rows_used']==0
    assert provenance['training_features_sha256']==sha(TRAIN/'features.json') and provenance['training_labels_sha256']==sha(TRAIN/'labels.json')
    assert candidate.estimator.n_features_in_==217 and len(candidate.estimator.estimators_)==300
    params=candidate.estimator.get_params(deep=False);assert params==base.estimator.get_params(deep=False)
    assert all(params[k]==v for k,v in p['configuration'].items())
    assert all(int(t.tree_.n_node_samples[0])==1825 for t in candidate.estimator.estimators_)
    columns=read(ROOT/'results/feature-comparison/columns.json')
    with np.load(ROOT/'results/feature-comparison/inputs.npz',allow_pickle=False) as original:
        matrices=[original['x'][:,[columns.index(n) for n in p['feature_columns']]]]
    for folder in (ROOT/'results/targeted-coverage-data',ROOT/'results/guarded-revision-data',ROOT/'results/signed-refinement-data',TRAIN):
        payload=read(folder/'features.json');matrices.append(np.asarray([r['values'] for r in payload['records']])[:,[payload['columns'].index(n) for n in p['feature_columns']]])
    combined=np.vstack(matrices);assert combined.shape==(1825,336)
    assert np.array_equal(combined.min(axis=0),candidate.feature_minimum) and np.array_equal(combined.max(axis=0),candidate.feature_maximum)
    for name,value in candidate.runtime_source_sha256.items():assert sha(ROOT/'isaforge'/name)==value
    timings=read(OUT/'timings.json');assert len(timings)==1 and timings[0]['training_count']==1825 and timings[0]['feature_count']==217 and timings[0]['fit_seconds']<=120
    return p,base,candidate,inc,current


def development():
    p,base,candidate,inc,current=models();saved=read(OUT/'development-predictions.json');saved_metrics=read(OUT/'development-metrics.json');computed={};fields=0;changes={}
    sources=panel_sources();assert set(saved)==set(COUNTS)
    for name,(row,features) in sources.items():
        assert len(row['actual_lut4'])==COUNTS[name]
        for key,value in row.items():assert saved[name][key]==value,(name,key)
        points=compute_points(row,features,p,base,candidate,inc,current);assert saved[name]['models']==points,name
        expected_routes=[{'compound':c,'add_boolean':a,'new_coverage':c or a} for c,a,_ in map(predicates,row['formulas'])]
        assert saved[name]['routes']==expected_routes
        computed[name]=panel_metrics(row['actual_lut4'],points)
        changes[name]={n:decision_changes(row['actual_lut4'],points[CURRENT],points[n],row['candidate_ids']) for n in POLICIES}
        for n,m in computed[name].items():fields+=old.compare_metric(saved_metrics['panels'][name][n],m)
    def subgroup(panel,folder,template):
        rows=read(ROOT/'results'/folder/'candidates.json');indices=[i for i,r in enumerate(rows) if r['template']==template];assert len(indices)==4
        payload=saved[panel]
        return panel_metrics([payload['actual_lut4'][i] for i in indices],{n:[values[i] for i in indices] for n,values in payload['models'].items()})
    named={'arithmetic_stress32':computed['arithmetic-stress'],
           'signed_dual_arithmetic4':subgroup('consumed-second-fresh32','budget-preserving-validation','signed_dual_arithmetic'),
           'signed_add_boolean4':subgroup('consumed-third-fresh40','guarded-revision-validation','heldout_signed_variable_add_boolean'),
           'compound_signed_add_xor4':subgroup('consumed-fourth-fresh40','signed-refinement-validation','heldout_compound_signed_add_xor')}
    for group,values in named.items():
        for n,m in values.items():fields+=old.compare_metric(saved_metrics['named_regressions'][group][n],m)
    gates={}
    for n in POLICIES:
        retained=all(no_worse(m[CURRENT],m[n]) for m in computed.values())
        fixed=all(named['compound_signed_add_xor4'][n][k]<=named['compound_signed_add_xor4'][PREVIOUS][k]+TOL for k in ('mae_lut4','positive_mape_percent'))
        previous=all(no_worse(named[group][CURRENT],named[group][n]) for group in ('arithmetic_stress32','signed_dual_arithmetic4','signed_add_boolean4'))
        gates[n]={'all_eight_retained_panels_pass':retained,'compound_remaining_regression_fixed':fixed,
                  'all_prior_named_fixes_preserved':previous,'development_gate_passed':retained and fixed and previous}
    selected=next((n for n in POLICIES if gates[n]['development_gate_passed']),None)
    assert gates==saved_metrics['gates'] and selected==saved_metrics['selected_candidate'] and (selected or POLICIES[0])==saved_metrics['evaluated_candidate']
    return {'panels':computed,'named_regressions':named,'gates':gates,'selected_candidate':selected,'numeric_fields_compared':fields,'development_points_replayed':sum(COUNTS.values())*len(next(iter(saved.values()))['models']),'cap_decision_changes':changes}


def chronology_jobs(final=False):
    features=read(TRAIN/'feature-completion.json');training=read(TRAIN/'completion.json')
    reports=[features,training];counts=[72,33]
    if final:reports.append(read(TEST/'completion.json'));counts.append(41)
    stats=[old.job_audit(r) for r in reports]
    assert [r['jobs'] for r in stats]==counts
    assert Counter(j['stage'] for j in training['native_worker_jobs'])=={'verify':1,'label':32}
    assert features['native_elapsed_seconds']+training['native_elapsed_seconds']<=180
    assert math.isclose(training['total_native_elapsed_seconds'],features['native_elapsed_seconds']+training['native_elapsed_seconds'],abs_tol=1e-9)
    events=[]
    for report in reports:
        for j in report['native_worker_jobs']:events.extend([(j['started_at_utc'],1),(j['finished_at_utc'],-1)])
    active=peak=0
    for _,delta in sorted(events,key=lambda x:(x[0],x[1])):active+=delta;peak=max(peak,active)
    assert active==0 and peak<=2
    assert max(j['finished_at_utc'] for j in features['native_worker_jobs'])<min(j['started_at_utc'] for j in training['native_worker_jobs'])
    assert read(TRAIN/'pretrain-audit.json')['audited_at_utc']<read(TRAIN/'label-attempt.json')['started_at_utc']
    assert read(OUT/'protocol.json')['frozen_at_utc']<read(TRAIN/'label-attempt.json')['started_at_utc']
    for folder,report in [(TRAIN,training)]+([(TEST,reports[-1])] if final else []):
        jobs=report['native_worker_jobs']
        assert max(j['finished_at_utc'] for j in jobs if j['stage']=='verify')<min(j['started_at_utc'] for j in jobs if j['stage']=='label')
    if final:
        assert Counter(j['stage'] for j in reports[-1]['native_worker_jobs'])=={'verify':1,'label':40}
        assert max(j['finished_at_utc'] for j in training['native_worker_jobs'])<min(j['started_at_utc'] for j in reports[-1]['native_worker_jobs'])
        assert read(TEST/'prelabel-audit.json')['audited_at_utc']<read(TEST/'label-attempt.json')['started_at_utc']
        assert read(OUT/'fresh-point-freeze.json')['frozen_at_utc']<min(j['started_at_utc'] for j in reports[-1]['native_worker_jobs'])
    total=sum(r['native_elapsed_seconds'] for r in reports);assert total<=300
    assert math.isclose(reports[-1]['total_native_elapsed_seconds'],total,abs_tol=1e-9)
    return {'native_jobs':sum(counts),'total_native_seconds':total,'recorded_worker_peak':peak}


def fresh_points():
    p,b,c,i,current=models();points=read(OUT/'fresh-predictions.json');rows=read(TEST/'candidates.json');features=read(TEST/'features.json')
    assert points['candidate_ids']==[r['candidate_id'] for r in rows] and points['formulas']==[r['formula'] for r in rows]
    assert points['models']==compute_points(points,features,p,b,c,i,current)
    assert points['routes']==[{'compound':a,'add_boolean':b,'new_coverage':a or b} for a,b,_ in map(predicates,points['formulas'])]
    freeze=read(OUT/'fresh-point-freeze.json');assert freeze['fresh_labels_present'] is False
    for key,path in [('protocol_sha256',OUT/'protocol.json'),('model_freeze_sha256',OUT/'model-freeze.json'),('predictions_sha256',OUT/'fresh-predictions.json'),('features_sha256',TEST/'features.json'),('candidates_sha256',TEST/'candidates.json')]:assert freeze[key]==sha(path)
    bridge=read(TEST/'point-freeze.json');assert bridge['target_label_jobs']==0;check_bindings(bridge['bindings'])
    dev=development();assert points['selected_candidate']==dev['selected_candidate']
    assert points['evaluated_candidate']==(dev['selected_candidate'] or POLICIES[0])
    return points,dev


def prelabel(write=False):
    authenticate();count=preserved();pretrain(False);jobs=chronology_jobs();points,dev=fresh_points()
    if write:assert not (TEST/'labels.json').exists() and not (TEST/'label-attempt.json').exists()
    paths=[OUT/n for n in ('model-freeze.json','fresh-point-freeze.json','fresh-predictions.json','development-predictions.json','development-metrics.json')]+[TEST/'point-freeze.json',TRAIN/'completion.json',TRAIN/'labels.json']
    return receipt(TEST/'prelabel-audit.json',{'bindings':{**frozen_bindings(),**{str(p.relative_to(ROOT)):sha(p) for p in paths}},
        'scientific_artifacts_preserved':count,'fresh_labels_absent_at_receipt':True,'fresh_predictions_replayed':240,
        'development':dev,'native_accounting_to_date':jobs,'weights_and_all_points_before_fresh_labels':True},write)



def final_audit(write=False):
    protocol=authenticate();count=preserved();prelabel(False);jobs=chronology_jobs(True);points,dev=fresh_points()
    labels=read(TEST/'labels.json');assert points['candidate_ids']==[r['candidate_id'] for r in labels]
    actual=[r['lut4'] for r in labels];m=panel_metrics(actual,points['models']);saved=read(OUT/'fresh-metrics.json');fields=old.compare_metric(saved['models'],m);gates={}
    indices=protocol['fresh_compound_indices']
    compound=panel_metrics([actual[i] for i in indices],{n:[values[i] for i in indices] for n,values in points['models'].items()})
    fields+=old.compare_metric(saved['fresh_compound_subgroup'],compound);assert saved['fresh_compound_count']==len(indices)
    changes={n:decision_changes(actual,points['models'][CURRENT],points['models'][n],points['candidate_ids']) for n in POLICIES}
    for n in POLICIES:
        checks={'strictly_better_base':accuracy(m['base'],m[n],True),'strictly_better_current':accuracy(m[CURRENT],m[n],True),
            'retained_style':m['checks'][n],
            'strictly_fewer_false_accept_cap_events':sum(m[n]['caps'][str(c)]['false_accept'] for c in CAPS)<sum(m[CURRENT]['caps'][str(c)]['false_accept'] for c in CAPS),
            'compound_accuracy_no_worse_current':accuracy(compound[CURRENT],compound[n])}
        passed=all(checks['strictly_better_base'].values()) and all(checks['strictly_better_current'].values()) and no_worse(m[CURRENT],m[n]) and checks['strictly_fewer_false_accept_cap_events'] and all(checks['compound_accuracy_no_worse_current'].values())
        gates[n]={'checks':checks,'fresh_gate_passed':passed,'development_gate_passed':dev['gates'][n]['development_gate_passed'],'eligible':passed and dev['selected_candidate']==n}
    assert gates==saved['gates']
    selected=dev['selected_candidate'];eligible=bool(selected and gates[selected]['eligible']);assert saved['scoped_experimental_eligibility']==eligible and saved['selected_candidate']==selected
    raw={kind:raw_audit(folder) for kind,folder in (('train',TRAIN),('test',TEST))}
    rows=read(TEST/'candidates.json');templates={}
    for template in sorted({r['template'] for r in rows}):
        ix=[i for i,r in enumerate(rows) if r['template']==template]
        templates[template]=panel_metrics([actual[i] for i in ix],{n:[values[i] for i in ix] for n,values in points['models'].items()})
    tradeoffs=[]
    compare_panels={**{'consumed:'+n:values for n,values in dev['panels'].items()},**{'named:'+n:values for n,values in dev['named_regressions'].items()},'fresh40':m,**{'fresh-template:'+n:values for n,values in templates.items()}}
    for panel,values in compare_panels.items():
        for n in (*POLICIES,ABLATION):
            for reference in ('base',PREVIOUS,CURRENT):
                for metric in ('mae_lut4','positive_mape_percent'):
                    if values[n][metric]>values[reference][metric]+TOL:
                        tradeoffs.append({'panel':panel,'candidate':n,'reference':reference,'metric':metric,'candidate_value':values[n][metric],'reference_value':values[reference][metric],'increase':values[n][metric]-values[reference][metric]})
    exposure={}
    for kind,folder in (('train',TRAIN),('fresh',TEST)):
        masks=[predicates(r['formula']) for r in read(folder/'candidates.json')]
        exposure[kind]={'compound':sum(c for c,a,_ in masks),'add_boolean':sum(a for c,a,_ in masks),'overlap':sum(c and a for c,a,_ in masks),'new_coverage_union':sum(c or a for c,a,_ in masks),'preserved_current':sum(not(c or a) for c,a,_ in masks)}
    report={'protocol_sha256':sha(OUT/'protocol.json'),'auditor_sha256':sha(Path(__file__)),
        'scientific_artifacts_preserved':count,'additional_prior_docs_artifacts_preserved':len(read(OUT/'auditor-prior-docs-artifacts.json')['files']),'old_data_scripts_models_unchanged':True,'new_fits':1,'new_training_count':32,'fresh_count':40,
        'native_accounting':jobs,'identity_audit':identity_audit(),'feature_collisions':feature_collisions(protocol),'raw_evidence':raw,'route_exposure':exposure,
        'development':dev,'fresh':m,'fresh_compound_subgroup':compound,'fresh_template_metrics_descriptive':templates,'fresh_gates':gates,'selected_candidate':selected,
        'evaluated_candidate':selected or POLICIES[0],'scoped_experimental_eligibility':eligible,'accuracy_regressions_all_comparisons':tradeoffs,
        'selected_candidate_new_false_rejections':[{'cap':cap,'candidate_id':points['candidate_ids'][i],'formula':points['formulas'][i],'template':rows[i]['template'],'actual_lut4':actual[i],'incumbent_lut4':points['models'][CURRENT][i],'candidate_lut4':points['models'][selected][i]} for cap in CAPS for i in range(40) if selected and actual[i]<=cap and points['models'][CURRENT][i]<=cap<points['models'][selected][i]],
        'fresh_numeric_fields_compared':fields,'fresh_predictions_replayed':len(points['models'])*40,'fresh_cap_decision_changes':changes,
        'false_acceptance_sum_unit':'circuit-budget events, not unique circuits; per-cap feasible/infeasible denominators and case IDs accompany changes',
        'policy_and_cohorts_before_training_labels':True,'weights_and_all_fresh_points_before_test_labels':True,
        'mathematical_guarantee':{'formula':'p=max(incumbent_signed,new1825_raw) on declared scope; incumbent elsewhere','proof':'p>=incumbent pointwise, so existing false rejections persist, no new false acceptances arise, maximum underprediction cannot worsen. False rejection counts can increase and are empirically gated separately at each declared cap.','unchanged_budget_classification_guarantee':False},
        'limitations':['Five fixed300-tree forests plus manual AST routing, not a pure learned selector.','Synthetic finite cohort with known identity/composition screens; no representative application or CPU integration claim.','Finite fresh budget/accuracy findings are not calibrated safety or no-worse guarantees on unseen circuits. Other caps, timing, power and routing unestablished.','Independent finite RV32 original-RTL vectors and mapped-cell recounts are not universal equivalence or mapped-netlist functional proof.','Old1793uncapped release is diagnostic only and cannot be promoted; retain all failures and gate violations.']}
    return receipt(OUT/'audit.json',report,write)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('command',choices=('preflight','pretrain','prelabel','final'),nargs='?',default='final')
    parser.add_argument('--write-receipt',action='store_true',help='Exclusively create a new receipt; default only replays and compares existing receipt.')
    args=parser.parse_args();result={'preflight':preflight,'pretrain':pretrain,'prelabel':prelabel,'final':final_audit}[args.command](args.write_receipt)
    print(json.dumps({'status':result['status'],'receipt_created':args.write_receipt,'audit_fits':0,'audit_native_jobs':0,
        **{k:result[k] for k in ('selected_candidate','scoped_experimental_eligibility','native_accounting','fresh_predictions_replayed') if k in result}},indent=2))
