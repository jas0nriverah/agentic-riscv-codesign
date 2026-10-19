"""Separate exact V6 inference wrapper caching only frozen mapping descriptors.

Frozen V5 extraction and V6 predict_features remain unchanged. A block is reused
only with its original graph/manifest, runtime/wrapper sources, tool and schema
identity, plus an intact payload digest. No model fitting or labels are used.
Cache integrity detects corruption; it is not authentication against an actor
who can rewrite both cache data and its digests.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import threading

import numpy as np
from . import area_model_v5 as v5
from . import area_model_v6 as v6
from .graph_features_v5 import PIPELINE,SCHEMA as GRAPH_SCHEMA,source_hashes as graph_sources
from .mapping_features_v6 import feature_vector

SCHEMA='isaforge-v6-mapping-block-cache-v1'
_LOCK_GUARD=threading.Lock()
_LOCKS={}


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


class MappingBlockCache:
    def __init__(self,directory):
        self.directory=Path(directory).resolve()
        self.runtime=v6.source_hashes();self.generic_runtime=graph_sources();self.wrapper_sha256=sha(__file__)

    def context(self,record,generic_cache,tool):
        folder=Path(generic_cache)/record['original_cache_key'];manifest=folder/'features.json'
        if sha(manifest)!=record['original_manifest_sha256']:raise ValueError('Original manifest differs from validated V5 record')
        cached=json.loads(manifest.read_text());context=cached['context'];graph=folder/'graph.json'
        if (cached['formula']!=record['formula'] or cached['cache_key']!=record['original_cache_key']
                or context['schema']!=GRAPH_SCHEMA or context['pipeline']!=PIPELINE
                or context['runtime_source_sha256']!=self.generic_runtime or context['tool']!=tool
                or sha(graph)!=cached['files_sha256']['graph.json']):
            raise ValueError('Original graph/source/tool/bytes differ')
        identity={'schema':SCHEMA,'formula':record['formula'],'feature_columns':list(v6.columns()[313:]),
            'original_cache_key':record['original_cache_key'],'original_manifest_sha256':sha(manifest),
            'original_graph_sha256':sha(graph),'runtime_source_sha256':self.runtime,
            'wrapper_source_sha256':self.wrapper_sha256,'frozen_tool':tool}
        return identity,graph

    def validate(self,cached,context,key):
        if (not isinstance(cached,dict) or set(cached)!={'schema','cache_key','context','values','payload_sha256'}
                or cached['schema']!=SCHEMA or cached['cache_key']!=key or cached['context']!=context
                or cached['payload_sha256']!=digest({k:v for k,v in cached.items() if k!='payload_sha256'})):
            raise ValueError('Mapping block cache schema/context/payload changed')
        values=np.asarray(cached['values'],dtype=float)
        if values.shape!=(23,) or not np.isfinite(values).all() or np.any(values<0):raise ValueError('Invalid cached mapping values')
        return values.tolist()

    def extract(self,record,generic_cache,tool):
        context,graph=self.context(record,generic_cache,tool);key=digest(context)
        path=self.directory/key/'features.json'
        with _LOCK_GUARD:lock=_LOCKS.setdefault(str(path),threading.Lock())
        with lock:
            if path.exists():values=self.validate(json.loads(path.read_text()),context,key);hit=True
            else:
                values=feature_vector(json.loads(graph.read_text()))
                cached={'schema':SCHEMA,'cache_key':key,'context':context,'values':values}
                cached['payload_sha256']=digest(cached)
                self.validate(cached,context,key)
                path.parent.mkdir(parents=True,exist_ok=True)
                temporary=path.with_name(f'features.{os.getpid()}.{threading.get_ident()}.tmp')
                temporary.write_text(json.dumps(cached,indent=2,allow_nan=False)+'\n');temporary.replace(path)
                hit=False
        return values,{'original_graph_sha256':context['original_graph_sha256'],
            'mapping_source_sha256':self.runtime['mapping_features_v6.py']},hit


class FeatureExtractor:
    def __init__(self,cache_root,mapping_cache_root,*,frozen_tool):
        self.cache_root=Path(cache_root).resolve();self.base=v5.FeatureExtractor(self.cache_root,frozen_tool=frozen_tool)
        self.mapping=MappingBlockCache(mapping_cache_root);self.last_cache_counts={'hits':0,'misses':0}

    def matrix(self,rows,workers=2):
        if v6.source_hashes()!=self.mapping.runtime or sha(__file__)!=self.mapping.wrapper_sha256:
            raise ValueError('Mapping wrapper/runtime changed')
        inputs=[{'formula':row['formula']} for row in rows]
        if not inputs:return np.empty((0,len(v6.columns()))),[]
        base,records=self.base.matrix(inputs,workers=workers);block=[];proofs=[];hits=0
        for record in records:
            values,proof,hit=self.mapping.extract(record,self.cache_root/'generic',self.base.graph.tool)
            block.append(values);proofs.append(proof);hits+=hit
        x=np.column_stack((base,np.asarray(block,dtype=float)))
        if x.shape!=(len(rows),len(v6.columns())) or not np.isfinite(x).all() or np.any(x<0):raise ValueError('Invalid cached V6 features')
        if v6.source_hashes()!=self.mapping.runtime or sha(__file__)!=self.mapping.wrapper_sha256:
            raise ValueError('Mapping wrapper/runtime changed during extraction')
        self.last_cache_counts={'hits':int(hits),'misses':len(rows)-int(hits)}
        return x,[{**record,**proof,'values':values.tolist()} for record,proof,values in zip(records,proofs,x)]


class Predictor:
    def __init__(self,model,cache_root,mapping_cache_root):
        self.model=model
        self.extractor=FeatureExtractor(cache_root,mapping_cache_root,frozen_tool=model.frozen_tool)

    def predict(self,rows):
        values,_=self.extractor.matrix(rows,workers=1)
        return self.model.predict_features(rows,values)


def load_model(path,cache_root,mapping_cache_root):
    return Predictor(v6.load_model(path,cache_root),cache_root,mapping_cache_root)


def main():
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model',type=Path,required=True);parser.add_argument('--candidates',type=Path,required=True)
    parser.add_argument('--cache-root',type=Path,required=True);parser.add_argument('--mapping-cache-root',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    if args.output.exists():raise ValueError('Inference output already exists')
    rows=json.loads(args.candidates.read_text())
    predictions=load_model(args.model,args.cache_root,args.mapping_cache_root).predict(rows)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(predictions,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'prediction_count':len(predictions),'output':str(args.output)}))


if __name__=='__main__':
    from .cached_mapping_inference_v6 import main as canonical_main
    canonical_main()
