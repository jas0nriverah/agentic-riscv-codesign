"""Point-only V8 application-transfer representations; original RTL cost retained.

Shared storage is frozen V6full336 followed by rewritten legacy119. Selected
336-column views have a different order from V6full336; names/indices are strict.
No training runner, target acquisition or inherited calibration is provided.
"""
from __future__ import annotations
from dataclasses import dataclass
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import platform
import sys
import joblib
import numpy as np
from sklearn.ensemble import ExtraTreesRegressor
from . import area_model_v5 as v5
from . import area_model_v6 as v6
from . import semantic_features_v7 as semantic
from . import structural_features_v5 as legacy
from .area_model import _versions
from .features import parse_formula

SCHEMA='isaforge-v8-point-model-v1'
FEATURE_SCHEMA='isaforge-v8-full455-v1'
VIEWS=('mapping217','legacy_original336','legacy_rewritten336')
TRAINED_VIEWS=VIEWS[1:]
FIXED_PARAMETERS=dict(v6.FIXED_PARAMETERS)
TRAINING_COUNT=1665
PROOF_BUDGET=semantic.Budget(proof_timeout_ms=500)
POINT_SCOPE='Point prediction and tree disagreement only; no calibrated application upper bound.'
SCHEMA_FIELDS=frozenset(('schema','feature_schema','artifact_sha256','feature_columns','selected_indices','selected_columns',
    'runtime_source_sha256','configuration','fitted_parameters','estimator_fingerprint','point_only','upper_margin_lut4',
    'view','training_formula_count','feature_minimum','feature_maximum','frozen_tool','training_provenance',
    'training_environment','audited_compatibility'))


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def columns():return v6.columns()+tuple('rewritten_'+name for name in legacy.FEATURE_NAMES)
def view_indices(view):
    if view not in VIEWS:raise ValueError('Unknown V8 feature view')
    base=v6.mapping_indices()
    if view=='mapping217':return base.copy()
    extra=np.arange(194,313) if view=='legacy_original336' else np.arange(336,455)
    return np.concatenate((base,extra))
def view_columns(view):return tuple(columns()[i] for i in view_indices(view))
def source_hashes():
    result=v6.source_hashes()
    result.update(semantic.source_hashes())
    result['area_model_v8.py']=sha(Path(__file__))
    return result

def compatibility():
    """Audited logical compatibility; native proof/build identities remain evidence."""
    solver=semantic.solver_identity()
    if not solver.get('available'):raise ValueError('V8 proof solver unavailable')
    return {'versions':_versions(),'solver_version':solver['version'],
            'solver_python_module_sha256':solver['python_module_sha256']}

def environment():
    """Record actual Python/native identity without binding an absolute host path."""
    return {'python':{'version':sys.version,'implementation':sys.implementation.name,
        'cache_tag':sys.implementation.cache_tag,'build':list(platform.python_build()),
        'executable':sys.executable,'executable_sha256':sha(sys.executable)},
        'platform':{'system':platform.system(),'release':platform.release(),'machine':platform.machine()},
        'versions':_versions(),'solver':deepcopy(semantic.solver_identity())}

def _valid_digest(value):return isinstance(value,str) and len(value)==64 and all(c in '0123456789abcdef' for c in value)
def _matrix(values,names,count):
    if tuple(names)!=columns():raise ValueError('V8 explicit full455 feature columns/order differ')
    x=np.asarray(values,dtype=float)
    if x.shape!=(count,455) or not np.isfinite(x).all() or np.any(x<0):raise ValueError('Invalid V8 full455 feature matrix')
    return x

