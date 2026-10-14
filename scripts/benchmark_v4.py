#!/usr/bin/env python3
"""Time unchanged V4/MasterRTL artifacts with empty and warm feature caches."""
from pathlib import Path
import argparse
import json
import sys
import time
from datetime import datetime,timezone
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from isaforge.area_model_v4 import load_model as load_v4,sha
from isaforge.masterrtl_baseline import load_model as load_master

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cache-root',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    if args.cache_root.exists():raise ValueError('Cold timing requires an absent cache root')
    root=ROOT/'results/2026-10-13-v4'
    candidates=root/'corpus/test/candidates.json'
    rows=json.loads(candidates.read_text())
    specs={'v4':(load_v4,root/'models/v4.joblib'),
           'masterrtl_retrained':(load_master,root/'models/masterrtl-retrained/masterrtl-sog.joblib')}
    result={'recorded_at_utc':datetime.now(timezone.utc).isoformat(),'formula_count':len(rows),
        'candidates_sha256':sha(candidates),'worker_count':1,'models':{},
        'scope':'Sequential same-machine runs; cold feature extraction plus prediction, then five immediate warm repeats. Model load separately timed. Startup and JSON serialization excluded. No training or target synthesis.',
        'limitations':['No uncertainty interval over runtime conditions; cold/warm timings cannot establish acquisition savings.',
        'V4 uses semantic normalization plus pre-ABC topology and structural features; both models use Yosys on cold inputs.']}
    for name,(loader,path) in specs.items():
        started=time.perf_counter();model=loader(path,args.cache_root/name)
        load=time.perf_counter()-started
        expected=json.loads((root/'predictions'/f'{name}.json').read_text())
        durations=[]
        for iteration in range(6):
            started=time.perf_counter();pred=model.predict(rows);durations.append(time.perf_counter()-started)
            if pred!=expected:raise ValueError(f'{name}: cold/warm predictions differ from freeze')
        result['models'][name]={'artifact_sha256':sha(path),'load_seconds':load,
            'cold_feature_and_prediction_seconds':durations[0],
            'warm_feature_and_prediction_seconds':durations[1:],
            'warm_median_seconds':float(np.median(durations[1:])),
            'identical_to_frozen_predictions':True}
        print(name,result['models'][name],flush=True)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n')

if __name__=='__main__':main()
