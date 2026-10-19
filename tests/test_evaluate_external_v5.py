"""Prelabel external protocol regressions; no real model/FPGA labels required."""
from copy import deepcopy
import hashlib
import importlib.util
from pathlib import Path
import sys

import numpy as np
import pytest

ROOT=Path(__file__).parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import evaluate_external_v5 as evaluator
import measure_external_v5 as measurement
from isaforge.features import candidate_id
from isaforge.rtl import generate_rtl


def input_rows():
    # Synthetic grammar inputs, with one duplicate formula weighted by program.
    rows=[];offset=0
    for benchmark,count in evaluator.EXPECTED_PROGRAM_COUNTS.items():
        for index in range(count):
            formula=f'addi(in0,{offset+index})'
            rows.append({'benchmark':benchmark,'candidate_id':candidate_id(benchmark,formula),
                         'formula':formula,'family':evaluator.PROGRAM_FAMILIES[benchmark]})
        offset+=count
    rows[-1]['formula']=rows[0]['formula']
    rows[-1]['candidate_id']=candidate_id(rows[-1]['benchmark'],rows[-1]['formula'])
    return rows


def test_exact_program_family_mapping_and_stratum():
    rows=input_rows();evaluator.validate_candidates(rows)
    rows[0]['family'],rows[5]['family']=rows[5]['family'],rows[0]['family']
    with pytest.raises(ValueError,match='identities'):evaluator.validate_candidates(rows)
    rows=input_rows();rows[0]['stratum']='speech_codec'
    with pytest.raises(ValueError,match='identities'):evaluator.validate_candidates(rows)


def test_macro_keeps_three_family_weights_and_duplicate_rows():
    rows=input_rows();y=np.zeros(80);p=np.array([{'graph_shortest_paths':3,'speech_codec':6,'multiset_word_search':12}[r['family']] for r in rows])
    scores=evaluator.scoped_metrics(rows,y,p,np.ones(80,bool))
    assert scores['macro_family_mae_lut4']==7
    assert scores['mae_lut4']==pytest.approx((5*3+47*6+28*12)/80)
    assert scores['row_count']==80


def test_empty_family_never_becomes_three_family_macro():
    rows=input_rows();y=np.ones(80);p=y.copy()
    mask=np.array([r['family']!='speech_codec' for r in rows])
    value=evaluator.scoped_metrics(rows,y,p,mask)
    assert value['macro_family_mae_lut4'] is None
    assert value['family_counts']['speech_codec']==0
    assert evaluator.scoped_metrics(rows,y,p,np.zeros(80,bool))['status']=='empty subset'


def test_bounds_are_original_margin_and_duplicate_prediction_consistent():
    rows=[{'formula':'addi(in0,1)','predicted_lut4':5.,'upper_lut4':7.,'outside_training_feature_ranges':1} for _ in range(2)]
    schema={'calibration':{'upper_margin_lut4':2.}}
    evaluator.validate_prediction_metadata('dual_semantics',rows,schema)
    wrong=deepcopy(rows);wrong[1]['upper_lut4']=8.
    with pytest.raises(ValueError,match='margin'):evaluator.validate_prediction_metadata('dual_semantics',wrong,schema)
    wrong=deepcopy(rows);wrong[1]['predicted_lut4']=6.
    with pytest.raises(ValueError,match='inconsistent'):evaluator.validate_prediction_metadata('dual_semantics',wrong,schema)
    unbounded=deepcopy(rows)
    for r in unbounded:r['upper_lut4']=None
    evaluator.validate_prediction_metadata('dual_semantics',unbounded,{'calibration':{'upper_margin_lut4':None}})


def test_coverage_preserves_all_rows_and_reports_ood():
    rows=[{'family':f} for f in evaluator.FAMILIES]
    predictions=[{'upper_lut4':v,'outside_training_feature_ranges':i} for i,v in enumerate((2.,None,1.))]
    result=evaluator.bound_diagnostics(rows,np.array([1.,1.,2.]),predictions)
    assert result['all']['finite_bound_fraction']==2/3
    assert result['all']['observed_candidate_coverage']==.5
    assert result['all']['outside_feature_range_rows']==2
    assert result['whole_family_coverage_count']==1


def test_overlap_consumes_all2313_and_separates_skeleton_matches():
    development=[{'formula':f'addi(in0,{i})'} for i in range(2057)]
    consumed=[{'formula':f'addi(in0,{2057+i})'} for i in range(256)]
    features=lambda rows:[{**r,'values':[i]} for i,r in enumerate(rows)]
    rows=[{'benchmark':'probe','candidate_id':'probe','formula':'addi(in0,9000)','family':'graph_shortest_paths'}]
    result=evaluator.overlap_report(rows,[{'formula':rows[0]['formula'],'values':[99999]}],development,consumed,features(development),features(consumed))
    assert result['records'][0]['formula_novel'] is True
    assert result['records'][0]['strict_novel'] is False
    assert result['records'][0]['overlap']['development']['original_skeleton'] is True
    with pytest.raises(ValueError,match='2313'):evaluator.overlap_report(rows,[],development[:-1],consumed,[],[])


def test_measurement_rejects_missing_review_before_any_tool(tmp_path,monkeypatch):
    calls=[]
    monkeypatch.setattr(measurement,'validate_committed_review',lambda *args:(_ for _ in ()).throw(ValueError('review missing')))
    monkeypatch.setattr(measurement.shutil,'which',lambda *args:calls.append(args))
    with pytest.raises(ValueError,match='review missing'):
        measurement.collect(tmp_path,tmp_path/'scratch',tmp_path/'label-approval.json')
    assert calls==[] and not (tmp_path/'label-release.json').exists()


def test_original_cache_requires_binary_and_all_output_hashes(tmp_path):
    formula='addi(in0,1)'
    (tmp_path/'candidate.v').write_text(generate_rtl(formula))
    for name in ('ice40-netlist.json','ice40.ys','ice40.log'):(tmp_path/name).write_text(name)
    metric={'formula':formula,'tool':'yosys fixture','tool_sha256':'binary','measurement_source':'rtl_synthesis',
            **{key:evaluator.sha(tmp_path/name) for name,key in [('candidate.v','rtl_sha256'),('ice40-netlist.json','netlist_sha256'),('ice40.ys','script_sha256'),('ice40.log','log_sha256')]}}
    evaluator.write(tmp_path/'metrics.json',metric)
    assert measurement.validate_cached(formula,tmp_path,'yosys fixture','binary')==metric
    with pytest.raises(ValueError,match='provenance'):measurement.validate_cached(formula,tmp_path,'yosys fixture','changed-binary')
    (tmp_path/'candidate.v').write_text('altered RTL')
    with pytest.raises(ValueError,match='provenance'):measurement.validate_cached(formula,tmp_path,'yosys fixture','binary')


def test_owned_worker_timeout_cleans_group_and_retains_log(tmp_path,monkeypatch):
    # Exercise bounded process cleanup without executing RTL or source workloads.
    monkeypatch.setattr(measurement,'WORKER','import time; print("started",flush=True); time.sleep(20)')
    with pytest.raises(__import__('subprocess').TimeoutExpired):
        measurement.run_owned({'kind':'synthetic'},tmp_path/'worker.log',timeout=.05)
    assert (tmp_path/'worker.log').is_file()
