#!/usr/bin/env python3
"""Bounded, matched feature comparison on consumed development data.

Prepare freezes recovered numeric inputs and label-independent grouped folds.
Run performs exactly 15 fits, with selection confined to each training fold.
No synthesis, model artifact, promotion, or independent-test claim is made.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import signal
import subprocess
import sys
import tarfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import numpy as np
import sklearn
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.model_selection import GroupKFold
from threadpoolctl import threadpool_limits
from isaforge import area_model_v6 as v6, area_model_v8 as v8
from isaforge.features import parse_formula
from isaforge.v5_corpus import equivalence_key

ARCHIVE_COMMIT = 'b64716a'
PARAMETERS = dict(v6.FIXED_PARAMETERS)
VIEWS = ('mapping217', 'original336', 'selected128')
SELECTED_COUNT = 128
CAPS = (32, 64, 128)
MAX_FITS = 15
MAX_SECONDS = 600


def sha_bytes(value): return hashlib.sha256(value).hexdigest()
def sha(path): return sha_bytes(Path(path).read_bytes())
def read(path): return json.loads(Path(path).read_text())
def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
def now(): return datetime.now(timezone.utc).isoformat()
def git_blob(path):
    return subprocess.check_output(['git', 'show', ARCHIVE_COMMIT + ':' + path], cwd=ROOT)


def merged_components(rows, prior, vectors=None):
    """Union old components, canonical strings and normalized commutative keys.

    All three archived proof modes are included conservatively. No target or
    feature magnitude enters grouping; these are sufficient identities only.
    """
    parent = list(range(len(rows)))
    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    def join(a, b):
        a, b = find(a), find(b)
        if a != b: parent[max(a, b)] = min(a, b)
    seen = {}
    for i, row in enumerate(rows):
        keys = [('prior', prior[row['formula']])]
        if vectors is not None: keys.append(('representation_collision217', tuple(vectors[i])))
        for formula in [row['formula'], *row['normalized_formulas'].values()]:
            keys.extend([('canonical', parse_formula(formula).canonical()),
                         ('equivalence', equivalence_key(formula))])
        for key in keys:
            if key in seen: join(i, seen[key])
            else: seen[key] = i
    return np.asarray([find(i) for i in range(len(rows))], dtype=int)


def selected_indices(importances, count=SELECTED_COUNT):
    values = np.asarray(importances, dtype=float)
    if values.ndim != 1 or not np.isfinite(values).all() or count > len(values):
        raise ValueError('Invalid feature importances or selection count')
    # Feature index breaks ties, then restore schema order for fitting.
    rank = np.lexsort((np.arange(len(values)), -values))
    return np.sort(rank[:count])


def metrics(y, p, groups):
    y, p, groups = np.asarray(y), np.asarray(p), np.asarray(groups)
    error = np.abs(p-y)
    positive, zero = y > 0, y == 0
    result = {'count': len(y), 'group_count': len(np.unique(groups)),
        'group_macro_mae_lut4': float(np.mean([error[groups == g].mean() for g in np.unique(groups)])),
        'pooled_mae_lut4': float(error.mean()),
        'positive_count': int(positive.sum()),
        'positive_mape_percent': float((error[positive]/y[positive]).mean()*100) if positive.any() else None,
        'zero_count': int(zero.sum()), 'zero_mae_lut4': float(error[zero].mean()) if zero.any() else None,
        'maximum_underprediction_lut4': float(np.maximum(y-p, 0).max()), 'caps': {}}
    for cap in CAPS:
        predicted_safe, actually_safe = p <= cap, y <= cap
        false_safe = predicted_safe & ~actually_safe
        rejected = ~predicted_safe & actually_safe
        result['caps'][str(cap)] = {'predicted_safe_count': int(predicted_safe.sum()),
            'false_safe_count': int(false_safe.sum()),
            'false_safe_fraction_of_predicted_safe': float(false_safe.sum()/predicted_safe.sum()) if predicted_safe.any() else None,
            'actually_safe_count': int(actually_safe.sum()), 'false_rejection_count': int(rejected.sum()),
            'false_rejection_fraction_of_actually_safe': float(rejected.sum()/actually_safe.sum()) if actually_safe.any() else None}
    return result


def prepare(output):
    output = Path(output)
    if output.exists() and any(output.iterdir()): raise ValueError('Preparation directory must be empty')
    started = time.monotonic()
    prefix = 'results/2026-10-14-development-semantics-v7/evidence/'
    archive = git_blob(prefix+'evidence.tar.gz')
    manifest_bytes = git_blob(prefix+'evidence-manifest.json')
    manifest = json.loads(manifest_bytes)
    if sha_bytes(archive) != manifest['archive']['sha256']: raise ValueError('Archive hash differs')
    required = ['prepared/fitting.json', 'prepared/proof-ledger.json',
                'prepared/matrices/base.json', 'prepared/matrices/legacy_original.json',
                'prepared/input-diagnostics.json']
    entries = {entry['path']: entry for entry in manifest['files']}
    recovered, member_hashes = {}, {}
    with tarfile.open(fileobj=io.BytesIO(archive), mode='r:gz') as tar:
        for name in required:
            member = tar.extractfile(name).read()
            if sha_bytes(member) != entries[name]['sha256'] or len(member) != entries[name]['bytes']:
                raise ValueError('Archived member differs: '+name)
            recovered[name] = json.loads(member)
            member_hashes[name] = sha_bytes(member)
    fitting = recovered['prepared/fitting.json']
    base, original = [recovered['prepared/matrices/'+name+'.json'] for name in ('base','legacy_original')]
    if tuple(base['columns']) != v6.mapping_columns() or tuple(original['columns']) != v8.view_columns('legacy_original336'):
        raise ValueError('Explicit217/336 column contract differs')
    x = np.asarray(original['values'], dtype=float)
    if x.shape != (1665,336) or not np.isfinite(x).all() or np.any(x<0): raise ValueError('Invalid archived1665x336')
    if not np.array_equal(x[:,:217], np.asarray(base['values'])): raise ValueError('217 prefix differs from archived base')
    train_path = 'results/2026-10-15-v8-application-transfer/training/training-data.json'
    train_bytes = git_blob(train_path)
    train = json.loads(train_bytes)
    full = np.asarray(train['values'], dtype=float)
    if tuple(train['columns']) != v8.columns() or full.shape != (1665,455): raise ValueError('455 storage contract differs')
    if not np.array_equal(full[:,v8.view_indices('legacy_original336')], x): raise ValueError('Full455 recovery differs')
    ledger = recovered['prepared/proof-ledger.json']
    rows = []
    for a,b,c in zip(fitting['rows'], train['rows'], ledger):
        if any(a[k] != b[k] for k in ('formula','development_index','lut4_count')) or a['formula'] != c['formula']:
            raise ValueError('Row/target alignment differs')
        rows.append({**a, 'normalized_formulas': {mode:record['normalized_formula'] for mode,record in c['modes'].items()}})
    if len(rows)!=1665: raise ValueError('Exact1665 rows required')
    split_path = 'results/2026-10-14-v5/split.json'
    split_bytes = git_blob(split_path)
    split = json.loads(split_bytes)
    if split['fit_indices'] != [r['development_index'] for r in rows]: raise ValueError('Fit indices differ')
    semantic_groups = merged_components(rows, split['component_by_formula'])
    groups = merged_components(rows, split['component_by_formula'], x[:,:217])
    old_fold = np.asarray(fitting['fold_ids'])
    crossed = [np.flatnonzero(groups==g).tolist() for g in np.unique(groups) if len(set(old_fold[groups==g]))>1]
    folds = np.full(len(rows), -1, dtype=int)
    for fold,(_,validation) in enumerate(GroupKFold(n_splits=5).split(x, groups=groups)): folds[validation]=fold
    if np.any(folds<0) or any(len(set(folds[groups==g]))!=1 for g in np.unique(groups)):
        raise ValueError('Grouping/fold isolation failed')
    zero = np.asarray(fitting['original_zero'], dtype=bool)
    if zero.shape != (1665,): raise ValueError('Original zero-mask shape differs')
    output.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(output/'inputs.npz', x=x, y=[r['lut4_count'] for r in rows], original_zero=zero)
    write(output/'rows.json', rows)
    write(output/'columns.json', original['columns'])
    write(output/'folds.json', [{'row_index':i,'development_index':r['development_index'],'group':int(groups[i]),
        'validation_fold':int(folds[i]),'historical_validation_fold':int(old_fold[i])} for i,r in enumerate(rows)])
    write(output/'grouping-audit.json', {'row_count':1665,'merged_group_count':len(np.unique(groups)),
        'semantic_group_count_before_representation_collisions':len(np.unique(semantic_groups)),
        'largest_group_rows':max(int(np.sum(groups==g)) for g in np.unique(groups)),
        'new_fold_group_counts':[len(np.unique(groups[folds==f])) for f in range(5)],
        'historical_group_count':len({split['component_by_formula'][r['formula']] for r in rows}),
        'old_crossfold_component_count_after_union':len(crossed),'old_crossfold_rows_after_union':sum(map(len,crossed)),
        'old_crossfold_components_after_union':crossed,'new_crossfold_component_count':0,
        'historical_archived_diagnostic': {k:{'crossfold_rows':v['crossfold_rows'],
        'crossfold_component_count':v['crossfold_component_count']} for k,v in recovered['prepared/input-diagnostics.json']['by_rewrite_mode'].items()},
        'new_fold_row_counts':np.bincount(folds).tolist()})
    inputs = {p.name:sha(p) for p in sorted(output.iterdir()) if p.is_file()}
    protocol = {'schema':'isaforge-matched-feature-comparison-v1','created_at_utc':now(),
        'scope':'Development grouped cross-validation on consumed fitting cohort; not an independent test.',
        'row_count':1665,'views':{'mapping217':'14 SOG +180 generic graph descriptors (original60, normalized60, absolute delta60) +23 original mapping descriptors',
        'original336':'mapping217 +119 original-formula legacy structural/semantic descriptors, in that order',
        'selected128':'128 columns of original336 selected separately within each training fold'},
        'storage_warning':'original336 reorders the same numeric features of V6 full336 storage into a nested217 prefix plus119 legacy features; full455 is archival storage only.',
        'configuration':PARAMETERS,'selection_count':128,'selection_rule':'Descending impurity importance from the same training-fold original336 forest; ties by source feature index; selected indices restored to schema order.',
        'grouping':'Union prior V5 components with canonical and V5 equivalence_key identities of originals and all three archived proof-mode normalized formulas, then conservatively union exact217-vector collisions across every view. Representation collisions are not claimed semantic identities. GroupKFold(5), no shuffle, no labels.',
        'zero_override':'Same frozen original generic graph operator-free indicator applied to all predictions; no semantic zero override.',
        'primary_metric':'Equal-weight mean of per-merged-component OOF MAE; all three views use identical folds.',
        'secondary_metrics':['pooled MAE','positive-target MAPE percent','zero-target MAE','maximum underprediction','false safe and false rejection at caps32/64/128','nine-stratum macro MAE'],
        'caps_definition':'Point predicted<=cap is safe; false safe means actual>cap. No calibrated-bound or coverage claim.',
        'maximum_fits':15,'maximum_wall_seconds':600,'workers':1,'new_synthesis':0,'fresh_holdout_rows':0,
        'planned_execution':'Five folds, each original336 (reused for selection), mapping217, selected128. No hyperparameter search, additional feature counts, final model fits, or secondary holdout scoring.',
        'input_sha256':inputs,'runner_sha256':sha(__file__),
        'recovery':{'archive_commit':subprocess.check_output(['git','rev-parse',ARCHIVE_COMMIT],cwd=ROOT,text=True).strip(),
        'archive_path':prefix+'evidence.tar.gz','archive_sha256':sha_bytes(archive),'manifest_sha256':sha_bytes(manifest_bytes),
        'member_sha256':member_hashes,'training_path':train_path,'training_sha256':sha_bytes(train_bytes),
        'split_path':split_path,'split_sha256':sha_bytes(split_bytes)},
        'python':sys.version,'numpy':np.__version__,'sklearn':sklearn.__version__,
        'producer_source_sha256':v8.source_hashes(),'preparation_seconds':time.monotonic()-started}
    write(output/'protocol.json', protocol)
    print(json.dumps({'prepared':str(output),'protocol_sha256':sha(output/'protocol.json'),
        'old_crossfold_rows_after_union':sum(map(len,crossed)),'merged_groups':len(np.unique(groups))}),flush=True)


def run(output):
    output = Path(output)
    protocol = read(output/'protocol.json')
    if protocol['runner_sha256'] != sha(__file__): raise ValueError('Frozen runner changed')
    if (protocol['python'] != sys.version or protocol['numpy'] != np.__version__ or protocol['sklearn'] != sklearn.__version__):
        raise ValueError('Frozen numerical environment changed')
    if any(sha(output/name)!=digest for name,digest in protocol['input_sha256'].items()): raise ValueError('Frozen input changed')
    if (output/'run-start.json').exists(): raise ValueError('Run already attempted; retain attempts')
    data = np.load(output/'inputs.npz', allow_pickle=False)
    x,y,zero=data['x'],data['y'],data['original_zero']
    rows, names, assignments = [read(output/name) for name in ('rows.json','columns.json','folds.json')]
    folds=np.asarray([r['validation_fold'] for r in assignments]);groups=np.asarray([r['group'] for r in assignments])
    start=time.monotonic();fits=[];selected=[];importance=[];predictions={v:np.full(len(y),np.nan) for v in VIEWS}
    write(output/'run-start.json',{'started_at_utc':now(),'protocol_sha256':sha(output/'protocol.json'),'planned_fits':15})
    def deadline(signum,frame): raise TimeoutError('Predeclared600-second wall budget exhausted')
    old_handler=signal.signal(signal.SIGALRM,deadline);signal.setitimer(signal.ITIMER_REAL,MAX_SECONDS)
    try:
        with threadpool_limits(limits=1):
            for fold in range(5):
                train,valid=np.flatnonzero(folds!=fold),np.flatnonzero(folds==fold)
                if set(groups[train]) & set(groups[valid]): raise ValueError('Group leakage')
                for view in ('original336','mapping217','selected128'):
                    indices=np.arange(336) if view=='original336' else np.arange(217) if view=='mapping217' else chosen
                    if len(fits)>=MAX_FITS or time.monotonic()-start>=MAX_SECONDS: raise TimeoutError('Fit/wall budget exhausted')
                    fit_start=time.monotonic();model=ExtraTreesRegressor(**PARAMETERS)
                    model.fit(x[train][:,indices],y[train]);fit_seconds=time.monotonic()-fit_start
                    predict_start=time.monotonic();p=np.maximum(model.predict(x[valid][:,indices]),0);p[zero[valid]]=0
                    predictions[view][valid]=p
                    fits.append({'fit_index':len(fits)+1,'fold':fold,'view':view,'feature_count':len(indices),
                        'training_rows':len(train),'validation_rows':len(valid),'fit_seconds':fit_seconds,
                        'predict_seconds':time.monotonic()-predict_start})
                    if view=='original336':
                        chosen=selected_indices(model.feature_importances_)
                        importance.append(model.feature_importances_.tolist())
                        selected.append({'fold':fold,'training_rows':train.tolist(),'selected_indices':chosen.tolist(),
                            'selected_columns':[names[i] for i in chosen], 'full336_training_importances':model.feature_importances_.tolist()})
                    write(output/'timings.json',fits)
                    print(f"fit{len(fits)}/15 fold{fold} {view} {fit_seconds:.3f}s",flush=True)
        if any(not np.isfinite(p).all() for p in predictions.values()): raise ValueError('Incomplete OOF coverage')
        write(output/'predictions.json',[{'row_index':i,'development_index':row['development_index'],
            'formula':row['formula'],'stratum':row['stratum'],'group':int(groups[i]),'validation_fold':int(folds[i]),
            'actual_lut4':float(y[i]),'original_zero_override':bool(zero[i]),
            'predicted_lut4':{v:float(predictions[v][i]) for v in VIEWS}} for i,row in enumerate(rows)])
        write(output/'selected-columns.json',selected)
        importance=np.asarray(importance)
        write(output/'importance-summary.json',sorted([{'column':name,'source_index':i,
            'mean_training_fold_importance':float(importance[:,i].mean()),
            'selected_fold_count':sum(i in entry['selected_indices'] for entry in selected)} for i,name in enumerate(names)],
            key=lambda r:(-r['mean_training_fold_importance'],r['source_index'])))
        strata=np.asarray([r['stratum'] for r in rows]);summary={}
        for view,p in predictions.items():
            m=metrics(y,p,groups)
            m['stratum_macro_mae_lut4']=float(np.mean([np.abs(y[strata==s]-p[strata==s]).mean() for s in np.unique(strata)]))
            m['by_stratum']={s:metrics(y[strata==s],p[strata==s],groups[strata==s]) for s in np.unique(strata)}
            m['by_fold']=[metrics(y[folds==f],p[folds==f],groups[folds==f]) for f in range(5)]
            summary[view]=m
        write(output/'summary.json',{'schema':'isaforge-matched-feature-comparison-v1','scope':protocol['scope'],
            'protocol_sha256':sha(output/'protocol.json'),'metrics':summary,'fits_completed':len(fits),
            'total_wall_seconds':time.monotonic()-start,'total_fit_seconds':sum(r['fit_seconds'] for r in fits),
            'paired_group_macro_mae_delta_vs_mapping217':{v:summary[v]['group_macro_mae_lut4']-summary['mapping217']['group_macro_mae_lut4'] for v in VIEWS},
            'limitations':['Consumed development cohort, no independent generalization claim.','Single predeclared seed and feature count; no uncertainty intervals.','Finite sufficient grouping does not prove absence of every semantic equivalence.','Impurity importances are correlated-feature diagnostics, not causal attributions.']})
        files={p.name:sha(p) for p in sorted(output.iterdir()) if p.is_file() and p.name!='manifest.json'}
        write(output/'manifest.json',{'files_sha256':files})
        print(json.dumps({'fits':len(fits),'wall_seconds':time.monotonic()-start,'metrics':{v:{k:summary[v][k] for k in ('group_macro_mae_lut4','pooled_mae_lut4','positive_mape_percent','maximum_underprediction_lut4')} for v in VIEWS}}),flush=True)
    except BaseException as exc:
        write(output/'failure.json',{'error':str(exc),'fits_completed':len(fits),'wall_seconds':time.monotonic()-start})
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,old_handler)


def replay(output):
    """Recompute all reported metrics from saved OOF predictions without fitting."""
    output=Path(output)
    manifest=read(output/'manifest.json')
    if any(sha(output/name)!=digest for name,digest in manifest['files_sha256'].items()):
        raise ValueError('Result artifact hash changed')
    predictions=read(output/'predictions.json');summary=read(output/'summary.json')
    y=np.asarray([r['actual_lut4'] for r in predictions]);groups=np.asarray([r['group'] for r in predictions])
    strata=np.asarray([r['stratum'] for r in predictions]);folds=np.asarray([r['validation_fold'] for r in predictions])
    for view in VIEWS:
        p=np.asarray([r['predicted_lut4'][view] for r in predictions])
        result=metrics(y,p,groups)
        result['stratum_macro_mae_lut4']=float(np.mean([np.abs(y[strata==s]-p[strata==s]).mean() for s in np.unique(strata)]))
        result['by_stratum']={s:metrics(y[strata==s],p[strata==s],groups[strata==s]) for s in np.unique(strata)}
        result['by_fold']=[metrics(y[folds==f],p[folds==f],groups[folds==f]) for f in range(5)]
        if result!=summary['metrics'][view]: raise ValueError('Metric replay differs: '+view)
    print(json.dumps({'status':'pass','rows':len(y),'views':list(VIEWS),'new_fits':0}),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('prepare','run','replay'))
    parser.add_argument('--output',type=Path,default=ROOT/'results/feature-comparison')
    args=parser.parse_args()
    {'prepare':prepare,'run':run,'replay':replay}[args.command](args.output)
