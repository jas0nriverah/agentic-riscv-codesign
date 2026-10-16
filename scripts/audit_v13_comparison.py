#!/usr/bin/env python3
"""V13 joint-input fairness and independent saved-point arithmetic replay.

No trainer/model/native import or fitting. Group reconstruction reuses the
independent V12 adjacency/fold auditor and frozen parser/V4 normalization;
metric arithmetic reuses the standard-library V12 results auditor. Native
feature geometry and model inference are separate checks, not claimed here.
"""
from __future__ import annotations
import argparse
import ast
from collections import Counter,defaultdict
import hashlib
import json
import math
from pathlib import Path
import re
import statistics
import struct
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import audit_v12_target_transform as geometry
import audit_v12_results as arithmetic

need,exact,loads,finite,stamp=(getattr(arithmetic,k) for k in ('need','exact','loads','finite','stamp'))
SEEDS=arithmetic.SEEDS
VIEWS=('control','augmented')
PARAMETERS=arithmetic.PARAMETERS
STRATA=arithmetic.STRATA
SELECTED=tuple(range(194))+tuple(range(313,336))
V12='results/2026-10-15-v12-target-transform'
V12_SHA='3934bf7dd0ef2c6c5dbc47e3ddd3a627f32523a9861c41697baa45e6d4e35377'
INPUT_SHA='e8b11316d6d0483d56d3544ac2dfa7d46d958de8cc7099b3a4b9bd4de99e5f5e'
CANDIDATE_SHA='d215ab0de627667c4622a039b33ac4bc07179cbc6bd43a36b4d3b5486ed3bba9'


def sha(body):return hashlib.sha256(body).hexdigest()
def read(path):return loads(Path(path).read_bytes())
def schedule():return [{'fit_index':i+1,'seed':s,'view':v,'fold':f} for i,(s,v,f) in enumerate((s,v,f) for s in SEEDS for v in VIEWS for f in range(5))]
def matrix_bytes(body,rows):
    need(body[:6]==b'\x93NUMPY' and body[6:8] in (b'\x01\x00',b'\x02\x00'),'Strict NPY1/2 required')
    size=2 if body[6]==1 else 4;start=8+size;length=int.from_bytes(body[8:start],'little');header=ast.literal_eval(body[start:start+length].decode('latin1'))
    need(set(header)=={'descr','fortran_order','shape'} and header['descr']=='<f4' and header['fortran_order'] is False
        and exact(header['shape'],(rows,217)),'Exact little-endian float32 C matrix required')
    values=body[start+length:];need(len(values)==rows*217*4,'Complete matrix byte length required')
    need(all(math.isfinite(v[0]) and v[0]>=0 for v in struct.iter_unpack('<f',values)),'Finite nonnegative learner matrix required')
    return values

def normalize_root(formula):
    value=geometry.frozen_normalize(formula)
    if value in ('in0','in1'):value=f'ori({value},0)'
    elif re.fullmatch('-?[0-9]+',value):value=f'lui({value})'
    return geometry.parse_formula(value).canonical()


