#!/usr/bin/env python3
"""Independent bounded boundary coverage and representation audit; no fits or native jobs.

Reconstructs old frozen forests, original-AST routes, exact even-n median,
all ordered points, separate cap events, finite-vector targets and LUT recounts.
"""
from __future__ import annotations
import argparse
from functools import lru_cache
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
OUT=ROOT/'results/boundary-coverage'
TRAIN=ROOT/'results/boundary-coverage-data'
TEST=ROOT/'results/boundary-coverage-validation'
CAPS=(32,64,128)
CURRENT='incumbent_signed'
RELEASE='budget_release_compound_only'
BROAD='boundary_median'
CANDIDATE='boundary_structural'
PREVIOUS=CANDIDATE
CANDIDATES=('boundary_augmented','boundary_coverage_only')
KINDS={'boundary_augmented':'augmented','boundary_coverage_only':'coverage'}
NAMES=('base',CURRENT,RELEASE,BROAD,CANDIDATE)
COUNTS={**prior.COUNTS,'consumed-fifth-fresh40':40,'consumed-sixth-broad40':40,'consumed-seventh-conditional18':18,'consumed-eighth-general32':32,'consumed-eighth-conditional24':24}
TOL=1e-10


def check_bindings(mapping,root=ROOT):
    for name,value in mapping.items():assert sha(root/name)==value,name


def preserved():
    snap=read(OUT/'auditor-prior-artifacts.json');check_bindings(snap['files'])
    ledger=read(ROOT/snap['goal_ledger']['path']);ledger.pop('status',None)
    assert ledger==snap['goal_ledger']['protected_content']
    assert subprocess.check_output(['git','submodule','status'],cwd=ROOT).decode().splitlines()==snap['submodules']
    return len(snap['files'])


def receipt(path,body,write=False):
    body={'schema':'independent-boundary-coverage-'+path.stem+'-v1','status':'pass','audited_at_utc':now(),**body,'audit_fits':0,'audit_native_jobs':0}
    if write:
        with path.open('x') as f:json.dump(body,f,indent=2,allow_nan=False);f.write('\n')
    else:
        saved=read(path);computed=dict(body)
        for value in (saved,computed):value.pop('audited_at_utc',None)
        assert saved==computed,'Read-only receipt mismatch:'+str(path)
    return body



def identity_audit():
    history=set(read(TRAIN/'historical-formulas.json'));assert history==set(read(TEST/'historical-formulas.json'))
    required=set(read(ROOT/'results/budget-release-data/historical-formulas.json'));aliases=set()
    folders=('selection-validation','targeted-coverage-data','targeted-coverage-validation','budget-preserving-validation','guarded-revision-data','guarded-revision-validation','signed-refinement-data','signed-refinement-validation','budget-release-data','budget-release-validation','boundary-repair-validation','boundary-challenge-validation','boundary-refinement-validation')
    for name in folders:
        folder=ROOT/'results'/name;required.update(r['formula'] for r in read(folder/('pool-candidates.json' if (folder/'pool-candidates.json').exists() else 'candidates.json')))
        for row in read(folder/'novelty.json')['comparisons']:aliases.update(row['forms'])
    assert required<=history,'Historical inventory omission'
    known=set().union(*(prior.identity_keys(f) for f in history|aliases));seen=set();old_skeletons={old.skeleton(f) for f in history};reports={};skeletons={}
    for kind,folder,filename,count in (('train',TRAIN,'candidates.json',32),('test',TEST,'pool-candidates.json',128)):
        rows=read(folder/filename);report=read(folder/'novelty.json');assert len(rows)==count and report['status']=='pass'
        assert [r['candidate_id'] for r in report['comparisons']]==[r['candidate_id'] for r in rows]
        for row,evidence in zip(rows,report['comparisons']):
            forms={row['formula'],*evidence['forms']};keys=set().union(*(prior.identity_keys(f) for f in forms))
            assert not keys&known and not keys&seen,row['candidate_id'];seen.update(keys)
            assert old.skeleton(row['formula']) not in old_skeletons,row['candidate_id']
        assert len({r['formula'] for r in rows})==len({r['candidate_id'] for r in rows})==count
        skeletons[kind]={old.skeleton(r['formula']) for r in rows};reports[kind]={'count':count,'templates':dict(Counter(r['template'] for r in rows))}
    assert not skeletons['train']&skeletons['test'],'Train/test constant-erased original AST overlap'
    return {'historical_formulas':len(history),'saved_prior_aliases':len(aliases),'known_identity_keys':len(known),'known_or_joint_identity_overlaps':0,'historical_or_cross_cohort_original_AST_skeleton_overlaps':0,'cohorts':reports,'all_previous200_and128_pool_rows_included':True}



def panel_sources():
    import audit_boundary_refinement as frozen
    result=frozen.panel_sources();folder=ROOT/'results/boundary-refinement-validation';rows=read(folder/'candidates.json');labels=read(folder/'labels.json');features=read(folder/'features.json');saved=read(ROOT/'results/boundary-refinement/fresh-predictions.json')
    for name,key in (('consumed-eighth-general32','general_selected_indices'),('consumed-eighth-conditional24','conditional_selected_indices')):
        ix=saved[key];result[name]=({'candidate_ids':[rows[i]['candidate_id'] for i in ix],'formulas':[rows[i]['formula'] for i in ix],'actual_lut4':[labels[i]['lut4'] for i in ix]}, {'columns':features['columns'],'records':[features['records'][i] for i in ix]})
    return result


_WEIGHTS=None



def structural_route(formula):
    root=old.parse(formula)
    if not isinstance(root,tuple) or root[0]!='xor':return False
    for add in root[1]:
        if not isinstance(add,tuple) or add[0]!='add':continue
        for shift in add[1]:
            if not isinstance(shift,tuple) or shift[0]!='sra':continue
            if not any(x in ('in0','in1') for x in old.nodes(shift[1][1])):continue
            ops={n[0] for n in old.nodes(shift[1][0]) if isinstance(n,tuple)}
            if {'addi','xori'}<=ops:return True
    return False



def points(rows,features):
    import numpy as np
    import audit_boundary_refinement as frozen
    oldpoints,routes,details=frozen.points(rows,features)
    fitted=models()[0];base=feature_matrix(features);scope=[ast_learning_scope(f) for f in rows['formulas']];raw={};support={}
    for name,kind in KINDS.items():
        x=np.hstack([base,np.asarray([ast_features(f) for f in rows['formulas']])]) if kind=='augmented' else base
        raw[name]=fitted[kind].predict(x).tolist();limits=[];values=[]
        for signed,previous,p,active in zip(oldpoints[CURRENT],oldpoints[PREVIOUS],raw[name],scope):
            caps=[cap for cap in CAPS if active and signed<=cap<previous and p<=cap];limits.append(caps);values.append(min(caps) if caps else previous)
        oldpoints[name]=values;support[name]=limits
    return oldpoints,routes,{**details,'learning_scope':scope,'learned_raw_lut4':raw,'learned_supported_caps_lut4':support}


def metrics(y,models):return {n:prior.metrics(y,p) for n,p in models.items()}


def accuracy(reference,candidate,strict=False):
    return {k:bool(candidate[k]<reference[k]-TOL if strict else candidate[k]<=reference[k]+TOL) for k in ('mae_lut4','positive_mape_percent')}


def cap_no_worse(reference,candidate,kind):return {str(c):candidate['caps'][str(c)][kind]<=reference['caps'][str(c)][kind] for c in CAPS}