def _provenance(value):
    if not isinstance(value,dict):raise ValueError('V8 training provenance required')
    indices=value.get('fit_indices')
    if (not isinstance(indices,list) or len(indices)!=TRAINING_COUNT
        or any(type(i) is not int or i<0 for i in indices) or len(set(indices))!=TRAINING_COUNT):
        raise ValueError('V8 exact1665 unique fitting indices required')
    actual=hashlib.sha256(json.dumps(indices,separators=(',',':')).encode()).hexdigest()
    fields=('fit_indices_sha256','training_dataset_sha256','development_dataset_sha256','development_features_sha256','split_sha256')
    if (any(not _valid_digest(value.get(k)) for k in fields) or actual!=value['fit_indices_sha256']
        or value['training_dataset_sha256']!=value['development_dataset_sha256']):
        raise ValueError('V8 fitting provenance hashes/aliases differ')

def _environment_record(value):
    if not isinstance(value,dict) or set(value)!=set(('python','platform','versions','solver')):
        raise ValueError('V8 observed training environment required')
    python=value['python'];solver=value['solver'];host=value['platform']
    if (not isinstance(python,dict) or not isinstance(solver,dict) or not isinstance(host,dict)
        or set(python)!=set(('version','implementation','cache_tag','build','executable','executable_sha256'))
        or any(not isinstance(python.get(k),str) or not python[k] for k in ('version','implementation','cache_tag','executable'))
        or not isinstance(python.get('build'),list) or len(python['build'])!=2 or any(not isinstance(v,str) for v in python['build'])
        or not _valid_digest(python.get('executable_sha256'))
        or set(host)!=set(('system','release','machine')) or any(not isinstance(v,str) or not v for v in host.values())
        or not isinstance(value['versions'],dict) or solver.get('available') is not True
        or not isinstance(solver.get('version'),str) or not solver['version']
        or not _valid_digest(solver.get('python_module_sha256'))
        or not isinstance(solver.get('native_libraries_sha256'),dict) or not solver['native_libraries_sha256']
        or any(not isinstance(k,str) or not k or not _valid_digest(v) for k,v in solver['native_libraries_sha256'].items())):
        raise ValueError('Invalid V8 Python/platform/native proof evidence')


class FeatureExtractor:
    def __init__(self,cache_root,*,frozen_tool=None):
        self.cache_root=Path(cache_root).resolve();self.base=v6.FeatureExtractor(self.cache_root,frozen_tool=frozen_tool)
        self.graph=self.base.graph

    def matrix(self,rows,workers=2):
        # No target, score, stratum, occurrence or identity field enters helpers.
        inputs=[{'formula':parse_formula(r['formula']).canonical()} for r in rows]
        if not inputs:return np.empty((0,455)),[]
        before=source_hashes();observed=environment();logical=compatibility()
        prefix,records=self.base.matrix(inputs,workers=workers)
        if (np.asarray(prefix).shape!=(len(inputs),336) or len(records)!=len(inputs)
            or any(r['formula']!=row['formula'] for row,r in zip(inputs,records))):
            raise ValueError('Frozen V6 input prefix/alignment differs')
        block=[];proofs=[]
        for row in inputs:
            modes=deepcopy(semantic.analyze_modes(row['formula'],budget=PROOF_BUDGET))
            normalized=modes['combined']['normalized_formula'];values=legacy.feature_dict(normalized)
            block.append([values[name] for name in legacy.FEATURE_NAMES]);proofs.append(modes)
        x=_matrix(np.column_stack((prefix,block)),columns(),len(inputs))
        if source_hashes()!=before or compatibility()!=logical:raise ValueError('V8 extraction source/solver changed')
        return x,[{**deepcopy(record),'values':values.tolist(),'v7_combined_normalized_formula':proof['combined']['normalized_formula'],
            'v7_modes':proof,'v8_feature_schema':FEATURE_SCHEMA,'v8_runtime_source_sha256':deepcopy(before),
            'v8_extraction_environment':deepcopy(observed),'v8_compatibility':deepcopy(logical)}
            for record,values,proof in zip(records,x,proofs)]


