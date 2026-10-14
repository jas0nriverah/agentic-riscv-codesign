"""V6 point/router lineage, uncalibrated bounds, portable label-free inference."""
from copy import deepcopy
import json
from pathlib import Path
import shutil

import joblib
import numpy as np
import pytest
from sklearn.ensemble import ExtraTreesRegressor
from isaforge import area_model_v6 as v6
from isaforge import area_model_v5 as v5


def matrix(n=4):
    x=np.zeros((n,len(v6.columns())));x[:,0]=np.arange(n)+1
    x[:,v6.columns().index('original_gate_count')]=1
    return x


def rows():
    return [{'benchmark':'fixture','candidate_id':str(i),'formula':f} for i,f in enumerate(
        ('addi(in0,1)','mul(in0,in1)','mulhsu(in0,in1)','slli(in0,2)'))]


def predictor(kind='mapping_v6'):
    x=matrix();estimator=ExtraTreesRegressor(**v6.FIXED_PARAMETERS).fit(x[:,v6.mapping_indices()],[2.,4.,6.,8.])
    tool={'version':'fixture','executable_sha256':'f'*64}
    model=v6.V6Predictor(estimator,kind,v6.columns(),4,v6.uncalibrated(),[0.]*len(v6.columns()),
        [10.]*len(v6.columns()),tool,v6.source_hashes())
    if kind=='router_v6':
        semantic=ExtraTreesRegressor(n_estimators=3,random_state=1,n_jobs=1).fit(x[:,:len(v5.columns())],[20.,40.,60.,80.])
        model.semantic_expert=v5.V5Predictor(semantic,'dual_semantics','extra_leaf1',v5.columns(),1665,
            {'upper_margin_lut4':99.,'assumption':'old expert scope'},[0.]*len(v5.columns()),[10.]*len(v5.columns()),tool)
        model.semantic_source={'artifact_sha256':'a'*64,'schema_sha256':'b'*64}
    return model


def test_feature_schema_and_fixed217_selection():
    assert len(v6.columns())==336 and len(v6.mapping_columns())==217
    assert np.array_equal(v6.mapping_indices()[:194],v5.view_indices('dual_graph'))
    assert all(n.startswith('mapping_') for n in v6.mapping_columns()[194:])


def test_uncalibrated_point_and_router_upper_bounds_are_null():
    for kind in v6.KINDS:
        results=predictor(kind).predict_features(rows(),matrix())
        assert all(r['upper_lut4'] is None and r['calibration_status']=='uncalibrated' for r in results)
    model=predictor('router_v6');results=model.predict_features(rows(),matrix())
    assert [r['predicted_lut4'] for r in results]==[2.,40.,60.,8.]
    assert [r['routed_expert'] for r in results]==['mapping_v6','dual_semantics','dual_semantics','mapping_v6']


def test_composite_calibration_does_not_reuse_expert_margin_or_change_points():
    model=predictor('router_v6');before=model.predict_features(rows(),matrix())
    model.calibration={'status':'calibrated','alpha':.1,'group_count':9,'rank':9,
        'upper_margin_lut4':3.,'assumption':'fresh complete calibration groups only'}
    after=model.predict_features(rows(),matrix())
    assert [r['predicted_lut4'] for r in after]==[r['predicted_lut4'] for r in before]
    assert all(r['upper_lut4']==r['predicted_lut4']+3 for r in after)


def test_original_zero_and_active_expert_domain_warning():
    model=predictor();x=matrix();x[0,v6.columns().index('original_gate_count')]=0
    x[1,v6.columns().index('v5_original_mul_count') if 'v5_original_mul_count' in v6.columns() else 312]=99999
    x[2,-1]=99999
    result=model.predict_features(rows(),x)
    assert result[0]['predicted_lut4']==result[0]['tree_disagreement_lut4']==0
    assert result[1]['outside_training_feature_ranges']==0
    assert result[2]['outside_training_feature_ranges']==1


@pytest.mark.parametrize('value',[float('nan'),float('inf'),-1.])
def test_bad_feature_values_rejected(value):
    x=matrix();x[0,0]=value
    with pytest.raises(ValueError,match='matrix'):predictor().predict_features(rows(),x)


@pytest.mark.parametrize('margin',[0.,1.,float('nan'),-1.])
def test_uncalibrated_model_never_invents_finite_confidence(margin):
    model=predictor();model.calibration['upper_margin_lut4']=margin
    with pytest.raises(ValueError):model.predict_features(rows(),matrix())


def test_prediction_ignores_fabricated_targets_and_identity_metadata():
    model=predictor('router_v6');clean=model.predict_features(rows(),matrix())
    poisoned=[{**r,'lut4_count':float('nan'),'carry_count':-100,'correctness_verified':False,'stratum':'other'} for r in rows()]
    assert model.predict_features(poisoned,matrix())==clean


def test_save_load_relocation_and_metadata_tampering(tmp_path):
    path=tmp_path/'source/model.joblib';model=predictor('router_v6');v6.save_model(model,path)
    elsewhere=tmp_path/'relocated';elsewhere.mkdir()
    for source in (path,path.with_suffix('.json')):shutil.copyfile(source,elsewhere/source.name)
    restored=v6.load_model(elsewhere/path.name,elsewhere/'new-cache')
    assert restored.predict_features(rows(),matrix())==model.predict_features(rows(),matrix())
    assert restored.cache_root==str((elsewhere/'new-cache').resolve())
    schema=elsewhere/'model.json';record=json.loads(schema.read_text());record['kind']='mapping_v6';schema.write_text(json.dumps(record))
    with pytest.raises(ValueError,match='metadata'):v6.load_model(elsewhere/path.name)


