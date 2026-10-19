"""Versioned V6 mapping and fixed multiply-router predictors.

Original generic implementation DAG descriptors are appended to frozen V5
features. No target labels enter extraction/inference. A newly trained point
model has no uncertainty bound until the final predictor is separately calibrated.
"""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

import joblib
import numpy as np
from . import area_model_v5 as v5
from .area_model import _versions
from .features import parse_formula
from .graph_features_v5 import PIPELINE,SCHEMA as GRAPH_SCHEMA,source_hashes as graph_sources
from .mapping_features_v6 import FEATURE_NAMES,feature_vector

SCHEMA='isaforge-v6-model-v1'
KINDS=('mapping_v6','router_v6')
FIXED_PARAMETERS={'n_estimators':300,'min_samples_leaf':1,'max_features':1.,'n_jobs':1,'random_state':2026101401}
MULTIPLY=frozenset(('mul','mulh','mulhu','mulhsu'))


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def columns():return tuple(v5.columns())+tuple('mapping_'+n for n in FEATURE_NAMES)
def mapping_indices():return np.concatenate((v5.view_indices('dual_graph'),np.arange(len(v5.columns()),len(columns()))))
def mapping_columns():return tuple(columns()[i] for i in mapping_indices())
def source_hashes():
    result=v5.source_hashes()
    for name in ('mapping_features_v6.py','area_model_v6.py'):result[name]=sha(Path(__file__).with_name(name))
    return result

def has_multiply(formula):
    pending=[parse_formula(formula)]
    while pending:
        node=pending.pop()
        if node.value in MULTIPLY:return True
        pending.extend(node.children)
    return False

def uncalibrated():
    return {'status':'uncalibrated','alpha':.1,'upper_margin_lut4':None,
            'assumption':'No new calibration labels used; no bound or coverage claim.'}


class FeatureExtractor:
    def __init__(self,cache_root,*,frozen_tool=None):
        self.cache_root=Path(cache_root).resolve()
        self.base=v5.FeatureExtractor(self.cache_root,frozen_tool=frozen_tool)
        self.graph=self.base.graph

    def matrix(self,rows,workers=2):
        # Deliberately discard every outcome/identity field before extraction.
        inputs=[{'formula':r['formula']} for r in rows]
        if not inputs:return np.empty((0,len(columns()))),[]
        before=source_hashes();base,records=self.base.matrix(inputs,workers=workers)
        block=[];provenance=[]
        for row in records:
            folder=self.cache_root/'generic'/row['original_cache_key'];manifest=folder/'features.json'
            if sha(manifest)!=row['original_manifest_sha256']:raise ValueError('Original graph manifest changed')
            cached=json.loads(manifest.read_text());context=cached['context'];graph=folder/'graph.json'
            if (cached['formula']!=row['formula'] or cached['cache_key']!=row['original_cache_key']
                    or context['schema']!=GRAPH_SCHEMA or context['pipeline']!=PIPELINE
                    or context['runtime_source_sha256']!=graph_sources() or context['tool']!=self.graph.tool
                    or sha(graph)!=cached['files_sha256']['graph.json']):
                raise ValueError('Original generic graph identity/source/tool/bytes differ')
            values=feature_vector(json.loads(graph.read_text()));block.append(values)
            provenance.append({'original_graph_sha256':sha(graph),'mapping_source_sha256':before['mapping_features_v6.py']})
        x=np.column_stack((base,np.asarray(block,dtype=float)))
        if x.shape!=(len(rows),len(columns())) or not np.isfinite(x).all() or np.any(x<0):raise ValueError('Invalid V6 features')
        if source_hashes()!=before:raise ValueError('V6 source changed during feature extraction')
        return x,[{**row,**proof,'values':values.tolist()} for row,proof,values in zip(records,provenance,x)]