def panel_metrics(y,values,raw=None):
    m=metrics(y,values);checks={}
    for name in CANDIDATES:
        c=m[name];checks[name]={'accuracy_no_worse_release':accuracy(m[RELEASE],c),'accuracy_no_worse_previous':accuracy(m[PREVIOUS],c),
            'caps':{str(cap):{'false_accept_no_worse_release':c['caps'][str(cap)]['false_accept']<=m[RELEASE]['caps'][str(cap)]['false_accept'],'false_reject_no_worse_signed':c['caps'][str(cap)]['false_reject']<=m[CURRENT]['caps'][str(cap)]['false_reject']} for cap in CAPS},
            'maximum_underprediction_no_worse':all(c['maximum_underprediction_lut4']<=m[n]['maximum_underprediction_lut4']+TOL for n in (RELEASE,PREVIOUS,CURRENT)),
            'pointwise_bounds':all(s<=v<=p<=r for s,v,p,r in zip(values[CURRENT],values[name],values[PREVIOUS],values[RELEASE])),
            'events_vs_signed':prior.cap_events(values[CURRENT],values[name],y),'events_vs_release':prior.cap_events(values[RELEASE],values[name],y),'events_vs_previous':prior.cap_events(values[PREVIOUS],values[name],y)}
    m['checks']=checks
    if raw is not None:m['raw_model_metrics']={n:prior.metrics(y,raw[n]) for n in CANDIDATES}
    return m


def passed(c):
    return all(c['accuracy_no_worse_release'].values()) and all(c['accuracy_no_worse_previous'].values()) and all(all(v.values()) for v in c['caps'].values()) and c['maximum_underprediction_no_worse'] and c['pointwise_bounds']


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
            if folder==TRAIN:assert json.loads(get(f'features/{i}/result.json'))==features['records'][i]
            else:assert features['records'][i]==read(folder/'pool-features.json')['records'][read(folder/'selection.json')['selected_pool_indices'][i]]
        if folder!=TRAIN:
            pool=read(folder/'pool-features.json');assert len(pool['records'])==128
            for i,record in enumerate(pool['records']):assert json.loads(get(f'features/{i}/result.json'))==record
    return {'archive_sha256':sha(archive),'members_hashed':len(members),'mapped_netlists_recounted':len(rows),'all_feature_results_authenticated':32 if folder==TRAIN else 128,'independent_RV32_vector_comparisons':2148*len(rows),'native_job_records_and_logs_authenticated':len(feature_jobs)+len(label_jobs)}



def feature_collisions():
    import numpy as np
    columns=read(ROOT/'results/budget-release/protocol.json')['selected_columns'];oldcols=read(ROOT/'results/feature-comparison/columns.json')
    with np.load(ROOT/'results/feature-comparison/inputs.npz',allow_pickle=False) as data:known={tuple(r) for r in data['x'][:,[oldcols.index(n) for n in columns]]}
    for name in ('selection-validation','targeted-coverage-data','targeted-coverage-validation','budget-preserving-validation','guarded-revision-data','guarded-revision-validation','signed-refinement-data','signed-refinement-validation','budget-release-data','budget-release-validation','boundary-repair-validation'):
        payload=read(ROOT/'results'/name/'features.json');matrix=np.asarray([r['values'] for r in payload['records']])[:,[payload['columns'].index(n) for n in columns]];known.update(tuple(r) for r in matrix)
    f=read(TEST/'pool-features.json');matrix=np.asarray([r['values'] for r in f['records']])[:,[f['columns'].index(n) for n in columns]]
    assert matrix.shape==(200,217) and np.isfinite(matrix).all() and (matrix>=0).all()
    return {'prior217_feature_rows_known':len(known),'pool217_unique':len({tuple(r) for r in matrix}),'pool_rows_with_prior217_collision':sum(tuple(r) in known for r in matrix),'scope':'Feature equality reported separately from formula and known semantic identity.'}



def chronology(final=False):
    features=read(TRAIN/'feature-completion.json');training=read(TRAIN/'completion.json');reports=[features,training]
    assert old.job_audit(features)['jobs']==160 and Counter((j['kind'],j['stage']) for j in features['native_worker_jobs'])=={('train','feature'):32,('test','feature'):128}
    assert old.job_audit(training)['jobs']==33 and Counter(j['stage'] for j in training['native_worker_jobs'])=={'verify':1,'label':32}
    assert read(TRAIN/'preflight-audit.json')['audited_at_utc']<read(TRAIN/'feature-attempt.json')['started_at_utc']
    assert read(TRAIN/'pretrain-audit.json')['audited_at_utc']<read(TRAIN/'label-attempt.json')['started_at_utc']
    assert max(j['finished_at_utc'] for j in features['native_worker_jobs'])<min(j['started_at_utc'] for j in training['native_worker_jobs'])
    if final:
        labels=read(TEST/'completion.json');reports.append(labels);selected_count=len(read(TEST/'candidates.json'))
        assert old.job_audit(labels)['jobs']==selected_count+1 and Counter(j['stage'] for j in labels['native_worker_jobs'])=={'verify':1,'label':selected_count}
        assert read(TEST/'prelabel-audit.json')['audited_at_utc']<read(TEST/'label-attempt.json')['started_at_utc']
        assert read(OUT/'fresh-point-freeze.json')['frozen_at_utc']<min(j['started_at_utc'] for j in labels['native_worker_jobs'])
        assert max(j['finished_at_utc'] for j in training['native_worker_jobs'])<min(j['started_at_utc'] for j in labels['native_worker_jobs'])
    for report in reports[1:]:assert max(j['finished_at_utc'] for j in report['native_worker_jobs'] if j['stage']=='verify')<min(j['started_at_utc'] for j in report['native_worker_jobs'] if j['stage']=='label')
    events=[event for report in reports for j in report['native_worker_jobs'] for event in ((j['started_at_utc'],1),(j['finished_at_utc'],-1))];active=peak=0
    for _,delta in sorted(events,key=lambda x:(x[0],x[1])):active+=delta;peak=max(peak,active)
    assert active==0 and peak<=2
    total=0
    for report in reports:
        total+=report['native_elapsed_seconds'];assert math.isclose(report['total_native_elapsed_seconds'],total,abs_tol=1e-9)
    assert total<=300
    return {'native_jobs':sum(len(r['native_worker_jobs']) for r in reports),'total_native_seconds':total,'recorded_worker_peak':peak,'new_fits':2}



AST_COLUMNS=(
 'local_chain_count','local_data_control_input_overlap','local_data_postadd_input_overlap','local_data_outerxor_input_overlap',
 'local_control_postadd_input_overlap','local_control_outerxor_input_overlap','local_postadd_outerxor_input_overlap',
 'local_data_postadd_shared_subtrees','local_data_outerxor_shared_subtrees','local_postadd_outerxor_shared_subtrees',
 'local_data_unknown_span_min','local_data_unknown_lsb_max','local_control_unknown_bits_max',
 'local_data_and_input_joins','local_data_or_input_joins','local_data_xor_input_joins')
MASK=(1<<32)-1


@lru_cache(maxsize=32768)
def ast_dependencies(node):
    if not isinstance(node,tuple):return frozenset((node,)) if node in ('in0','in1') else frozenset()
    return frozenset().union(*(ast_dependencies(n) for n in node[1]))


def ast_chains(formula):
    root=old.parse(formula);result=[]
    if not isinstance(root,tuple) or root[0]!='xor':return result
    for outer_index,add in enumerate(root[1]):
        if not isinstance(add,tuple) or add[0]!='add':continue
        for shift_index,shift in enumerate(add[1]):
            if not isinstance(shift,tuple) or shift[0]!='sra' or not ast_dependencies(shift[1][1]):continue
            ops={n[0] for n in old.nodes(shift[1][0]) if isinstance(n,tuple)}
            if {'addi','xori'}<=ops:result.append((shift[1][0],shift[1][1],add[1][1-shift_index],root[1][1-outer_index]))
    return result


@lru_cache(maxsize=32768)
def ast_known_bits(node):
    if not isinstance(node,tuple):return ((~node)&MASK,node&MASK) if isinstance(node,int) else (0,0)
    op,args=node;bits=[ast_known_bits(n) for n in args]
    if op=='lui':return bits[0]
    if all((zero|one)==MASK for zero,one in bits):
        value=old.evaluate((op,tuple(one for zero,one in bits)),0,0)
        return (~value)&MASK,value&MASK
    z0,o0=bits[0];z1,o1=bits[1] if len(bits)>1 else (0,0)
    if op in ('and','andi'):return z0|z1,o0&o1
    if op in ('or','ori'):return z0&z1,o0|o1
    if op in ('xor','xori'):return (z0&z1)|(o0&o1),(z0&o1)|(o0&z1)
    if op in ('slt','slti','sltu','sltiu'):return MASK^1,0
    if op in ('sll','slli','srl','srli','sra','srai') and ((z1|o1)&31)==31:
        amount=o1&31
        if amount==0:return z0,o0
        if op in ('sll','slli'):return ((z0<<amount)|((1<<amount)-1))&MASK,(o0<<amount)&MASK
        high=MASK^((1<<(32-amount))-1)
        if op in ('srl','srli'):return (z0>>amount)|high,o0>>amount
        return (z0>>amount)|(high if z0&(1<<31) else 0),(o0>>amount)|(high if o0&(1<<31) else 0)
    return 0,0


