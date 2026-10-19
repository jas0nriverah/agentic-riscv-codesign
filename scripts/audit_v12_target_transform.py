#!/usr/bin/env python3
"""Independent V12 input/group/fold reconstruction; no runner, fits or native jobs.

The study recipe is shared (the author helped specify it). Graph traversal,
float32 packing, fold arithmetic and comparisons are separately implemented.
Frozen parsing/V4 semantic normalization remain shared input-only definitions.
"""
from __future__ import annotations
import argparse
import ast
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import struct
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from isaforge.features import parse_formula
from isaforge.structural_features_v4 import normalize_formula as frozen_normalize

V9='results/2026-10-15-v9-coverage-development'
V5='results/2026-10-14-v5'
SELECTED=tuple(range(194))+tuple(range(313,336))
STRATA=tuple(sorted(('workload','arithmetic_chain','shared_diamond','parallel_branches','mask_logic','constant_shifts','variable_shifts','comparators','multiplication')))
SEEDS=(2026101421,2026101422,2026101423)


def need(value,message):
    if not value:raise ValueError(message)


def digest(data):return hashlib.sha256(data).hexdigest()
def compact(value):return json.dumps(value,separators=(',',':'),allow_nan=False).encode()
def loads(data):
    def unique(items):
        out={}
        for k,v in items:need(k not in out,'Duplicate JSON key');out[k]=v
        return out
    return json.loads(data,object_pairs_hook=unique)
def read(path):return loads(Path(path).read_bytes())
def finite(value):return type(value) in (int,float) and math.isfinite(value) and value>=0


def commutative(formula):
    def visit(n):
        if not n.children:return str(n.value)
        children=[visit(c) for c in n.children]
        if n.value in ('add','and','or','xor','mul','mulh','mulhu'):children.sort()
        return str(n.value)+'('+','.join(children)+')'
    return visit(parse_formula(frozen_normalize(formula)))


def float32_row(values):
    need(len(values)==217 and all(finite(v) for v in values),'Exact finite nonnegative217 values required')
    return b''.join(struct.pack('<f',0.0 if value==0 else value) for value in values)


def npy_bytes(data):
    need(data[:6]==b'\x93NUMPY' and data[6:8] in (b'\x01\x00',b'\x02\x00'),'Strict NPY1/2 matrix required')
    length_size=2 if data[6]==1 else 4;start=8+length_size
    length=int.from_bytes(data[8:start],'little');header=ast.literal_eval(data[start:start+length].decode('latin1'))
    need(set(header)=={'descr','fortran_order','shape'} and header['descr']=='<f4' and header['fortran_order'] is False
        and type(header['shape']) is tuple and header['shape']==(1713,217) and all(type(n) is int for n in header['shape']), 'Prepared matrix dtype/order/shape differs')
    body=data[start+length:];need(len(body)==1713*217*4,'Exact matrix byte length required')
    return body


