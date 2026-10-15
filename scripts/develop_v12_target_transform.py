#!/usr/bin/env python3
"""V12 input-only preparation and separately released30-fit target-scale study.

Same1713 original targets and217 saved features; two target views, five NEW
leakage-closed folds, three paired seeds. Never extract features, normalize with
SMT, open evaluation targets, tune parameters or fit a31st deployment model.
"""
from __future__ import annotations
import argparse
from collections import Counter,defaultdict
from datetime import datetime,timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import joblib
import numpy as np
from sklearn.ensemble import ExtraTreesRegressor
import sklearn.ensemble._forest as forest_runtime
import sklearn.tree._tree as tree_runtime
from threadpoolctl import threadpool_limits
from isaforge import area_model_v6 as v6
from isaforge.features import parse_formula
from isaforge.v5_corpus import equivalence_key,skeleton

V9='results/2026-10-15-v9-coverage-development'
V5='results/2026-10-14-v5'
V8_TRAINING='results/2026-10-15-v8-application-transfer/training/training-data.json'
V9_PREPARATION_SHA='468d264af46134f6717e317c9fcdc10c47f0f45e5938ec5da2999793d2977dca'
V9_POINT_SHA='ba377ae7ee17d7f656a1e05e5139fa98ec04f1b63d29d73e9322662eabe333bc'
SCHEMA='isaforge-v12-target-transform-preparation-v1'
SEEDS=(2026101421,2026101422,2026101423)
VIEWS=('raw','log1p')
STRATA=('arithmetic_chain','comparators','constant_shifts','mask_logic','multiplication','parallel_branches','shared_diamond','variable_shifts','workload')
CAPS=(32,64,128)
PARAMETERS={'n_estimators':300,'criterion':'squared_error','min_samples_leaf':1,'max_features':1.0,'n_jobs':1}
PRODUCT_CONTEXTS=('direct_product','add_after_product','sub_before_product','masked_sub_before_product')
SHIFT_CONTEXTS=('add_signed_shift_sign_sub','sub_signed_shift_sign_sub')


def need(condition,message):
    if not condition:raise ValueError(message)

def now():return datetime.now(timezone.utc).isoformat()
def utc(value):
    need(type(value) is str,'UTC timestamp required')
    result=datetime.fromisoformat(value.replace('Z','+00:00'))
    need(result.tzinfo is not None and result.utcoffset().total_seconds()==0,'UTC-aware timestamp required')
    return result
def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def digest(value):return hashlib.sha256(canonical(value)).hexdigest()
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):
    def unique(items):
        out={}
        for key,value in items:
            need(key not in out,'Duplicate JSON key');out[key]=value
        return out
    return json.loads(Path(path).read_bytes(),object_pairs_hook=unique)
def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x') as stream:json.dump(value,stream,indent=2,allow_nan=False);stream.write('\n')
def record(path,root):return {'path':os.path.relpath(Path(path).resolve(),Path(root).resolve()),'sha256':sha(path)}
def source_paths():
    return [Path(__file__).resolve(),ROOT/'tests/test_develop_v12_target_transform.py',ROOT/'docs/v12-model-direction.md',
        ROOT/'scripts/audit_v12_target_transform.py',ROOT/'tests/test_audit_v12_target_transform.py',*sorted((ROOT/'isaforge').glob('*.py'))]
def check_hashes(bindings):
    need(all(path.is_file() and sha(path)==value for path,value in bindings.items()),'Source/input/runtime bytes changed')
def numeric(values,shape):
    data=np.asarray(values,dtype=np.float64)
    need(data.shape==shape and np.isfinite(data).all() and np.all(data>=0),'Complete finite nonnegative numeric matrix required')
    return data

def selected_float32(full,indices):
    selected=np.asarray(full[:,indices],dtype='<f4').copy(order='C')
    need(np.isfinite(selected).all(),'Selected features overflow float32')
    selected[selected==0]=0 # signed zero compares identically inside the learner
    return selected


def runtime():
    files=[Path(sys.executable).resolve(),Path(forest_runtime.__file__).resolve(),Path(tree_runtime.__file__).resolve()]
    return {'python':platform.python_version(),'packages':{name:importlib.metadata.version(name) for name in ('numpy','scipy','scikit-learn','joblib','threadpoolctl')},
        'files':[{'path':str(p),'sha256':sha(p)} for p in files],
        'boundary':'Versioned same-host fitting runtime, not a hermetic OS or complete shared-library image.'}