def ast_unknown_shape(node):
    zero,one=ast_known_bits(node);assert not zero&one and 0<=zero<=MASK and 0<=one<=MASK
    unknown=MASK^(zero|one)
    if not unknown:return 0,32,0
    low=(unknown&-unknown).bit_length()-1
    return unknown.bit_length()-low,low,unknown.bit_count()


@lru_cache(maxsize=32768)
def ast_subtree_key(node):
    if not isinstance(node,tuple):return str(node)
    op,args=node;children=[ast_subtree_key(n) for n in args]
    if op in ('add','and','or','xor'):children.sort()
    return op+'('+','.join(children)+')'


def ast_nonleaf_subtrees(node):return {ast_subtree_key(n) for n in old.nodes(node) if isinstance(n,tuple) and ast_dependencies(n)}


def ast_learning_scope(formula):
    return any((isinstance(outer,tuple) and outer[0] in ('and','or','xor')) or ast_unknown_shape(data)[0]<=16 for data,control,post,outer in ast_chains(formula))


def ast_features(formula):
    chains=ast_chains(formula)
    if not chains:return [0]*16
    records=[]
    for data,control,post,outer in chains:
        nodes=(data,control,post,outer);deps=[ast_dependencies(n) for n in nodes];trees=[ast_nonleaf_subtrees(n) for n in nodes]
        span,low,_=ast_unknown_shape(data)
        records.append([1,*[len(deps[a]&deps[b]) for a,b in ((0,1),(0,2),(0,3),(1,2),(1,3),(2,3))],
            *[len(trees[a]&trees[b]) for a,b in ((0,2),(0,3),(2,3))],span,low,((MASK^(ast_known_bits(control)[0]|ast_known_bits(control)[1]))&31).bit_count(),
            *[sum(isinstance(n,tuple) and n[0]==op and all(ast_dependencies(c) for c in n[1]) for n in old.nodes(data)) for op in ('and','or','xor')]])
    result=[max(r[i] for r in records) for i in range(16)];result[0]=len(records);result[10]=min(r[10] for r in records)
    assert 0<=result[0]<=4 and all(0<=x<=2 for x in result[1:7]) and all(0<=x<=32 for x in result[10:12]) and 0<=result[12]<=5
    return result



def verify_tree_training(estimator,x,y):
    import numpy as np
    x=np.asarray(x,dtype=float);y=np.asarray(y,dtype=float)
    assert x.shape[0]==len(y) and np.isfinite(x).all() and np.isfinite(y).all() and (y>=0).all()
    assert len(estimator.estimators_)==300 and estimator.n_features_in_==x.shape[1] and estimator.bootstrap is False
    checked_leaves=0
    for tree in estimator.estimators_:
        assert int(tree.tree_.n_node_samples[0])==len(y)
        assert math.isclose(float(tree.tree_.value[0,0,0]),float(y.mean()),rel_tol=1e-12,abs_tol=1e-8)
        leaf=tree.apply(x);counts=np.bincount(leaf,minlength=tree.tree_.node_count);sums=np.bincount(leaf,weights=y,minlength=tree.tree_.node_count);used=counts>0
        assert (tree.tree_.children_left[used]==-1).all() and np.array_equal(counts[used],tree.tree_.n_node_samples[used])
        assert np.allclose(sums[used]/counts[used],tree.tree_.value[used,0,0],rtol=1e-12,atol=1e-8)
        checked_leaves+=int(used.sum())
    return {'trees_verified':300,'training_rows':len(y),'selected_features':x.shape[1],'training_leaf_assignments_checked':300*len(y),'leaf_counts_and_target_means_verified':checked_leaves,'absolute_leaf_mean_tolerance':1e-8,'new_fits':0}



def input_coverage_audit():
    document=read(OUT/'input-coverage-audit.json');rows=read(TRAIN/'candidates.json');assert document['columns']==list(AST_COLUMNS) and len(document['new_training'])==32
    for i,(row,saved) in enumerate(zip(rows,document['new_training'])):
        assert saved=={'index':i,'formula':row['formula'],'template':row['template'],'features':ast_features(row['formula'])}
    matched=[]
    for target in document['consumed_targets']:
        v=ast_features(target['formula']);prefix=[i for i,row in enumerate(rows) if ast_features(row['formula'])[:10]==v[:10]];full=[i for i,row in enumerate(rows) if ast_features(row['formula'])==v]
        assert target['features']==v and target['first10_matching_new_training_indices']==prefix and target['full16_matching_new_training_indices']==full and full
        matched.append({'candidate_id':target['candidate_id'],'prefix_matches':len(prefix),'full16_matches':full})
    assert len(matched)==4
    check_bindings(document['sources_sha256'])
    return {'artifact_sha256':sha(OUT/'input-coverage-audit.json'),'training_AST_rows_replayed':32,'consumed_target_input_profiles':matched,'no_new_target_labels_used':True,'scope':'Input representation coverage only; no physical cost transfer claim.'}



_NEW_MODELS=None
_MODEL_FORENSICS=None

