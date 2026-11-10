#!/usr/bin/env python3
"""Fixed two-seed extension and frozen experimental full-data point models.

No synthesis, adaptive subset search, model promotion, or independent-test claim.
Prepare freezes the protocol before run; replay uses only the standard library.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import signal
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(Path(__file__).parent))
from replay_selection_stability import SEEDS, VIEWS, eligibility, selection_stability, summaries, replay

MAX_FITS = 33
MAX_SECONDS = 600
SCHEMA = 'isaforge-selection-stability-v1'
PARAMETERS = {'n_estimators':300,'min_samples_leaf':1,'max_features':1.,'n_jobs':1,'random_state':SEEDS[0]}


def read(path): return json.loads(Path(path).read_text())
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def now(): return datetime.now(timezone.utc).isoformat()
def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')


def source_hashes():
    names = ('scripts/test_selection_stability.py','scripts/replay_selection_stability.py',
             'scripts/compare_features.py','scripts/replay_feature_comparison.py')
    return {name:sha(ROOT/name) for name in names}


def prepare(output,source):
    import numpy as np
    import sklearn
    from isaforge import area_model_v8 as v8
    output,source=Path(output),Path(source)
    if output.exists() and any(output.iterdir()): raise ValueError('Preparation directory must be empty')
    prior_protocol,prior_manifest=read(source/'protocol.json'),read(source/'manifest.json')
    for name,digest in prior_manifest['files_sha256'].items():
        if sha(source/name)!=digest: raise ValueError('Prior frozen evidence differs: '+name)
    if prior_protocol['configuration']!=PARAMETERS: raise ValueError('Original parameters changed')
    output.mkdir(parents=True,exist_ok=True)
    for name in ('inputs.npz','rows.json','columns.json','folds.json','grouping-audit.json'):
        shutil.copyfile(source/name,output/name)
    for name in ('protocol.json','predictions.json','summary.json','selected-columns.json','manifest.json','timings.json'):
        target=output/'original-seed'/name;target.parent.mkdir(exist_ok=True)
        shutil.copyfile(source/name,target)
    inputs={str(p.relative_to(output)):sha(p) for p in sorted(output.rglob('*')) if p.is_file()}
    protocol={'schema':SCHEMA,'created_at_utc':now(),'original_seed':SEEDS[0],'new_seeds':list(SEEDS[1:]),
        'scope':'Consumed development data; original seed reused descriptively. Repeated seeds are not independent data.',
        'row_count':1665,'group_count':522,'fold_count':5,'views':list(VIEWS),'configuration':PARAMETERS,
        'selection_count':128,'selection_rule':prior_protocol['selection_rule'],
        'grouping':prior_protocol['grouping'],'primary_metric':prior_protocol['primary_metric'],
        'caps_definition':prior_protocol['caps_definition'],'zero_override':prior_protocol['zero_override'],
        'strict_eligibility':{'reference':'mapping217','primary':'selected128 group-macro MAE strictly lower on every one of three seeds',
            'caps':'Across all three seeds, sum false-safe counts and sum false-rejection counts each no worse at every cap32/64/128',
            'underprediction':'Maximum underprediction over all rows and all three seeds no worse',
            'mean_error_promising':'Primary MAE strictly lower on every seed; report separately even when budget/tail gate fails',
            'independence_warning':'Aggregates describe algorithm randomness on the same 1665 rows; no independent-sample inference or pooled confidence interval.'},
        'maximum_new_fits':MAX_FITS,'planned_new_cv_fits':30,'planned_full_data_fits':3,'maximum_wall_seconds':MAX_SECONDS,
        'workers':1,'native_threads':1,'new_synthesis':0,'fresh_holdout_rows':0,
        'planned_execution':'Each new seed: five fixed folds; original336 reused for importance selection, mapping217, selected128. Then original-seed full-data mapping217, original336 selector, selected128. Exactly33 fits. No adaptive counts, seeds, subsets, or parameter search.',
        'full_data_candidate':'Fit original336 selector on all1665 rows with originalseed2026101401, deterministically select128, fit selected128. Persist all3 experimental point forests even if strict eligibility fails. No promotion or calibration.',
        'input_sha256':inputs,'runner_source_sha256':source_hashes(),'producer_source_sha256':v8.source_hashes(),
        'full455_columns':list(v8.columns()),'full455_to_original336_indices':v8.view_indices('legacy_original336').tolist(),
        'python':sys.version,'numpy':np.__version__,'sklearn':sklearn.__version__}
    write(output/'protocol.json',protocol)
    print(json.dumps({'prepared':str(output),'protocol_sha256':sha(output/'protocol.json'),'new_fits':0}),flush=True)


class FrozenPredictor:
    """Experimental point predictions from an explicitly named 336 or 455 schema."""
    def __init__(self,estimator,metadata): self.estimator,self.metadata=estimator,metadata

    def predict_features(self,values,columns,original_zero=None):
        import numpy as np
        if list(columns)!=self.metadata['source_columns']: raise ValueError('Explicit original336 feature schema/order differs')
        x=np.asarray(values,dtype=float)
        if x.ndim!=2 or x.shape[1]!=336 or not np.isfinite(x).all() or np.any(x<0): raise ValueError('Invalid original336 feature matrix')
        zero=x[:,self.metadata['zero_override']['source_column_index']]==0
        if original_zero is not None:
            supplied=np.asarray(original_zero)
            if supplied.dtype!=np.bool_ or supplied.shape!=(len(x),) or not np.array_equal(supplied,zero):
                raise ValueError('Generic-graph zero override differs')
        p=np.maximum(self.estimator.predict(x[:,self.metadata['selected_indices']]),0)
        p[zero]=0
        return p

    def predict_full455(self,values,columns,original_zero=None):
        import numpy as np
        if list(columns)!=self.metadata['full455_columns']: raise ValueError('Explicit full455 feature schema/order differs')
        x=np.asarray(values,dtype=float)
        if x.ndim!=2 or x.shape[1]!=455 or not np.isfinite(x).all() or np.any(x<0): raise ValueError('Invalid full455 feature matrix')
        return self.predict_features(x[:,self.metadata['full455_to_original336_indices']],self.metadata['source_columns'],original_zero)


def load_predictor(output,view='selected128'):
    import joblib
    from isaforge import area_model_v6 as v6, area_model_v8 as v8
    if view not in VIEWS: raise ValueError('Unknown frozen experimental view')
    output=Path(output);metadata=read(output/'models'/f'{view}.json');artifact=output/'models'/f'{view}.joblib'
    protocol=read(output/'protocol.json')
    if metadata['schema']!=SCHEMA or metadata['experimental_only'] is not True or metadata['point_only'] is not True:
        raise ValueError('Experimental point model schema differs')
    if metadata['view']!=view or metadata['artifact_sha256']!=sha(artifact) or metadata['protocol_sha256']!=sha(output/'protocol.json'):
        raise ValueError('Frozen artifact/protocol hash differs')
    if metadata['runtime_source_sha256']!=v8.source_hashes() or protocol['runner_source_sha256']!=source_hashes():
        raise ValueError('Frozen inference source differs')
    names=read(output/'columns.json')
    if (metadata['source_columns']!=names or names!=list(v8.view_columns('legacy_original336'))
        or metadata['full455_columns']!=list(v8.columns())
        or metadata['full455_to_original336_indices']!=v8.view_indices('legacy_original336').tolist()):
        raise ValueError('Frozen feature schema differs')
    selected=metadata['selected_indices']
    expected=list(range(217)) if view=='mapping217' else list(range(336)) if view=='original336' else read(output/'models/full-data-selection.json')['selected_indices']
    if selected!=expected or metadata['selected_columns']!=[names[i] for i in selected]: raise ValueError('Frozen selected indices differ')
    if metadata['zero_override']!={'source_column':'original_gate_count','source_column_index':names.index('original_gate_count'),'condition':'equals0'}:
        raise ValueError('Frozen zero override differs')
    model=joblib.load(artifact)
    if model.n_features_in_!=len(selected) or v6.estimator_fingerprint(model)!=metadata['estimator_fingerprint']:
        raise ValueError('Frozen fitted forest state differs')
    return FrozenPredictor(model,metadata)


def run(output):
    import joblib
    import numpy as np
    import sklearn
    from sklearn.ensemble import ExtraTreesRegressor
    from threadpoolctl import threadpool_limits
    from compare_features import selected_indices
    from isaforge import area_model_v6 as v6, area_model_v8 as v8
    output=Path(output);protocol=read(output/'protocol.json')
    if protocol['runner_source_sha256']!=source_hashes() or protocol['producer_source_sha256']!=v8.source_hashes():
        raise ValueError('Frozen runner/producer source differs')
    if (protocol['python'],protocol['numpy'],protocol['sklearn'])!=(sys.version,np.__version__,sklearn.__version__):
        raise ValueError('Frozen numerical environment differs')
    for name,digest in protocol['input_sha256'].items():
        if sha(output/name)!=digest: raise ValueError('Frozen input differs: '+name)
    if (output/'run-start.json').exists(): raise ValueError('Run already attempted; retain attempt')
    with np.load(output/'inputs.npz',allow_pickle=False) as data:
        x,y,zero=data['x'],data['y'],data['original_zero']
    names,rows,assignments=[read(output/name) for name in ('columns.json','rows.json','folds.json')]
    folds=np.asarray([r['validation_fold'] for r in assignments]);groups=np.asarray([r['group'] for r in assignments])
    if x.shape!=(1665,336) or len(set(groups))!=522 or not np.array_equal(zero,x[:,names.index('original_gate_count')]==0):
        raise ValueError('Frozen1665/336/522/zero contract differs')
    predictions=[{'seed':SEEDS[0],**r} for r in read(output/'original-seed/predictions.json')]
    selections=[{'seed':SEEDS[0],**r} for r in read(output/'original-seed/selected-columns.json')]
    fits=[];start=time.monotonic()
    write(output/'run-start.json',{'started_at_utc':now(),'protocol_sha256':sha(output/'protocol.json'),'planned_new_fits':33})
    def deadline(signum,frame): raise TimeoutError('Predeclared600-second total wall budget exhausted')
    old=signal.signal(signal.SIGALRM,deadline);signal.setitimer(signal.ITIMER_REAL,MAX_SECONDS)
    def fit(stage,seed,fold,view,indices,train):
        if len(fits)>=MAX_FITS or time.monotonic()-start>=MAX_SECONDS: raise TimeoutError('Fit/wall budget exhausted')
        began=time.monotonic();model=ExtraTreesRegressor(**{**PARAMETERS,'random_state':seed})
        model.fit(x[train][:,indices],y[train])
        fits.append({'fit_index':len(fits)+1,'stage':stage,'seed':seed,'fold':fold,'view':view,
                     'feature_count':len(indices),'training_rows':len(train),'fit_seconds':time.monotonic()-began})
        write(output/'timings.json',fits)
        print(f"fit{len(fits)}/33 {stage} seed{seed} fold{fold} {view} {fits[-1]['fit_seconds']:.3f}s",flush=True)
        return model
    try:
        with threadpool_limits(limits=1):
            for seed in SEEDS[1:]:
                p={v:np.full(len(y),np.nan) for v in VIEWS}
                for fold in range(5):
                    train,valid=np.flatnonzero(folds!=fold),np.flatnonzero(folds==fold)
                    if set(groups[train])&set(groups[valid]): raise ValueError('Group leakage')
                    for view in ('original336','mapping217','selected128'):
                        indices=np.arange(336) if view=='original336' else np.arange(217) if view=='mapping217' else chosen
                        model=fit('cross_validation',seed,fold,view,indices,train)
                        values=np.maximum(model.predict(x[valid][:,indices]),0);values[zero[valid]]=0;p[view][valid]=values
                        if view=='original336':
                            chosen=selected_indices(model.feature_importances_)
                            selections.append({'seed':seed,'fold':fold,'training_rows':train.tolist(),'selected_indices':chosen.tolist(),
                                'selected_columns':[names[i] for i in chosen],'full336_training_importances':model.feature_importances_.tolist()})
                if any(not np.isfinite(v).all() for v in p.values()): raise ValueError('Incomplete OOF coverage')
                predictions.extend([{'seed':seed,'row_index':i,'development_index':r['development_index'],'formula':r['formula'],
                    'stratum':r['stratum'],'group':int(groups[i]),'validation_fold':int(folds[i]),'actual_lut4':float(y[i]),
                    'original_zero_override':bool(zero[i]),'predicted_lut4':{v:float(p[v][i]) for v in VIEWS}} for i,r in enumerate(rows)])
            write(output/'predictions.json',predictions);write(output/'selected-columns.json',selections)
            for view in VIEWS:
                indices=np.arange(217) if view=='mapping217' else np.arange(336) if view=='original336' else chosen
                model=fit('full_data',SEEDS[0],None,view,indices,np.arange(len(y)))
                artifact=output/'models'/f'{view}.joblib';artifact.parent.mkdir(exist_ok=True)
                joblib.dump(model,artifact,compress=3)
                write(output/'models'/f'{view}.json',{'schema':SCHEMA,'view':view,'experimental_only':True,'point_only':True,
                    'upper_margin_lut4':None,'uncertainty_scope':'Uncalibrated experimental point model; no hardware budget guarantee.',
                    'artifact_sha256':sha(artifact),'estimator_fingerprint':v6.estimator_fingerprint(model),
                    'configuration':{**PARAMETERS},'source_columns':names,'selected_indices':indices.tolist(),
                    'selected_columns':[names[i] for i in indices],'full455_columns':protocol['full455_columns'],
                    'full455_to_original336_indices':protocol['full455_to_original336_indices'],
                    'zero_override':{'source_column':'original_gate_count','source_column_index':names.index('original_gate_count'),'condition':'equals0'},
                    'runtime_source_sha256':v8.source_hashes(),'training_row_count':len(y),
                    'training_input_sha256':protocol['input_sha256'],'protocol_sha256':sha(output/'protocol.json'),
                    'training_environment':{'python':sys.version,'numpy':np.__version__,'sklearn':sklearn.__version__}})
                if view=='original336':
                    chosen=selected_indices(model.feature_importances_)
                    write(output/'models/full-data-selection.json',{'seed':SEEDS[0],'training_row_count':len(y),
                        'selected_indices':chosen.tolist(),'selected_columns':[names[i] for i in chosen],
                        'full336_training_importances':model.feature_importances_.tolist()})
        per_seed=summaries(predictions)
        summary={'schema':SCHEMA,'scope':protocol['scope'],'protocol_sha256':sha(output/'protocol.json'),
                 'fits_completed':len(fits),'cv_fits_completed':30,'full_data_fits_completed':3,
                 'total_wall_seconds':time.monotonic()-start,'total_fit_seconds':sum(r['fit_seconds'] for r in fits),
                 'per_seed':per_seed,'selection_stability':selection_stability(selections),'eligibility':eligibility(per_seed),
                 'limitations':['Same consumed1665 rows across all seeds; seed replicates are not independent evidence.',
                    'No new synthesis or independent test within this experiment.',
                    'One fixed feature count and configuration; no optimal-subset claim.',
                    'Full-data candidate is experimental even when mean error improves; not calibrated or promoted.']}
        write(output/'summary.json',summary)
        write(output/'manifest.json',{'files_sha256':{str(p.relative_to(output)):sha(p) for p in sorted(output.rglob('*')) if p.is_file() and p!=output/'manifest.json'}})
        print(json.dumps({'fits':len(fits),'wall_seconds':time.monotonic()-start,'eligibility':summary['eligibility']}),flush=True)
    except BaseException as exc:
        write(output/'failure.json',{'error':str(exc),'fits_completed':len(fits),'wall_seconds':time.monotonic()-start})
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,old)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('prepare','run','replay'))
    parser.add_argument('--output',type=Path,default=ROOT/'results/selection-stability')
    parser.add_argument('--source',type=Path,default=ROOT/'results/feature-comparison')
    args=parser.parse_args()
    prepare(args.output,args.source) if args.command=='prepare' else {'run':run,'replay':replay}[args.command](args.output)