def recipe():
    return {'schema':'isaforge-v12-target-transform-recipe-v1','training_rows':1713,'original_rows':1665,'coverage_rows':48,
        'selected_feature_columns':list(v6.mapping_columns()),'selected_indices':[int(i) for i in v6.mapping_indices()],
        'full_columns':list(v6.columns()),'matrix_dtype':'little-endian float32; signed zero normalized','seeds':list(SEEDS),
        'target_views':list(VIEWS),'parameters':PARAMETERS,'folds':5,'maximum_fits':30,
        'decode':{'raw':'max(0,forest_mean)','log1p':'max(0,expm1(forest_mean_log))'},
        'original_zero_override':'Both views force0 only when saved original_gate_count==0; after inverse transform.',
        'group_rules':['inherited_V5_component','canonical_original_or_saved_accepted_form','frozen_commutative_key','new_coverage_context','exact_float32_selected_vector'],
        'component_order':'(-row_count,SHA256(compact sorted canonical-formula JSON))',
        'fold_score':'(sum_s component_count[s]*fold_count[s],fold_total_rows,fold_index)',
        'train_validation':'Four folds fit; fifth assessment. Every training partition all9strata; assessment folds nonempty.',
        'primary':'Mean over3 pairedseeds of nine-stratum macro OOF MAE(log1p minus raw)',
        'metrics':['pooled MAE','bias','RMSLE','positive MAPE and denominator','zero MAE and denominator','P95/P99/max absolute error','maximum underprediction','cap32/64/128 FA/FR and feasible denominators','paired changed decisions'],
        'quantile_method':'numpy.quantile method=linear','caps':list(CAPS),'strata':list(STRATA),
        'new_physical_labels':0,'new_feature_extractions':0,'new_solver_queries':0,'evaluation_target_reads':0,
        'automatic_retries':False,'hyperparameter_search':False,'final_refit':False,'smearing':False,'sample_weights':False,
        'scope':'Fitting-only consumed development. No calibration, application acquisition, CPU or fresh transfer claim.'}


def saved_new_forms(record):
    original=parse_formula(record['formula']).canonical();forms={original,parse_formula(record['normalized_formula']).canonical()};statuses={}
    need(type(record.get('v7_modes')) is dict,'Saved three-mode proof metadata required')
    for mode in ('bit','affine','combined'):
        stored=record['v7_modes'][mode];status=stored['metadata']['status'];statuses[mode]=status
        if status=='accepted':forms.add(parse_formula(stored['normalized_formula']).canonical())
    return sorted(forms),statuses