def reconstruct_groups(rows,vectors,aliases):
    sources=[]
    for r in rows:
        if r['source']=='original1665':sources.append(('old_component',str(r['inherited_component'])))
        else:sources.append(('coverage_context',('v13:' if r['source']=='coverage_v13' else 'v9:')+r['context']))
    components,diagnostic=geometry.reconstruct_groups(rows,vectors,[set(a) for a in aliases],sources)
    row_components=[None]*len(rows)
    for c in components:
        for i in c['indices']:row_components[i]=c['component_id']
    def skeleton(formula):
        def visit(node):return ('C' if type(node.value) is int else 'I') if not node.children else str(node.value)+'('+','.join(visit(c) for c in node.children)+')'
        return visit(geometry.parse_formula(formula))
    skeletons=defaultdict(list)
    for i,r in enumerate(rows):skeletons[skeleton(r['formula'])].append(i)
    groups={'schema':'isaforge-v13-joint-leakage-groups-v1','components':[
        {'component_id':c['component_id'],'members':c['indices'],'formulas':c['formulas'],'row_count':len(c['indices']),
            'strata':dict(Counter(rows[i]['stratum'] for i in c['indices']))} for c in sorted(components,key=lambda c:(-len(c['indices']),c['component_id']))],
        'row_components':row_components,'edges':diagnostic['edges'],'edge_counts':dict(Counter(e['reason'] for e in diagnostic['edges'])),
        'float32_collision_classes':[e for e in diagnostic['edges'] if e['reason']=='exact_float32_selected_vector'],
        'skeleton_diagnostic_only':[{'skeleton':k,'members':v} for k,v in sorted(skeletons.items()) if len(v)>1],'targets_used_for_grouping':False}
    assignment=geometry.reconstruct_folds(rows,components);ids=assignment['fold_ids'];details=[]
    for f in range(5):
        val=assignment['validation_indices'][f];train=assignment['training_indices'][f];control=[i for i in train if rows[i]['cohort']=='original1713']
        counts=dict(Counter(rows[i]['stratum'] for i in control));need(set(counts)==set(STRATA),'Every CONTROL training fold needs nine strata')
        details.append({'fold':f,'validation_indices':val,'training_indices':train,'training_strata':assignment['training_stratum_counts'][f],
            'validation_strata':assignment['validation_stratum_counts'][f],'missing_validation_strata':sorted(set(STRATA)-set(assignment['validation_stratum_counts'][f])),
            'training_has_all9strata':True,'control_training_indices':control,'control_training_strata':counts,'control_training_has_all9strata':True})
    split={'schema':'isaforge-v13-joint-folds-v1','fold_ids':ids,'component_fold':{c['component_id']:ids[c['indices'][0]] for c in components},
        'folds':details,'feasible':True,'failure_reason':None,'labels_used_for_assignment':False}
    return groups,split


def reconstruct_inputs(root,get):
    """Saved1713 prefix plus sealed48 whitelist; no feature extractor or model."""
    old=ROOT/V12;old_preparation=get(old/'preparation.json');need(sha((old/'preparation.json').read_bytes())==V12_SHA,'Exact V12 fitting freeze required')
    old_bind={(old/e['path']).resolve():e['sha256'] for e in old_preparation['files']}
    for name in ('fitting.json','matrix.npy'):
        need(old_bind.get(old/name)==sha((old/name).read_bytes()),'Old fitting data unbound or changed')
    base=get(old/'fitting.json');old_matrix=matrix_bytes((old/'matrix.npy').read_bytes(),1713)
    recipe_path=ROOT/'results/2026-10-15-v9-coverage-development/recipe.json'
    need(old_bind.get(recipe_path)==sha(recipe_path.read_bytes()),'Old feature schema/tool recipe unbound')
    saved_recipe=get(recipe_path);old_recipe={'full_columns':saved_recipe['feature_columns'],'selected_feature_columns':saved_recipe['selected_columns'],'selected_indices':saved_recipe['selected_indices']}
    need(sha((root/'preparation.json').read_bytes())==INPUT_SHA and sha((root/'candidates.json').read_bytes())==CANDIDATE_SHA,'Exact original/recovery V13 candidate seal required')
    candidates=get(root/'candidates.json');labels=get(root/'measurements/attempt-0000/labels.json');measurement=get(root/'measurements/completion.json')
    need(measurement['complete'] is True and measurement['failures']==[] and type(measurement['new_physical_measurements']) is int
        and measurement['new_physical_measurements']==48 and measurement['labels_sha256']==sha((root/'measurements/attempt-0000/labels.json').read_bytes()),'Complete48 original labels required')
    need(exact(measurement,get(root/'measurements/attempt-0000/completion.json')),'Root/stage label completion differs')
    stage=root/'features/attempt-0000';features=get(stage/'features.json');done=get(root/'features/completion.json')
    need(exact(done,get(stage/'completion.json')) and done['complete'] is True and done['failures']==[] and type(done['completed_extractions']) is int
        and done['completed_extractions']==48 and done['features_sha256']==sha((stage/'features.json').read_bytes())
        and done['measurement_completion_sha256']==sha((root/'measurements/completion.json').read_bytes()),'Complete authenticated48 features required')
    need(features['columns']==old_recipe['full_columns'] and old_recipe['selected_indices']==list(SELECTED),'Identical original336/selected217 feature order required')
    fields={r['formula']:r for r in features['records']};targets={r['formula']:r for r in labels};formulas={r['formula'] for r in candidates}
    need(len(candidates)==len(formulas)==len(fields)==len(features['records'])==len(targets)==len(labels)==48
        and set(fields)==set(targets)==formulas,'Unique complete48 formula join required')
    rows=[{**r,'cohort':'original1713'} for r in base['rows']];zero=base['original_zero'][:];aliases=base['aliases'][:];vectors=[old_matrix[i*868:(i+1)*868] for i in range(1713)]
    need(len(rows)==len(zero)==len(aliases)==1713 and all(type(v) is bool for v in zero),'Complete original1713 whitelist required')
    for c in candidates:
        formula=c['formula'];record=fields[formula];target=targets[formula]
        need(record['candidate_id']==target['candidate_id']==c['candidate_id'] and all(k in target and exact(target[k],v) for k,v in c.items()),'New candidate identity differs')
        need(type(target['lut4_count']) is int and target['lut4_count']>=0 and target['correctness_verified'] is True,'Strict original target and correctness required')
        values=record['values'];need(len(values)==336 and all(finite(v) for v in values),'Complete finite original336 feature row required')
        rows.append({'formula':formula,'source':'coverage_v13','cohort':'coverage48','candidate_id':c['candidate_id'],'family':c['family'],
            'context':c['context'],'stratum':c['stratum'],'lut4_count':target['lut4_count']})
        aliases.append(sorted({formula,normalize_root(formula)}));vectors.append(geometry.float32_row([values[i] for i in SELECTED]));zero.append(values[features['columns'].index('original_gate_count')]==0)
    need(len(rows)==len({r['formula'] for r in rows})==1761 and all(type(r['lut4_count']) is int and r['lut4_count']>=0 for r in rows),'Exact unique1761 targets required')
    return rows,vectors,aliases,zero,old_recipe


