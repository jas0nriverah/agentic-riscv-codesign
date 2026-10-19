"""Synthetic-only V15 chronology, full-panel scoring and resource tests."""
import copy
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import pytest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('evaluate_v15_scoped',ROOT/'scripts/evaluate_v15_scoped.py')
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)


def test_exact_four_new_templates_eight_parameters():
    rows=m.candidates()
    assert len(rows)==len({r['formula'] for r in rows})==32
    assert rows[0]['formula']=='mul(xor(in0,in1),addi(0,31))'
    assert rows[8]['formula']=='xor(mul(in0,addi(0,31)),in1)'
    assert rows[16]['formula']=='sub(srai(xor(in0,in1),2),srai(in1,31))'
    assert rows[-1]['formula']=='sub(srai(sub(in0,in1),16),srai(in1,31))'
    import model_v15_scoped as router
    assert all(router.route(r['formula'])['source_model']=='V9' for r in rows)


def test_formula_projection_ignores_historical_targets_and_tracks_aliases():
    data={'rows':[{'formula':'add(in0,in1)','lut4_count':998,'accepted_forms':['add(in1,in0)']}], 'labels':[1,2]}
    assert list(m.formula_inputs(data))==['add(in0,in1)','add(in1,in0)']


def test_duplicate_original_or_declared_alias_stops_before_jobs(tmp_path,monkeypatch):
    monkeypatch.setattr(m,'ROOT',tmp_path)
    path=tmp_path/'reference.json'; m.write(path,[{'formula':'add(in0,in1)','accepted_forms':[m.candidates()[0]['formula']]}])
    with pytest.raises(ValueError,match='without replacements'): m.novelty(m.candidates(),{'old':path})
    m.write(path,[{'formula':'add(in0,in1)'}]); result,b=m.novelty(m.candidates(),{'old':path})
    assert result['all32_absent'] and b[path]==m.sha(path)


def points(rows):
    vals=[{'candidate_id':r['candidate_id'],'formula':r['formula'],'predicted_lut4':8.,'upper_lut4':None,'calibration_status':'uncalibrated'} for r in rows]
    return {'models':{'V6':copy.deepcopy(vals),'V9':copy.deepcopy(vals),'V15':copy.deepcopy(vals)},'routes':[{'source_model':'V9'} for r in rows]}


@pytest.mark.parametrize('poison',['partial','model','negative','bool','chosen','order'])
def test_all_frozen_points_exactly_before_labels(poison):
    rows=m.candidates(); p=points(rows)
    if poison=='partial':p['models']['V9'].pop()
    elif poison=='model':p['models']['other']=p['models']['V9']
    elif poison=='negative':p['models']['V6'][0]['predicted_lut4']=-1
    elif poison=='bool':p['models']['V6'][0]['predicted_lut4']=True
    elif poison=='chosen':p['models']['V15'][0]['predicted_lut4']=9
    else:p['models']['V6'].reverse()
    with pytest.raises(ValueError):m.validate_points(p,rows)


def test_metrics_full_panel_macro_templates_caps_and_underprediction():
    rows=m.candidates(); p=points(rows)
    for i,r in enumerate(p['models']['V9']):r['predicted_lut4']=float(i)
    p['models']['V15']=copy.deepcopy(p['models']['V9'])
    labels=[{'candidate_id':r['candidate_id'],'lut4':64} for r in rows]
    report=m.metrics(rows,p,labels)
    assert report['models']['V6']['macro_template_mae']==56
    assert report['models']['V9']['macro_template_mae']==48.5
    assert report['delta_v15_minus_v6']==-7.5 and report['delta_v15_minus_v9']==0
    assert report['models']['V15']['caps']['32']['false_accept']==32
    assert report['models']['V15']['caps']['64']['false_accept']==0
    assert report['models']['V15']['worst_underprediction']['lut4']==64
    with pytest.raises(ValueError):m.metrics(rows,p,labels[:-1])