def load_inputs():
    """Read only whitelisted training/identity sources; no model or eval data."""
    root=ROOT/V9
    names=['preparation.json','recipe.json','original-training.json','consumed-input-ledger.json','identity-analysis.json','candidates.json',
        'measurements/completion.json','measurements/attempt-0000/completion.json','measurements/attempt-0000/labels.json',
        'fit-attempt-0000/coverage-features.json','fit-attempt-0000/point-freeze.json','fit-attempt-0000/models/mapping-coverage.json']
    paths=[root/n for n in names]+[ROOT/V5/'development-data.json',ROOT/V5/'split.json',ROOT/V8_TRAINING]
    before={p:sha(p) for p in paths}
    prep,old_recipe,base,ledger,identities,candidates,done,stage_done,labels,features,point,model=[read(root/n) for n in names]
    need(sha(root/'preparation.json')==V9_PREPARATION_SHA and sha(root/'fit-attempt-0000/point-freeze.json')==V9_POINT_SHA,'Exact frozen V9 preparation/fit point required')
    bound={(root/e['path']).resolve():e['sha256'] for e in prep['files']}
    for n in ('recipe.json','original-training.json','consumed-input-ledger.json','identity-analysis.json','candidates.json'):
        need(bound.get((root/n).resolve())==sha(root/n),'V9 input is absent from original freeze: '+n)
    need(done==stage_done and done.get('complete') is True and done.get('failures')==[] and done['candidate_count']==48
        and done['preparation_sha256']==V9_PREPARATION_SHA and done['labels_sha256']==sha(root/names[8]),'Exact successful48 original measurements required')
    need(point['training_rows']==1713 and point['new_fits']==1 and point['preparation_sha256']==V9_PREPARATION_SHA
        and point['schema_sha256']==sha(root/names[11]),'Frozen1713 V9 training lineage differs')
    provenance=model['training_provenance']
    need(provenance['preparation_sha256']==V9_PREPARATION_SHA and provenance['coverage_features_sha256']==sha(root/names[9])
        and provenance['coverage_labels_sha256']==sha(root/names[8]),'Saved original coverage feature/target lineage differs')
    need(base['columns']==features['columns']==list(v6.columns()) and len(base['rows'])==1665 and len(features['records'])==48
        and old_recipe['selected_columns']==list(v6.mapping_columns()) and old_recipe['selected_indices']==[int(i) for i in v6.mapping_indices()], 'Same336/selected217 fitting schema required')
    for name,value in point['source_sha256'].items():need(sha(ROOT/'isaforge'/name)==value,'Frozen original feature source changed')
    source=read(ROOT/V5/'development-data.json');old_split=read(ROOT/V5/'split.json');v8=read(ROOT/V8_TRAINING)
    need(len(source)==2057 and sha(ROOT/V5/'development-data.json')==base['training_provenance']['development_dataset_sha256']
        and sha(ROOT/V5/'split.json')==base['training_provenance']['split_sha256'],'Original fitting metadata/split lineage differs')
    full=numeric(base['values'],(1665,336));v8full=numeric(v8['values'],(1665,455))
    need(v8['rows']==base['rows'] and np.array_equal(full,v8full[:,:336]),'V9 original features must replay frozen V8 training prefix')
    fields={r['formula']:r for r in features['records']};targets={r['formula']:r['lut4_count'] for r in labels};saved={r['formula']:r for r in identities}
    need(len(fields)==len(targets)==len(saved)==len(candidates)==48 and set(fields)==set(targets)==set(saved)=={r['formula'] for r in candidates},'Complete unique48 coverage input join required')
    aliases_by_formula={r['formula']:r['accepted_forms'] for r in ledger['records']}
    need(len(aliases_by_formula)==len(ledger['records']),'Consumed alias originals must be unique')
    rows=[];aliases=[];y=[];statuses=Counter()
    for i,row in enumerate(base['rows']):
        formula=row['formula'];index=row['development_index'];need(type(index) is int and 0<=index<len(source),'Valid fitting metadata index required');metadata=source[index]
        need(type(index) is int and 0<=index<len(source) and metadata['formula']==formula and formula in aliases_by_formula
            and formula in old_split['component_by_formula'],'Fitting development-index/alias/component coverage differs')
        rows.append({'formula':formula,'source':'original1665','development_index':index,'stratum':metadata.get('stratum','workload'),
            'inherited_component':old_split['component_by_formula'][formula]})
        aliases.append(sorted({parse_formula(f).canonical() for f in [formula,*aliases_by_formula[formula]]}));y.append(row['lut4_count'])
    new_values=[]
    for candidate in candidates:
        formula=candidate['formula'];context=candidate['context'];need(context in (*PRODUCT_CONTEXTS,*SHIFT_CONTEXTS),'Fixed six coverage contexts required')
        need(saved[formula]['context']==context and fields[formula]['formula']==formula,'Coverage identity context differs')
        forms,counts=saved_new_forms(saved[formula]);statuses.update(mode+':'+status for mode,status in counts.items())
        rows.append({'formula':formula,'source':'coverage48','context':context,'stratum':'multiplication' if context in PRODUCT_CONTEXTS else 'constant_shifts'})
        need(parse_formula(fields[formula]['normalized_formula']).canonical() in forms,'Saved feature normalization must agree with identity ledger')
        aliases.append(forms);new_values.append(fields[formula]['values']);y.append(targets[formula])
    full=np.vstack((full,numeric(new_values,(48,336))));truth=np.asarray(y,dtype=np.float64)
    need(len(rows)==len({r['formula'] for r in rows})==1713 and set(r['stratum'] for r in rows)==set(STRATA)
        and np.isfinite(truth).all() and np.all(truth>=0) and np.all(truth==np.floor(truth)),'Complete1713 unique original target rows and9strata required')
    need(Counter(r.get('context') for r in rows[1665:])==Counter({c:8 for c in (*PRODUCT_CONTEXTS,*SHIFT_CONTEXTS)}),'Every fixed coverage context must have8rows')
    for row,target in zip(rows,truth):row['lut4_count']=int(target)
    zero=full[:,list(v6.columns()).index('original_gate_count')]==0
    selected=selected_float32(full,v6.mapping_indices())
    check_hashes(before)
    return rows,full,selected,zero,aliases,{'new_mode_status_counts':dict(statuses),'original_alias_metadata':'Saved compact accepted forms; historical fallback statuses not reconstructed.'},paths


