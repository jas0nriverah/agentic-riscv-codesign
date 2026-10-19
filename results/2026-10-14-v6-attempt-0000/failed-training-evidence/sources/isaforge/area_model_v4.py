"""Semantics-normalized, graph-aware LUT4 prediction. No mapped labels in features.

V4 is a new development model. Earlier models and their frozen evidence remain
unchanged. Cold feature extraction runs label-free Yosys pre-ABC processing.
"""
from __future__ import annotations

from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import hashlib
import json
import time
import threading

import numpy as np

from .features import parse_formula
from .masterrtl_baseline import SOGExtractor, FEATURE_COLUMNS as SOG_COLUMNS

GRAPH_COLUMNS = (
    'gate_count', 'output_driven_bits', 'output_distinct_driven_bits',
    'output_constant_bits', 'output_wire_bits', 'input_support_bits',
    'depth_max', 'output_depth_mean', 'gate_depth_mean',
    'fanout_max', 'fanout_mean', 'fanout_gt1_count', 'fanout_gt4_count',
    'output_support_mean', 'output_support_max',
    'support_le2_count', 'support_le4_count', 'support_gt4_count',
    'greedy_lut4_cover', 'output_gate_reuse',
) + tuple('edge_'+a+'_'+b for a in ('and','or','not','xor','mux')
          for b in ('and','or','not','xor','mux'))

# Fixed before heldout labels exist. The selector only compares these six
# combined-feature candidates. Feature ablations use the same raw-depth3 fit.
CONFIGS = {
    'xgb_raw_d3': {'kind':'xgb', 'log_target':False, 'max_depth':3},
    'xgb_raw_d6': {'kind':'xgb', 'log_target':False, 'max_depth':6},
    'xgb_log_d3': {'kind':'xgb', 'log_target':True, 'max_depth':3},
    'xgb_log_d6': {'kind':'xgb', 'log_target':True, 'max_depth':6},
    'extra_leaf1': {'kind':'extra', 'log_target':False, 'min_samples_leaf':1},
    'extra_leaf3': {'kind':'extra', 'log_target':False, 'min_samples_leaf':3},
}
SEED = 2026101401


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_hashes():
    directory=Path(__file__).parent
    files=('area_model_v4.py','structural_features_v4.py','masterrtl_baseline.py',
           'structural_features_v3.py','area_model_v3.py','area_model_v2.py',
           'area_model.py','features.py','rtl.py','synthesis.py')
    return {f:sha(directory/f) for f in files}


