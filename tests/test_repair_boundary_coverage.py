"""Exact cap adjudication, even-tree median semantics and separate error gates."""
import importlib.util
from pathlib import Path
import numpy as np
SPEC=importlib.util.spec_from_file_location('boundary',Path(__file__).parents[1]/'scripts/repair_boundary_coverage.py')
r=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(r)


def test_exact_cap_repair_and_mean_median_consensus_preserves_supported_crossing():
    p,c=r.adjudicate([126.5,121.63],[129.3,141.8],[128.,156.],[True,True])
    assert p.tolist()==[128.,141.8] and c==[[128],[]]


def test_smallest_unsupported_crossed_cap_and_no_changes_outside_route():
    p,c=r.adjudicate([20.,20.,129.,128.],[150.,150.,150.,150.],[32.,32.,128.,128.],[True,False,True,True])
    assert p.tolist()==[32.,150.,150.,128.]
    assert c==[[32,64,128],[],[],[128]]


def test_even300_median_is_average_middle_values_not_strict_majority():
    class Tree:
        def __init__(self,value):self.value=value
        def predict(self,x):return np.full(len(x),self.value)
    class Estimator:estimators_=[Tree(128.)]*150+[Tree(130.)]*150
    class Model:estimator=Estimator()
    medians,trees=r.tree_medians(Model(),np.zeros((1,336)))
    assert medians.tolist()==[129.]
    assert int(np.sum(trees[:,0]>128))==150
    p,c=r.adjudicate([126.],[130.],medians,[True])
    assert p.tolist()==[130.] and c==[[]]


def test_false_accept_gain_cannot_offset_a_new_false_reject():
    models={'base':[128.,128.],r.CURRENT:[128.,128.],r.BUDGET:[129.,129.],r.NAME:[129.,129.]}
    m=r.panel_metrics({'models':models,'actual_lut4':[150.,125.]})
    assert m['checks']['caps']['128']=={'false_accept_no_worse_release':True,'false_reject_no_worse_signed':False}
    assert not r.passed(m['checks'])


def test_repair_may_not_reintroduce_release_false_acceptance():
    models={'base':[128.],r.CURRENT:[128.],r.BUDGET:[150.],r.NAME:[128.]}
    m=r.panel_metrics({'models':models,'actual_lut4':[150.]})
    assert not m['checks']['caps']['128']['false_accept_no_worse_release']
    assert not r.passed(m['checks'])


def test_fresh_equal_release_does_not_establish_repair_transfer():
    saved={'models':{'base':[128.],r.CURRENT:[128.],r.BUDGET:[140.],r.NAME:[140.]},'routes':[{'compound':True}]}
    dev={'selected_candidate':r.NAME,'gates':{r.NAME:{'development_gate_passed':True}}}
    _,_,gates,eligible=r.score_values(saved,[150.],dev,[0])
    checks=gates[r.NAME]['checks']
    assert all(checks['strictly_better_signed'].values())
    assert checks['strictly_fewer_false_accept_cap_events_than_signed']
    assert checks['fresh_modified_prediction_count']==0 and not checks['fresh_repair_exercised']
    assert not gates[r.NAME]['fresh_gate_passed'] and not eligible