def build_groups(rows,matrix,aliases):
    """Label-blind transitive closure; edge reasons retain non-equivalence links."""
    count=len(rows);need(matrix.shape==(count,217) and matrix.dtype==np.dtype('<f4') and len(aliases)==count,'Matched selected217float32 rows required')
    parent=list(range(count))
    def find(i):
        while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
        return i
    def union(a,b):
        a,b=find(a),find(b)
        if a!=b:parent[max(a,b)]=min(a,b)
    buckets=defaultdict(list);skeletons=defaultdict(list)
    for i,(row,forms) in enumerate(zip(rows,aliases)):
        original=parse_formula(row['formula']).canonical();need(original==row['formula'] and original in forms,'Canonical original included in saved forms required')
        if row['source']=='original1665':buckets['inherited_V5_component',str(row['inherited_component'])].append(i)
        else:buckets['new_coverage_context',row['context']].append(i)
        for f in sorted(set(forms)):
            canonical_form=parse_formula(f).canonical();buckets['canonical_original_or_saved_accepted_form',canonical_form].append(i)
            buckets['frozen_commutative_key',equivalence_key(canonical_form)].append(i)
        vector=np.asarray(matrix[i],dtype='<f4').copy();vector[vector==0]=0
        buckets['exact_float32_selected_vector',hashlib.sha256(vector.tobytes(order='C')).hexdigest()].append(i)
        skeletons[skeleton(original)].append(i)
    edges=[]
    for (reason,key),indices in sorted(buckets.items()):
        members=sorted(set(indices))
        if len(members)<2:continue
        for i in members[1:]:union(members[0],i)
        edges.append({'reason':reason,'key':key,'members':members})
    members=defaultdict(list)
    for i in range(count):members[find(i)].append(i)
    components=[];row_components=['']*count
    for group in members.values():
        formulas=sorted(rows[i]['formula'] for i in group);identifier=digest(formulas)
        components.append({'component_id':identifier,'members':group,'formulas':formulas,'row_count':len(group),'strata':dict(Counter(rows[i]['stratum'] for i in group))})
        for i in group:row_components[i]=identifier
    components.sort(key=lambda c:(-c['row_count'],c['component_id']))
    return {'schema':'isaforge-v12-leakage-groups-v1','components':components,'row_components':row_components,'edges':edges,
        'edge_counts':dict(Counter(e['reason'] for e in edges)),
        'float32_collision_classes':[e for e in edges if e['reason']=='exact_float32_selected_vector'],
        'skeleton_diagnostic_only':[{'skeleton':key,'members':indices} for key,indices in sorted(skeletons.items()) if len(indices)>1],
        'targets_used_for_grouping':False}


def assign_folds(rows,groups):
    folds=[[] for _ in range(5)];counts=[Counter() for _ in range(5)];component_folds={}
    for component in groups['components']:
        c=component['strata'];fold=min(range(5),key=lambda f:(sum(n*counts[f][s] for s,n in c.items()),len(folds[f]),f))
        folds[fold].extend(component['members']);counts[fold].update(c);component_folds[component['component_id']]=fold
    ids=[-1]*len(rows);details=[]
    for fold,validation in enumerate(folds):
        validation.sort();training=sorted(set(range(len(rows)))-set(validation))
        for i in validation:need(ids[i]==-1,'Assessment row repeated');ids[i]=fold
        train_counts=Counter(rows[i]['stratum'] for i in training);val_counts=Counter(rows[i]['stratum'] for i in validation)
        details.append({'fold':fold,'validation_indices':validation,'training_indices':training,'training_strata':dict(train_counts),
            'validation_strata':dict(val_counts),'missing_validation_strata':sorted(set(STRATA)-set(val_counts)),
            'training_has_all9strata':set(train_counts)==set(STRATA)})
    feasible=len(groups['components'])>=5 and all(folds) and all(d['training_has_all9strata'] for d in details) and -1 not in ids
    return {'schema':'isaforge-v12-group-folds-v1','fold_ids':ids,'component_fold':component_folds,'folds':details,'feasible':feasible,
        'failure_reason':None if feasible else 'Need>=5components,nonemptyassessmentfolds,andall9strataineverytrainingpartition; grouping must not be weakened.',
        'labels_used_for_assignment':False}


