#!/usr/bin/env python3
"""Prepare and review a fixed fitting-only V7 representation study before fitting.

No hardware tools, new targets, held-out labels, parameter search or model release.
Preparation is input/proof-only; fit requires a separate parent-authored review.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/'scripts'))
import numpy as np
from sklearn.ensemble import ExtraTreesRegressor
from threadpoolctl import threadpool_limits
from develop_v6 import fold_plan, metrics
from develop_v6_targeted import fitting_inputs, aligned_oof, read, sha, write
from isaforge.area_model import _versions
from isaforge import area_model_v5 as v5
from isaforge import structural_features_v5 as legacy
from isaforge import semantic_features_v7 as semantic
from isaforge.features import parse_formula
from isaforge.mapping_features_v6 import FEATURE_NAMES as MAPPING_NAMES
from isaforge.v5_corpus import equivalence_key

SCHEMA = 'isaforge-v7-fitting-development-v1'
SEEDS = (2026101421, 2026101422, 2026101423)
CONFIGURATION = {'n_estimators': 300, 'min_samples_leaf': 1, 'max_features': 1., 'n_jobs': 1}
VIEWS = ('base', 'bit', 'affine', 'both', 'legacy_original', 'legacy_rewritten')
CAPS = (16, 32, 64, 128, 256)
TOTAL_SOLVER_CPU_SECONDS = 900


def now(): return datetime.now(timezone.utc).isoformat()
def digest(value): return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
def outside(path):
    path = Path(path).resolve()
    if path == ROOT or ROOT in path.parents: raise ValueError('Development output must be outside repository')
    return path


def numeric_matrix(values, shape):
    matrix = np.asarray(values, dtype=float)
    if matrix.shape != shape or not np.isfinite(matrix).all() or np.any(matrix < 0):
        raise ValueError('Feature matrix must have declared shape and finite nonnegative values')
    return matrix


def bound_file(root, manifest, relative):
    matches = [r['sha256'] for r in manifest['files'] if r['path'] == relative]
    path = root/relative
    if len(matches) != 1 or sha(path) != matches[0]: raise ValueError('Frozen file identity differs: '+relative)
    return path


def archive_digest(records, suffix):
    matches = [v for k, v in records.items() if Path(k).as_posix().endswith('/'+suffix) or k == suffix]
    if len(matches) != 1: raise ValueError('Historical input missing or ambiguous: '+suffix)
    return matches[0]


def load_inputs(root, diagnostics, mapping_root, v6_root):
    """Reuse only the old fitting cohort and hash-bound original336 input values."""
    rows, fit, dependencies = fitting_inputs(root, diagnostics)
    split = read(root/'split.json'); frozen = read(root/'freeze.json')
    training = bound_file(root, frozen, 'training-start.json')
    if read(training)['sources'] != v5.source_hashes(): raise ValueError('Frozen V5 runtime differs')
    features = read(root/'development-features.json')
    if tuple(features['columns']) != v5.columns(): raise ValueError('V5 feature schema differs')
    records = [features['records'][i] for i in fit]
    if any(r['formula'] != f['formula'] for r, f in zip(rows, records)): raise ValueError('Fitting feature alignment differs')
    x = numeric_matrix([r['values'] for r in records], (1665, 313))
    plan_path = mapping_root/'plan.json'; summary_path = mapping_root/'summary.json'; block_path = mapping_root/'features.json'
    plan, summary, block = map(read, (plan_path, summary_path, block_path))
    if (plan['schema'] != 'isaforge-v6-mapping-development-v1' or plan['seeds'] != list(SEEDS)
            or plan['configuration'] != CONFIGURATION or plan['versions'] != _versions()
            or plan['fitting_formula_indices'] != fit or plan['fold_validation_indices'] != split['fold_validation_indices']
            or summary['source_plan_sha256'] != sha(plan_path) or tuple(block['columns']) != MAPPING_NAMES
            or any(plan.get(k) != 0 for k in ('calibration_rows_used','test_rows_used','external_rows_used','new_hardware_measurements'))):
        raise ValueError('Historical mapping development plan differs')
    for path in dependencies:
        suffix = 'results/2026-10-14-v5/'+path.name
        if archive_digest(plan['input_sha256'], suffix) != sha(path): raise ValueError('Mapping input binding differs')
    for name in ('develop_v6.py', 'develop_v6_mapping.py', 'develop_v6_targeted.py'):
        snapshot = mapping_root/'sources'/name
        if sha(snapshot) != archive_digest(plan['input_sha256'], 'scripts/'+name): raise ValueError('Historical source snapshot differs')
        dependencies.append(snapshot)
    module = ROOT/'isaforge/mapping_features_v6.py'
    if sha(module) != archive_digest(plan['input_sha256'], 'isaforge/mapping_features_v6.py'): raise ValueError('Mapping descriptor source differs')
    if len(block['records']) != 1665 or any((r['formula'], i) != (b['formula'], b['development_index'])
            for r, i, b in zip(rows, fit, block['records'])): raise ValueError('Mapping block alignment differs')
    mapped = numeric_matrix([r['values'] for r in block['records']], (1665, 23))
    point_path = v6_root/'point-freeze.json'; point = read(point_path)
    if (point['schema'] != 'isaforge-v6-point-freeze-v1' or point['source_v5_freeze']['sha256'] != sha(root/'freeze.json')
            or (v6_root/point['source_v5_freeze']['path']).resolve()!=(root/'freeze.json').resolve()):
        raise ValueError('V6 fitting lineage differs')
    consumed_path = bound_file(v6_root, point, 'corpus/consumed-features.json')
    consumed = read(consumed_path)
    expected_columns = list(v5.columns())+['mapping_'+n for n in MAPPING_NAMES]
    if consumed['columns'] != expected_columns: raise ValueError('Consumed full336 schema differs')
    by_formula = {r['formula']: r for r in consumed['records']}
    if len(by_formula) != len(consumed['records']): raise ValueError('Consumed formulas must be unique')
    for position, row in enumerate(rows):
        values = by_formula[row['formula']]['values']
        if values[:313] != x[position].tolist() or values[313:] != mapped[position].tolist():
            raise ValueError('Mapping features do not replay frozen V6 fitting inputs')
    dependencies += [training, root/'freeze.json', diagnostics/'run-start.json', diagnostics/'source-manifest.json',
                     plan_path, summary_path, block_path, point_path, consumed_path, module]
    references = {}
    for seed in SEEDS:
        path = mapping_root/'predictions'/f'dual_graph_plus_mapping-seed-{seed}.json'
        references[str(seed)] = aligned_oof(rows, fit, read(path)).tolist(); dependencies.append(path)
    groups = {i: split['component_by_formula'][r['formula']] for i, r in zip(fit, rows)}
    folds = fold_plan(fit, split['fold_validation_indices'], groups)
    columns = [v5.columns()[i] for i in v5.view_indices('dual_graph')]+['mapping_'+n for n in MAPPING_NAMES]
    base = np.column_stack((x[:, v5.view_indices('dual_graph')], mapped))
    return rows, fit, split, folds, base, columns, v5.original_zero(x), references, dependencies


def duplicate_diagnostic(keys, fold_ids):
    buckets = defaultdict(list)
    for i, key in enumerate(keys): buckets[key].append(i)
    duplicates = [v for v in buckets.values() if len(v)>1]
    crossed = [v for v in duplicates if len({fold_ids[i] for i in v})>1]
    return {'unique_count': len(buckets), 'duplicate_class_count': len(duplicates),
            'duplicate_rows': sum(map(len, duplicates)), 'crossfold_class_count': len(crossed),
            'crossfold_rows': sum(map(len, crossed)), 'crossfold_classes': crossed}


def equivalence_diagnostic(formulas, normalized, groups, fold_ids):
    """Join existing groups and every original/accepted normalized identity key."""
    parent = list(range(len(formulas)))
    def find(i):
        while parent[i] != i: parent[i] = parent[parent[i]]; i = parent[i]
        return i
    def join(a,b):
        a,b=find(a),find(b)
        if a!=b: parent[max(a,b)]=min(a,b)
    seen = {}
    for i,(original, new, group) in enumerate(zip(formulas, normalized, groups)):
        keys = [('old_component', group)]
        for formula in (original, new):
            keys += [('canonical', parse_formula(formula).canonical()), ('commutative', str(equivalence_key(formula)))]
        for key in keys:
            if key in seen: join(i,seen[key])
            else: seen[key]=i
    components=defaultdict(list)
    for i in range(len(formulas)): components[find(i)].append(i)
    cross=[v for v in components.values() if len({fold_ids[i] for i in v})>1]
    return {'component_count':len(components),'component_sizes':sorted(map(len,components.values())),
            'crossfold_component_count':len(cross),'crossfold_rows':sum(map(len,cross)),
            'crossfold_components':cross,'row_components':[find(i) for i in range(len(formulas))]}


def prevalence(matrix, names, folds):
    return {name:{'unique_values':int(len(np.unique(matrix[:,j]))),'nonzero_rows':int(np.count_nonzero(matrix[:,j])),
        'minimum':float(matrix[:,j].min()),'maximum':float(matrix[:,j].max()),
        'training_unique_values_by_fold':[int(len(np.unique(matrix[t,j]))) for t,_ in folds],
        'training_variance_by_fold':[float(np.var(matrix[t,j])) for t,_ in folds]}
        for j,name in enumerate(names)}


def source_paths():
    # All package modules cover the recursive legacy/parser/feature dependencies.
    return sorted([*ROOT.joinpath('isaforge').glob('*.py'), Path(__file__).resolve(),
        ROOT/'scripts/develop_v6.py',ROOT/'scripts/develop_v6_targeted.py',ROOT/'docs/v7-development-protocol.md',
        *ROOT.joinpath('tests').glob('test_semantic_features_v7*.py'),ROOT/'tests/test_develop_v7_semantics.py',
        ROOT/'results/2026-10-14-development-semantics-v7/audit/audit_fitting.py',
        ROOT/'results/2026-10-14-development-semantics-v7/audit/prove_rules.py'])


def check_hashes(records):
    if any(not Path(path).is_file() or sha(path)!=value for path,value in records.items()):
        raise ValueError('Bound input/source changed')


def prepare(root, diagnostics, mapping_root, v6_root, output):
    output=outside(output)
    if output.exists() and any(output.iterdir()): raise ValueError('Existing preparation is immutable')
    if not semantic.solver_identity().get('available'): raise ValueError('Formal solver unavailable; preparation stopped')
    budget=semantic.Budget(proof_timeout_ms=500)
    rows,fit,split,folds,base,base_names,zero,references,dependencies=load_inputs(root,diagnostics,mapping_root,v6_root)
    y=[r['lut4_count'] for r in rows]; strata=[r.get('stratum','workload') for r in rows]
    if len(set(strata))!=9 or not np.isfinite(y).all() or np.any(np.asarray(y)<0): raise ValueError('Expected all nine fitting strata and valid targets')
    proof_root=ROOT/'results/2026-10-14-development-semantics-v7/audit'
    generic=read(proof_root/'generic-proofs.json');proof_audit=read(proof_root/'fitting-inputs/fitting-input-audit.json')
    if (generic.get('status')!='pass' or generic.get('proof_count')!=110 or len(generic.get('results',[]))!=110
        or any(p.get('result')!='unsat' or p.get('replayed_result')!='unsat' for p in generic['results'])
        or proof_audit.get('status')!='pass' or proof_audit.get('rows')!=1665):
        raise ValueError('Complete passing universal/fitting proof audits required before preparation')
    if sha(proof_root/'prove_rules.py')!=generic['source_sha256']:raise ValueError('Generic proof source changed')
    for name,value in proof_audit['source_sha256'].items():
        if sha(ROOT/name)!=value:raise ValueError('Independent proof audit source changed: '+name)
    proof_files=sorted(p for p in proof_root.rglob('*') if p.is_file() and p.suffix in ('.py','.json','.smt2'))
    paths=list(dict.fromkeys([*dependencies,*source_paths(),*proof_files]))
    hashes={str(p.resolve()):sha(p) for p in paths}
    fold_ids=np.full(1665,-1,dtype=int)
    for k,(_,v) in enumerate(folds): fold_ids[v]=k
    names={'base':base_names,'bit':base_names+list(semantic.BIT_NAMES),'affine':base_names+list(semantic.AFFINE_NAMES),
           'both':base_names+list(semantic.FEATURE_NAMES),'legacy_original':base_names+list(legacy.FEATURE_NAMES),
           'legacy_rewritten':base_names+list(legacy.FEATURE_NAMES)}
    plan={'schema':SCHEMA,'stage':'pre-feature-plan','created_at_utc':now(),'scope':'Fitting-only descriptive development; no independent evaluation',
        'input_sha256':hashes,'independent_proof_inputs':{str(p.resolve()):sha(p) for p in proof_files},'versions':_versions(),'solver':semantic.solver_identity(),'budget':asdict(budget),
        'total_solver_cpu_seconds':TOTAL_SOLVER_CPU_SECONDS,'seeds':SEEDS,'configuration':CONFIGURATION,'maximum_fits':90,
        'columns':names,'fitting_formula_indices':fit,'fold_validation_indices':split['fold_validation_indices'],
        'formula_sha256':digest([r['formula'] for r in rows]),'targets_sha256':digest(y),'fold_ids_sha256':digest(fold_ids.tolist()),
        'old_component_ids_sha256':digest([split['component_by_formula'][r['formula']] for r in rows]),
        'v5_freeze_sha256':sha(root/'freeze.json'),'input_features_sha256':sha(root/'development-features.json'),
        'split_sha256':sha(root/'split.json'),'fit_indices_sha256':digest(fit),
        'zero_override':'Original generic graph operator-free indicator only; unchanged across all views',
        'primary':'Mean across3 seeds of nine-stratum macro OOF MAE both minus base',
        'calibration_rows_used':0,'test_rows_used':0,'external_rows_used':0,'new_hardware_measurements':0,
        'review_policy':'No fit until separate parent approval binds pre-score freeze and independent proof audit; all new crossfold equivalences require explicit assessment'}
    write(output/'plan.json',plan)
    for path in source_paths():
        target=output/'sources'/path.relative_to(ROOT); target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,target)
    ledgers=[]; bit=[]; affine=[]; old=[]; rewritten=[]; solver_cpu=0.
    for i,row in enumerate(rows):
        modes=semantic.analyze_modes(row['formula'],budget=budget)
        if set(modes)!={'bit','affine','combined'}: raise ValueError('Three proof modes required')
        b=[modes['bit']['features'][n] for n in semantic.BIT_NAMES]
        a=[modes['affine']['features'][n] for n in semantic.AFFINE_NAMES]
        if b+a != [modes['combined']['features'][n] for n in semantic.FEATURE_NAMES]: raise ValueError('Combined block nesting differs')
        for mode,record in modes.items():
            if record['original_formula']!=parse_formula(row['formula']).canonical(): raise ValueError('Proof record input differs')
            if record['metadata'].get('original_zero_override') is not False: raise ValueError('Semantic zero override forbidden')
            certificate=record['metadata']['certificate']
            if certificate['final']!=record['normalized_formula']: raise ValueError('Proof certificate output differs')
        solver_cpu+=modes['combined']['metadata']['proof_engine']['solver_seconds']
        ledgers.append({'formula':row['formula'],'development_index':fit[i],'modes':modes})
        bit.append(b);affine.append(a)
        original_values=legacy.feature_dict(row['formula'])
        old.append([original_values[n] for n in legacy.FEATURE_NAMES])
        rewritten_values=legacy.feature_dict(modes['combined']['normalized_formula'])
        rewritten.append([rewritten_values[n] for n in legacy.FEATURE_NAMES])
        if solver_cpu>TOTAL_SOLVER_CPU_SECONDS:
            write(output/'preparation-failure.json',{'reason':'total proof CPU budget exceeded','rows_completed':i+1,'solver_cpu_seconds':solver_cpu})
            write(output/'partial-proof-ledger.json',ledgers);raise ValueError('Total proof CPU budget exceeded; no fits permitted')
        if (i+1)%100==0: print('prepared formula proofs',i+1,'/1665',flush=True)
    matrices={'base':base,'bit':np.column_stack((base,bit)),'affine':np.column_stack((base,affine)),
              'both':np.column_stack((base,bit,affine)),'legacy_original':np.column_stack((base,old)),
              'legacy_rewritten':np.column_stack((base,rewritten))}
    originals=[r['formula'] for r in rows]; groups=[split['component_by_formula'][f] for f in originals]
    baseline_equivalence=equivalence_diagnostic(originals,originals,groups,fold_ids.tolist())
    diagnostics_out={'original_equivalence':baseline_equivalence,'by_rewrite_mode':{},'exact_vector_duplicates':{},'prevalence':{},'solver_cpu_seconds':solver_cpu}
    for mode in ('bit','affine','combined'):
        normalized=[r['modes'][mode]['normalized_formula'] for r in ledgers]
        diagnostics_out['by_rewrite_mode'][mode]={'changed_rows':sum(parse_formula(a).canonical()!=b for a,b in zip(originals,normalized)),
            'statuses':dict(Counter(r['modes'][mode]['metadata']['status'] for r in ledgers)),
            **equivalence_diagnostic(originals,normalized,groups,fold_ids.tolist())}
    for view,matrix in matrices.items():
        numeric_matrix(matrix,(1665,len(names[view])))
        diagnostics_out['prevalence'][view]=prevalence(matrix,names[view],folds)
        diagnostics_out['exact_vector_duplicates'][view]=duplicate_diagnostic([tuple(r) for r in matrix],fold_ids.tolist())
        write(output/'matrices'/f'{view}.json',{'columns':names[view],'values':matrix.tolist()})
    write(output/'proof-ledger.json',ledgers)
    write(output/'input-diagnostics.json',diagnostics_out)
    write(output/'fitting.json',{'rows':[{'formula':r['formula'],'development_index':i,'stratum':s,'lut4_count':y0}
        for r,i,s,y0 in zip(rows,fit,strata,y)],'fold_ids':fold_ids.tolist(),'original_zero':zero.tolist(),'base_oof_reference':references})
    check_hashes(hashes)
    files={p.relative_to(output).as_posix():sha(p) for p in sorted(output.rglob('*')) if p.is_file()}
    cross={mode:sum(len({baseline_equivalence['row_components'][i] for i in component})>1
              for component in d['crossfold_components']) for mode,d in diagnostics_out['by_rewrite_mode'].items()}
    seal={'schema':SCHEMA,'stage':'pre-score-freeze','status':'parent_review_required','created_at_utc':now(),'files_sha256':files,
        'plan_sha256':sha(output/'plan.json'),'new_equivalence_crossfold_components':cross,
        'crossfold_vector_class_counts':{v:d['crossfold_class_count'] for v,d in diagnostics_out['exact_vector_duplicates'].items()},
        'all_original_folds_descriptive':True,'fits_completed':0,'maximum_fits':90,'solver_cpu_seconds':solver_cpu}
    write(output/'pre-score-freeze.json',seal)
    print(json.dumps({'status':seal['status'],'pre_score_freeze_sha256':sha(output/'pre-score-freeze.json'),'crossfold':cross}))
    return seal


def detailed_metrics(y,p,strata):
    result=metrics(y,p,strata)
    def cell(mask):
        a,b=y[mask],p[mask];e=b-a;ae=np.abs(e);positive=a>0;zero=a==0
        return {'count':int(mask.sum()),'mae_lut4':float(ae.mean()),'signed_bias_lut4':float(e.mean()),
            'rmsle':float(np.sqrt(np.mean((np.log1p(b)-np.log1p(a))**2))),
            'positive_target_count':int(positive.sum()),'positive_mape_percent':float(np.mean(ae[positive]/a[positive])*100) if positive.any() else None,
            'zero_target_count':int(zero.sum()),'zero_mae_lut4':float(ae[zero].mean()) if zero.any() else None,
            'p95_absolute_error_lut4':float(np.quantile(ae,.95)),'p99_absolute_error_lut4':float(np.quantile(ae,.99)),
            'worst_absolute_error_lut4':float(ae.max()),'maximum_underprediction_lut4':float(np.maximum(-e,0).max()),
            'underprediction_count':int((e<0).sum()),'overprediction_count':int((e>0).sum()),'exact_prediction_count':int((e==0).sum()),
            'caps':{str(cap):{'false_accept_count':int(((b<=cap)&(a>cap)).sum()),'false_reject_count':int(((b>cap)&(a<=cap)).sum()),
                'predicted_feasible_count':int((b<=cap).sum()),'actually_feasible_count':int((a<=cap).sum()),'count':len(a)} for cap in CAPS}}
    result['all_rows']=cell(np.ones(len(y),dtype=bool));result['by_stratum']={s:cell(strata==s) for s in sorted(set(strata))}
    return result


def validate_prepared(prepared,review_path):
    prepared=outside(prepared);seal=read(prepared/'pre-score-freeze.json');plan=read(prepared/'plan.json');review=read(review_path)
    if seal.get('schema')!=SCHEMA or seal.get('stage')!='pre-score-freeze' or seal.get('fits_completed')!=0 or seal.get('maximum_fits')!=90:
        raise ValueError('Invalid pre-score freeze')
    for name,value in seal['files_sha256'].items():
        path=(prepared/name).resolve()
        if prepared not in path.parents or sha(path)!=value: raise ValueError('Prepared file changed')
    if sha(prepared/'plan.json')!=seal['plan_sha256']: raise ValueError('Prepared plan changed')
    check_hashes(plan['input_sha256'])
    if plan['versions']!=_versions() or plan['seeds']!=list(SEEDS) or plan['configuration']!=CONFIGURATION or set(plan['columns'])!=set(VIEWS):
        raise ValueError('Fixed fitting configuration differs')
    if (review.get('schema')!='isaforge-v7-parent-fit-review-v1' or review.get('approved') is not True
        or review.get('pre_score_freeze_sha256')!=sha(prepared/'pre-score-freeze.json')
        or review.get('preserve_original_folds_descriptive') is not True
        or datetime.fromisoformat(review['reviewed_at_utc'])<datetime.fromisoformat(seal['created_at_utc'])):
        raise ValueError('Separate parent review required')
    if any(seal['new_equivalence_crossfold_components'].values()) and not (isinstance(review.get('crossfold_equivalence_assessment'),str) and review['crossfold_equivalence_assessment'].strip()):
        raise ValueError('Parent must assess newly established crossfold equivalence before descriptive fits')
    if any(seal['crossfold_vector_class_counts'].values()) and not (isinstance(review.get('crossfold_vector_assessment'),str) and review['crossfold_vector_assessment'].strip()):
        raise ValueError('Parent must assess full-vector crossfold duplicates before descriptive fits')
    proof=review['independent_proof_audit'];proof_path=Path(proof['path'])
    if not proof_path.is_absolute():proof_path=Path(review_path).resolve().parent/proof_path
    audit=read(proof_path)
    if (sha(proof_path)!=proof['sha256'] or str(audit.get('status','')).lower() not in ('passed','pass')
        or review.get('proof_ledger_sha256')!=sha(prepared/'proof-ledger.json')
        or review.get('semantic_source_sha256')!=sha(ROOT/'isaforge/semantic_features_v7.py')):
        raise ValueError('Passing independent proof audit required')
    if (audit.get('rows')!=1665 or audit.get('fit_formula_sha256')!=plan['formula_sha256']
        or any(audit.get(key)!=plan[key] for key in ('v5_freeze_sha256','input_features_sha256','split_sha256','fit_indices_sha256'))
        or audit.get('source_sha256',{}).get('isaforge/semantic_features_v7.py')!=review['semantic_source_sha256']
        or audit.get('source_sha256',{}).get('isaforge/features.py')!=sha(ROOT/'isaforge/features.py')
        or audit.get('solver_version')!=plan['solver']['version'] or semantic.solver_identity()!=plan['solver']):
        raise ValueError('Independent proof audit source/solver/fitting cohort differs')
    for name,value in audit['source_sha256'].items():
        if sha(ROOT/name)!=value:raise ValueError('Independent proof audit source changed: '+name)
    independent_path=proof_path.with_name('fitting-input-records.json')
    if sha(independent_path)!=audit.get('records_sha256'):raise ValueError('Independent proof records changed')
    independent=read(independent_path);ledger=read(prepared/'proof-ledger.json')
    if len(independent)!=1665 or len(ledger)!=1665:raise ValueError('Independent ledger coverage differs')
    for actual,expected in zip(ledger,independent):
        if (actual['formula']!=expected['formula'] or actual['development_index']!=expected['original_index']
            or any(actual['modes'][mode][key]!=expected['modes'][mode][key]
                for mode in ('bit','affine','combined') for key in ('normalized_formula','features'))):
            raise ValueError('Prepared features/normal forms differ from independently audited records')
    return prepared,seal,plan,review,proof_path


@threadpool_limits.wrap(limits=1)
def fit(prepared,review_path):
    prepared,seal,plan,review,proof_path=validate_prepared(prepared,review_path)
    output=prepared/'fit'
    if output.exists():raise ValueError('Existing fitting attempt is immutable')
    data=read(prepared/'fitting.json');rows=data['rows'];ids=np.asarray(data['fold_ids']);y=np.asarray([r['lut4_count'] for r in rows],dtype=float)
    strata=np.asarray([r['stratum'] for r in rows]);zero=np.asarray(data['original_zero'],dtype=bool)
    if len(rows)!=1665 or set(ids)!=set(range(5)) or zero.shape!=(1665,):raise ValueError('Prepared row/fold coverage differs')
    if digest(y.tolist())!=plan['targets_sha256'] or digest(ids.tolist())!=plan['fold_ids_sha256']:raise ValueError('Prepared label/fold hash differs')
    matrices={}
    for view in VIEWS:
        record=read(prepared/'matrices'/f'{view}.json')
        if record['columns']!=plan['columns'][view]:raise ValueError('Prepared column order differs')
        matrices[view]=numeric_matrix(record['values'],(1665,len(record['columns'])))
    write(output/'fit-start.json',{'schema':SCHEMA,'started_at_utc':now(),'pre_score_freeze_sha256':sha(prepared/'pre-score-freeze.json'),
        'review_sha256':sha(review_path),'independent_proof_audit_sha256':sha(proof_path),'seeds':SEEDS,'configuration':CONFIGURATION,'maximum_fits':90})
    scores={v:{} for v in VIEWS};predictions={};reuse={};fits=0
    for seed in SEEDS:
        for view in VIEWS:
            duplicate=next((old for old in VIEWS[:VIEWS.index(view)] if np.array_equal(matrices[old],matrices[view])),None)
            times=[];params=ExtraTreesRegressor(**CONFIGURATION,random_state=seed).get_params(deep=True)
            if duplicate is not None:p=predictions[(duplicate,seed)].copy();reuse[view]=duplicate
            else:
                p=np.zeros(1665)
                for fold in range(5):
                    training=ids!=fold;validation=ids==fold;began=time.perf_counter()
                    model=ExtraTreesRegressor(**CONFIGURATION,random_state=seed)
                    model.fit(matrices[view][training],y[training]);p[validation]=np.maximum(model.predict(matrices[view][validation]),0)
                    times.append(time.perf_counter()-began);fits+=1
                p[zero]=0
            if view=='base' and not np.array_equal(p,np.asarray(data['base_oof_reference'][str(seed)])):
                raise ValueError('Base217 failed exact historical OOF replay; study stopped')
            predictions[(view,seed)]=p;scores[view][str(seed)]={**detailed_metrics(y,p,strata),'parameters':params,'fold_fit_predict_seconds':times,'reused_view':duplicate}
            write(output/'predictions'/f'{view}-seed-{seed}.json',[{**r,'predicted_lut4':float(p[i]),'signed_error_lut4':float(p[i]-y[i])} for i,r in enumerate(rows)])
            write(output/'metrics'/f'{view}-seed-{seed}.json',scores[view][str(seed)])
            print(view,seed,'macro-MAE',scores[view][str(seed)]['macro_stratum_mae_lut4'],flush=True)
    summary={'schema':SCHEMA,'scope':'Descriptive fitting-only CV on consumed original folds; not independent evaluation',
        'scores':scores,'fits_completed':fits,'exact_matrix_reuse':reuse,'by_view':{},'paired_comparisons':{},
        'seed_uncertainty':'Sample SD over3 algorithm seeds on identical data; no population CI or significance claim',
        'new_equivalence_crossfold_components':seal['new_equivalence_crossfold_components'],'pre_score_freeze_sha256':sha(prepared/'pre-score-freeze.json')}
    for view in VIEWS:
        m=[scores[view][str(s)]['macro_stratum_mae_lut4'] for s in SEEDS]
        summary['by_view'][view]={'macro_mae_mean':float(np.mean(m)),'macro_mae_sample_sd':float(np.std(m,ddof=1)),
            'by_stratum_mean_mae':{st:float(np.mean([scores[view][str(s)]['by_stratum'][st]['mae_lut4'] for s in SEEDS])) for st in sorted(set(strata))}}
    for left,right in [('both','base'),('bit','base'),('affine','base'),('both','bit'),('both','affine'),('legacy_rewritten','legacy_original'),('both','legacy_rewritten')]:
        values=[scores[left][str(s)]['macro_stratum_mae_lut4']-scores[right][str(s)]['macro_stratum_mae_lut4'] for s in SEEDS]
        summary['paired_comparisons'][left+'_minus_'+right]={'values_lut4':values,'mean_lut4':float(np.mean(values)),
            'per_stratum_mean_difference':{st:summary['by_view'][left]['by_stratum_mean_mae'][st]-summary['by_view'][right]['by_stratum_mean_mae'][st] for st in sorted(set(strata))}}
    validate_prepared(prepared,review_path)
    if fits>90:raise ValueError('Fit budget exceeded')
    write(output/'summary.json',summary);return summary


def main():
    parser=argparse.ArgumentParser(description=__doc__);commands=parser.add_subparsers(dest='command',required=True)
    p=commands.add_parser('prepare');p.add_argument('--root',type=Path,default=ROOT/'results/2026-10-14-v5')
    p.add_argument('--diagnostics',type=Path,default=ROOT/'results/2026-10-14-development-diagnostics')
    p.add_argument('--mapping-root',type=Path,default=ROOT/'results/2026-10-14-development-mapping')
    p.add_argument('--v6-root',type=Path,default=ROOT/'results/2026-10-14-v6');p.add_argument('--output',type=Path,required=True)
    p=commands.add_parser('fit');p.add_argument('--prepared',type=Path,required=True);p.add_argument('--review',type=Path,required=True)
    args=parser.parse_args()
    if args.command=='prepare':prepare(*[Path(getattr(args,n)).resolve() for n in ('root','diagnostics','mapping_root','v6_root','output')])
    else:fit(args.prepared,args.review)

if __name__=='__main__':main()