def input_audit(root):
    root=Path(root).resolve();out=root/'fitting';snapshots={}
    def data(p):
        p=Path(p).resolve();body=p.read_bytes();h=sha(body);need(p not in snapshots or snapshots[p]==h,'Audit input changed while reading');snapshots[p]=h;return body
    def get(p):return loads(data(p))
    manifest=get(out/'preparation.json');prep_sha=sha(data(out/'preparation.json'))
    need(manifest['schema']=='isaforge-v13-matched-coverage-preparation-v1' and manifest['status']=='prepared-inputs-only' and manifest['grouping_feasible'] is True
        and not (out/'preparation-failure.json').exists(),'Complete feasible fitting preparation required')
    for k,v in [('rows',1761),('old_rows',1713),('new_rows',48),('selected_columns',217),('fits_completed',0),('maximum_fits',30),('evaluation_target_reads',0),('new_solver_queries',0),('new_feature_extractions',0)]:need(exact(manifest[k],v),'Strict preparation count differs')
    bindings={}
    for e in manifest['files']:
        p=(out/e['path']).resolve();need(set(e)=={'path','sha256'} and not Path(e['path']).is_absolute() and p.is_relative_to(ROOT)
            and p not in bindings and sha(data(p))==e['sha256'],'Changed/duplicate/external flat input binding');bindings[p]=e['sha256']
    required={out/n for n in ('recipe.json','runtime.json','fitting.json','matrix.npy','groups.json','split.json')}|{ROOT/'scripts/develop_v13_coverage.py'}
    need(required<=set(bindings),'Prepared payload/trainer source missing')
    declared={(out/p).resolve() for p in manifest['source_paths']+manifest['input_paths']}
    need(declared<=set(bindings),'Declared source/input omitted from flat bindings')
    rows,vectors,aliases,zero,old_recipe=reconstruct_inputs(root,get)
    data_set=get(out/'fitting.json');need(exact(data_set,{'rows':rows,'original_zero':zero,'aliases':aliases}),'Prepared whitelist/zero/alias join differs')
    need(matrix_bytes(data(out/'matrix.npy'),1761)==b''.join(vectors),'Exact shared selected217float32 matrix differs')
    need({r['stratum'] for r in rows[:1713]}==set(STRATA) and Counter(r['family'] for r in rows[1713:])=={
        'correlated_high_products':16,'affine_masked_chains':16,'comparator_shift_compositions':16},'Primary nine-strata / secondary16perfamily denominators differ')
    groups,split=reconstruct_groups(rows,vectors,aliases)
    need(exact(get(out/'groups.json'),groups) and exact(get(out/'split.json'),split),'Independent complete joint closure/fold/control training replay differs')
    recipe=get(out/'recipe.json')
    need(recipe['schema']=='isaforge-v13-matched-coverage-recipe-v1' and exact(recipe['parameters'],PARAMETERS) and exact(recipe['views'],list(VIEWS))
        and exact(recipe['seeds'],list(SEEDS)) and recipe['target_transform']=='none' and recipe['final_refit'] is False and recipe['sample_weights'] is False
        and recipe['hyperparameter_search'] is False and recipe['feature_columns']==old_recipe['selected_feature_columns'] and recipe['selected_indices']==list(SELECTED)
        and exact(recipe['folds'],5) and exact(recipe['maximum_fits'],30),'Matched raw300-tree feature/fit recipe differs')
    need(exact(manifest['fit_schedule'],schedule()),'Exactly30 fixed paired slots required')
    # This directly checks the no-target-geometry contract on the authorized rows.
    poisoned=[{**r,'lut4_count':-9999,'residual':float('nan'),'predicted_lut4':999999,'benchmark':'POISON'} for r in rows]
    pg,ps=reconstruct_groups(poisoned,vectors,aliases);need(exact(pg,groups) and exact(ps,split),'Targets/outcomes changed groups/folds')
    for p in snapshots:need(sha(p.read_bytes())==snapshots[p],'Audit evidence mutated')
    report={'schema':'isaforge-v13-independent-input-audit-v1','status':'pass','preparation_sha256':prep_sha,'audit_source_sha256':sha(Path(__file__).read_bytes()),
        'bound_files_verified':len(bindings),'rows_verified':1761,'primary_original_rows':1713,'secondary_coverage_rows':48,'features_verified':217,
        'component_count':len(groups['components']),'fold_validation_counts':[len(d['validation_indices']) for d in split['folds']],
        'control_training_counts':[len(d['control_training_indices']) for d in split['folds']],
        'all_control_and_augmented_training_have9strata':True,'target_poison_geometry_unchanged':True,'fits_run':0,'native_jobs':0,'evaluation_target_reads':0,
        'independence':'No trainer import. Reuses independent V12 adjacency/float32/greedy-fold auditor, shared frozen parser/V4 normalization; independently joins savedV12+V13whitelists and verifies exactjointmatrix/groups/control exclusions. New336 native-feature geometry was checked by frozen feature workflow; not independently re-extracted here.'}
    return report,rows,zero,split,recipe,manifest,bindings