def prepare(root):
    root=Path(root).resolve();need(root.is_relative_to(ROOT) and not root.exists(),'Fresh repository-owned preparation root required')
    sources=source_paths();need(all(p.is_file() for p in sources),'Finish runner/tests/protocol/input-auditor sources before preparation')
    rows,full,matrix,zero,aliases,diagnostics,inputs=load_inputs();before={p:sha(p) for p in [*sources,*inputs]}
    groups=build_groups(rows,matrix,aliases);split=assign_folds(rows,groups);environment=runtime()
    root.mkdir(parents=True)
    try:
        write(root/'recipe.json',recipe());write(root/'runtime.json',environment)
        write(root/'fitting.json',{'rows':rows,'original_zero':zero.tolist(),'aliases':aliases,'identity_diagnostics':diagnostics,
            'stratum_counts':dict(Counter(r['stratum'] for r in rows)),'zero_target_count':sum(r['lut4_count']==0 for r in rows),'original_zero_override_count':int(zero.sum())})
        with (root/'matrix.npy').open('xb') as stream:np.save(stream,matrix,allow_pickle=False)
        write(root/'groups.json',groups);write(root/'split.json',split)
        check_hashes(before)
        files=[*sources,*inputs,*sorted(p for p in root.rglob('*') if p.is_file())]
        manifest={'schema':SCHEMA,'status':'prepared-inputs-only' if split['feasible'] else 'infeasible-grouping; review-required','created_at_utc':now(),
            'fits_completed':0,'maximum_fits':30,'new_physical_labels':0,'new_feature_extractions':0,'new_solver_queries':0,'evaluation_target_reads':0,
            'rows':1713,'selected_columns':217,'components':len(groups['components']),'grouping_feasible':split['feasible'],
            'files':[record(p,root) for p in dict.fromkeys(files)],'source_paths':[os.path.relpath(p,root) for p in sources],
            'input_paths':[os.path.relpath(p,root) for p in inputs],
            'fit_schedule':[{'seed':seed,'view':view,'fold':fold,'fit_index':i+1} for i,(seed,view,fold) in enumerate(itertools_product())]}
        write(root/'preparation.json',manifest)
        need(split['feasible'],'Infeasible grouping retained; review before any fit')
        validate(root)
        return manifest
    except BaseException as error:
        write(root/'preparation-failure.json',{'error':repr(error),'fits_completed':0,'at_utc':now()});raise


def itertools_product():
    return [(seed,view,fold) for seed in SEEDS for view in VIEWS for fold in range(5)]