def graph_features(netlist):
    """Deterministic topology/support descriptors from the pre-ABC graph.

    Greedy four-input covering is a descriptive, carry-unaware graph feature,
    not an invocation of ABC, technology mapping, or a measured LUT label.
    """
    module=netlist['modules']['candidate']
    drivers={}; kinds={}; fanout=Counter()
    for cell in module.get('cells',{}).values():
        outputs=[b for p,bits in cell['connections'].items()
                 if cell['port_directions'][p]=='output' for b in bits]
        if len(outputs)!=1:raise ValueError('Expected one-bit primitive output')
        out=outputs[0]
        if out in drivers:raise ValueError('Multiple graph drivers')
        ins=tuple(b for p,bits in cell['connections'].items()
                  if cell['port_directions'][p]=='input' for b in bits)
        drivers[out]=ins
        kinds[out]=cell['type'].strip('$_').lower()
        if kinds[out] not in ('and','or','not','xor','mux'):
            raise ValueError('Unsupported pre-ABC primitive')
        fanout.update(b for b in ins if isinstance(b,int))
    outputs=[b for p in module['ports'].values() if p['direction']=='output' for b in p['bits']]
    fanout.update(b for b in outputs if isinstance(b,int))
    active=set()
    @lru_cache(None)
    def detail(bit):
        if not isinstance(bit,int):return 0,frozenset()
        if bit not in drivers:return 0,frozenset((bit,))
        if bit in active:raise ValueError('Cyclic combinational graph')
        active.add(bit)
        children=[detail(b) for b in drivers[bit]]
        active.remove(bit)
        return 1+max((v[0] for v in children),default=0),frozenset().union(*(v[1] for v in children))
    details={b:detail(b) for b in drivers}
    outdetail=[detail(b) for b in outputs]
    # Cover shared outputs once. Each cover cuts at up to four input signals.
    @lru_cache(None)
    def cut(bit):
        leaves=set(b for b in drivers[bit] if isinstance(b,int))
        while True:
            choices=[]
            for leaf in leaves:
                if leaf not in drivers:continue
                candidate=(leaves-{leaf})|{b for b in drivers[leaf] if isinstance(b,int)}
                if len(candidate)<=4:
                    choices.append((-detail(leaf)[0],len(candidate),leaf,candidate))
            if not choices:break
            leaves=min(choices,key=lambda v:v[:3])[3]
        return tuple(sorted(leaves))
    covered=set()
    def cover(bit):
        if bit not in drivers or bit in covered:return
        covered.add(bit)
        for b in cut(bit):cover(b)
    for b in outputs:cover(b)
    gate_depths=[v[0] for v in details.values()]
    supports=[len(v[1]) for v in details.values()]
    driven=[b for b in outputs if b in drivers]
    mean=lambda xs:float(np.mean(xs)) if xs else 0.
    values={
        'gate_count':len(drivers),'output_driven_bits':len(driven),
        'output_distinct_driven_bits':len(set(driven)),
        'output_constant_bits':sum(not isinstance(b,int) for b in outputs),
        'output_wire_bits':sum(isinstance(b,int) and b not in drivers for b in outputs),
        'input_support_bits':len(frozenset().union(*(v[1] for v in outdetail))),
        'depth_max':max(gate_depths,default=0),
        'output_depth_mean':mean([v[0] for v in outdetail]),
        'gate_depth_mean':mean(gate_depths),
        'fanout_max':max(fanout.values(),default=0),'fanout_mean':mean(list(fanout.values())),
        'fanout_gt1_count':sum(v>1 for v in fanout.values()),
        'fanout_gt4_count':sum(v>4 for v in fanout.values()),
        'output_support_mean':mean([len(v[1]) for v in outdetail]),
        'output_support_max':max((len(v[1]) for v in outdetail),default=0),
        'support_le2_count':sum(v<=2 for v in supports),
        'support_le4_count':sum(v<=4 for v in supports),
        'support_gt4_count':sum(v>4 for v in supports),
        'greedy_lut4_cover':len(covered),'output_gate_reuse':len(driven)-len(set(driven)),
    }
    edges=Counter((kinds[b],kinds[out]) for out,ins in drivers.items() for b in ins if b in drivers)
    values.update({'edge_'+a+'_'+b:edges[(a,b)] for a in ('and','or','not','xor','mux')
                   for b in ('and','or','not','xor','mux')})
    return np.array([values[n] for n in GRAPH_COLUMNS],dtype=float)


class FeatureExtractor:
    def __init__(self,cache_dir,*,yosys='yosys',frozen_tool=None):
        self.sog=SOGExtractor(cache_dir,yosys=yosys,frozen_tool=frozen_tool)
        self.memo={}
        self.locks={}
        self.lock_guard=threading.Lock()

    def extract(self,formula):
        from .structural_features_v4 import normalize_formula, feature_dict, FEATURE_NAMES
        canonical=parse_formula(formula).canonical()
        if canonical in self.memo:return self.memo[canonical]
        normalized=normalize_formula(canonical)
        with self.lock_guard:
            lock=self.locks.setdefault(normalized,threading.Lock())
        with lock:
            record,cached=self.sog.extract(normalized)
        netlist=json.loads((self.sog.cache_dir/record['cache_key']/'sog.json').read_text())
        structure=feature_dict(canonical)
        vector=np.concatenate((np.array(record['feature_values']),graph_features(netlist),
                               np.array([structure[n] for n in FEATURE_NAMES])))
        if not np.isfinite(vector).all() or np.any(vector<0):raise ValueError('Invalid feature vector')
        result={'formula':canonical,'normalized_formula':normalized,'cache_key':record['cache_key'],
                'values':vector.tolist(),'cache_hit':cached,
                'sog_features_sha256':sha(self.sog.cache_dir/record['cache_key']/'features.json')}
        self.memo[canonical]=result
        return result

    def matrix(self,rows,workers=2):
        with ThreadPoolExecutor(max_workers=workers) as pool:
            records=list(pool.map(self.extract,[r['formula'] for r in rows]))
        return np.array([r['values'] for r in records],dtype=float),records