def reconstruct_inputs(base=ROOT):
    base=Path(base);root=base/V9
    old=read(root/'original-training.json');features=read(root/'fit-attempt-0000/coverage-features.json')
    new=read(root/'candidates.json');labels=read(root/'measurements/attempt-0000/labels.json')
    metadata=read(base/V5/'development-data.json');split=read(base/V5/'split.json')
    aliases_ledger=read(root/'consumed-input-ledger.json');identity=read(root/'identity-analysis.json')
    recipe=read(root/'recipe.json');model_path=root/'fit-attempt-0000/models/mapping-coverage.json';model=read(model_path)
    point_path=root/'fit-attempt-0000/point-freeze.json';point=read(point_path)
    need(digest((root/'preparation.json').read_bytes())=='468d264af46134f6717e317c9fcdc10c47f0f45e5938ec5da2999793d2977dca'
        and digest(point_path.read_bytes())=='ba377ae7ee17d7f656a1e05e5139fa98ec04f1b63d29d73e9322662eabe333bc'
        and point['schema_sha256']==digest(model_path.read_bytes()), 'Exact frozen V9 preparation/fit schema required')
    provenance=model['training_provenance']
    need(len(old['rows'])==len(old['values'])==1665 and len(old['columns'])==336 and len(new)==len(labels)==len(features['records'])==48, 'Exact authorized1665+48 inputs required')
    need(features['columns']==old['columns'] and recipe['selected_indices']==list(SELECTED), 'Fixed217 feature order differs')
    need(digest((root/'fit-attempt-0000/coverage-features.json').read_bytes())==provenance['coverage_features_sha256']
        and digest((root/'measurements/attempt-0000/labels.json').read_bytes())==provenance['coverage_labels_sha256'], 'V9 fitted feature/label lineage differs')
    need(digest((base/V5/'development-data.json').read_bytes())==old['training_provenance']['development_dataset_sha256']
        and digest((base/V5/'split.json').read_bytes())==old['training_provenance']['split_sha256'], 'Original fitting provenance differs')
    need(recipe['original_training']['sha256']==digest((root/'original-training.json').read_bytes()), 'V9 original training binding differs')
    original_v8=read(base/'results/2026-10-15-v8-application-transfer/training/training-data.json')
    need(original_v8['rows']==old['rows'] and original_v8['columns'][:336]==old['columns']
        and [r[:336] for r in original_v8['values']]==old['values'], 'Original336 prefix differs from frozen455 fitting source')
    fmap={r['formula']:r for r in features['records']};lmap={r['formula']:r for r in labels};imap={r['formula']:r for r in identity}
    ledger={r['formula']:r['accepted_forms'] for r in aliases_ledger['records']}
    need(len(fmap)==len(lmap)==len(imap)==48 and set(fmap)==set(lmap)==set(imap)=={r['formula'] for r in new}, 'New48 complete formula identities required')
    rows=[];vectors=[];accepted=[];sourcegroups=[]
    for i,(r,values) in enumerate(zip(old['rows'],old['values'])):
        index=r['development_index'];need(type(index) is int and 0<=index<len(metadata) and metadata[index]['formula']==r['formula'], 'Original metadata index differs')
        need(index==old['training_provenance']['fit_indices'][i] and finite(r['lut4_count']), 'Original authorized fit index/target differs')
        need(len(values)==336 and all(finite(v) for v in values),'Original336 vector invalid')
        rows.append({'formula':r['formula'],'stratum':metadata[index].get('stratum','workload'),'lut4_count':r['lut4_count'],
            'original_zero':values[old['columns'].index('original_gate_count')]==0,'origin':'original1665','origin_index':index})
        vectors.append(float32_row([values[j] for j in SELECTED]));accepted.append(set(ledger[r['formula']])|{r['formula']})
        sourcegroups.append(('old_component',str(split['component_by_formula'][r['formula']])))
    accepted_status=Counter()
    for r in new:
        formula=r['formula'];v=fmap[formula]['values'];target=lmap[formula]['lut4_count'];need(finite(target) and len(v)==336 and all(finite(x) for x in v),'New336/target invalid')
        context=r['context'];need(context in ('direct_product','add_after_product','sub_before_product','masked_sub_before_product','add_signed_shift_sign_sub','sub_signed_shift_sign_sub'),'Fixed six coverage contexts required')
        rows.append({'formula':formula,'stratum':'multiplication' if 'product' in context else 'constant_shifts','lut4_count':target,
            'original_zero':v[old['columns'].index('original_gate_count')]==0,'origin':'coverage48','origin_index':len(rows)-1665})
        vectors.append(float32_row([v[j] for j in SELECTED]));a={formula,imap[formula]['normalized_formula']}
        for mode in ('bit','affine','combined'):
            record=imap[formula]['v7_modes'][mode];status=record['metadata']['status'];accepted_status[mode+':'+status]+=1
            if status=='accepted':a.add(record['normalized_formula'])
        accepted.append(a);sourcegroups.append(('coverage_context',context))
    need(len(rows)==len({r['formula'] for r in rows})==1713 and set(r['stratum'] for r in rows)==set(STRATA), 'Unique1713/nine strata required')
    return rows,vectors,accepted,sourcegroups,{'accepted_new_mode_statuses':dict(accepted_status),'columns':old['columns'],'selected_columns':[old['columns'][i] for i in SELECTED]}