def cohort_scores(rows,points):
    result={}
    def score(indices):return arithmetic.metrics([rows[i]['lut4_count'] for i in indices],[points[i] for i in indices],[rows[i]['stratum'] for i in indices])
    for name in ('original1713','coverage48'):result[name]=score([i for i,r in enumerate(rows) if r['cohort']==name])
    result['coverage_by_family']={f:score([i for i,r in enumerate(rows) if r.get('family')==f]) for f in sorted({r['family'] for r in rows if r['cohort']=='coverage48'})}
    return result

def paired(rows,control,augmented):
    result={}
    for name in ('original1713','coverage48'):
        indices=[i for i,r in enumerate(rows) if r['cohort']==name];raw=arithmetic.decisions([rows[i]['lut4_count'] for i in indices],[control[i] for i in indices],[augmented[i] for i in indices])
        result[name]={cap:{k.replace('raw','control').replace('log','augmented'):v for k,v in counts.items()} for cap,counts in raw.items()}
    return result

def verify_points(records,rows,zero,ids):
    need(type(records) is list and len(records)==1761,'Every1761 heldout row required');points=[]
    for i,(p,r) in enumerate(zip(records,rows)):
        need(set(p)==set(r)|{'fold','original_zero','encoded_prediction','decoded_before_zero','predicted_lut4'} and exact({k:p[k] for k in r},r),'Saved-point row identity/order differs')
        need(exact(p['fold'],ids[i]) and exact(p['original_zero'],zero[i]),'Shared heldout fold or zero identity differs')
        encoded,before,point=(p[k] for k in ('encoded_prediction','decoded_before_zero','predicted_lut4'))
        need(all(type(x) is float and finite(x) for x in (encoded,before,point)) and before==encoded and point==(0.0 if zero[i] else before),'Rawpoint/zero/decode differs')
        points.append(point)
    return points