def models():
    global _NEW_MODELS,_MODEL_FORENSICS
    if _NEW_MODELS is not None:return _NEW_MODELS,_MODEL_FORENSICS
    import numpy as np,joblib
    p=authenticate();seal=read(OUT/'model-freeze.json');check_bindings(seal['files_sha256'],OUT)
    assert seal['fits_completed']==2 and seal['wall_seconds']<=120 and seal['protocol_sha256']==sha(OUT/'protocol.json') and seal['feature_freeze_sha256']==sha(OUT/'feature-freeze.json')
    rows=read(ROOT/'results/feature-comparison/rows.json');cols=read(ROOT/'results/feature-comparison/columns.json')
    with np.load(ROOT/'results/feature-comparison/inputs.npz',allow_pickle=False) as d:xs=[d['x'][:,[cols.index(n) for n in p['base_columns']]]];ys=[d['y']]
    for folder,count in ((ROOT/'results/targeted-coverage-data',64),(ROOT/'results/guarded-revision-data',32),(ROOT/'results/signed-refinement-data',32),(ROOT/'results/budget-release-data',32),(TRAIN,32)):
        r=read(folder/'candidates.json');labels=read(folder/'labels.json');assert len(r)==len(labels)==count and [v['candidate_id'] for v in r]==[v['candidate_id'] for v in labels]
        assert all(v['status']=='complete' and v['formula']==row['formula'] for row,v in zip(r,labels));rows.extend(r);xs.append(feature_matrix(read(folder/'features.json')));ys.append(np.asarray([v['lut4'] for v in labels]))
    x=np.vstack(xs);y=np.concatenate(ys);aug=np.hstack([x,np.asarray([ast_features(r['formula']) for r in rows])]);assert x.shape==(1857,217) and aug.shape==(1857,233) and y.shape==(1857,)
    expected=[{'training_index':i,'candidate_id':r.get('candidate_id','original:'+str(i)),'formula':r['formula'],'actual_lut4':float(y[i]),'source':'original1665' if i<1665 else 'frozen_extra160' if i<1825 else 'new_training32'} for i,r in enumerate(rows)]
    manifest=read(OUT/'training-manifest.json');assert manifest['rows']==expected and manifest['consumed_evaluation_labels_fitted']==0
    with np.load(OUT/'training-inputs.npz',allow_pickle=False) as d:assert set(d.files)=={'coverage','augmented','y'} and np.array_equal(d['coverage'],x) and np.array_equal(d['augmented'],aug) and np.array_equal(d['y'],y)
    run=read(OUT/'run-start.json');assert read(TRAIN/'completion.json')['completed_at_utc']<run['started_at_utc']<seal['frozen_at_utc']
    assert run['training_labels_sha256']==sha(TRAIN/'labels.json') and run['training_features_sha256']==sha(TRAIN/'features.json') and run['planned_fits']==run['maximum_fits']==2
    timings=read(OUT/'timings.json');assert [(v['index'],v['kind']) for v in timings]==[(1,'augmented'),(2,'coverage')]
    assert sorted(v.name for v in OUT.glob('fit-attempt-*.json'))==['fit-attempt-1.json','fit-attempt-2.json']
    oldmodel=joblib.load(ROOT/'models/base/model.joblib').estimator;result={};reports={};starts=[]
    for i,(kind,matrix) in enumerate((('augmented',aug),('coverage',x)),1):
        meta=read(OUT/(kind+'.json'));model=joblib.load(OUT/(kind+'.joblib'));attempt=read(OUT/('fit-attempt-'+str(i)+'.json'));starts.append(attempt['started_at_utc'])
        assert meta['columns']==p['base_columns']+(list(AST_COLUMNS) if kind=='augmented' else []) and meta['training_count']==1857 and meta['old_training_count']==1825 and meta['new_training_count']==32 and meta['consumed_labels_fitted']==0 and meta['calibration']=='uncalibrated' and meta['upper_lut4'] is None
        assert meta['artifact_sha256']==sha(OUT/(kind+'.joblib')) and meta['protocol_sha256']==sha(OUT/'protocol.json') and meta['runtime_versions']==p['runtime_versions']
        assert model.get_params(deep=False)==oldmodel.get_params(deep=False) and all(model.get_params()[k]==v for k,v in p['policy']['configuration'].items())
        assert attempt['fit_index']==i and attempt['kind']==kind and attempt['training_count']==1857 and attempt['feature_count']==matrix.shape[1] and attempt['training_inputs_sha256']==sha(OUT/'training-inputs.npz')
        assert timings[i-1]['feature_count']==matrix.shape[1] and timings[i-1]['training_count']==1857 and 0<timings[i-1]['fit_seconds']<=120
        reports[kind]=verify_tree_training(model,matrix,y);result[kind]=model
    assert run['started_at_utc']<starts[0]<starts[1]<seal['frozen_at_utc'] and sum(t['fit_seconds'] for t in timings)<=seal['wall_seconds']
    _NEW_MODELS=result;_MODEL_FORENSICS={'training_rows':1857,'frozen_training_rows':1825,'new_training_rows':32,'consumed_evaluation_labels_fitted':0,'ordered_manifest_and_all_arrays_exactly_reconstructed':True,'training_inputs_sha256':sha(OUT/'training-inputs.npz'),'fits':reports}
    return result,_MODEL_FORENSICS


def authenticate():
    import platform,numpy,sklearn,joblib
    p=read(OUT/'protocol.json');plan=read(TRAIN/'plan.json');pool=read(TEST/'pool-candidates.json');train=read(TRAIN/'candidates.json')
    assert p['schema']=='isaforge-boundary-coverage-v1' and p['planned_fits']==p['maximum_fits']==2 and p['maximum_fit_seconds']==120 and p['fit_threads']==1 and p['total_training_rows']==1857 and p['consumed_labels_fitted']==0
    assert p['runtime_versions']=={'python':platform.python_version(),'numpy':numpy.__version__,'sklearn':sklearn.__version__,'joblib':joblib.__version__}
    assert p['gates']['tolerance']==TOL and p['retained_panels']==COUNTS and sum(COUNTS.values())==897
    assert p['policy']['fit_order']==['augmented233','coverage217'] and p['policy']['configuration']==read(ROOT/'results/budget-release/protocol.json')['configuration']
    assert p['policy']['learned_decision']=='On learning scope, for each cap32/64/128 require signed<=cap<previous_structural AND newly trained RAW MEAN<=cap. Return smallest qualifying cap; otherwise previous_structural exactly. Outside scope previous_structural exactly. No margin, additional median or threshold tuning.'
    assert len(p['base_columns'])==len(set(p['base_columns']))==217 and p['augmented_columns']==p['base_columns']+list(AST_COLUMNS)
    assert p['local_features']['columns']==list(AST_COLUMNS) and p['local_features']['count']==16 and 'LOW5' in p['local_features']['widths']
    assert p['selection']['general_count']==32 and p['selection']['shared_controls']==8 and p['selection']['challenge_count']==96 and p['selection']['maximum_active']==16 and p['selection']['minimum_active']==4 and p['selection']['minimum_templates']==2 and p['selection']['requires_cap128'] is True
    assert len(train)==32 and all(ast_learning_scope(r['formula']) for r in train)
    assert len(pool)==128 and all(r['pool_index']==i for i,r in enumerate(pool)) and [i for i,r in enumerate(pool) if r['cohort']=='general']==list(range(32)) and [i for i,r in enumerate(pool) if r['reserved_control']]==list(range(24,32))
    assert sum(ast_learning_scope(r['formula']) for r in pool[:32])==16 and all(ast_learning_scope(r['formula']) for r in pool[32:])
    for section in ('sources_sha256','inputs_sha256'):check_bindings(p[section])
    assert read(TEST/'plan.json')==plan and plan['schema']=='boundary-coverage-train32-pool128-v1'
    assert plan['training_count']==32 and plan['training_sharing_count']==plan['training_narrow_count']==16 and plan['pool_count']==128 and plan['general_count']==32 and plan['general_learning_scope_count']==16 and plan['general_existing_scope_only_count']==8 and plan['general_control_count']==8 and plan['challenge_pool_count']==96 and plan['maximum_selected_count']==48
    assert plan['policy']=={'total_native_seconds':300,'workers':2,'fits':0,'retries':0,'replacement_candidates':0,'random_vectors':2048,'vectors_per_formula':2148,'caps_lut4':[32,64,128]}
    for section in ('sources','inputs','prior_inventory_sources'):check_bindings(plan[section])
    for tool in read(TRAIN/'tools.json').values():assert sha(tool['path'])==tool['sha256']
    assert read(OUT/'goal-update-at-freeze.json')['relationship_to_original_goal'].startswith('Clarifies')
    input_coverage_audit()
    return p


def frozen_bindings():
    files=[OUT/n for n in ('protocol.json','auditor-prior-artifacts.json','goal-at-freeze.json','goal-update-at-freeze.json','input-coverage-audit.json')]
    files += [folder/n for folder in (TRAIN,TEST) for n in ('plan.json','novelty.json','historical-formulas.json','tools.json')]+[TRAIN/'candidates.json',TEST/'pool-candidates.json']
    return {str(p.relative_to(ROOT)):sha(p) for p in files}


def preflight(write=False):
    p=authenticate();count=preserved();identities=identity_audit()
    if write:
        assert not any((folder/n).exists() for folder in (TRAIN,TEST) for n in ('labels.json','features.json','pool-features.json','label-attempt.json','feature-attempt.json','selection.json'))
        assert not (OUT/'run-start.json').exists()
    return receipt(TRAIN/'preflight-audit.json',{'bindings':frozen_bindings(),'scientific_artifacts_preserved':count,'identity_audit':identities,
        'reviewed_policy':p['policy'],'reviewed_selection':p['selection'],'reviewed_gates':p['gates'],'reviewed_local_features':p['local_features'],
        'input_coverage_audit':input_coverage_audit(),'planned_fits':2,'no_new_features_labels_fits_or_attempts_at_receipt':True,
        'general32_fixed_before_predictions':True,'shared_control_count':8,'shared_controls_not_independent':True,'no_pooled_metric':True},write)



