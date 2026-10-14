#!/usr/bin/env python3
"""Develop V4 on released development labels, then freeze label-free predictions."""
from pathlib import Path
import argparse
from datetime import datetime, timezone
import json
import os
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import joblib
import numpy as np
from sklearn.model_selection import GroupKFold
from threadpoolctl import threadpool_limits
from isaforge.area_model import _validated_rows,_unique_formulas,_versions
from isaforge.area_model_v4 import (CONFIGS,FeatureExtractor,V4Predictor,columns,
    estimate,fit_estimator,grouping,sha,source_hashes,GRAPH_COLUMNS,SOG_COLUMNS)
from isaforge import masterrtl_baseline as master


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')


def read(path):return json.loads(path.read_text())
def now():return datetime.now(timezone.utc).isoformat()
def record(path,base):return {'path':os.path.relpath(path,base),'sha256':sha(path)}


def stats(y,p,strata):
    positive=y>0
    return {'mae_lut4':float(abs(y-p).mean()),
            'macro_stratum_mae_lut4':float(np.mean([abs(y[strata==s]-p[strata==s]).mean() for s in sorted(set(strata))])),
            'rmsle':float(np.sqrt(np.mean((np.log1p(y)-np.log1p(p))**2))),
            'positive_mape_percent':float((100*abs(y[positive]-p[positive])/y[positive]).mean()),
            'by_stratum_mae_lut4':{s:float(abs(y[strata==s]-p[strata==s]).mean()) for s in sorted(set(strata))}}