def reconstruct_groups(rows,vectors,accepted,sourcegroups):
    need(len(rows)==len(vectors)==len(accepted)==len(sourcegroups),'Matched grouping rows required')
    classes=defaultdict(list)
    for index,(row,vector,forms,source) in enumerate(zip(rows,vectors,accepted,sourcegroups)):
        classes[source].append(index);classes['float32_vector',vector].append(index)
        for form in forms|{row['formula']}:
            canonical=parse_formula(form).canonical();classes['accepted_alias',canonical].append(index)
            classes['commutative_alias',commutative(canonical)].append(index)
    adjacency=[set() for _ in rows];reasons=Counter();collision_classes=[];edges=[]
    reason_names={'old_component':'inherited_V5_component','coverage_context':'new_coverage_context','float32_vector':'exact_float32_selected_vector','accepted_alias':'canonical_original_or_saved_accepted_form','commutative_alias':'frozen_commutative_key'}
    for (reason,key),members in classes.items():
        members=sorted(set(members))
        if len(members)>1:
            reasons[reason]+=1
            edges.append({'reason':reason_names[reason],'key':digest(key) if type(key) is bytes else key,'members':members})
            if reason=='float32_vector':collision_classes.append(members)
            for index in members[1:]:adjacency[members[0]].add(index);adjacency[index].add(members[0])
    unseen=set(range(len(rows)));components=[]
    while unseen:
        todo=[min(unseen)];members=set()
        while todo:
            index=todo.pop()
            if index in members:continue
            members.add(index);todo.extend(adjacency[index]-members)
        unseen-=members;indices=sorted(members);formulas=sorted(rows[i]['formula'] for i in indices)
        components.append({'component_id':digest(compact(formulas)),'indices':indices,'formulas':formulas})
    components.sort(key=lambda c:c['component_id'])
    return components,{'shared_key_classes':dict(reasons),'float32_collision_classes':sorted(collision_classes),'edges':sorted(edges,key=lambda e:(e['reason'],e['key']))}


def reconstruct_folds(rows,components):
    need(len(components)>=5,'At least five components required')
    counts=[Counter() for _ in range(5)];totals=[0]*5;fold_ids=[None]*len(rows)
    for component in sorted(components,key=lambda c:(-len(c['indices']),c['component_id'])):
        c=Counter(rows[i]['stratum'] for i in component['indices'])
        fold=min(range(5),key=lambda f:(sum(n*counts[f][s] for s,n in c.items()),totals[f],f))
        for i in component['indices']:need(fold_ids[i] is None,'Duplicated component row');fold_ids[i]=fold
        counts[fold].update(c);totals[fold]+=len(component['indices'])
    need(all(v is not None for v in fold_ids) and all(totals),'Complete nonempty fivefold assignment required')
    validation=[[i for i,f in enumerate(fold_ids) if f==fold] for fold in range(5)]
    training=[[i for i,f in enumerate(fold_ids) if f!=fold] for fold in range(5)]
    need(all({rows[i]['stratum'] for i in indices}==set(STRATA) for indices in training),'Every training fold must contain nine strata')
    return {'fold_ids':fold_ids,'validation_indices':validation,'training_indices':training,
        'validation_stratum_counts':[dict(Counter(rows[i]['stratum'] for i in v)) for v in validation],
        'training_stratum_counts':[dict(Counter(rows[i]['stratum'] for i in v)) for v in training]}


def typed_equal(a,b):
    if type(a) is not type(b):return False
    if type(a) is dict:return set(a)==set(b) and all(typed_equal(a[k],b[k]) for k in a)
    if type(a) is list:return len(a)==len(b) and all(typed_equal(x,y) for x,y in zip(a,b))
    return a==b