def development():
    authenticate();models();saved=read(OUT/'development-predictions.json');stored=read(OUT/'development-metrics.json');computed={};fields=0
    assert set(saved)==set(COUNTS)
    for name,(row,features) in panel_sources().items():
        assert len(row['actual_lut4'])==COUNTS[name]
        for key,value in row.items():assert saved[name][key]==value,(name,key)
        values,routes,details=points(row,features);assert values==saved[name]['models'] and routes==saved[name]['routes'],name
        for key,value in details.items():assert saved[name][key]==value,(name,key)
        computed[name]=panel_metrics(row['actual_lut4'],values,details['learned_raw_lut4']);fields+=old.compare_metric(stored['panels'][name],computed[name])
    def subset(panel,ix):
        row=saved[panel];return panel_metrics([row['actual_lut4'][i] for i in ix],{n:[v[i] for i in ix] for n,v in row['models'].items()},{n:[v[i] for i in ix] for n,v in row['learned_raw_lut4'].items()})
    def group(panel,folder,template):
        ix=[i for i,r in enumerate(read(ROOT/'results'/folder/'candidates.json')) if r['template']==template];assert len(ix)==4;return subset(panel,ix)
    named={'arithmetic_stress32':computed['arithmetic-stress'],'signed_dual_arithmetic4':group('consumed-second-fresh32','budget-preserving-validation','signed_dual_arithmetic'),
        'signed_add_boolean4':group('consumed-third-fresh40','guarded-revision-validation','heldout_signed_variable_add_boolean'),
        'compound_signed_add_xor4':group('consumed-fourth-fresh40','signed-refinement-validation','heldout_compound_signed_add_xor'),
        'fifth_compound_signed_add_xor4':group('consumed-fifth-fresh40','budget-release-validation','heldout_compound_signed_add_xor'),
        'fifth_compound_signed_xordata_addxor4':group('consumed-fifth-fresh40','budget-release-validation','heldout_compound_signed_xordata_addxor')}
    broad=saved['consumed-sixth-broad40'];named['broad_compound32']=subset('consumed-sixth-broad40',[i for i,f in enumerate(broad['formulas']) if structural_route(f)])
    latest=saved['consumed-seventh-conditional18'];fr=[i for i,y in enumerate(latest['actual_lut4']) if y<=128<latest['models'][RELEASE][i]];fa=[i for i,y in enumerate(latest['actual_lut4']) if any(latest['models'][BROAD][i]<=c<latest['models'][RELEASE][i] and y>c for c in CAPS)]
    assert len(fr)==8 and len(fa)==2;named['eight_corrected_fr']=subset('consumed-seventh-conditional18',fr);named['two_previous_new_fa']=subset('consumed-seventh-conditional18',fa)
    general=saved['consumed-eighth-general32'];four=[i for i,y in enumerate(general['actual_lut4']) if y<=128<general['models'][PREVIOUS][i]];assert len(four)==4
    named['four_confident_fr']=subset('consumed-eighth-general32',four);named['prior_active16']=subset('consumed-eighth-conditional24',list(range(16)))
    # The broad-compound named group uses the predeclared original compound predicate, not the later structural gate.
    named['broad_compound32']=subset('consumed-sixth-broad40',[i for i,f in enumerate(broad['formulas']) if prior.predicates(f)[0]])
    for name,m in named.items():fields+=old.compare_metric(stored['named_regressions'][name],m)
    required=[]
    for panel,ix,groupname in (('consumed-fifth-fresh40',[12],'original125'),('consumed-seventh-conditional18',fr,'later_eight'),('consumed-eighth-general32',[i for i,y in enumerate(general['actual_lut4']) if y<=128<general['models'][RELEASE][i]],'general_five'),('consumed-eighth-conditional24',list(range(16)),'active_sixteen')):
        row=saved[panel]
        for i in ix:required.append({'group':groupname,'candidate_id':row['candidate_ids'][i],'formula':row['formulas'][i],'actual_lut4':row['actual_lut4'][i],'cap':128,'predictions':{n:row['models'][n][i] for n in CANDIDATES}})
    assert len(required)==len({r['candidate_id'] for r in required})==30 and required==stored['required_rejection_cases']
    gates={}
    for n in CANDIDATES:
        decision=saved['consumed-fifth-fresh40']['models'][n][12]<=128 and all(latest['models'][n][i]<=128 for i in fr) and all(latest['models'][n][i]>c for i in fa for c in CAPS if latest['models'][BROAD][i]<=c<latest['models'][RELEASE][i] and latest['actual_lut4'][i]>c) and all(general['models'][n][i]<=128 for i in four)
        gate={'all_thirteen_retained_panels_pass':all(passed(m['checks'][n]) for m in computed.values()),'all_named_subgroups_preserved':all(passed(m['checks'][n]) for m in named.values()),'all_explicit_decision_repairs_pass':decision,
            'all_thirty_required_rejections_repaired':all(r['predictions'][n]<=r['cap'] for r in required),'outside_learning_scope_exact_previous':all(row['models'][n][i]==row['models'][PREVIOUS][i] for row in saved.values() for i,active in enumerate(row['learning_scope']) if not active)}
        gate['development_gate_passed']=all(gate.values());gates[n]=gate
    chosen=next((n for n in CANDIDATES if gates[n]['development_gate_passed']),None)
    assert gates==stored['gates'] and stored['selected_candidate']==chosen and stored['evaluated_candidate']==(chosen or CANDIDATES[0]) and stored['metric_rows']==897 and stored['unique_consumed_circuits']==889 and stored['shared_controls']==8 and stored['no_pooled_metric'] is True
    return {'panels':computed,'named_regressions':named,'required_rejection_cases':required,'gates':gates,'selected_candidate':chosen,'evaluated_candidate':chosen or CANDIDATES[0],'metric_rows':897,'unique_consumed_circuits':889,'shared_controls':8,'no_pooled_metric':True,'numeric_fields_compared':fields,'development_points_replayed':897*7}


def historical_records():
    import numpy as np
    selected=read(OUT/'protocol.json')['base_columns'];columns=read(ROOT/'results/feature-comparison/columns.json');rows=read(ROOT/'results/feature-comparison/rows.json')
    with np.load(ROOT/'results/feature-comparison/inputs.npz',allow_pickle=False) as data:blocks=[data['x'][:,[columns.index(n) for n in selected]]]
    formulas=[r['formula'] for r in rows]
    folders=('targeted-coverage-data','guarded-revision-data','signed-refinement-data','budget-release-data','research-baselines','application-transfer','arithmetic-stress','selection-validation','targeted-coverage-validation','budget-preserving-validation','guarded-revision-validation','signed-refinement-validation','budget-release-validation','boundary-repair-validation')
    paths=[ROOT/'results'/folder/'features.json' for folder in folders]+[ROOT/'results'/folder/n for folder in ('boundary-challenge-validation','boundary-refinement-validation') for n in ('features.json','pool-features.json')]
    for path in paths:
        f=read(path);blocks.append(np.asarray([r['values'] for r in f['records']],dtype=float)[:,[f['columns'].index(n) for n in selected]]);formulas.extend(r['formula'] for r in f['records'])
    history=np.vstack(blocks);assert history.shape==(3042,217) and len(formulas)==3042 and np.isfinite(history).all()
    return formulas,history


def feature_matrix(features):
    import numpy as np
    columns=read(OUT/'protocol.json')['base_columns'];x=np.asarray([r['values'] for r in features['records']],dtype=float)[:,[features['columns'].index(n) for n in columns]]
    assert np.isfinite(x).all() and (x>=0).all()
    return x


def feature_freshness():
    import numpy as np
    formulas,h=historical_records();haug=np.hstack([h,np.asarray([ast_features(f) for f in formulas],dtype=float)])
    tr=read(TRAIN/'candidates.json');pool=read(TEST/'pool-candidates.json');tx=feature_matrix(read(TRAIN/'features.json'));px=feature_matrix(read(TEST/'pool-features.json'))
    t={'coverage':tx,'augmented':np.hstack([tx,np.asarray([ast_features(r['formula']) for r in tr])])};p={'coverage':px,'augmented':np.hstack([px,np.asarray([ast_features(r['formula']) for r in pool])])};reports={}
    assert tx.shape==(32,217) and px.shape==(128,217)
    for kind,history in (('coverage',h),('augmented',haug)):
        known={tuple(float(v) for v in row) for row in history};train_keys=[tuple(float(v) for v in row) for row in t[kind]];both=known|set(train_keys);keys=[tuple(float(v) for v in row) for row in p[kind]];clusters={};reps=[]
        for i,key in enumerate(keys):clusters.setdefault(key,[]).append(i);reps.append(clusters[key][0])
        reports[kind]={'historical_unique_count':len(known),'training_historical_matches':[i for i,k in enumerate(train_keys) if k in known],'training_unique_count':len(set(train_keys)),
            'pool_historical_or_training_matches':[i for i,k in enumerate(keys) if k in both],'pool_cluster_representatives':reps,'pool_duplicate_clusters':[v for v in clusters.values() if len(v)>1]}
    return {'historical_rows':3042,'fitted_rows':1825,'unique_consumed_labels':889,'prior_pool_rows':[200,128],'representations':reports,
        'training_fresh':all(not r['training_historical_matches'] and r['training_unique_count']==32 for r in reports.values()),'equality':'Exact float64 numeric tuples; no rounding, no labels.'}