@threadpool_limits.wrap(limits=1,user_api='blas')
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'results/2026-10-13-v4')
    args=parser.parse_args();out=args.output.resolve()
    if (out/'freeze.json').exists():raise ValueError('Already frozen: refusing retraining')
    original=[ROOT/'results/2026-10-13/dataset.json',ROOT/'results/2026-10-13-prospective/transfer/dataset.json',
              ROOT/'results/2026-10-13-prospective/final/dataset.json',ROOT/'results/2026-10-13-v3/probe/dataset.json',
              out/'corpus/development/dataset.json']
    rows=_unique_formulas(_validated_rows([r for path in original for r in read(path)]))
    rows=sorted(rows,key=lambda r:r['formula'])
    test=read(out/'corpus/test/candidates.json')
    if len(rows)!=1289 or len(test)!=256:raise ValueError('Incomplete planned cohort')
    if {r['formula'] for r in rows}&{r['formula'] for r in test}:raise ValueError('Train/test overlap')
    training=out/'development-data.json';write(training,rows)
    snapshot=source_hashes()
    protocol=ROOT/'docs/v4-protocol.md';protocol_hash=sha(protocol)
    control_snapshot={str(p):sha(p) for p in (Path(__file__).resolve(),ROOT/'scripts/evaluate_v4.py')}
    write(out/'training-start.json',{'started_at_utc':now(),'configurations':CONFIGS,
          'runtime_source_sha256':snapshot,'protocol_sha256':protocol_hash,'control_source_sha256':control_snapshot,
          'dataset_sources':[record(p,out) for p in original],
          'selection':'five normalized operator-skeleton GroupKFold; macro nine-stratum OOF MAE; no test labels'})
    cache=ROOT/'generated/masterrtl-baseline/sog-cache'
    extractor=FeatureExtractor(cache)
    started=time.perf_counter();x,records=extractor.matrix(rows,workers=2)
    training_feature_seconds=time.perf_counter()-started
    write(out/'development-features.json',{'columns':columns(),'records':records,'seconds':training_feature_seconds})
    print(f'Extracted {len(rows)} development feature vectors in {training_feature_seconds:.2f}s',flush=True)
    y=np.array([r['lut4_count'] for r in rows]);strata=np.array([r.get('stratum','workload') for r in rows])
    groups=np.array([grouping(r['formula']) for r in rows])
    folds=list(GroupKFold(n_splits=5).split(x,y,groups))
    zero=x[:,len(SOG_COLUMNS)+GRAPH_COLUMNS.index('gate_count')]==0
    selections={};oof={}
    for name in CONFIGS:
        p=np.zeros(len(y));start=time.perf_counter()
        for train,valid in folds:
            model=fit_estimator(x[train],y[train],name)
            p[valid]=estimate(model,x[valid],name)
        p[zero]=0
        selections[name]=stats(y,p,strata);oof[name]=p.tolist()
        print(name,selections[name],f'{time.perf_counter()-start:.2f}s',flush=True)
    selected=min(selections,key=lambda n:(selections[n]['macro_stratum_mae_lut4'],n))
    ablations={}
    for name,stop in [('normalized_sog',len(SOG_COLUMNS)),('normalized_sog_graph',len(SOG_COLUMNS)+len(GRAPH_COLUMNS))]:
        p=np.zeros(len(y))
        for train,valid in folds:
            model=fit_estimator(x[train,:stop],y[train],'xgb_raw_d3')
            p[valid]=estimate(model,x[valid,:stop],'xgb_raw_d3')
        p[zero]=0;ablations[name]=stats(y,p,strata)
    ablations['combined']=selections['xgb_raw_d3']
    write(out/'development-evaluation.json',{'status':'development-only configuration selection; not unbiased generalization',
        'selected':selected,'group_count':len(set(groups)),'folds':[{'train_count':len(t),'validation_count':len(v),
        'validation_formula_indices':v.tolist()} for t,v in folds],
        'stratum_counts':{s:int(np.sum(strata==s)) for s in sorted(set(strata))},
        'configurations':CONFIGS,'selection_metrics':selections,'oof_predictions':oof,'feature_ablations':ablations})
    fitted=fit_estimator(x,y,selected)
    model=V4Predictor(fitted,selected,len(rows),columns(),str(cache),dict(extractor.sog.tool))
    modelpath=out/'models/v4.joblib';modelpath.parent.mkdir(parents=True,exist_ok=True)
    joblib.dump(model,modelpath,compress=3)
    write(modelpath.with_suffix('.json'),{'artifact_sha256':sha(modelpath),'runtime_source_sha256':snapshot,
          'configuration':selected,'feature_columns':columns(),'training_formula_count':len(rows),
          'training_dataset_sha256':sha(training),'trained_at_utc':now(),'versions':_versions(),
          'fitted_parameters':fitted.get_params(),'frozen_tool':dict(extractor.sog.tool)})
    # Same-data, fixed public-recipe baseline separates data gain from V4 gain.
    start=time.perf_counter();master.SOGExtractor(cache).matrix(rows,workers=2)
    matched=master.train_model(rows,cache)
    matched_dir=out/'models/masterrtl-retrained'
    matched_paths=master.save_model(matched,matched_dir,{'training_dataset_sha256':sha(training)})
    print('Same-data MasterRTL fit',time.perf_counter()-start,flush=True)
    from isaforge.area_model_v2 import load_model as load_v2
    from isaforge.area_model_v3 import load_model as load_v3
    old=ROOT/'results/2026-10-13-v3'
    artifacts={'v4':modelpath,'masterrtl_retrained':Path(matched_paths['model_path']),
        'masterrtl_frozen':old/'masterrtl/masterrtl-sog.joblib',
        'v2_frozen':old/'models/area-model-v2-full.joblib',
        'v3_frozen':old/'models/area-model-v3.joblib'}
    models={'v4':model,'masterrtl_retrained':matched,
        'masterrtl_frozen':master.load_model(artifacts['masterrtl_frozen'],cache),
        'v2_frozen':load_v2(artifacts['v2_frozen']),
        'v3_frozen':load_v3(artifacts['v3_frozen'])}
    # Probe contains only identities and formulas here. No test dataset read.
    started=time.perf_counter();xt,testrecords=extractor.matrix(test,workers=2)
    write(out/'test-features.json',{'columns':columns(),'records':testrecords,
        'initial_feature_batch_seconds':time.perf_counter()-started,
        'initial_cache_hit_count':sum(r['cache_hit'] for r in testrecords)})
    entries={}
    for name,predictor in models.items():
        start=time.perf_counter();predictions=predictor.predict(test);elapsed=time.perf_counter()-start
        path=out/'predictions'/f'{name}.json';write(path,predictions)
        write(path.with_suffix('.timing.json'),{'formula_count':len(test),'seconds':elapsed,
            'scope':'feature plus ML prediction; process startup/model loading/JSON serialization excluded',
            'cache':'v4 features pre-extracted; original SOG may be cold for first MasterRTL comparator'})
        entries[name]={'frozen_at_utc':now(),'predictions':record(path,out),'artifact':record(artifacts[name],out),
            'sources':[record(ROOT/'isaforge'/f,out) for f in snapshot]+[record(Path(__file__),out),
             record(artifacts[name].with_suffix('.json'),out),record(out/'development-evaluation.json',out),
             record(out/'training-start.json',out)]}
    if (snapshot!=source_hashes() or sha(protocol)!=protocol_hash
            or any(sha(Path(p))!=h for p,h in control_snapshot.items())):
        raise ValueError('Source/protocol changed during fitting; do not release test labels')
    manifest={'schema':'isaforge-v4-freeze-v1',
        'candidate_frozen_at_utc':read(out/'corpus/test/freeze.json')['frozen_at_utc'],
        'candidates':record(out/'corpus/test/candidates.json',out),
        'development_data':record(training,out),'protocol':record(protocol,out),
        'evaluator':record(ROOT/'scripts/evaluate_v4.py',out),'models':entries}
    write(out/'freeze.json',manifest)
    print(json.dumps({'selected':selected,'freeze':str(out/'freeze.json'),'test_labels_read':False}),flush=True)


if __name__=='__main__':main()