def audit_preparation(root):
    root=Path(root).resolve();manifest=read(root/'preparation.json')
    need(manifest.get('schema')=='isaforge-v12-target-transform-preparation-v1' and manifest['status']=='prepared-inputs-only'
        and manifest['grouping_feasible'] is True and not (root/'preparation-failure.json').exists(),'Complete input-only V12 preparation required')
    for k,v in [('fits_completed',0),('maximum_fits',30),('new_physical_labels',0),('new_feature_extractions',0),('new_solver_queries',0),('evaluation_target_reads',0),('rows',1713),('selected_columns',217)]:need(type(manifest[k]) is int and manifest[k]==v,'Strict declared V12 preparation counts required')
    bindings={}
    for entry in manifest['files']:
        need(set(entry)=={'path','sha256'} and type(entry['path']) is str and not Path(entry['path']).is_absolute(),'Relative exact file binding required')
        path=(root/entry['path']).resolve();need(path.is_relative_to(ROOT) and path not in bindings and digest(path.read_bytes())==entry['sha256'],'Changed/duplicate/external prepared binding');bindings[path]=entry['sha256']
    required=[ROOT/'scripts/develop_v12_target_transform.py',ROOT/'tests/test_develop_v12_target_transform.py',
        ROOT/'docs/v12-model-direction.md',Path(__file__).resolve(),ROOT/'tests/test_audit_v12_target_transform.py',*sorted((ROOT/'isaforge').glob('*.py'))]
    declared={(root/p).resolve() for p in manifest['source_paths']}
    need(declared==set(required) and all(p in bindings for p in required),'Complete required source closure required')
    required_inputs=[ROOT/V9/n for n in ('preparation.json','recipe.json','original-training.json','consumed-input-ledger.json','identity-analysis.json','candidates.json',
        'measurements/completion.json','measurements/attempt-0000/completion.json','measurements/attempt-0000/labels.json','fit-attempt-0000/coverage-features.json',
        'fit-attempt-0000/point-freeze.json','fit-attempt-0000/models/mapping-coverage.json')]+[ROOT/V5/'development-data.json',ROOT/V5/'split.json',ROOT/'results/2026-10-15-v8-application-transfer/training/training-data.json']
    need({(root/p).resolve() for p in manifest['input_paths']}==set(required_inputs) and all(p in bindings for p in required_inputs),'Exact fitting-only input closure required')
    for name in ('recipe.json','runtime.json','fitting.json','matrix.npy','groups.json','split.json'):need(root/name in bindings,'Prepared payload missing from flat bindings')
    rows,vectors,aliases,sources,diagnostic=reconstruct_inputs();components,group_diag=reconstruct_groups(rows,vectors,aliases,sources);folds=reconstruct_folds(rows,components)
    data=read(root/'fitting.json');groups=read(root/'groups.json');split=read(root/'split.json');recipe=read(root/'recipe.json')
    native_rows=[]
    for i,(r,source) in enumerate(zip(rows,sources)):
        common={'formula':r['formula'],'source':r['origin'],'stratum':r['stratum'],'lut4_count':int(r['lut4_count'])}
        if i<1665:
            common.update(development_index=r['origin_index'],inherited_component=source[1])
        else:common.update(context=source[1])
        native_rows.append(common)
    need(typed_equal(data['rows'],native_rows),'Prepared whitelist row/target/source/stratum differs')
    need(typed_equal(data['original_zero'],[r['original_zero'] for r in rows]) and data['aliases']==[sorted(parse_formula(f).canonical() for f in a) for a in aliases], 'Prepared original-zero or accepted aliases differ')
    need(npy_bytes((root/'matrix.npy').read_bytes())==b''.join(vectors),'Exact independent float32 matrix replay differs')
    need(data['stratum_counts']==dict(Counter(r['stratum'] for r in rows)) and type(data['zero_target_count']) is int and data['zero_target_count']==sum(r['lut4_count']==0 for r in rows)
        and type(data['original_zero_override_count']) is int and data['original_zero_override_count']==sum(r['original_zero'] for r in rows),'Fitting denominators differ')
    need(data['identity_diagnostics']['new_mode_status_counts']==diagnostic['accepted_new_mode_statuses'],'Saved proof acceptance/fallback diagnostic differs')
    expected={c['component_id']:c for c in components};actual={c['component_id']:c for c in groups['components']}
    need(len(actual)==len(groups['components'])==len(expected) and set(actual)==set(expected),'Component identity/count differs')
    for key,c in actual.items():
        e=expected[key];need(c['members']==e['indices'] and c['formulas']==e['formulas'] and type(c['row_count']) is int and c['row_count']==len(e['indices'])
            and c['strata']==dict(Counter(rows[i]['stratum'] for i in e['indices'])),'Independent component members/metadata differ')
    row_components=[None]*len(rows)
    for c in components:
        for i in c['indices']:row_components[i]=c['component_id']
    need(groups['row_components']==row_components and groups['targets_used_for_grouping'] is False,'Row component coverage or label-use declaration differs')
    def skeleton(formula):
        def visit(n):return ('C' if type(n.value) is int else 'I') if not n.children else str(n.value)+'('+','.join(visit(c) for c in n.children)+')'
        return visit(parse_formula(formula))
    skeletons=defaultdict(list)
    for i,r in enumerate(rows):skeletons[skeleton(r['formula'])].append(i)
    expected_groups={'schema':'isaforge-v12-leakage-groups-v1',
        'components':[{'component_id':c['component_id'],'members':c['indices'],'formulas':c['formulas'],'row_count':len(c['indices']),
            'strata':dict(Counter(rows[i]['stratum'] for i in c['indices']))} for c in sorted(components,key=lambda c:(-len(c['indices']),c['component_id']))],
        'row_components':row_components,'edges':group_diag['edges'],'edge_counts':dict(Counter(e['reason'] for e in group_diag['edges'])),
        'float32_collision_classes':[e for e in group_diag['edges'] if e['reason']=='exact_float32_selected_vector'],
        'skeleton_diagnostic_only':[{'skeleton':key,'members':indices} for key,indices in sorted(skeletons.items()) if len(indices)>1],
        'targets_used_for_grouping':False}
    need(typed_equal(groups,expected_groups),'Independent complete edge/collision/skeleton/component reconstruction differs')

    need(split['fold_ids']==folds['fold_ids'] and split['feasible'] is True and split['failure_reason'] is None and split['labels_used_for_assignment'] is False and len(split['folds'])==5,'Independent deterministic fold assignment differs')
    for index,record in enumerate(split['folds']):
        need(type(record['fold']) is int and record['fold']==index and record['validation_indices']==folds['validation_indices'][index]
            and record['training_indices']==folds['training_indices'][index] and record['training_strata']==folds['training_stratum_counts'][index]
            and record['validation_strata']==folds['validation_stratum_counts'][index] and record['training_has_all9strata'] is True
            and record['missing_validation_strata']==sorted(set(STRATA)-set(record['validation_strata'])),'Fold indices/stratum feasibility differs')
    expected_component_fold={c['component_id']:folds['fold_ids'][c['indices'][0]] for c in components}
    need(split['component_fold']==expected_component_fold and manifest['components']==len(components),'Component fold identity differs')
    need(recipe['selected_indices']==list(SELECTED) and recipe['selected_feature_columns']==diagnostic['selected_columns'] and recipe['full_columns']==diagnostic['columns'],'Recipe feature schema differs')
    need(typed_equal(recipe['parameters'],{'n_estimators':300,'criterion':'squared_error','min_samples_leaf':1,'max_features':1.0,'n_jobs':1})
        and recipe['seeds']==list(SEEDS) and recipe['target_views']==['raw','log1p'] and recipe['folds']==5 and recipe['maximum_fits']==30
        and recipe['decode']=={'raw':'max(0,forest_mean)','log1p':'max(0,expm1(forest_mean_log))'}, 'Fixed30fit model recipe differs')
    need(all(recipe[k] is False for k in ('automatic_retries','hyperparameter_search','final_refit','smearing','sample_weights'))
        and all(type(recipe[k]) is int and recipe[k]==0 for k in ('new_physical_labels','new_feature_extractions','new_solver_queries','evaluation_target_reads')),'Forbidden extra work in recipe')
    schedule=[{'seed':seed,'view':view,'fold':fold,'fit_index':i+1} for i,(seed,view,fold) in enumerate((s,v,f) for s in SEEDS for v in ('raw','log1p') for f in range(5))]
    need(typed_equal(manifest['fit_schedule'],schedule),'Exactly30 paired fixed fits required')
    poisoned=[{**r,'lut4_count':999999-i,'target':-1,'prediction':float('nan'),'residual':float('inf'),'benchmark':'POISON'} for i,r in enumerate(rows)]
    pc,pd=reconstruct_groups(poisoned,vectors,aliases,sources);pf=reconstruct_folds(poisoned,pc)
    need(pc==components and pd==group_diag and pf==folds,'Target/outcome poison altered independent groups or folds')
    report={'schema':'isaforge-v12-independent-input-audit-v1','status':'pass','preparation_sha256':digest((root/'preparation.json').read_bytes()),
        'audit_source_sha256':digest(Path(__file__).read_bytes()),'rows_verified':len(rows),'features_verified':217,'matrix_bytes_verified':len(b''.join(vectors)),
        'component_count':len(components),'largest_component_rows':sorted([len(c['indices']) for c in components],reverse=True)[:12],
        'independent_shared_key_class_counts':group_diag['shared_key_classes'],'float32_collision_classes':len(group_diag['float32_collision_classes']),
        'fold_validation_counts':[len(v) for v in folds['validation_indices']],'fold_training_stratum_counts':folds['training_stratum_counts'],
        'new_mode_status_counts':diagnostic['accepted_new_mode_statuses'],'target_poison_groups_and_folds_unchanged':True,
        'fits_run':0,'evaluation_target_reads':0,'native_jobs':0,'bound_files_verified':len(bindings),
        'independence':'Shared predeclared recipe and frozen formula parser/V4 normalization; separately implemented adjacency closure, float32 packing, deterministic folds and target-poison replay. No V12 runner import, model fitting, native tool calls or V6/V8 evaluation-target reads.'}
    return report,rows,folds,manifest


def run(root):
    return audit_preparation(root)[0]


audit=run
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',type=Path,required=True);parser.add_argument('--output',type=Path)
    args=parser.parse_args();result=run(args.root)
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        with args.output.open('x') as stream:json.dump(result,stream,indent=2,allow_nan=False);stream.write('\n')
    print(json.dumps(result,indent=2,allow_nan=False))