def test_source_and_artifact_changes_fail_closed(tmp_path,monkeypatch):
    path=tmp_path/'model.joblib';v6.save_model(predictor(),path)
    monkeypatch.setattr(v6,'source_hashes',lambda:{'different':'source'})
    with pytest.raises(ValueError,match='source'):v6.load_model(path)


def test_save_never_overwrites_point_artifact(tmp_path):
    path=tmp_path/'point.joblib';model=predictor();v6.save_model(model,path)
    with pytest.raises(ValueError,match='New V6'):v6.save_model(model,path)


def test_empty_features_and_extraction_forwards_formula_only(tmp_path,monkeypatch):
    seen=[]
    class Base:
        def __init__(self,*args,**kwargs):self.graph=object()
        def matrix(self,inputs,workers):seen.extend(inputs);raise RuntimeError('stop before cache access')
    monkeypatch.setattr(v6.v5,'FeatureExtractor',Base)
    extractor=v6.FeatureExtractor(tmp_path)
    empty,records=extractor.matrix([])
    assert empty.shape==(0,336) and records==[]
    with pytest.raises(RuntimeError):extractor.matrix([{'formula':'addi(in0,1)','lut4_count':float('nan')}])
    assert seen==[{'formula':'addi(in0,1)'}]


def test_estimator_weights_are_bound_beyond_parameters(tmp_path):
    path=tmp_path/'model.joblib';model=predictor();v6.save_model(model,path)
    changed=joblib.load(path);changed.estimator.estimators_[0].tree_.value[:]+=1
    joblib.dump(changed,path,compress=3)
    schema_path=path.with_suffix('.json');schema=json.loads(schema_path.read_text())
    schema['artifact_sha256']=v6.sha(path);schema_path.write_text(json.dumps(schema))
    with pytest.raises(ValueError,match='weights'):v6.load_model(path)


def test_train_blocks_fresh_release_before_reading_inputs(tmp_path,monkeypatch):
    import sys
    sys.path.insert(0,str(Path(__file__).parents[1]/'scripts'))
    import train_v6
    fresh=tmp_path/'corpus/calibration';fresh.mkdir(parents=True);(fresh/'label-release.json').write_text('{}')
    calls=[];monkeypatch.setattr(train_v6,'validate_inputs',lambda *a,**k:calls.append(a))
    with pytest.raises(ValueError,match='released'):train_v6.run(tmp_path,tmp_path,tmp_path/'cache')
    assert calls==[] and not (tmp_path/'training-start.json').exists()


def test_fit_selection_uses_exact_old_fit_only_and_checks_feature_prefix():
    import sys
    sys.path.insert(0,str(Path(__file__).parents[1]/'scripts'))
    import train_v6
    root=Path(__file__).parents[1]/'results/2026-10-14-v5'
    frozen=train_v6.read(root/'development-features.json');split=train_v6.read(root/'split.json')
    records=[{'formula':r['formula'],'values':r['values']+[0.]*23} for r in frozen['records']]
    # An unused old calibration feature cannot enter any fitting array.
    records[split['calibration_indices'][0]]['values'][-1]=float('nan')
    selected,indices,x,y,_=train_v6.select_fitting(root,records)
    assert indices==split['fit_indices'] and x.shape==(1665,336) and np.isfinite(x).all()
    assert len(selected)==len(y)==1665
    records[indices[0]]['values'][0]+=1
    with pytest.raises(ValueError,match='replay differs'):train_v6.select_fitting(root,records)


def test_real300tree217column_roundtrip_and_padding_vs_named_fields(tmp_path):
    rng=np.random.default_rng(2026101551)
    x=rng.normal(size=(96,217));y=rng.normal(size=96)
    estimator=ExtraTreesRegressor(**v6.FIXED_PARAMETERS).fit(x,y)
    expected=v6.estimator_fingerprint(estimator)
    path=tmp_path/'real-forest.joblib'
    for _ in range(2):
        joblib.dump(estimator,path,compress=3);estimator=joblib.load(path)
        assert v6.estimator_fingerprint(estimator)==expected
    nodes=estimator.estimators_[0].tree_.__getstate__()['nodes']
    used={i for name in nodes.dtype.names for i in range(nodes.dtype.fields[name][1],nodes.dtype.fields[name][1]+nodes.dtype.fields[name][0].itemsize)}
    padding=set(range(nodes.dtype.itemsize))-used
    assert padding  # Regression specifically exercises sklearn structured padding.
    raw=nodes.view(np.uint8).reshape(len(nodes),nodes.dtype.itemsize)
    raw[:,sorted(padding)]^=127
    assert v6.estimator_fingerprint(estimator)==expected
    nodes['threshold'][0]+=1
    assert v6.estimator_fingerprint(estimator)!=expected


def test_semantic_fingerprint_ignores_cache_host_but_binds_inference_metadata():
    expert=predictor('router_v6').semantic_expert
    expected=v6.semantic_fingerprint(expert)
    expert.cache_root='/unrelated/relocated/cache'
    assert v6.semantic_fingerprint(expert)==expected
    expert.feature_maximum[0]+=1
    assert v6.semantic_fingerprint(expert)!=expected


def test_fingerprint_preserves_numeric_width_and_canonical_endianness():
    import hashlib
    def digest(array):
        h=hashlib.sha256();v6._fingerprint_value(h,array);return h.hexdigest()
    little=np.asarray([1,2,3],dtype='<i8');big=little.astype('>i8')
    assert digest(little)==digest(big)
    assert digest(little)!=digest(little.astype('<i4'))
    assert digest(little)!=digest(little.reshape(3,1))