def native_body(folder,relative):
    path=folder/'raw'/relative
    if path.exists():return path.read_bytes()
    manifest=read(folder/'raw-evidence-manifest.json')
    with zipfile.ZipFile(folder/manifest['archive']) as archive:return archive.read('raw/'+relative)


def pretrain(write=False):
    authenticate();count=preserved();preflight(False);features=read(TRAIN/'feature-completion.json');jobs=old.job_audit(features)
    assert jobs['jobs']==160 and Counter((j['kind'],j['stage']) for j in features['native_worker_jobs'])=={('train','feature'):32,('test','feature'):128}
    assert features['native_elapsed_seconds']==features['total_native_elapsed_seconds']<=300
    assert read(TRAIN/'preflight-audit.json')['audited_at_utc']<read(TRAIN/'feature-attempt.json')['started_at_utc']
    for kind,folder,filename,expected in (('train',TRAIN,'features.json',32),('test',TEST,'pool-features.json',128)):
        records=read(folder/filename)['records'];assert len(records)==expected
        for j in features['native_worker_jobs']:
            if j['kind']!=kind:continue
            index=j['index'];prefix='features/'+str(index)+'/'
            assert json.loads(native_body(folder,prefix+'worker.json'))==j and digest(native_body(folder,prefix+'worker.log'))==j['log_sha256'] and json.loads(native_body(folder,prefix+'result.json'))==records[index]
    fresh=feature_freshness();assert fresh==read(OUT/'feature-freshness.json')
    seal=read(OUT/'feature-freeze.json');assert seal['training_fresh']==fresh['training_fresh'] and seal['protocol_sha256']==sha(OUT/'protocol.json');check_bindings(seal['bindings'])
    assert features['completed_at_utc']<seal['frozen_at_utc']
    if write:assert not any((folder/n).exists() for folder in (TRAIN,TEST) for n in ('labels.json','label-attempt.json')) and not (OUT/'run-start.json').exists()
    paths=[TRAIN/'feature-completion.json',TRAIN/'features.json',TEST/'pool-features.json',OUT/'feature-freshness.json',OUT/'feature-freeze.json']
    return receipt(TRAIN/'pretrain-audit.json',{'bindings':{**frozen_bindings(),**{str(p.relative_to(ROOT)):sha(p) for p in paths}},'scientific_artifacts_preserved':count,
        'feature_jobs':160,'feature_native_seconds':features['native_elapsed_seconds'],'recorded_worker_peak':jobs['peak_recorded_workers'],'feature_freshness':fresh,
        'training_feature_eligibility':fresh['training_fresh'],'new_training_and_fresh_labels_attempts_absent_at_receipt':True,'feature_records_and_worker_logs_authenticated':160,
        'independent_AST_feature_values_replayed':3042+32+128,'audit_fits':0,'audit_native_jobs':0},write)



def select(pool,values,fresh,evaluated):
    general=list(range(32));controls=list(range(24,32));reps={k:r['pool_cluster_representatives'] for k,r in fresh['representations'].items()};historical=set().union(*(r['pool_historical_or_training_matches'] for r in fresh['representations'].values()));generalkeys={k:{v[i] for i in general} for k,v in reps.items()}
    raw=[i for i,r in enumerate(pool) if r['cohort']=='challenge' and any(values[evaluated][i]<=c<values[PREVIOUS][i] for c in CAPS)];excluded=[i for i in raw if any(reps[k][i] in generalkeys[k] for k in reps)];eligible=[i for i in raw if i not in excluded and i not in historical];groups={}
    for i in eligible:groups.setdefault(pool[i]['template'],[]).append(i)
    cursor={k:0 for k in groups};seen={k:set(v) for k,v in generalkeys.items()};active=[];skipped=[]
    while len(active)<16:
        progress=False
        for template in sorted(groups):
            if len(active)>=16:break
            group=groups[template]
            while cursor[template]<len(group) and any(reps[k][group[cursor[template]]] in seen[k] for k in reps):skipped.append(group[cursor[template]]);cursor[template]+=1
            if cursor[template]<len(group):
                i=group[cursor[template]];cursor[template]+=1;active.append(i);progress=True
                for k in reps:seen[k].add(reps[k][i])
        if not progress:break
    result={'general_pool_indices':general,'reserved_control_pool_indices':controls,'raw_active_pool_indices':raw,'eligible_active_pool_indices':eligible,'historical_collision_active_pool_indices':[i for i in raw if i in historical],
        'general_feature_collision_active_pool_indices':excluded,'skipped_duplicate_active_pool_indices':skipped,'selected_active_pool_indices':active,'selected_pool_indices':general+active}
    selected=general+active;checks={}
    for kind,r in fresh['representations'].items():
        keys=r['pool_cluster_representatives'];history=set(r['pool_historical_or_training_matches']);checks[kind+'_general_feature_novel']=not bool(history&set(general));checks[kind+'_general_unique']=len({keys[i] for i in general})==32;checks[kind+'_selected_unique']=len({keys[i] for i in selected})==len(selected)
    templates=sorted({pool[i]['template'] for i in active});caps={str(c):sum(values[evaluated][i]<=c<values[PREVIOUS][i] for i in active) for c in CAPS}
    checks.update({'at_least_four_new_learned_corrections':len(active)>=4,'at_least_two_templates':len(templates)>=2,'at_least_one_cap128':caps['128']>=1})
    coverage={'pool_count':128,'general_count':32,'shared_control_count':8,'raw_active_count':len(raw),'eligible_active_count':len(eligible),'selected_active_count':len(active),'selected_templates':templates,'correction_caps':caps,'unique_label_count':len(selected),'conditional_count':len(active)+8,'checks':checks,'passed':all(checks.values())}
    return result,coverage


def fresh_points():
    authenticate();pool=read(TEST/'pool-candidates.json');features=read(TEST/'pool-features.json');saved_pool=read(OUT/'pool-predictions.json');dev=development();evaluated=dev['evaluated_candidate']
    assert saved_pool['candidate_ids']==[r['candidate_id'] for r in pool] and saved_pool['formulas']==[r['formula'] for r in pool] and saved_pool['templates']==[r['template'] for r in pool]
    values,routes,details=points(saved_pool,features);assert saved_pool['models']==values and saved_pool['routes']==routes
    for key,value in details.items():assert saved_pool[key]==value,key
    freshness=feature_freshness();assert freshness==read(OUT/'feature-freshness.json');selection,coverage=select(pool,values,freshness,evaluated);stored=read(TEST/'selection.json')
    for key,value in selection.items():assert stored[key]==value,key
    assert stored['coverage']==coverage and stored['labels_present'] is False and stored['evaluated_candidate']==evaluated and stored['pool_predictions_sha256']==sha(OUT/'pool-predictions.json')
    indices=selection['selected_pool_indices'];rows=read(TEST/'candidates.json');assert rows==[pool[i] for i in indices] and read(TEST/'features.json')=={'columns':features['columns'],'records':[features['records'][i] for i in indices]}
    saved=read(OUT/'fresh-predictions.json')
    for key in ('candidate_ids','formulas','templates','routes','structural_scope','applied_qualifying_caps_lut4','forest_medians_lut4','qualifying_caps_lut4','learning_scope'):assert saved[key]==[saved_pool[key][i] for i in indices],key
    for key in ('models','tree_predictions_above_cap','learned_raw_lut4','learned_supported_caps_lut4'):assert saved[key]=={n:[v[i] for i in indices] for n,v in saved_pool[key].items()},key
    assert saved['general_selected_indices']==list(range(32)) and saved['active_selected_indices']==list(range(32,len(indices))) and saved['shared_control_selected_indices']==list(range(24,32)) and saved['conditional_selected_indices']==list(range(32,len(indices)))+list(range(24,32))
    assert saved['selection_coverage']==coverage and saved['selected_candidate']==saved_pool['selected_candidate']==dev['selected_candidate'] and saved['evaluated_candidate']==saved_pool['evaluated_candidate']==evaluated
    seal=read(OUT/'fresh-point-freeze.json');assert seal['fresh_labels_present'] is False and seal['new_fits']==0;check_bindings(seal['bindings'])
    bridge=read(TEST/'point-freeze.json');assert bridge['target_label_jobs']==0;check_bindings(bridge['bindings'])
    assert read(OUT/'model-freeze.json')['frozen_at_utc']<saved_pool['created_at_utc']<stored['frozen_at_utc']<seal['frozen_at_utc']
    return saved,dev