def results_audit(root,require_models=False):
    root=Path(root).resolve();report,rows,zero,split,recipe,manifest,bindings=input_audit(root);out=root/'fitting';stage=out/'fit-attempt-0000'
    approval=read(out/'fit-approval.json');claim=read(out/'fit-claim.json');done=read(stage/'completion.json');approval_sha=sha((out/'fit-approval.json').read_bytes())
    need(approval['status']=='approved-v13-thirty-matched-coverage-fits' and approval['preparation_sha256']==report['preparation_sha256']
        and approval['runner_sha256']==bindings[ROOT/'scripts/develop_v13_coverage.py'] and exact(approval['maximum_fits'],30)
        and re.fullmatch('[0-9a-f]{40}',approval['freeze_commit']) is not None,'Exact30-slot source release required')
    entry=approval['independent_input_audit'];review_path=(out/entry['path']).resolve();review=read(review_path)
    need(review_path.is_relative_to(root) and sha(review_path.read_bytes())==entry['sha256'] and review['status']=='pass'
        and review['preparation_sha256']==report['preparation_sha256'],'Approved independent input review differs')
    need(exact(claim['maximum_fits'],30) and claim['approval_sha256']==approval_sha and claim['preparation_sha256']==report['preparation_sha256']
        and stamp(claim['claimed_at_utc'])>=stamp(approval['reviewed_at_utc'])>=stamp(manifest['created_at_utc']),'Claim/review/preparation chronology differs')
    need(done['schema']=='isaforge-v13-matched-fit-completion-v1' and done['complete'] is True and done['error'] is None
        and all(exact(done[k],30) for k in ('fits_attempted','fits_completed','maximum_fits')) and done['preparation_sha256']==report['preparation_sha256']
        and done['approval_sha256']==approval_sha and done['runner_sha256']==approval['runner_sha256']
        and all(exact(done[k],0) for k in ('evaluation_target_reads','new_solver_queries','new_feature_extractions','new_physical_labels')),'Complete exact30-fit run required')
    need({p.name for p in (stage/'receipts').iterdir()}=={f'{i:02d}-{s}.json' for i in range(1,31) for s in ('start','completed')},'Exactly60 receipts required')
    artifacts=[];previous=stamp(claim['claimed_at_utc'])
    for job in schedule():
        i=job['fit_index'];start=read(stage/'receipts'/f'{i:02d}-start.json');end=read(stage/'receipts'/f'{i:02d}-completed.json');d=split['folds'][job['fold']]
        training=d['control_training_indices'] if job['view']=='control' else d['training_indices']
        expected={**job,'parameters':{**PARAMETERS,'random_state':job['seed']},'training_indices':training,'validation_indices':d['validation_indices'],'started_at_utc':start['started_at_utc']}
        need(exact(start,expected) and all(k in end and exact(end[k],v) for k,v in start.items()),'Receipt training/assessment/group exclusion differs')
        need(stamp(start['started_at_utc'])>=previous and stamp(end['completed_at_utc'])>=stamp(start['started_at_utc']) and finite(end['elapsed_seconds'])
            and end['save_load_points_exact'] is True and re.fullmatch('[0-9a-f]{64}',end['estimator_fingerprint']) is not None,'Receipt chronology/state differs');previous=stamp(end['completed_at_utc'])
        artifact=end['artifact'];name=f"models/{i:02d}-{job['view']}-seed-{job['seed']}-fold-{job['fold']}.joblib";p=stage/name
        need(exact(artifact['path'],name) and re.fullmatch('[0-9a-f]{64}',artifact['sha256']) is not None and type(end['artifact_bytes']) is int and end['artifact_bytes']>0,'Model byte receipt identity differs')
        if p.exists():need(sha(p.read_bytes())==artifact['sha256'] and p.stat().st_size==end['artifact_bytes'],'Available model bytes differ')
        else:need(not require_models,'Required model byte artifact missing')
        artifacts.append({'fit_index':i,**artifact,'bytes':end['artifact_bytes'],'present_and_hash_verified':p.exists()})
    need(stamp(done['completed_at_utc'])>=previous,'Completion predates lastfit')
    names={f'{v}-seed-{s}.json' for v in VIEWS for s in SEEDS}
    for folder in ('predictions','metrics'):need({p.name for p in (stage/folder).iterdir()}==names,'Exact six point/metric sets required')
    points={};scores={};roundoff=[]
    for s in SEEDS:
        for v in VIEWS:
            n=f'{v}-seed-{s}.json';points[v,s]=verify_points(read(stage/'predictions'/n),rows,zero,split['fold_ids']);scores[v,s]=cohort_scores(rows,points[v,s])
            roundoff.extend(arithmetic.compare(read(stage/'metrics'/n),scores[v,s],'/metrics/'+n))
    differences=[scores['augmented',s]['original1713']['macro_stratum_mae_lut4']-scores['control',s]['original1713']['macro_stratum_mae_lut4'] for s in SEEDS]
    expected={'schema':'isaforge-v13-matched-coverage-comparison-v1','scope':recipe['scope'],'fits_completed':30,
        'primary_augmented_minus_control_original1713_macro_mae_lut4':{'per_seed':dict(zip(map(str,SEEDS),differences)),'mean':statistics.fmean(differences),'sample_sd_algorithm_seeds':statistics.stdev(differences)},
        'scores':{v:{str(s):scores[v,s] for s in SEEDS} for v in VIEWS},'paired_cap_decisions':{str(s):paired(rows,points['control',s],points['augmented',s]) for s in SEEDS},
        'promotion':'No automatic promotion/final refit; original1713 cap64FA/FR and tails remain separate endpoints; new48 secondary only.'}
    need(sha((stage/'summary.json').read_bytes())==done['summary_sha256'],'Summary digest differs');roundoff.extend(arithmetic.compare(read(stage/'summary.json'),expected,'/summary'))
    return {'schema':'isaforge-v13-independent-results-audit-v1','status':'pass','complete':True,'preparation_sha256':report['preparation_sha256'],
        'completion_sha256':sha((stage/'completion.json').read_bytes()),'audit_source_sha256':sha(Path(__file__).read_bytes()),'input_audit':report,
        'fit_receipts_verified':30,'saved_point_sets_verified':6,'saved_point_rows_verified':10566,'primary_recomputed':expected['primary_augmented_minus_control_original1713_macro_mae_lut4'],
        'scores_recomputed':expected['scores'],'paired_cap_decisions_recomputed':expected['paired_cap_decisions'],'artifacts':artifacts,
        'available_model_hashes_verified':sum(a['present_and_hash_verified'] for a in artifacts),'score_roundoff_differences':roundoff,
        'float_replay_policy':{'absolute_tolerance':arithmetic.FLOAT_ABS_TOLERANCE,'max_ulps':arithmetic.FLOAT_ULPS,'types_counts_rawdecode':'exact'},
        'independence':'Standard-library saved-point metric/cap/tail arithmetic; no V13 trainer/model/native import or inference/retraining. Group helper and parser/V4 reuse disclosed in input_audit. Separate frozen nativefeature workflow supplies336 records; local model bytes hashed only if present.'}


def run(root,action='inputs',require_models=False):
    need(action in ('inputs','results'),'Known auditor action required')
    return input_audit(root)[0] if action=='inputs' else results_audit(root,require_models)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--action',choices=('inputs','results'),required=True);p.add_argument('--root',type=Path,required=True);p.add_argument('--output',type=Path);p.add_argument('--require-models',action='store_true')
    a=p.parse_args();result=run(a.root,a.action,a.require_models);destination=a.output or a.root/'fitting'/('independent-input-audit.json' if a.action=='inputs' else 'independent-results-audit.json')
    with destination.open('x') as stream:json.dump(result,stream,indent=2,allow_nan=False);stream.write('\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('scores_recomputed','artifacts','score_roundoff_differences','paired_cap_decisions_recomputed')},indent=2,allow_nan=False))