def validate(root):
    root=Path(root).resolve();manifest=read(root/'preparation.json')
    need(root.is_relative_to(ROOT) and not (root/'preparation-failure.json').exists() and manifest.get('schema')==SCHEMA
        and manifest.get('status')=='prepared-inputs-only' and manifest.get('fits_completed')==0 and manifest.get('maximum_fits')==30
        and manifest.get('rows')==1713 and manifest.get('selected_columns')==217 and manifest.get('grouping_feasible') is True,'Complete feasible input-only freeze required')
    bindings={}
    for entry in manifest['files']:
        path=(root/entry['path']).resolve();need(not Path(entry['path']).is_absolute() and path.is_relative_to(ROOT) and path not in bindings
            and sha(path)==entry['sha256'],'Changed/duplicate/external prepared binding');bindings[path]=entry['sha256']
    need(set(manifest['source_paths'])=={os.path.relpath(p,root) for p in source_paths()} and all(p in bindings for p in source_paths()),'Complete required source closure needed')
    needed=[root/n for n in ('recipe.json','runtime.json','fitting.json','matrix.npy','groups.json','split.json')]
    need(all(p in bindings for p in needed) and read(root/'recipe.json')==recipe() and read(root/'runtime.json')==runtime(),'Prepared recipe/runtime identity differs')
    data=read(root/'fitting.json');matrix=np.load(root/'matrix.npy',allow_pickle=False)
    need(matrix.shape==(1713,217) and matrix.dtype==np.dtype('<f4') and np.isfinite(matrix).all() and np.all(matrix>=0),'Complete frozen1713x217 matrix required')
    groups=build_groups(data['rows'],matrix,data['aliases']);split=assign_folds(data['rows'],groups)
    need(groups==read(root/'groups.json') and split==read(root/'split.json') and split['feasible'],'Group/split must replay exactly')
    rows,full,expected,zero,aliases,diagnostics,inputs=load_inputs()
    need(set(manifest['input_paths'])=={os.path.relpath(p,root) for p in inputs} and all(p in bindings for p in inputs),'Complete explicit fitting input closure required')
    need(data['rows']==rows and data['aliases']==aliases and data['original_zero']==zero.tolist() and data['identity_diagnostics']==diagnostics
        and np.array_equal(matrix,expected),'Prepared whitelist data/matrix differs from frozen training inputs')
    need(manifest['fit_schedule']==[{'seed':seed,'view':view,'fold':fold,'fit_index':i+1} for i,(seed,view,fold) in enumerate(itertools_product())],'Exactly30 fixed fits required')
    bindings[root/'preparation.json']=sha(root/'preparation.json')
    return manifest,data,matrix,groups,split,bindings


def metrics(y,p,strata):
    y=np.asarray(y,dtype=float);p=np.asarray(p,dtype=float);strata=np.asarray(strata)
    need(y.shape==p.shape==strata.shape and y.size and np.isfinite(y).all() and np.isfinite(p).all() and np.all(y>=0) and np.all(p>=0),'Complete finite nonnegative scores required')
    def cell(mask):
        a,b=y[mask],p[mask];error=b-a;ae=np.abs(error);pos=a>0;zero=a==0
        need(len(a)>0,'Metric cell must be nonempty')
        return {'count':len(a),'mae_lut4':float(ae.mean()),'signed_bias_lut4':float(error.mean()),'rmsle':float(np.sqrt(np.mean((np.log1p(b)-np.log1p(a))**2))),
            'positive_target_count':int(pos.sum()),'positive_mape_percent':float(np.mean(ae[pos]/a[pos])*100) if pos.any() else None,
            'zero_target_count':int(zero.sum()),'zero_mae_lut4':float(ae[zero].mean()) if zero.any() else None,
            'p95_absolute_error_lut4':float(np.quantile(ae,.95,method='linear')),'p99_absolute_error_lut4':float(np.quantile(ae,.99,method='linear')),
            'worst_absolute_error_lut4':float(ae.max()),'maximum_underprediction_lut4':float(np.maximum(a-b,0).max()),
            'caps':{str(cap):{'false_accept_count':int(((b<=cap)&(a>cap)).sum()),'false_reject_count':int(((b>cap)&(a<=cap)).sum()),
                'actually_feasible_count':int((a<=cap).sum()),'actually_infeasible_count':int((a>cap).sum()),'predicted_feasible_count':int((b<=cap).sum()),'count':len(a)} for cap in CAPS}}
    by={s:cell(strata==s) for s in sorted(set(strata))}
    return {'pooled':cell(np.ones(len(y),dtype=bool)),'by_stratum':by,'macro_stratum_mae_lut4':float(np.mean([c['mae_lut4'] for c in by.values()]))}


def decode(prediction,view,zero):
    values=np.asarray(prediction,dtype=float)
    need(view in VIEWS and values.shape==np.asarray(zero).shape and np.isfinite(values).all(),'Matched finite encoded points required')
    with np.errstate(over='raise',invalid='raise'):decoded=np.expm1(values) if view=='log1p' else values.copy()
    need(np.isfinite(decoded).all(),'Decoded point overflow')
    before=np.maximum(decoded,0);points=before.copy();points[np.asarray(zero,dtype=bool)]=0
    return before,points