def columns():
    from .structural_features_v4 import FEATURE_NAMES
    return tuple('sog_'+n for n in SOG_COLUMNS)+tuple('graph_'+n for n in GRAPH_COLUMNS)+tuple(FEATURE_NAMES)


def grouping(formula):
    """Operator skeleton groups ignore literal values and input renaming."""
    from .structural_features_v4 import normalize_formula
    def visit(node):
        if not node.children:return 'C' if isinstance(node.value,int) else 'I'
        return str(node.value)+'('+','.join(visit(c) for c in node.children)+')'
    return visit(parse_formula(normalize_formula(formula)))


def fit_estimator(x,y,config):
    c=CONFIGS[config]
    if c['kind']=='xgb':
        from xgboost import XGBRegressor
        model=XGBRegressor(n_estimators=300,learning_rate=.04,max_depth=c['max_depth'],
                           min_child_weight=3,reg_lambda=5,n_jobs=1,random_state=SEED)
    else:
        from sklearn.ensemble import ExtraTreesRegressor
        model=ExtraTreesRegressor(n_estimators=300,min_samples_leaf=c['min_samples_leaf'],
                                  max_features=1.,n_jobs=1,random_state=SEED)
    model.fit(x,np.log1p(y) if c['log_target'] else y)
    return model


def estimate(model,x,config):
    values=np.asarray(model.predict(x),dtype=float)
    if CONFIGS[config]['log_target']:values=np.expm1(values)
    return np.maximum(values,0)


@dataclass
class V4Predictor:
    estimator:object
    configuration:str
    training_formula_count:int
    feature_columns:tuple
    feature_cache:str
    frozen_tool:dict | None = None

    def predict(self,rows):
        if tuple(self.feature_columns)!=columns():raise ValueError('Feature schema mismatch')
        if not rows:return []
        x,_=FeatureExtractor(self.feature_cache,frozen_tool=self.frozen_tool).matrix(rows,workers=1)
        values=estimate(self.estimator,x,self.configuration)
        # A pre-ABC graph with no operators is constants/wiring: exact zero.
        values[x[:,len(SOG_COLUMNS)+GRAPH_COLUMNS.index('gate_count')]==0]=0
        return [{**{k:r[k] for k in ('benchmark','candidate_id','formula') if k in r},
                 'predicted_lut4':float(p),'model':'v4_'+self.configuration}
                for r,p in zip(rows,values)]


def load_model(path,cache_dir=None):
    """Load a trusted local joblib only after manifest/source verification."""
    import joblib
    path=Path(path);schema=json.loads(path.with_suffix('.json').read_text())
    if schema['artifact_sha256']!=sha(path) or schema['runtime_source_sha256']!=source_hashes():
        raise ValueError('V4 artifact/source hash mismatch')
    model=joblib.load(path)
    if not isinstance(model,V4Predictor):raise ValueError('Invalid V4 artifact')
    if tuple(schema['feature_columns'])!=columns() or model.frozen_tool!=schema['frozen_tool']:
        raise ValueError('V4 feature/tool schema mismatch')
    if cache_dir is not None:model.feature_cache=str(Path(cache_dir).resolve())
    return model


def main(argv=None):
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model',required=True,type=Path)
    parser.add_argument('--candidates',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--cache-dir',type=Path)
    args=parser.parse_args(argv)
    started=time.perf_counter()
    model=load_model(args.model,args.cache_dir)
    rows=json.loads(args.candidates.read_text())
    if not isinstance(rows,list):raise ValueError('Candidates must be a JSON list')
    predictions=model.predict(rows)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(predictions,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'prediction_count':len(predictions),'load_and_inference_seconds':time.perf_counter()-started}))
    return 0


if __name__=='__main__':
    from .area_model_v4 import main as canonical_main
    raise SystemExit(canonical_main())