def prelabel(write=False):
    authenticate();count=preserved();pretrain(False);jobs=chronology();saved,dev=fresh_points();_,forensics=models()
    if write:assert not any((TEST/n).exists() for n in ('labels.json','label-attempt.json'))
    files=[OUT/n for n in ('feature-freeze.json','feature-freshness.json','model-freeze.json','pool-predictions.json','fresh-point-freeze.json','fresh-predictions.json','cached-inference-check.json')]+[TRAIN/'completion.json',TRAIN/'labels.json']+[TEST/n for n in ('selection.json','candidates.json','features.json','point-freeze.json','pool-features.json')]
    return receipt(TEST/'prelabel-audit.json',{'bindings':{**frozen_bindings(),**{str(p.relative_to(ROOT)):sha(p) for p in files}},'scientific_artifacts_preserved':count,'fresh_labels_and_attempts_absent_at_receipt':True,
        'fresh_predictions_replayed':len(saved['candidate_ids'])*7,'all_pool_predictions_replayed':896,'development_predictions_replayed':897*7,'feature_freshness':feature_freshness(),'selection_coverage':saved['selection_coverage'],
        'development':dev,'matched_training_forensics':forensics,'training_raw_evidence':raw_audit(TRAIN),'cached_inference':cached_inference(saved),'native_accounting_to_date':jobs,
        'weights_all_pool_points_and_exact_selected_subset_before_labels':True,'general32_fixed_before_predictions':True,'shared_control_count':8,'shared_controls_not_independent':True,'no_pooled_metric':True},write)



def cached_inference(saved):
    path=OUT/'cached-inference-check.json';cache=read(path)
    assert cache['model']==saved['evaluated_candidate'] and cache['selected_candidate']==saved['selected_candidate'] and cache['fits']==cache['native_jobs']==0 and cache['calibration_status']=='uncalibrated' and cache['upper_lut4'] is None
    for key in ('candidate_ids','formulas','models','routes','structural_scope','applied_qualifying_caps_lut4','forest_medians_lut4','qualifying_caps_lut4','tree_predictions_above_cap','learning_scope','learned_raw_lut4','learned_supported_caps_lut4'):assert cache[key]==saved[key],key
    assert cache['predicted_lut4']==saved['models'][saved['evaluated_candidate']] and cache['protocol_sha256']==sha(OUT/'protocol.json') and cache['features_sha256']==sha(TEST/'features.json') and cache['candidates_sha256']==sha(TEST/'candidates.json')
    return {'artifact_sha256':sha(path),'predictions_replayed':len(saved['candidate_ids']),'all_seven_models_and_raw_learning_details_replayed':True,'fits':0,'native_jobs':0,'source':'cached features and original AST only'}



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





def descriptive_diagnostics(saved,actual,rows):
    path=OUT/'failure-diagnostics.json';document=read(path);cases=[]
    for i in saved['general_selected_indices']:
        y=actual[i];signed=saved['models'][CURRENT][i];release=saved['models'][RELEASE][i];refined=saved['models'][CANDIDATE][i]
        remaining=[c for c in CAPS if y<=c and signed<=c<refined]
        corrected=[c for c in CAPS if y<=c<release and refined<=c]
        if not remaining and not corrected:continue
        cases.append({'selected_index':i,'pool_index':rows[i]['pool_index'],'candidate_id':rows[i]['candidate_id'],'template':rows[i]['template'],'parameter':rows[i]['parameter'],'formula':rows[i]['formula'],
            'actual_lut4':y,'signed_lut4':signed,'release_lut4':release,'broad_median_lut4':saved['models'][BROAD][i],'refined_lut4':refined,
            'forest_median_lut4':saved['forest_medians_lut4'][i],'structural_scope':saved['structural_scope'][i],
            'remaining_fr_caps_vs_signed':remaining,'corrected_fr_caps_vs_release':corrected})
    assert document['cases']==cases and 'descriptive' in document['scope'] and 'no policy' in document['scope']
    return {'diagnostic_sha256':sha(path),'numeric_identity_formula_parameter_scope_and_cap_fields_replayed':len(cases),
        'remaining_false_rejection_circuit_budget_events':sum(len(r['remaining_fr_caps_vs_signed']) for r in cases),
        'corrected_false_rejection_circuit_budget_events':sum(len(r['corrected_fr_caps_vs_release']) for r in cases),
        'postlabel_descriptive_only':True,'no_new_rule_or_eligibility_change':True}



