"""Projection and pre-fit gates only; never execute an experiment fit."""
import importlib.util
from pathlib import Path
import sys
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
spec=importlib.util.spec_from_file_location('train_v8_applications',ROOT/'scripts/train_v8_applications.py')
t=importlib.util.module_from_spec(spec);spec.loader.exec_module(t)


def rows():return [{'benchmark':'synthetic','candidate_id':'fixture','formula':'add(in0,in1)'}]
def prediction(**extra):return [{**rows()[0],'predicted_lut4':5.,'tree_disagreement_lut4':1.,'outside_training_feature_ranges':0,**extra}]


def test_projection_strips_historical_bounds_and_outcome_poison():
    value=t.point_projection(rows(),prediction(upper_lut4=999,calibration_status='calibrated',upper_margin_lut4=99,lut4_count=float('nan'),carry_count=1),'mapping_v6')[0]
    assert value['upper_lut4'] is None and value['calibration_status']=='point_only_application_pilot'
    assert value['predicted_lut4']==5 and value['tree_disagreement_lut4']==1
    assert 'lut4_count' not in value and 'upper_margin_lut4' not in value and 'carry_count' not in value


def test_master_reference_missing_diagnostics_are_explicit_none():
    value=t.point_projection(rows(),[{**rows()[0],'predicted_lut4':5.}],'masterrtl_fixed')[0]
    assert value['tree_disagreement_lut4'] is None and value['outside_training_feature_ranges'] is None


@pytest.mark.parametrize('value',[True,-1,float('nan'),float('inf')])
def test_projection_rejects_invalid_points(value):
    with pytest.raises(ValueError):t.point_projection(rows(),prediction(predicted_lut4=value),'mapping_v6')


def test_projection_requires_exact_identity_order_and_coverage():
    with pytest.raises(ValueError,match='coverage'):t.point_projection(rows(),[],'mapping_v6')
    for field in ('benchmark','candidate_id','formula'):
        with pytest.raises(ValueError,match='identity'):t.point_projection(rows(),prediction(**{field:'wrong'}),'mapping_v6')


@pytest.mark.parametrize('existing',['training-start.json','point-freeze.json','label-release.json','measurements'])
def test_training_rejects_existing_attempt_or_labels_before_reading_inputs(tmp_path,existing,monkeypatch):
    root=tmp_path/'root';root.mkdir();(root/existing).write_text('{}')
    monkeypatch.setattr(t,'read',lambda *_:pytest.fail('Existing-stage gate must precede all reads'))
    monkeypatch.setattr(t.ExtraTreesRegressor,'fit',lambda *_:pytest.fail('No fits in a gate test'))
    with pytest.raises(ValueError,match='immutable'):t.run(root,tmp_path/'training',tmp_path/'review',tmp_path/'cache')
    assert not (root/'fit-attempts').exists()


def test_training_rejects_unsealed_inputs_before_estimators(tmp_path,monkeypatch):
    root=tmp_path/'root';root.mkdir()
    monkeypatch.setattr(t,'read',lambda *_:{'status':'not-sealed'})
    monkeypatch.setattr(t.ExtraTreesRegressor,'fit',lambda *_:pytest.fail('No fits before source/input seal'))
    with pytest.raises(ValueError,match='source-bound'):t.run(root,tmp_path/'training',tmp_path/'review',tmp_path/'cache')
    assert not (root/'training-start.json').exists()


@pytest.mark.parametrize('field,value',[('tree_disagreement_lut4',-1),('tree_disagreement_lut4',True),('tree_disagreement_lut4',float('nan')),('outside_training_feature_ranges',True),('outside_training_feature_ranges',-1),('outside_training_feature_ranges',1.5)])
def test_projection_rejects_invalid_diagnostics(field,value):
    with pytest.raises(ValueError):t.point_projection(rows(),prediction(**{field:value}),'mapping_v6')


def test_shared_formula_projection_requires_identical_points_across_programs():
    first=rows()[0];second={**first,'benchmark':'second','candidate_id':'second'}
    values=[{**first,'predicted_lut4':1.},{**second,'predicted_lut4':2.}]
    with pytest.raises(ValueError,match='same model point'):t.point_projection([first,second],values,'mapping_v6')