@dataclass
class V8Predictor:
    estimator:object
    view:str
    feature_columns:tuple
    training_formula_count:int
    feature_minimum:list
    feature_maximum:list
    frozen_tool:dict
    runtime_source_sha256:dict
    training_provenance:dict
    training_environment:dict
    audited_compatibility:dict
    cache_root:str='generated/v5-features'

    def validate(self):
        if self.view not in TRAINED_VIEWS:raise ValueError('V8 trains only the two new legacy views; frozen V6 is the mapping baseline')
        if tuple(self.feature_columns)!=columns() or self.runtime_source_sha256!=source_hashes():raise ValueError('V8 feature schema/source differs')
        if self.audited_compatibility!=compatibility():raise ValueError('V8 ML/solver logical compatibility differs')
        if type(self.training_formula_count) is not int or self.training_formula_count!=TRAINING_COUNT:raise ValueError('V8 original1665 fitting rows required')
        _provenance(self.training_provenance);_environment_record(self.training_environment)
        training=self.training_environment
        if (training['versions']!=self.audited_compatibility['versions']
            or training['solver']['version']!=self.audited_compatibility['solver_version']
            or training['solver']['python_module_sha256']!=self.audited_compatibility['solver_python_module_sha256']):
            raise ValueError('V8 training environment/compatibility record differs')
        expected=ExtraTreesRegressor(**FIXED_PARAMETERS).get_params(deep=True)
        if not isinstance(self.estimator,ExtraTreesRegressor) or self.estimator.get_params(deep=True)!=expected:raise ValueError('V8 full fixed estimator parameters differ')
        if (getattr(self.estimator,'n_features_in_',None)!=len(view_columns(self.view)) or getattr(self.estimator,'n_outputs_',None)!=1
            or len(getattr(self.estimator,'estimators_',()))!=300):raise ValueError('V8 fitted forest dimensions/count differ')
        if any(int(t.tree_.n_node_samples[0])!=TRAINING_COUNT for t in self.estimator.estimators_):raise ValueError('V8 fitted forest training sample count differs')
        low,high=np.asarray(self.feature_minimum,dtype=float),np.asarray(self.feature_maximum,dtype=float)
        if (low.shape!=(455,) or high.shape!=(455,) or not np.isfinite(low).all() or not np.isfinite(high).all()
            or np.any(low<0) or np.any(low>high)):raise ValueError('V8 full455 fitting ranges differ')
        if (not isinstance(self.frozen_tool,dict) or set(self.frozen_tool)!=set(('version','executable_sha256'))
            or not isinstance(self.frozen_tool['version'],str) or not self.frozen_tool['version']
            or not _valid_digest(self.frozen_tool['executable_sha256'])):raise ValueError('Invalid V8 frozen generic tool')
        if hasattr(self,'calibration') or hasattr(self,'upper_margin_lut4'):raise ValueError('V8 point-only models cannot carry calibration or an upper margin')
        try:json.dumps({'provenance':self.training_provenance,'environment':self.training_environment},allow_nan=False)
        except (TypeError,ValueError) as error:raise ValueError('V8 provenance/environment must be finite JSON evidence') from error

    def predict_features(self,rows,x,*,feature_columns):
        self.validate();x=_matrix(x,feature_columns,len(rows))
        if not rows:return []
        clean=[{k:r[k] for k in ('benchmark','candidate_id','formula') if k in r} for r in rows]
        for row in clean:parse_formula(row['formula'])
        indices=view_indices(self.view);selected=x[:,indices]
        p=np.maximum(self.estimator.predict(selected),0)
        spread=np.asarray([t.predict(selected) for t in self.estimator.estimators_]).std(axis=0)
        zero=v5.original_zero(x[:,:313]);p[zero]=0;spread[zero]=0
        outside=((x<np.asarray(self.feature_minimum))|(x>np.asarray(self.feature_maximum)))[:,indices].sum(axis=1)
        if not np.isfinite(p).all() or not np.isfinite(spread).all():raise ValueError('Invalid V8 point predictions')
        return [{**row,'predicted_lut4':float(p[i]),'upper_lut4':None,'tree_disagreement_lut4':float(spread[i]),
            'outside_training_feature_ranges':int(outside[i]),'model':'v8_'+self.view,'calibration_status':'point_only',
            'uncertainty_scope':POINT_SCOPE} for i,row in enumerate(clean)]

    def compatibility_report(self):
        observed=environment()
        return {'audited_compatible':self.audited_compatibility==compatibility(),'training_environment':deepcopy(self.training_environment),
                'observed_environment':observed,'observed_environment_differs':observed!=self.training_environment,
                'scope':'Logical point-model compatibility does not promise identical timed native cold extraction.'}

    def predict_with_evidence(self,rows,workers=1):
        self.validate();observed=environment()
        x,records=FeatureExtractor(self.cache_root,frozen_tool=self.frozen_tool).matrix(rows,workers=workers)
        return {'predictions':self.predict_features(rows,x,feature_columns=columns()),'feature_columns':list(columns()),
            'feature_records':records,'extraction_environment':observed,'compatibility_report':self.compatibility_report(),'runtime_source_sha256':source_hashes(),
            'cold_feature_identity_scope':'Actual native proof/tool identities and fallbacks are evidence; logical compatibility alone does not guarantee identical timed cold extraction.'}

    def predict(self,rows):return self.predict_with_evidence(rows)['predictions']