@dataclass
class V6Predictor:
    estimator:object
    kind:str
    feature_columns:tuple
    training_formula_count:int
    calibration:dict
    feature_minimum:list
    feature_maximum:list
    frozen_tool:dict
    runtime_source_sha256:dict
    training_provenance:dict|None=None
    semantic_expert:object|None=None
    semantic_source:dict|None=None
    cache_root:str='generated/v6-features'

    def validate(self):
        if self.kind not in KINDS or tuple(self.feature_columns)!=columns() or self.runtime_source_sha256!=source_hashes():
            raise ValueError('V6 kind/schema/runtime differs')
        if type(self.training_formula_count) is not int or self.training_formula_count<1:raise ValueError('Invalid fitting count')
        if any(self.estimator.get_params().get(k)!=v for k,v in FIXED_PARAMETERS.items()):raise ValueError('V6 estimator parameters differ')
        if getattr(self.estimator,'n_features_in_',None)!=len(mapping_columns()) or len(getattr(self.estimator,'estimators_',()))!=300:
            raise ValueError('Invalid fitted mapping estimator')
        low,high=np.asarray(self.feature_minimum,dtype=float),np.asarray(self.feature_maximum,dtype=float)
        if low.shape!=(len(columns()),) or high.shape!=low.shape or not np.isfinite(low).all() or not np.isfinite(high).all() or np.any(low<0) or np.any(low>high):
            raise ValueError('Invalid V6 fitting feature ranges')
        if (set(self.frozen_tool)!= {'version','executable_sha256'} or not isinstance(self.frozen_tool['version'],str)
                or not isinstance(self.frozen_tool['executable_sha256'],str) or len(self.frozen_tool['executable_sha256'])!=64):
            raise ValueError('Invalid frozen generic tool identity')
        if not isinstance(self.calibration.get('assumption'),str) or not self.calibration['assumption']:
            raise ValueError('Missing uncertainty scope')
        state=self.calibration.get('status');margin=self.calibration.get('upper_margin_lut4')
        if state not in ('uncalibrated','calibrated') or self.calibration.get('alpha')!=.1:
            raise ValueError('Invalid V6 calibration state')
        if state=='uncalibrated' and margin is not None:raise ValueError('Uncalibrated model cannot supply a bound')
        if margin is not None and (isinstance(margin,bool) or not isinstance(margin,(float,int)) or not np.isfinite(margin) or margin<0):
            raise ValueError('Invalid calibrated upper margin')
        if state=='calibrated' and (type(self.calibration.get('group_count')) is not int or self.calibration['group_count']<1):
            raise ValueError('Calibrated model requires complete group evidence')
        if self.kind=='mapping_v6':
            if self.semantic_expert is not None or self.semantic_source is not None:raise ValueError('Mapping model has unexpected semantic expert')
        else:
            expert=self.semantic_expert
            if (not isinstance(expert,v5.V5Predictor) or expert.view!='dual_semantics'
                    or tuple(expert.feature_columns)!=v5.columns() or expert.frozen_tool!=self.frozen_tool
                    or expert.training_formula_count!=1665
                    or not isinstance(self.semantic_source,dict) or set(self.semantic_source)!={'artifact_sha256','schema_sha256'}):
                raise ValueError('Router semantic expert lineage differs')

    def predict_features(self,rows,x):
        self.validate();x=np.asarray(x,dtype=float)
        if x.shape!=(len(rows),len(columns())) or not np.isfinite(x).all() or np.any(x<0):raise ValueError('Invalid V6 inference matrix')
        if not rows:return []
        clean=[{k:r[k] for k in ('benchmark','candidate_id','formula') if k in r} for r in rows]
        for row in clean:parse_formula(row['formula'])
        indices=mapping_indices();selected=x[:,indices]
        p=np.maximum(self.estimator.predict(selected),0)
        spread=np.asarray([tree.predict(selected) for tree in self.estimator.estimators_]).std(axis=0)
        zero=v5.original_zero(x[:,:len(v5.columns())]);p[zero]=0;spread[zero]=0
        outside=((x<np.asarray(self.feature_minimum))|(x>np.asarray(self.feature_maximum)))[:,indices].sum(axis=1)
        route=np.array([has_multiply(r['formula']) for r in rows]) if self.kind=='router_v6' else np.zeros(len(rows),bool)
        if route.any():
            positions=np.flatnonzero(route)
            semantic=self.semantic_expert.predict_features([clean[i] for i in positions],x[route,:len(v5.columns())])
            for i,value in zip(positions,semantic):
                p[i]=value['predicted_lut4'];spread[i]=value['tree_disagreement_lut4']
                outside[i]=value['outside_training_feature_ranges']
        if not np.isfinite(p).all() or np.any(p<0) or not np.isfinite(spread).all():raise ValueError('Invalid V6 predictions')
        margin=self.calibration['upper_margin_lut4']
        return [{**row,'predicted_lut4':float(p[i]),'upper_lut4':None if margin is None else float(p[i]+margin),
                 'tree_disagreement_lut4':float(spread[i]),'outside_training_feature_ranges':int(outside[i]),
                 'model':self.kind,'routed_expert':'dual_semantics' if route[i] else 'mapping_v6',
                 'uncertainty_scope':self.calibration['assumption'],'calibration_status':self.calibration['status']}
                for i,row in enumerate(clean)]

    def predict(self,rows):
        x,_=FeatureExtractor(self.cache_root,frozen_tool=self.frozen_tool).matrix(rows,workers=1)
        return self.predict_features(rows,x)


