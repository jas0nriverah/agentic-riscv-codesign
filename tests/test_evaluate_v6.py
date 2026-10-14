"""Staged release/calibration/cluster and evidence contracts, without real labels."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import numpy as np
import pytest

sys.path.insert(0,str(Path(__file__).parents[1]/'scripts'))
import evaluate_v6 as evaluate
import measure_v6 as measure

def row(index=0,stratum='a'):
    return {'benchmark':'fixture','candidate_id':str(index),'formula':f'addi(in0,{index})','stratum':stratum}

def test_complete_group_max_not_individual_row_quantile():
    # Nine exchangeable groups: one large group has only one severe residual.
    groups=['large']*100+[f'g{i}' for i in range(8)]
    y=np.array([0.]*99+[100.]+list(range(8)));p=np.zeros(len(y))
    value=evaluate.group_upper_margin(y,p,groups)
    assert value['group_count']==9 and value['rank']==9
    assert value['upper_margin_lut4']==100

def test_rank_finite_sample_unbounded_and_zero_policy():
    value=evaluate.group_upper_margin(np.arange(8),np.zeros(8),list(range(8)))
    assert value['rank']==9 and value['upper_margin_lut4'] is None
    value=evaluate.group_upper_margin(np.zeros(9),np.ones(9),list(range(9)))
    assert value['rank']==9 and value['upper_margin_lut4']==0
    value=evaluate.group_upper_margin(np.arange(20),np.zeros(20),list(range(20)))
    assert value['rank']==19 and value['upper_margin_lut4']==18

@pytest.mark.parametrize('y,p,g',[([],[],[]),([1],[1,2],['a']),([float('nan')],[1],['a']),([[1]],[[1]],['a']),([1],[1],[])])
def test_margin_rejects_invalid_arrays(y,p,g):
    with pytest.raises(ValueError):evaluate.group_upper_margin(y,p,g)

def cluster_fixture():
    strata=[];groups=[];difference=[]
    for s in range(8):
        for g in range(8):
            for _ in range(1+(g%3)):
                strata.append(f's{s}');groups.append(f's{s}-g{g}');difference.append(float(s+1))
    return np.asarray(difference),np.asarray(strata),np.asarray(groups)

def test_stratified_component_bootstrap_fixed_weights_no_rejection():
    d,s,g=cluster_fixture();result=evaluate.paired_stratified_components(d,s,g,128)
    assert result['macro_stratum_mae_difference_lut4']==4.5
    assert result['descriptive_stratified_component_bootstrap_95_interval']==[4.5,4.5]
    assert set(result['component_counts_by_stratum'].values())=={8}
    assert result['empty_draw_rejection'] is False
    assert result==evaluate.paired_stratified_components(d,s,g,128)

def test_bootstrap_replays_whole_unequal_components_with_shared_paired_draws():
    d,s,g=cluster_fixture();d=np.asarray([float(int(group.split('g')[1])) for group in g])
    actual=evaluate.paired_stratified_components(d,s,g,64)
    rng=np.random.default_rng(evaluate.BOOTSTRAP_SEED);samples=np.zeros(64)
    for stratum in sorted(set(s)):
        names=sorted(set(g[s==stratum]))
        for replicate in range(64):
            selected=rng.integers(0,len(names),len(names))
            rows=[i for index in selected for i,group in enumerate(g) if group==names[index]]
            samples[replicate]+=float(np.mean(d[rows]))/8
    assert actual['descriptive_stratified_component_bootstrap_95_interval']==np.quantile(samples,[.025,.975]).tolist()

def test_bootstrap_cross_stratum_components_and_thin_groups_reject():
    d,s,g=cluster_fixture();bad=g.copy();bad[s=='s1']=g[s=='s0']
    with pytest.raises(ValueError,match='noncrossing'):evaluate.paired_stratified_components(d,s,bad,8)
    keep=g!='s0-g0'
    with pytest.raises(ValueError,match='eight components'):evaluate.paired_stratified_components(d[keep],s[keep],g[keep],8)
    with pytest.raises(ValueError):evaluate.paired_stratified_components(d,s,g,True)

def test_upper_predictions_require_order_and_original_point_margin():
    rows=[row(0),row(1)];pred=[{**r,'predicted_lut4':1.,'upper_lut4':3.} for r in rows]
    evaluate.validate_predictions(rows,pred,margin=2.)
    with pytest.raises(ValueError,match='order'):evaluate.validate_predictions(rows,pred[::-1],margin=2.)
    wrong=deepcopy(pred);wrong[0]['upper_lut4']=4.
    with pytest.raises(ValueError,match='margin'):evaluate.validate_predictions(rows,wrong,margin=2.)
    wrong=deepcopy(pred);wrong[0]['upper_lut4']=True
    with pytest.raises(ValueError):evaluate.validate_predictions(rows,wrong,margin=0.)
    for r in pred:r['upper_lut4']=None
    evaluate.validate_predictions(rows,pred,margin=None)
    with pytest.raises(ValueError):evaluate.validate_predictions(rows,pred,margin=2.)

def test_zero_positive_tail_cap_and_complete_group_coverage():
    rows=[row(i) for i in range(3)];pred=[{**r,'predicted_lut4':p,'upper_lut4':u} for r,p,u in zip(rows,[0.,1.,3.],[0.,2.,4.])]
    metrics=evaluate.model_metrics(rows,np.array([0.,3.,3.]),pred,{r['formula']:'a' if i<2 else 'b' for i,r in enumerate(rows)})
    assert metrics['zero_count']==1 and metrics['positive_count']==2
    assert metrics['zero_target_mae_lut4']==0
    assert metrics['upper_bound']['candidate_coverage']==2/3
    assert metrics['upper_bound']['whole_component_coverage']==.5
    assert metrics['cap_feasibility']['16']['true_accept_count']==3
    assert metrics['upper_bound']['by_stratum']['a']['whole_component_coverage']==.5

def test_uncertainty_metadata_has_finite_spread_and_integer_domain_counts():
    valid={'tree_disagreement_lut4':.5,'outside_training_feature_ranges':2,'uncertainty_scope':'descriptive'}
    evaluate.validate_uncertainty_metadata([valid])
    for field,value in [('tree_disagreement_lut4',float('nan')),('tree_disagreement_lut4',-1),('outside_training_feature_ranges',True),('outside_training_feature_ranges',337),('uncertainty_scope','')]:
        with pytest.raises(ValueError,match='metadata'):evaluate.validate_uncertainty_metadata([{**valid,field:value}])

def test_verification_sources_bind_ordered_original_formulas():
    from isaforge.rtl import generate_rtl
    formulas=['add(in0,in1)','xor(in0,in1)'];source=evaluate.verification_source(formulas)
    assert generate_rtl(formulas[0],'candidate_0') in source
    assert generate_rtl(formulas[1],'candidate_1') in source
    assert 'candidate_0 c0(.in0(in0), .in1(in1), .result(out_0));' in source
    assert source!=evaluate.verification_source(formulas[::-1])

def test_verification_seed_boundary_and_shape_are_checked(tmp_path):
    import itertools,random
    from isaforge.rtl import BOUNDARIES
    seed=evaluate.VERIFICATION_SEEDS['calibration'];rng=random.Random(seed)
    pairs=list(itertools.product(BOUNDARIES,repeat=2))+[(rng.getrandbits(32),rng.getrandbits(32)) for _ in range(2048)]
    lines=[' '.join(f'{v:08x}' for v in (a,b,0,0)) for a,b in pairs];path=tmp_path/'vectors.txt';path.write_text('\n'.join(lines)+'\n')
    evaluate.validate_verification_vectors(path,2,seed)
    with pytest.raises(ValueError,match='seed/shape'):evaluate.validate_verification_vectors(path,2,seed+1)
    with pytest.raises(ValueError,match='seed/shape'):evaluate.validate_verification_vectors(path,3,seed)
    path.write_text('\n'.join(lines[:-1]))
    with pytest.raises(ValueError,match='count differs'):evaluate.validate_verification_vectors(path,2,seed)

def review_fixture(tmp_path,monkeypatch):
    root=tmp_path/'result';root.mkdir()
    evaluate.write(root/'point-freeze.json',{'frozen_at_utc':'2026-10-15T00:00:00+00:00'})
    monkeypatch.setattr(evaluate,'ROOT',tmp_path)
    monkeypatch.setattr(evaluate,'validate_point_freeze',lambda *a:None)
    monkeypatch.setattr(evaluate,'freeze_records',lambda *a:[evaluate.record(root/'point-freeze.json',root)])
    review={'schema':'isaforge-v6-label-review-v1','scope':'calibration','approved_for_label_release':True,
        'freeze_sha256':evaluate.sha(root/'point-freeze.json'),'freeze_commit':'1'*40,'reviewed_at_utc':'2026-10-15T00:00:01+00:00'}
    monkeypatch.setattr(evaluate.subprocess,'run',lambda *a,**k:SimpleNamespace(returncode=0,stdout=(root/'point-freeze.json').read_bytes()))
    return root,review

def test_stage_review_binds_exact_committed_bytes(tmp_path,monkeypatch):
    root,review=review_fixture(tmp_path,monkeypatch)
    assert evaluate.validate_review(root,'calibration',review)==review
    monkeypatch.setattr(evaluate.subprocess,'run',lambda *a,**k:SimpleNamespace(returncode=0,stdout=b'changed'))
    with pytest.raises(ValueError,match='approved commit'):evaluate.validate_review(root,'calibration',review)

@pytest.mark.parametrize('field,value',[('scope','test'),('freeze_sha256','wrong'),('approved_for_label_release',False),('freeze_commit','HEAD'),('reviewed_at_utc','2026-10-14T23:59:59+00:00')])
def test_review_rejects_wrong_scope_hash_authorization_commit_or_time(tmp_path,monkeypatch,field,value):
    root,review=review_fixture(tmp_path,monkeypatch);review[field]=value
    with pytest.raises(ValueError,match='parent approval'):evaluate.validate_review(root,'calibration',review)

def test_test_stage_requires_calibration_freeze_first(tmp_path,monkeypatch):
    root,review=review_fixture(tmp_path,monkeypatch)
    monkeypatch.setattr(evaluate,'validate_calibration_freeze',lambda *a:(_ for _ in ()).throw(ValueError('calibration not frozen')))
    with pytest.raises(ValueError,match='calibration not frozen'):evaluate.validate_review(root,'test',review)

def test_calibration_refuses_consumed_test_and_existing_freeze(tmp_path):
    evaluate.write(tmp_path/'corpus/test/label-release.json',{})
    with pytest.raises(ValueError,match='precede test'):evaluate.calibrate(tmp_path)
    (tmp_path/'corpus/test/label-release.json').unlink();evaluate.write(tmp_path/'calibration-freeze.json',{})
    with pytest.raises(ValueError,match='immutable'):evaluate.calibrate(tmp_path)

def test_missing_parent_review_blocks_measurement_before_native_tool(tmp_path,monkeypatch):
    calls=[]
    monkeypatch.setattr(measure,'validate_point_freeze',lambda *a:({}, {}, {}, {}, {}))
    monkeypatch.setattr(measure,'validate_review',lambda *a:(_ for _ in ()).throw(ValueError('no review')))
    monkeypatch.setattr(measure.shutil,'which',lambda *a:calls.append(a))
    with pytest.raises(ValueError,match='no review'):measure.collect(tmp_path,'calibration',tmp_path/'review')
    assert not calls and not list(tmp_path.rglob('label-release.json'))

def test_owned_worker_deadline_retains_log_and_finishes_group(tmp_path,monkeypatch):
    monkeypatch.setattr(measure,'WORKER','import time;print("started",flush=True);time.sleep(30)')
    owner=measure.OwnedWorkers()
    with pytest.raises(subprocess.TimeoutExpired):measure.run_owned({'kind':'fixture'},tmp_path/'worker.log',owner,timeout=.1)
    assert not owner.active and (tmp_path/'worker.log').is_file()
    owner.cancel()
    with pytest.raises(RuntimeError,match='canceled'):
        with (tmp_path/'other.log').open('wb') as stream:owner.launch([sys.executable,'-c','pass'],stream)

def archive_fixture(tmp_path,monkeypatch):
    monkeypatch.setattr(measure,'ROOT',tmp_path)
    monkeypatch.setattr(evaluate,'ROOT',tmp_path)
    root=tmp_path/'results/v6';scope='calibration';directory=root/'corpus'/scope
    scratch=tmp_path/measure.PREFIX/scope/'attempt-0000';scratch.mkdir(parents=True)
    (scratch/'netlist.json').write_text('{"cells":{}}')
    for folder in ('obj_dir','obj_dir_wrapv'):
        (scratch/folder).mkdir();(scratch/folder/'binary.o').write_text('compiler')
    import os
    evaluate.write(directory/'completion.json',{'complete':True,'failures':[],'scratch_directory':os.path.relpath(scratch,root)})
    manifest=measure.pack(root,scope)
    return root,scope,scratch,manifest

def test_stage_archive_relocates_exactly_and_omits_compiler_objects(tmp_path,monkeypatch):
    root,scope,scratch,manifest=archive_fixture(tmp_path,monkeypatch)
    assert len(manifest['files'])==1
    assert evaluate.validate_archive(root,scope)==manifest
    moved=tmp_path/'moved';measure.restore(root,scope,moved);measure.restore(root,scope,moved)
    assert (moved/manifest['files'][0]['path']).read_bytes()==(scratch/'netlist.json').read_bytes()
    with pytest.raises(ValueError,match='immutable'):measure.pack(root,scope)

def test_archive_existing_changed_and_corrupt_zip_reject(tmp_path,monkeypatch):
    root,scope,scratch,manifest=archive_fixture(tmp_path,monkeypatch)
    (scratch/'netlist.json').write_text('changed')
    with pytest.raises(ValueError,match='refusing overwrite'):measure.restore(root,scope,tmp_path)
    with (root/'corpus'/scope/'raw-evidence.zip').open('ab') as stream:stream.write(b'changed')
    with pytest.raises(ValueError,match='identity differs'):measure.restore(root,scope,tmp_path)

@pytest.mark.parametrize('name',['/tmp/escape',measure.PREFIX+'calibration/../escape',measure.PREFIX+'test/attempt/file',measure.PREFIX+'calibration/a\\b'])
def test_archive_stage_paths_cannot_escape(tmp_path,name):
    with pytest.raises(ValueError):measure.destination(name,tmp_path,'calibration')

def test_archive_prefix_symlink_cannot_escape(tmp_path):
    outside=tmp_path/'outside';outside.mkdir();root=tmp_path/'root';prefix=root/measure.PREFIX/'calibration';prefix.parent.mkdir(parents=True)
    prefix.symlink_to(outside,target_is_directory=True)
    with pytest.raises(ValueError,match='escapes'):measure.destination(measure.PREFIX+'calibration/file',root,'calibration')