def save_model(model,path):
    model.validate();path=Path(path);schema_path=path.with_suffix('.json')
    if path.suffix!='.joblib' or path.exists() or schema_path.exists():raise ValueError('New immutable V8 artifact/schema paths required')
    path.parent.mkdir(parents=True,exist_ok=True);joblib.dump(model,path,compress=3)
    schema={'schema':SCHEMA,'feature_schema':FEATURE_SCHEMA,'artifact_sha256':sha(path),'feature_columns':list(columns()),
        'selected_indices':view_indices(model.view).tolist(),'selected_columns':list(view_columns(model.view)),
        'runtime_source_sha256':source_hashes(),'configuration':FIXED_PARAMETERS,'fitted_parameters':model.estimator.get_params(deep=True),
        'estimator_fingerprint':v6.estimator_fingerprint(model.estimator),'point_only':True,'upper_margin_lut4':None,
        **{name:getattr(model,name) for name in ('view','training_formula_count','feature_minimum','feature_maximum','frozen_tool',
            'training_provenance','training_environment','audited_compatibility')}}
    schema_path.write_text(json.dumps(schema,indent=2,allow_nan=False)+'\n')
    return {'artifact':path,'schema':schema_path}


def load_model(path,cache_root=None):
    path=Path(path);record=json.loads(path.with_suffix('.json').read_text());view=record.get('view')
    if (set(record)!=SCHEMA_FIELDS or record.get('schema')!=SCHEMA or record.get('feature_schema')!=FEATURE_SCHEMA or view not in TRAINED_VIEWS
        or record.get('artifact_sha256')!=sha(path) or record.get('feature_columns')!=list(columns())
        or record.get('selected_indices')!=view_indices(view).tolist() or record.get('selected_columns')!=list(view_columns(view))
        or record.get('runtime_source_sha256')!=source_hashes() or record.get('configuration')!=FIXED_PARAMETERS
        or record.get('audited_compatibility')!=compatibility() or record.get('point_only') is not True
        or record.get('upper_margin_lut4') is not None):raise ValueError('V8 artifact/source/schema/compatibility differs')
    model=joblib.load(path)
    if not isinstance(model,V8Predictor):raise ValueError('Invalid V8 artifact class')
    model.validate()
    for field in ('view','feature_columns','runtime_source_sha256','training_formula_count','feature_minimum','feature_maximum','frozen_tool',
                  'training_provenance','training_environment','audited_compatibility'):
        value=getattr(model,field);value=list(value) if field=='feature_columns' else value
        if value!=record[field]:raise ValueError('V8 artifact metadata differs: '+field)
    if (model.estimator.get_params(deep=True)!=record['fitted_parameters']
        or v6.estimator_fingerprint(model.estimator)!=record['estimator_fingerprint']):raise ValueError('V8 fitted parameters/weights differ')
    model.cache_root=str(Path(cache_root).resolve()) if cache_root is not None else str(path.parent/'cache')
    return model
