"""Synthetic-state V8 contracts only: no study data or experiment fit is used."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import joblib
import numpy as np
import pytest
from sklearn.ensemble import ExtraTreesRegressor
from isaforge import area_model_v8 as v8
from isaforge import area_model_v6 as v6


def toy_matrix(n=4):
    x=np.zeros((n,455));x[:,0]=np.arange(n)%2+1
    x[:,v8.columns().index('original_gate_count')]=1
    return x


def toy_rows():
    return [{'benchmark':'SYNTHETIC_UNIT_FIXTURE_ONLY','candidate_id':str(i),'formula':f} for i,f in enumerate(
        ('addi(in0,1)','mul(in0,in1)','sub(in0,in0)','slli(in0,2)'))]


def toy_provenance():
    indices=list(range(1665))
    return {'fixture_scope':'SYNTHETIC_UNIT_TEST_ONLY_NO_EXPERIMENT_DATA','fit_indices':indices,
        'fit_indices_sha256':hashlib.sha256(json.dumps(indices,separators=(',',':')).encode()).hexdigest(),
        'training_dataset_sha256':'a'*64,'development_dataset_sha256':'a'*64,'development_features_sha256':'b'*64,'split_sha256':'c'*64}


@pytest.fixture(scope='module')
def toy_forest():
    # Actually1665 synthetic rows (only2 distinct feature patterns), never an
    # 8-row forest with false metadata and never labels from a study file.
    x=toy_matrix(1665);y=np.where(x[:,0]==1,2.,8.)
    return ExtraTreesRegressor(**v8.FIXED_PARAMETERS).fit(x[:,v8.view_indices('legacy_original336')],y)


def toy_model(forest,view='legacy_original336'):
    return v8.V8Predictor(deepcopy(forest),view,v8.columns(),1665,[0.]*455,[10.]*455,
        {'version':'SYNTHETIC_UNIT_TOOL','executable_sha256':'f'*64},v8.source_hashes(),toy_provenance(),v8.environment(),v8.compatibility())


def test_storage_and_selected_views_have_explicit_distinct_order():
    assert len(v8.columns())==455 and v8.columns()[:336]==v6.columns()
    assert v8.view_indices('mapping217').tolist()==list(range(194))+list(range(313,336))
    assert v8.view_indices('legacy_original336').tolist()==list(range(194))+list(range(313,336))+list(range(194,313))
    assert v8.view_indices('legacy_rewritten336').tolist()==list(range(194))+list(range(313,336))+list(range(336,455))
    assert len(v8.view_columns('legacy_original336'))==len(v6.columns())==336
    assert v8.view_columns('legacy_original336')!=v6.columns()
    assert all(n.startswith('rewritten_') for n in v8.columns()[336:])


def test_explicit_input_column_names_required_and_same_width_order_rejected(toy_forest):
    model=toy_model(toy_forest)
    with pytest.raises(TypeError):model.predict_features(toy_rows(),toy_matrix())
    names=list(v8.columns());names[0],names[1]=names[1],names[0]
    with pytest.raises(ValueError,match='columns/order'):model.predict_features(toy_rows(),toy_matrix(),feature_columns=names)
    with pytest.raises(ValueError):model.predict_features(toy_rows(),toy_matrix()[:,:336],feature_columns=v6.columns())


def test_point_only_original_zero_and_selected_range_warning(toy_forest):
    for view in v8.TRAINED_VIEWS:
        model=toy_model(toy_forest,view);x=toy_matrix();x[0,v8.columns().index('original_gate_count')]=0
        x[1,-1]=999
        result=model.predict_features(toy_rows(),x,feature_columns=v8.columns())
        assert all(r['upper_lut4'] is None and r['calibration_status']=='point_only' for r in result)
        assert result[0]['predicted_lut4']==result[0]['tree_disagreement_lut4']==0
        assert result[2]['predicted_lut4']>0 # Semantic zero is NEVER original-cost zero.
        assert result[1]['outside_training_feature_ranges']==(view=='legacy_rewritten336')


def test_predictions_ignore_target_score_identity_poison(toy_forest):
    model=toy_model(toy_forest);clean=toy_rows()
    poisoned=[{**r,'lut4_count':float('nan'),'carry_count':-4,'correctness_verified':False,'stratum':'POISON','predicted_lut4':1e99,'upper_margin_lut4':1e99} for r in clean]
    assert model.predict_features(clean,toy_matrix(),feature_columns=v8.columns())==model.predict_features(poisoned,toy_matrix(),feature_columns=v8.columns())


@pytest.mark.parametrize('value',[float('nan'),float('inf'),-1.])
def test_invalid_matrix_values_rejected(toy_forest,value):
    x=toy_matrix();x[0,0]=value
    with pytest.raises(ValueError,match='matrix'):toy_model(toy_forest).predict_features(toy_rows(),x,feature_columns=v8.columns())


@pytest.mark.parametrize('field,value',[('training_formula_count',8),('view','mapping217'),('calibration',{'upper_margin_lut4':3}),('upper_margin_lut4',0.)])
def test_wrong_training_scope_or_transplanted_calibration_rejected(toy_forest,field,value):
    model=toy_model(toy_forest);setattr(model,field,value)
    with pytest.raises(ValueError):model.validate()


def test_wrong_forest_sample_count_and_unmatched_parameter_rejected(toy_forest):
    model=toy_model(toy_forest);model.estimator=ExtraTreesRegressor(**v8.FIXED_PARAMETERS).fit(toy_matrix()[:,v8.view_indices(model.view)],[1.,2.,3.,4.])
    with pytest.raises(ValueError,match='sample count'):model.validate()
    model=toy_model(toy_forest);model.estimator.set_params(criterion='absolute_error')
    with pytest.raises(ValueError,match='full fixed'):model.validate()


def test_training_index_hash_alias_and_runtime_bindings(toy_forest):
    for change in ('hash','indices','alias','source','compatibility'):
        model=toy_model(toy_forest)
        if change=='hash':model.training_provenance['split_sha256']='bad'
        elif change=='indices':model.training_provenance['fit_indices'][1]=0
        elif change=='alias':model.training_provenance['development_dataset_sha256']='b'*64
        elif change=='source':model.runtime_source_sha256={'different':'a'*64}
        else:model.audited_compatibility['solver_version']='different'
        with pytest.raises(ValueError):model.validate()


def test_model_roundtrip_relocated_and_symlink_artifact(toy_forest,tmp_path):
    model=toy_model(toy_forest);path=tmp_path/'source/model.joblib';v8.save_model(model,path)
    expected=model.predict_features(toy_rows(),toy_matrix(),feature_columns=v8.columns())
    moved=tmp_path/'moved';moved.mkdir()
    for old in (path,path.with_suffix('.json')):shutil.copyfile(old,moved/old.name)
    alias=tmp_path/'alias.joblib';alias.symlink_to(moved/'model.joblib');alias.with_suffix('.json').symlink_to(moved/'model.json')
    restored=v8.load_model(alias,cache_root=tmp_path/'cache')
    assert restored.predict_features(toy_rows(),toy_matrix(),feature_columns=v8.columns())==expected
    assert restored.cache_root==str((tmp_path/'cache').resolve())
    with pytest.raises(ValueError,match='immutable'):v8.save_model(model,path)


def test_schema_width_equal_order_tampering_rejected(toy_forest,tmp_path):
    path=tmp_path/'model.joblib';v8.save_model(toy_model(toy_forest),path);schema_path=path.with_suffix('.json')
    original=json.loads(schema_path.read_text())
    for field in ('selected_columns','selected_indices','feature_columns'):
        record=deepcopy(original);record[field][0],record[field][1]=record[field][1],record[field][0];schema_path.write_text(json.dumps(record))
        with pytest.raises(ValueError,match='schema'):v8.load_model(path)


def test_named_tree_weight_mutation_rejected_after_artifact_hash_updated(toy_forest,tmp_path):
    path=tmp_path/'model.joblib';v8.save_model(toy_model(toy_forest),path)
    changed=joblib.load(path);changed.estimator.estimators_[0].tree_.value[:]+=1;joblib.dump(changed,path,compress=3)
    schema_path=path.with_suffix('.json');record=json.loads(schema_path.read_text());record['artifact_sha256']=v8.sha(path);schema_path.write_text(json.dumps(record))
    with pytest.raises(ValueError,match='weights'):v8.load_model(path)


def test_python_path_and_os_differences_are_exposed_without_changing_points(toy_forest):
    model=toy_model(toy_forest);expected=model.predict_features(toy_rows(),toy_matrix(),feature_columns=v8.columns())
    model.training_environment['python']['executable']='/other/virtualenv/python'
    model.training_environment['platform']['release']='other-recorded-release'
    model.validate();assert model.compatibility_report()['observed_environment_differs'] is True
    assert model.predict_features(toy_rows(),toy_matrix(),feature_columns=v8.columns())==expected


def test_extraction_forwards_only_formula_and_preserves_proofs(tmp_path,monkeypatch):
    seen=[]
    class Base:
        def __init__(self,*args,**kwargs):self.graph=object()
        def matrix(self,inputs,workers):
            seen.extend(inputs);x=np.zeros((len(inputs),336))
            return x,[{'formula':r['formula'],'values':[0.]*336,'prefix_evidence':'STRICT_FROZEN_V6'} for r in inputs]
    monkeypatch.setattr(v8.v6,'FeatureExtractor',Base)
    extractor=v8.FeatureExtractor(tmp_path);x,records=extractor.matrix([{'formula':'sub(ori(in0,255),in0)','lut4_count':float('nan'),'stratum':'POISON'}])
    assert seen==[{'formula':'sub(ori(in0,255),in0)'}]
    assert x.shape==(1,455) and np.array_equal(x[:,:336],np.zeros((1,336)))
    assert records[0]['prefix_evidence']=='STRICT_FROZEN_V6' and records[0]['values']==x[0].tolist()
    assert 'POISON' not in str(records) and 'lut4_count' not in str(records)
    assert records[0]['v7_modes']['combined']['metadata']['solver']['native_libraries_sha256']
    assert records[0]['v7_modes']['combined']['metadata']['certificate']['steps']
    empty,empty_records=extractor.matrix([]);assert empty.shape==(0,455) and empty_records==[]


def test_schema_rejects_injected_calibration_and_missing_point_marker(toy_forest,tmp_path):
    path=tmp_path/'model.joblib';v8.save_model(toy_model(toy_forest),path);schema_path=path.with_suffix('.json')
    original=json.loads(schema_path.read_text())
    for field in ('calibration','upper_margin_lut4'):
        record=deepcopy(original)
        if field=='calibration':record[field]={'status':'calibrated','upper_margin_lut4':5}
        else:record.pop(field)
        schema_path.write_text(json.dumps(record))
        with pytest.raises(ValueError,match='schema'):v8.load_model(path)


def test_native_proof_identity_difference_is_reported_not_relabelled(toy_forest):
    model=toy_model(toy_forest);before=deepcopy(model.training_environment)
    model.training_environment['solver']['native_libraries_sha256']={'other-platform-build':'e'*64}
    model.validate();report=model.compatibility_report()
    assert report['audited_compatible'] is True and report['observed_environment_differs'] is True
    assert model.training_environment['solver']['native_libraries_sha256']=={'other-platform-build':'e'*64}
    assert report['observed_environment']['solver']==before['solver']


def test_predict_with_evidence_retains_actual_extraction_records(toy_forest,monkeypatch):
    model=toy_model(toy_forest);seen=[]
    class Extract:
        def __init__(self,*args,**kwargs):pass
        def matrix(self,rows,workers):
            seen.append(workers)
            return toy_matrix(len(rows)),[{'formula':r['formula'],'actual_native_proof':'SYNTHETIC_LEDGER'} for r in rows]
    monkeypatch.setattr(v8,'FeatureExtractor',Extract)
    evidence=model.predict_with_evidence(toy_rows(),workers=2)
    assert seen==[2] and len(evidence['feature_records'])==4
    assert all(r['actual_native_proof']=='SYNTHETIC_LEDGER' for r in evidence['feature_records'])
    assert evidence['feature_columns']==list(v8.columns())
    assert all(p['upper_lut4'] is None for p in evidence['predictions'])
    assert evidence['extraction_environment']['solver']['native_libraries_sha256']


def test_environment_and_report_are_independent_snapshots(toy_forest):
    observed=v8.environment();original=deepcopy(v8.semantic.solver_identity())
    observed['solver']['native_libraries_sha256'].clear()
    assert v8.semantic.solver_identity()==original
    model=toy_model(toy_forest);report=model.compatibility_report()
    report['training_environment']['solver']['native_libraries_sha256'].clear()
    assert model.training_environment['solver']['native_libraries_sha256']


def test_noncanonical_valid_formula_is_canonicalized_before_frozen_prefix(tmp_path,monkeypatch):
    seen=[]
    class Base:
        def __init__(self,*args,**kwargs):self.graph=object()
        def matrix(self,inputs,workers):
            seen.extend(inputs)
            return np.zeros((len(inputs),336)),[{'formula':r['formula'],'values':[0.]*336} for r in inputs]
    monkeypatch.setattr(v8.v6,'FeatureExtractor',Base)
    _,records=v8.FeatureExtractor(tmp_path).matrix([{'formula':' addi( in0, 001 ) '}])
    assert seen==[{'formula':'addi(in0,1)'}] and records[0]['formula']=='addi(in0,1)'


@pytest.mark.parametrize('part',['solver','python','platform'])
def test_malformed_environment_record_rejected_cleanly(toy_forest,part):
    model=toy_model(toy_forest);model.training_environment[part]='invalid'
    with pytest.raises(ValueError,match='environment|evidence'):model.validate()


def test_mutated_extraction_evidence_cannot_poison_later_calls(tmp_path,monkeypatch):
    source={'formula':'sub(ori(in0,255),in0)','values':[0.]*336,'prefix_nested':{'identity':'original'}}
    class Base:
        def __init__(self,*args,**kwargs):self.graph=object()
        def matrix(self,inputs,workers):return np.zeros((1,336)),[source]
    monkeypatch.setattr(v8.v6,'FeatureExtractor',Base)
    extractor=v8.FeatureExtractor(tmp_path);rows=[{'formula':source['formula']}]
    solver=deepcopy(v8.semantic.solver_identity());x,records=extractor.matrix(rows)
    assert records[0]['v7_modes']['combined']['metadata']['certificate']['steps']
    records[0]['v7_modes']['combined']['metadata']['solver']['native_libraries_sha256'].clear()
    records[0]['v7_modes']['combined']['metadata']['certificate']['steps'].clear()
    records[0]['v8_extraction_environment']['solver']['native_libraries_sha256'].clear()
    records[0]['prefix_nested']['identity']='POISON'
    again,fresh=extractor.matrix(rows)
    assert np.array_equal(x,again) and v8.semantic.solver_identity()==solver
    assert source['prefix_nested']['identity']=='original'
    assert fresh[0]['v7_modes']['combined']['metadata']['solver']['native_libraries_sha256']
    assert fresh[0]['v7_modes']['combined']['metadata']['certificate']['steps']