def harness(tmp_path,monkeypatch,feature_fail=False,map_fail=False):
    root=tmp_path/'results/eval'; root.mkdir(parents=True); rows=m.candidates(); p=points(rows)
    monkeypatch.setattr(m,'ROOT',tmp_path); monkeypatch.setattr(m.hardware,'ROOT',tmp_path)
    monkeypatch.setattr(m,'validate',lambda r:({'scope':'synthetic'},rows,{'executables':{'yosys':{'path':'/synth/yosys','version':'synthetic'}}}))
    monkeypatch.setattr(m,'git_freeze',lambda *a:None)
    m.write(root/'plan.json',{'synthetic':True})
    monkeypatch.setattr(m.shutil,'disk_usage',lambda p:SimpleNamespace(free=100*1024**3))
    owner=SimpleNamespace(processes={},cancel=lambda:([],[]))
    monkeypatch.setattr(m.hardware,'HardwareWorkers',lambda t:owner)
    monkeypatch.setattr(m.hardware.native,'validate_tools',lambda t:None)
    monkeypatch.setattr(m,'validate_proof',lambda *a:None)
    monkeypatch.setattr(m.hardware,'validate_metric',lambda metric,*a:metric)
    calls=[]
    def owned(command,folder,owner,guard):
        folder.mkdir(parents=True); calls.append(command[2]); guard()
        if command[2]=='feature-worker':
            if feature_fail:raise ValueError('synthetic feature failure')
            row=next(r for r in rows if r['formula']==command[-1]); value={**row,'values':[0]*336}
        else:
            assert not(root/'point-freeze.json').exists()
            assert not any(c in ('verify','map') for c in calls)
            value=p
        m.write(folder/'result.json',value); return value
    def worker(payload,folder,owner,hot,guard):
        assert (root/'point-freeze.json').is_file(), 'Any target stage must follow frozen all96 points'
        folder.mkdir(parents=True); calls.append(payload['kind']); guard()
        if payload['kind']=='verify':return {'verified':True,'formula_count':32}
        assert 'verify' in calls
        if map_fail and payload['formula']==rows[1]['formula']:raise ValueError('synthetic mapping failure')
        return {'ice40_lut4_count':4,'formula':payload['formula']}
    monkeypatch.setattr(m,'owned',owned); monkeypatch.setattr(m.hardware,'run_worker',worker)
    return root,calls


def test_complete32_chronology_retains_full_outputs_without_jobs(tmp_path,monkeypatch):
    root,calls=harness(tmp_path,monkeypatch)
    done=m.run(root,'a'*40)
    assert done['complete'] and done['completed_mapping_count']==32
    assert calls.count('feature-worker')==32 and calls.count('prediction-worker')==1 and calls.count('verify')==1 and calls.count('map')==32
    assert m.read(root/'attempt/metrics.json')['delta_v15_minus_v9']==0
    assert len(m.read(root/'attempt/labels.json'))==32
    assert m.read(root/'point-freeze.json')['prediction_count']==96
    with pytest.raises(ValueError,match='no retries'):m.run(root,'a'*40)


def test_feature_failure_never_predicts_or_reads_targets(tmp_path,monkeypatch):
    root,calls=harness(tmp_path,monkeypatch,feature_fail=True)
    with pytest.raises(ValueError,match='primary unavailable'):m.run(root,'a'*40)
    assert 'prediction-worker' not in calls and 'verify' not in calls and 'map' not in calls
    assert not m.read(root/'attempt/completion.json')['complete']


def test_one_failed_target_never_scores_partial_or_replaces(tmp_path,monkeypatch):
    root,calls=harness(tmp_path,monkeypatch,map_fail=True)
    with pytest.raises(ValueError,match='primary unavailable'):m.run(root,'a'*40)
    assert not(root/'attempt/metrics.json').exists() and not(root/'attempt/labels.json').exists()
    assert not m.read(root/'attempt/completion.json')['complete']
    assert calls.count('map')<=32


def test900s_guard_checks_global_deadline(tmp_path,monkeypatch):
    monkeypatch.setattr(m.hardware,'ROOT',tmp_path); monkeypatch.setattr(m.shutil,'disk_usage',lambda p:SimpleNamespace(free=100*1024**3))
    with pytest.raises(ValueError,match='deadline'):m.Guard(tmp_path/'raw',tmp_path/'out',began=m.time.monotonic()-901,maximum_seconds=900)
