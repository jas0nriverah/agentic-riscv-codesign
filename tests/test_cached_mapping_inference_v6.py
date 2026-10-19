"""Strict descriptor-cache corruption/dependency gates and exact feature reuse."""
from copy import deepcopy
import json
from pathlib import Path

import numpy as np
import pytest
from isaforge import cached_mapping_inference_v6 as cached
from isaforge.mapping_features_v6 import feature_vector


def original_cache(tmp_path):
    generic=tmp_path/'generic';folder=generic/'original';folder.mkdir(parents=True)
    graph={'modules':{'candidate':{'ports':{'in':{'direction':'input','bits':[1,2]},'out':{'direction':'output','bits':[3]}},
        'cells':{'and':{'type':'$_AND_','port_directions':{'A':'input','B':'input','Y':'output'},'connections':{'A':[1],'B':[2],'Y':[3]}}}}}}
    (folder/'graph.json').write_text(json.dumps(graph))
    tool={'version':'fixture','executable_sha256':'a'*64}
    manifest={'formula':'and(in0,in1)','cache_key':'original','context':{'schema':cached.GRAPH_SCHEMA,
        'pipeline':cached.PIPELINE,'runtime_source_sha256':cached.graph_sources(),'tool':tool},
        'files_sha256':{'graph.json':cached.sha(folder/'graph.json')}}
    (folder/'features.json').write_text(json.dumps(manifest))
    record={'formula':manifest['formula'],'original_cache_key':'original','original_manifest_sha256':cached.sha(folder/'features.json')}
    return generic,record,tool,graph


def test_first_compute_then_exact_reuse_without_graph_analysis(tmp_path,monkeypatch):
    generic,record,tool,graph=original_cache(tmp_path);cache=cached.MappingBlockCache(tmp_path/'blocks')
    values,proof,hit=cache.extract(record,generic,tool)
    assert not hit and values==feature_vector(graph)
    monkeypatch.setattr(cached,'feature_vector',lambda *a:(_ for _ in ()).throw(RuntimeError('must reuse block')))
    repeated,reproof,hit=cache.extract(record,generic,tool)
    assert hit and repeated==values and reproof==proof


@pytest.mark.parametrize('mutation',['value','payload','schema','source','columns'])
def test_cache_mutations_fail_closed(tmp_path,mutation):
    generic,record,tool,_=original_cache(tmp_path);cache=cached.MappingBlockCache(tmp_path/'blocks')
    cache.extract(record,generic,tool);path=next((tmp_path/'blocks').glob('*/features.json'));value=json.loads(path.read_text())
    if mutation=='value':value['values'][0]+=1
    if mutation=='payload':value['payload_sha256']='changed'
    if mutation=='schema':value['schema']='other'
    if mutation=='source':value['context']['runtime_source_sha256']['mapping_features_v6.py']='changed'
    if mutation=='columns':value['context']['feature_columns'][0]='other'
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError,match='changed'):cache.extract(record,generic,tool)


def test_changed_original_graph_manifest_and_tool_are_rejected(tmp_path):
    generic,record,tool,_=original_cache(tmp_path);cache=cached.MappingBlockCache(tmp_path/'blocks')
    cache.extract(record,generic,tool)
    with pytest.raises(ValueError,match='tool'):cache.extract(record,generic,{**tool,'version':'other'})
    (generic/'original/graph.json').write_text('{}')
    with pytest.raises(ValueError,match='bytes'):cache.extract(record,generic,tool)
    (generic/'original/features.json').write_text('{}')
    with pytest.raises(ValueError,match='manifest'):cache.extract(record,generic,tool)


def test_base_features_and_records_preserved_and_outcomes_ignored(tmp_path,monkeypatch):
    generic,record,tool,graph=original_cache(tmp_path)
    base=np.arange(313,dtype=float).reshape(1,313)
    fullrecord={**record,'normalized_formula':record['formula'],'cache_hit':True,'values':base[0].tolist()}
    seen=[]
    class Base:
        def __init__(self,*a,**k):self.graph=type('Graph',(),{'tool':tool})()
        def matrix(self,rows,workers):seen.extend(rows);return base,[fullrecord]
    monkeypatch.setattr(cached.v5,'FeatureExtractor',Base)
    extractor=cached.FeatureExtractor(tmp_path,tmp_path/'blocks',frozen_tool=tool)
    rows=[{'formula':record['formula'],'lut4_count':float('nan'),'predicted_lut4':-999}]
    x,records=extractor.matrix(rows)
    assert x.shape==(1,336) and x[0,:313].tolist()==base[0].tolist()
    assert x[0,313:].tolist()==feature_vector(graph)
    assert seen==[{'formula':record['formula']}]
    assert records[0]['mapping_source_sha256']==cached.v6.source_hashes()['mapping_features_v6.py']
    assert extractor.last_cache_counts=={'hits':0,'misses':1}
    repeated,_=extractor.matrix(rows);assert np.array_equal(x,repeated)
    assert extractor.last_cache_counts=={'hits':1,'misses':0}


@pytest.mark.parametrize('invalid',[[],[0.]*22,[-1.]+[0.]*22])
def test_invalid_payload_values_rejected_even_with_recomputed_digest(tmp_path,invalid):
    generic,record,tool,_=original_cache(tmp_path);cache=cached.MappingBlockCache(tmp_path/'blocks')
    cache.extract(record,generic,tool);path=next((tmp_path/'blocks').glob('*/features.json'))
    value=json.loads(path.read_text());value['values']=invalid
    value['payload_sha256']=cached.digest({k:v for k,v in value.items() if k!='payload_sha256'})
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError,match='Invalid cached mapping values'):cache.extract(record,generic,tool)


@pytest.mark.parametrize('during_extraction',[False,True])
def test_public_extractor_checks_runtime_before_and_after(tmp_path,monkeypatch,during_extraction):
    generic,record,tool,graph=original_cache(tmp_path)
    initial=cached.v6.source_hashes();state={'changed':not during_extraction}
    class Base:
        def __init__(self,*a,**k):self.graph=type('Graph',(),{'tool':tool})()
        def matrix(self,rows,workers):
            state['changed']=True
            return np.zeros((1,313)),[record]
    monkeypatch.setattr(cached.v5,'FeatureExtractor',Base)
    extractor=cached.FeatureExtractor(tmp_path,tmp_path/'blocks',frozen_tool=tool)
    monkeypatch.setattr(cached.v6,'source_hashes',lambda:({**initial,'area_model_v6.py':'changed'} if state['changed'] else initial))
    with pytest.raises(ValueError,match='runtime changed'):extractor.matrix([{'formula':record['formula']}])