def save_model(model,path):
    model.validate();path=Path(path);schema=path.with_suffix('.json')
    if path.suffix!='.joblib' or path.exists() or schema.exists():raise ValueError('New V6 artifact/schema path required')
    path.parent.mkdir(parents=True,exist_ok=True);joblib.dump(model,path,compress=3)
    record={'schema':SCHEMA,'artifact_sha256':sha(path),'runtime_source_sha256':source_hashes(),'versions':_versions(),
            'feature_columns':list(columns()),'mapping_columns':list(mapping_columns()),'kind':model.kind,
            'configuration':FIXED_PARAMETERS,'fitted_parameters':model.estimator.get_params(),'estimator_fingerprint':joblib.hash(model.estimator),
            'training_formula_count':model.training_formula_count,'frozen_tool':model.frozen_tool,
            'calibration':model.calibration,'feature_minimum':model.feature_minimum,'feature_maximum':model.feature_maximum,
            'training_provenance':model.training_provenance,'semantic_source':model.semantic_source,
            'semantic_expert_fingerprint':None if model.semantic_expert is None else joblib.hash(model.semantic_expert)}
    schema.write_text(json.dumps(record,indent=2,allow_nan=False)+'\n')
    return {'artifact':path,'schema':schema}


def load_model(path,cache_root=None):
    path=Path(path);schema=json.loads(path.with_suffix('.json').read_text())
    if (schema.get('schema')!=SCHEMA or schema['artifact_sha256']!=sha(path)
            or schema['runtime_source_sha256']!=source_hashes() or schema['versions']!=_versions()
            or tuple(schema['feature_columns'])!=columns() or tuple(schema['mapping_columns'])!=mapping_columns()
            or schema['configuration']!=FIXED_PARAMETERS):raise ValueError('V6 source/artifact/schema/environment differs')
    model=joblib.load(path)
    if not isinstance(model,V6Predictor):raise ValueError('Invalid V6 artifact class')
    model.validate()
    for field in ('kind','training_formula_count','frozen_tool','calibration','feature_minimum','feature_maximum','semantic_source','training_provenance'):
        if getattr(model,field)!=schema[field]:raise ValueError(f'V6 artifact metadata mismatch: {field}')
    if joblib.hash(model.estimator)!=schema['estimator_fingerprint']:raise ValueError('Fitted mapping estimator weights differ')
    fingerprint=None if model.semantic_expert is None else joblib.hash(model.semantic_expert)
    if fingerprint!=schema['semantic_expert_fingerprint']:raise ValueError('Embedded frozen semantic expert differs')
    if model.estimator.get_params()!=schema['fitted_parameters']:raise ValueError('V6 fitted parameters differ')
    model.cache_root=str(Path(cache_root).resolve()) if cache_root is not None else str(path.parent/'cache')
    return model


def main():
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model',type=Path,required=True)
    parser.add_argument('--candidates',type=Path,required=True)
    parser.add_argument('--cache-root',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():raise ValueError('Inference output already exists')
    rows=json.loads(args.candidates.read_text())
    predictions=load_model(args.model,args.cache_root).predict(rows)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(predictions,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'prediction_count':len(predictions),'output':str(args.output)}))


if __name__=='__main__':
    from .area_model_v6 import main as canonical_main
    canonical_main()