def final_audit(write=False):
    protocol=authenticate();count=preserved();prelabel(False);jobs=chronology(True);saved,dev=fresh_points();_,forensics=models()
    rows=read(TEST/'candidates.json');labels=read(TEST/'labels.json');assert saved['candidate_ids']==[r['candidate_id'] for r in labels]
    y=[r['lut4'] for r in labels];scored=read(OUT/'fresh-metrics.json')
    def subset(ix):return panel_metrics([y[i] for i in ix],{n:[v[i] for i in ix] for n,v in saved['models'].items()},{n:[v[i] for i in ix] for n,v in saved['learned_raw_lut4'].items()})
    general=subset(saved['general_selected_indices']);conditional=subset(saved['conditional_selected_indices']);active=subset(saved['active_selected_indices']) if saved['active_selected_indices'] else None
    fields=old.compare_metric(scored['models'],general)+old.compare_metric(scored['conditional_models'],conditional)
    if active:fields+=old.compare_metric(scored['active_subgroup'],active)
    else:assert scored['active_subgroup'] is None
    gates={}
    for n in CANDIDATES:
        ix=[i for i in saved['active_selected_indices'] if any(saved['models'][n][i]<=c<saved['models'][PREVIOUS][i] for c in CAPS)]
        activity={'new_corrections':len(ix),'templates':len({saved['templates'][i] for i in ix}),'cap128':sum(saved['models'][n][i]<=128<saved['models'][PREVIOUS][i] for i in ix)}
        activity_pass=activity['new_corrections']>=4 and activity['templates']>=2 and activity['cap128']>=1
        checks={'coverage':saved['selection_coverage'],'model_specific_activity':activity,'model_specific_activity_passes':activity_pass,'general_no_loss':passed(general['checks'][n]),'general_strict_signed':accuracy(general[CURRENT],general[n],True),
            'general_strict_fa_gain_signed':sum(general[n]['caps'][str(c)]['false_accept'] for c in CAPS)<sum(general[CURRENT]['caps'][str(c)]['false_accept'] for c in CAPS),
            'conditional_full_passes':passed(conditional['checks'][n]),'active_subset_passes':bool(active and passed(active['checks'][n]))}
        ok=checks['coverage']['passed'] and activity_pass and checks['general_no_loss'] and all(checks['general_strict_signed'].values()) and checks['general_strict_fa_gain_signed'] and checks['conditional_full_passes'] and checks['active_subset_passes']
        gates[n]={'checks':checks,'fresh_gate_passed':ok,'development_gate_passed':dev['gates'][n]['development_gate_passed'],'eligible':ok and dev['selected_candidate']==n}
    chosen=dev['selected_candidate'];evaluated=dev['evaluated_candidate'];eligible=bool(chosen and gates[chosen]['eligible'])
    assert gates==scored['gates'] and scored['scoped_experimental_eligibility']==eligible and scored['selected_candidate']==chosen and scored['evaluated_candidate']==evaluated
    assert scored['selection_coverage']==saved['selection_coverage'] and scored['no_pooled_metric'] is True and scored['general_count']==32 and scored['conditional_count']==len(saved['conditional_selected_indices']) and scored['active_count']==len(saved['active_selected_indices']) and scored['shared_controls']==8 and scored['unique_label_count']==len(y) and scored['fits']==2 and scored['native_jobs']==0 and scored['fresh_labels_sha256']==sha(TEST/'labels.json')
    templates={}
    for t in sorted({r['template'] for r in rows}):templates[t]=subset([i for i,r in enumerate(rows) if r['template']==t])
    def decisions(ix,n):
        result={}
        for reference in (CURRENT,RELEASE,PREVIOUS):
            caps={}
            for cap in CAPS:
                cases=[]
                for i in ix:
                    before=saved['models'][reference][i];after=saved['models'][n][i]
                    if (before<=cap)==(after<=cap):continue
                    event=('corrected_false_reject' if y[i]<=cap else 'new_false_accept') if after<=cap else ('new_false_reject' if y[i]<=cap else 'corrected_false_accept')
                    cases.append({'candidate_id':rows[i]['candidate_id'],'formula':rows[i]['formula'],'template':rows[i]['template'],'actual_lut4':y[i],'reference_lut4':before,'learned_lut4':after,'trained_raw_mean_lut4':saved['learned_raw_lut4'][n][i],'event':event})
                feasible=sum(y[i]<=cap for i in ix);caps[str(cap)]={'actual_feasible':feasible,'actual_infeasible':len(ix)-feasible,'changed_decisions':cases}
            result[reference]=caps
        return result
    checks=gates[evaluated]['checks'];scientific={
        'development_selected_candidate_exists':chosen is not None,'all_thirty_known_required_repairs':all(r['predictions'][evaluated]<=r['cap'] for r in dev['required_rejection_cases']),
        'four_confident_FR_and_two_prior_FA_protections':dev['gates'][evaluated]['all_explicit_decision_repairs_pass'],
        'all_thirteen_retained_panels897_rows889_unique_preserved':dev['gates'][evaluated]['all_thirteen_retained_panels_pass'],
        'all_eleven_named_groups_including_prior_active16_preserved':dev['gates'][evaluated]['all_named_subgroups_preserved'],
        'fresh_general_strict_signed_accuracy_and_FA_gains':all(checks['general_strict_signed'].values()) and checks['general_strict_fa_gain_signed'],
        'fresh_general_no_loss_to_release_and_previous_or_added_signed_FR':checks['general_no_loss'],
        'new_learned_activity_four_cases_two_templates_cap128':checks['coverage']['passed'] and checks['model_specific_activity_passes'],
        'conditional_full_no_loss_and_FR_gates':checks['conditional_full_passes'],'active_only_no_loss_and_FR_gates':checks['active_subset_passes'],
        'zero_consumed_labels_fitted_verified_by_ordered_matrix_and_all_tree_leaves':forensics['consumed_evaluation_labels_fitted']==0,
        'features_cohorts_gates_and_fixed_fit_hierarchy_before_labels_and_weights_points_before_test_labels':True,
        'bounded_two_fits_single_thread_300native_seconds_peak_two':jobs['new_fits']==2 and jobs['total_native_seconds']<=300 and jobs['recorded_worker_peak']<=2,
        'all_prior_scientific_artifacts_preserved_and_only_goal_status_mutable':count==len(read(OUT/'auditor-prior-artifacts.json')['files']),
        'independent_RTL_netlist_source_chronology_cached_inference_audits_pass':True,'shared_controls_disclosed_no_pooled_or_independent_cohort_claim':True}
    assert all(scientific.values())==eligible
    raw={kind:raw_audit(folder) for kind,folder in (('train',TRAIN),('test',TEST))}
    body={'protocol_sha256':sha(OUT/'protocol.json'),'auditor_sha256':sha(Path(__file__)),'scientific_artifacts_preserved':count,'old_data_scripts_models_figures_unchanged':True,'goal_ledger_status_only_mutable':True,
        'fits':2,'new_training_rows':32,'total_training_rows':1857,'matched_training_forensics':forensics,'native_accounting':jobs,'identity_audit':identity_audit(),'feature_freshness':feature_freshness(),'input_coverage_audit':input_coverage_audit(),
        'training_and_fresh_raw_evidence':raw,'cached_inference':cached_inference(saved),'development':dev,'fresh_general32':general,'fresh_conditional_full':conditional,'fresh_active_only':active,
        'fresh_template_metrics_descriptive':templates,'fresh_gates':gates,'selected_candidate':chosen,'evaluated_candidate':evaluated,'scoped_experimental_eligibility':eligible,
        'selection_coverage':saved['selection_coverage'],'pool_count':128,'selected_unique_label_count':len(y),'shared_control_count':8,'shared_control_selected_indices':saved['shared_control_selected_indices'],'shared_controls_not_independent':True,
        'general_cap_decision_cases':decisions(saved['general_selected_indices'],evaluated),'conditional_full_cap_decision_cases':decisions(saved['conditional_selected_indices'],evaluated),'active_only_cap_decision_cases':decisions(saved['active_selected_indices'],evaluated),
        'selected_numeric_fields_compared':fields,'development_predictions_replayed':897*7,'all_pool_predictions_replayed':128*7,'selected_predictions_replayed':len(y)*7,'all_predictions_replayed':897*7+128*7+len(y)*7,
        'old_forest_tree_outputs_replayed':(897+128)*300,'new_training_leaf_assignments_replayed':1857*300*2,
        'zero_consumed_evaluation_labels_fitted':True,'all_training_inputs_targets_and16_AST_features_independently_reconstructed':True,
        'policy_cohorts_and_fit_hierarchy_before_features_and_new_labels':True,'both_fixed_models_and_all_pool_points_selection_before_test_labels':True,
        'mape_definition':'100*mean(abs(actual-predicted)/actual) over actual>0; zero-target rows remain in MAE, tail and per-cap denominators and are excluded only from MAPE.',
        'false_acceptance_sum_unit':'circuit-budget events, not unique circuits; per-cap feasible/infeasible counts and changed-case identities are reported separately',
        'scientific_goal_requirement_checks':scientific,'scientific_goal_requirements_passed':all(scientific.values()),'goal_completion_verified':False,'publication_and_full_validation_verification_pending':True,
        'no_pooled_metric':True,'conditional_population_not_representative':True,'general_population_fixed_targeted_synthetic_not_representative':True,
        'mathematical_bounds':'signed<=candidate<=previous_structural<=release; prior accepted repairs cannot become rejected by upward drift. Separate FA<=release and FR<=signed caps permit no new mistakes by count offsets.',
        'limitations':['Matched fixed217/233forests use the same1857training rows; augmentation versus coverage is selected on consumed development only, with no postfresh model switch.','Learned means support physical caps only inside a development-informed local AST scope; this is not a global regressor replacement, calibrated bound or universal safety.','Fresh general and prediction-conditioned active populations are separate, with8shared controls explicitly reused; no pooled or independent-cohort claim.','All128pool features and all32training inputs/labels remain retained, including unselected pool rows and failed or unpromoted candidates.','Finite originalRTL vectors and mappedcell recounts are not universal equivalence, mappednetlist functional proof, application independence, timing, power or CPU-performance evidence.','Prospective activity coverage remains binding even when development repairs succeed; insufficient new cases/templates blocks promotion and goal completion.']}
    return receipt(OUT/'audit.json',body,write)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('command',choices=('preflight','pretrain','prelabel','final'),nargs='?',default='final');parser.add_argument('--write-receipt',action='store_true');args=parser.parse_args()
    result=globals()[{'final':'final_audit'}.get(args.command,args.command)](args.write_receipt)
    print(json.dumps({'status':result['status'],'receipt_created':args.write_receipt,'audit_fits':0,'audit_native_jobs':0,**{k:result[k] for k in ('selected_candidate','scoped_experimental_eligibility','native_accounting','fresh_predictions_replayed') if k in result}},indent=2))
