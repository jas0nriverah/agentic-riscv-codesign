"""Clean inference wrapper: synthetic models/features, no historical evidence files."""
import copy
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('clean_predict',ROOT/'scripts/predict.py')
p = importlib.util.module_from_spec(spec); spec.loader.exec_module(p)


@pytest.fixture(autouse=True)
def no_actual_models_or_native(monkeypatch):
    monkeypatch.setattr(p.runtime,'load_model',lambda *a,**k:pytest.fail('Actual model load forbidden'))
    monkeypatch.setattr(p.runtime.FeatureExtractor,'matrix',lambda *a,**k:pytest.fail('Actual feature extraction forbidden'))


@pytest.mark.parametrize('formula',[
    'mul(in0,1)','mul(2047,in0)','mul(in0,addi(0,47))','xor(mul(in0,159),in1)',
    'sub(srai(in0,0),srai(in1,31))','sub(srai(xor(in0,in1),31),srai(in1,31))',
])
def test_fixed_scoped_gate_routes_covered_original_syntax(formula):
    assert p.route(formula)['source_model']=='coverage'


@pytest.mark.parametrize('formula',[
    'add(in0,in1)','mul(in0,in1)','mul(in0,-7)','mul(in0,0)','mul(in0,2048)',
    'mul(in0,addi(0,-7))','mul(in0,addi(in1,7))','mul(in0,add(3,4))','mulh(in0,7)','mulhu(in0,7)','mulhsu(in0,7)',
    'sub(srai(in0,32),srai(in1,31))','sub(srai(in0,-1),srai(in1,31))','sub(srai(in0,2),srai(in1,30))',
    'sub(srli(in0,2),srai(in1,31))','sub(srai(7,2),srai(in1,31))','sub(srai(in0,2),srai(addi(0,7),31))',
])
def test_fixed_scoped_gate_keeps_unsupported_cases_on_base(formula):
    assert p.route(formula)=={'source_model':'base','coverage_classes':[]}


def rows():
    return [{'candidate_id':'a','formula':'add(in0,in1)'},{'candidate_id':'b','formula':'mul(in0,31)'}]


def features():
    return {'columns':list(p.runtime.columns()),'records':[dict(r,values=[0.]*336) for r in rows()]}


@pytest.mark.parametrize('poison',['columns','order','id','width','nan','negative','bool'])
def test_cached_features_reject_bad_schema_identity_and_values(poison):
    data=features()
    if poison=='columns':data['columns'].reverse()
    elif poison=='order':data['records'].reverse()
    elif poison=='id':data['records'][0]['candidate_id']='changed'
    elif poison=='width':data['records'][0]['values'].pop()
    else:data['records'][0]['values'][0]={'nan':float('nan'),'negative':-1,'bool':True}[poison]
    with pytest.raises(ValueError):p.matrix(rows(),data)


@pytest.fixture
def pair(tmp_path,monkeypatch):
    monkeypatch.setattr(p,'ROOT',tmp_path);defs={};calls=[]
    for name,count in [('base',1665),('coverage',1713)]:
        path=tmp_path/'models'/name/'model.joblib';path.parent.mkdir(parents=True);path.write_text('SYNTHETIC '+name)
        path.with_suffix('.json').write_text('{}')
        defs[name]=(p.sha(path),p.sha(path.with_suffix('.json')),count)
    monkeypatch.setattr(p,'MODELS',defs)
    def load(path):
        name=path.parent.name;calls.append(('load',name))
        def predict(observed,x):
            calls.append(('predict',name,[r['candidate_id'] for r in observed]));assert x.shape==(len(observed),336)
            return [{**{k:r[k] for k in ('candidate_id','formula','benchmark') if k in r},'predicted_lut4':0. if r['candidate_id']=='a' else (10. if name=='base' else 20.),
                     'upper_lut4':None,'calibration_status':'uncalibrated','tree_disagreement_lut4':.25,'model':'mapping_v6','routed_expert':'mapping_v6','outside_training_feature_ranges':7} for r in observed]
        return SimpleNamespace(kind='mapping_v6',training_formula_count=defs[name][2],calibration={'status':'uncalibrated','upper_margin_lut4':None},frozen_tool={'version':'SYNTHETIC'},predict_features=predict)
    monkeypatch.setattr(p.runtime,'load_model',load)
    return calls


def test_scoped_preserves_exact_base_fallback_and_coverage_points(pair):
    x=p.matrix(rows(),features());base,_=p.predict(rows(),x,'base');coverage,_=p.predict(rows(),x,'coverage')
    selected,routes=p.predict(rows(),x,'scoped')
    assert selected==[base[0],coverage[1]] and selected[0]['predicted_lut4']==0
    assert [r['source_model'] for r in routes]==['base','coverage']
    assert pair[-4:]==[('load','base'),('predict','base',['a']),('load','coverage'),('predict','coverage',['b'])]
    poisoned=[{**r,'lut4_count':float('nan'),'predicted_lut4':-999} for r in rows()]
    assert p.predict(poisoned,x,'scoped')==(selected,routes)


@pytest.mark.parametrize('which',['artifact','metadata'])
def test_frozen_hash_mismatch_fails_before_model_load(pair,which):
    path=p.ROOT/'models/base'/('model.joblib' if which=='artifact' else 'model.json');path.write_text('POISON')
    with pytest.raises(ValueError,match='hash differs'):p.load('base')
    assert pair==[]


def test_cached_run_never_extracts_and_writes_descriptive_points(pair,tmp_path):
    candidate=tmp_path/'candidates.json';saved=tmp_path/'features.json';out=tmp_path/'predictions.json'
    candidate.write_text(json.dumps(rows()));saved.write_text(json.dumps(features()))
    result=p.run(candidate,saved,'scoped',out,tmp_path/'cache')
    assert result==json.loads(out.read_text()) and result['model']=='scoped' and result['fits']==0
    assert result['candidate_sha256']==p.sha(candidate) and result['features_sha256']==p.sha(saved)
    assert [r['predicted_lut4'] for r in result['predictions']]==[0.,20.]
    assert not(tmp_path/'cache').exists()
    with pytest.raises(ValueError,match='Fresh'):p.run(candidate,saved,'base',out,tmp_path/'cache')


def test_optional_extraction_uses_frozen_tool_and_explicit_cache(pair,tmp_path,monkeypatch):
    candidate=tmp_path/'candidates.json';candidate.write_text(json.dumps(rows()));seen=[]
    class Extractor:
        def __init__(self,cache_root,*,frozen_tool):seen.append((cache_root,frozen_tool))
        def matrix(self,observed,workers):assert observed==rows() and workers==1;return np.zeros((2,336)),[]
    monkeypatch.setattr(p.runtime,'FeatureExtractor',Extractor)
    result=p.run(candidate,None,'base',tmp_path/'output.json',tmp_path/'cache')
    assert seen==[(tmp_path/'cache',{'version':'SYNTHETIC'})] and result['features_sha256'] is None
    assert [c for c in pair if c[0]=='load']==[('load','base')]