def paired_decisions(y,raw,log):
    return {str(cap):{'raw_accept_log_reject_count':int(((raw<=cap)&(log>cap)).sum()),'raw_reject_log_accept_count':int(((raw>cap)&(log<=cap)).sum()),
        'raw_correct_log_wrong_count':int((((raw<=cap)==(y<=cap))&((log<=cap)!=(y<=cap))).sum()),
        'raw_wrong_log_correct_count':int((((raw<=cap)!=(y<=cap))&((log<=cap)==(y<=cap))).sum()),'count':len(y)} for cap in CAPS}


def fit(root,approval):
    root=Path(root).resolve();approval=Path(approval).resolve();manifest,data,matrix,groups,split,bindings=validate(root)
    need(approval==root/'fit-approval.json' and not (root/'fit-claim.json').exists() and not (root/'fit-attempt-0000').exists(),'Exact approval and fresh single fit attempt required')
    review=read(approval)
    need(review.get('status')=='approved-v12-thirty-fit-comparison' and review.get('preparation_sha256')==sha(root/'preparation.json')
        and review.get('runner_sha256')==sha(__file__) and review.get('maximum_fits')==30 and re.fullmatch('[0-9a-f]{40}',review.get('freeze_commit','')),'Exact parent30fit release required')
    need(utc(review['reviewed_at_utc'])>=utc(manifest['created_at_utc']),'Parent review must follow preparation')
    for path,expected in bindings.items():
        committed=subprocess.check_output(['git','show',review['freeze_commit']+':'+path.relative_to(ROOT).as_posix()],cwd=ROOT)
        need(hashlib.sha256(committed).hexdigest()==expected,'Git freeze differs')
    independent_path=(root/review['independent_input_audit']['path']).resolve()
    need(independent_path.is_relative_to(root) and sha(independent_path)==review['independent_input_audit']['sha256'],'Bound independent input review required')
    independent=read(independent_path)
    need(independent.get('schema')=='isaforge-v12-independent-input-audit-v1' and independent.get('status')=='pass'
        and independent.get('preparation_sha256')==sha(root/'preparation.json')
        and independent.get('audit_source_sha256')==sha(ROOT/'scripts/audit_v12_target_transform.py'),'Independent input audit must pass this preparation with frozen source')
    bindings.update({approval:sha(approval),independent_path:sha(independent_path)})
    # Native package files live outside the repository and cannot be Git-bound.
    # Their declared hashes are checked at every fit and after the final fit.
    bindings.update({Path(entry['path']):entry['sha256'] for entry in read(root/'runtime.json').get('files',[])})
    check_hashes(bindings)
    out=root/'fit-attempt-0000';out.mkdir()
    claimed=now();need(utc(claimed)>=utc(review['reviewed_at_utc']),'Fit claim must follow parent review')
    write(root/'fit-claim.json',{'maximum_fits':30,'preparation_sha256':sha(root/'preparation.json'),'approval_sha256':sha(approval),'claimed_at_utc':claimed})
    bindings[root/'fit-claim.json']=sha(root/'fit-claim.json')
    rows=data['rows'];y=np.asarray([r['lut4_count'] for r in rows],dtype=float);strata=np.asarray([r['stratum'] for r in rows]);zero=np.asarray(data['original_zero'],dtype=bool)
    ids=np.asarray(split['fold_ids']);predictions={};scores={};receipts=[];attempts=0;error=None
    try:
        with threadpool_limits(limits=1):
            for seed in SEEDS:
                for view in VIEWS:
                    encoded=np.full(len(rows),np.nan);counts=np.zeros(len(rows),dtype=int)
                    for fold in range(5):
                        check_hashes(bindings);attempts+=1;training=ids!=fold;validation=ids==fold
                        start={'fit_index':attempts,'seed':seed,'view':view,'fold':fold,'parameters':{**PARAMETERS,'random_state':seed},
                            'training_indices':np.flatnonzero(training).tolist(),'validation_indices':np.flatnonzero(validation).tolist(),'started_at_utc':now()}
                        need(utc(start['started_at_utc'])>=utc(claimed),'Fit must start after reviewed claim')
                        write(out/'receipts'/f'{attempts:02d}-start.json',start);began=time.monotonic()
                        estimator=ExtraTreesRegressor(**PARAMETERS,random_state=seed)
                        estimator.fit(matrix[training],np.log1p(y[training]) if view=='log1p' else y[training])
                        direct=estimator.predict(matrix[validation]);fingerprint=v6.estimator_fingerprint(estimator)
                        artifact=out/'models'/f'{attempts:02d}-{view}-seed-{seed}-fold-{fold}.joblib';artifact.parent.mkdir(parents=True,exist_ok=True)
                        need(not artifact.exists(),'Fresh per-fit artifact required');joblib.dump(estimator,artifact,compress=3)
                        restored=joblib.load(artifact)
                        need(restored.get_params(deep=True)==estimator.get_params(deep=True) and v6.estimator_fingerprint(restored)==fingerprint
                            and np.array_equal(restored.predict(matrix[validation]),direct),'Exact model save/load state and point roundtrip required')
                        encoded[validation]=direct;counts[validation]+=1
                        receipt={**start,'completed_at_utc':now(),'elapsed_seconds':time.monotonic()-began,'estimator_fingerprint':fingerprint,'artifact':record(artifact,out),'artifact_bytes':artifact.stat().st_size,'save_load_points_exact':True}
                        write(out/'receipts'/f'{attempts:02d}-completed.json',receipt);receipts.append(receipt)
                    need(np.all(counts==1),'Every row needs exactly one held-out point per seed/view')
                    before,points=decode(encoded,view,zero)
                    records=[{**r,'fold':int(ids[i]),'original_zero':bool(zero[i]),'encoded_prediction':float(encoded[i]),
                        'decoded_before_zero':float(before[i]),'predicted_lut4':float(points[i])} for i,r in enumerate(rows)]
                    path=out/'predictions'/f'{view}-seed-{seed}.json';write(path,records)
                    saved=read(path);need(saved==records and np.array_equal(np.asarray([r['predicted_lut4'] for r in saved]),points),'Exact saved-point roundtrip required before scoring')
                    predictions[view,seed]=points;scores[view,seed]=metrics(y,points,strata)
                    write(out/'metrics'/f'{view}-seed-{seed}.json',scores[view,seed])
                    print('completed',view,seed,'fits',attempts,'/30',flush=True)
        need(attempts==len(receipts)==30,'Exactly30 completed fits required')
        check_hashes(bindings)
        differences=[scores['log1p',seed]['macro_stratum_mae_lut4']-scores['raw',seed]['macro_stratum_mae_lut4'] for seed in SEEDS]
        summary={'schema':'isaforge-v12-target-transform-comparison-v1','scope':recipe()['scope'],'fits_completed':30,
            'primary_log_minus_raw_macro_mae_lut4':{'per_seed':dict(zip(map(str,SEEDS),differences)),'mean':float(np.mean(differences)),'sample_sd_algorithm_seeds':float(np.std(differences,ddof=1))},
            'scores':{view:{str(seed):scores[view,seed] for seed in SEEDS} for view in VIEWS},
            'paired_cap_decisions':{str(seed):paired_decisions(y,predictions['raw',seed],predictions['log1p',seed]) for seed in SEEDS},
            'promotion':'No automatic promotion or final refit; mean,cap64FA/FR,P99 and maximum-underprediction are separate review endpoints.'}
        write(out/'summary.json',summary)
    except BaseException as exc:error=exc
    done={'schema':'isaforge-v12-fit-completion-v1','complete':error is None,'fits_attempted':attempts,'fits_completed':len(receipts),'maximum_fits':30,
        'preparation_sha256':sha(root/'preparation.json'),'approval_sha256':sha(approval),'runner_sha256':sha(__file__),'error':repr(error) if error else None,
        'summary_sha256':sha(out/'summary.json') if (out/'summary.json').exists() else None,'completed_at_utc':now(),'evaluation_target_reads':0,'new_physical_labels':0,'new_feature_extractions':0,'new_solver_queries':0}
    write(out/'completion.json',done)
    if error is not None:raise error
    return done


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=('prepare','validate','fit'));parser.add_argument('--root',type=Path,required=True);parser.add_argument('--approval',type=Path)
    args=parser.parse_args()
    if args.action=='prepare':result=prepare(args.root)
    elif args.action=='validate':
        manifest,data,matrix,groups,split,bindings=validate(args.root);result={'status':'valid','rows':len(data['rows']),'components':len(groups['components']),'fits_completed':0,'maximum_fits':30}
    else:
        if args.approval is None:parser.error('fit requires explicit --approval')
        result=fit(args.root,args.approval)
    print(json.dumps(result,indent=2,allow_nan=False))
