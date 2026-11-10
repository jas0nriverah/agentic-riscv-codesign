"""Budget release changes decisions only upward and gates both kinds of error."""
import importlib.util
from pathlib import Path
import numpy as np
SPEC=importlib.util.spec_from_file_location('release',Path(__file__).parents[1]/'scripts/release_budget_coverage.py')
r=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(r)


class Model:
    def __init__(self,values):self.values=values
    def predict_features(self,rows,x):return [{'predicted_lut4':v} for v in self.values]


def test_routing_is_original_ast_and_release_crosses_caps_without_lowering(monkeypatch):
    rows=[{'formula':f} for f in ['xor(add(sra(addi(xori(in0,13),37),in1),in0),in1)',
        'xor(add(in0,sra(in1,in0)),and(in0,in1))','srl(in0,in1)',
        'sub(sra(addi(xori(in0,13),37),in1),in0)']]
    routing=[r.signed.route(row['formula']) for row in rows]
    monkeypatch.setattr(r.signed,'points',lambda *args:({'base':[60.]*4,r.signed.CURRENT:[63.]*4,r.signed.PRIMARY:[64.,128.,64.,128.]},routing))
    values,_=r.points(rows,np.zeros((4,336)),Model([90.,140.,200.,100.]),Model([80.,130.,220.,110.]))
    assert values[r.PRIMARY]==[90.,140.,64.,128.]
    assert values[r.ABLATION]==[80.,130.,64.,128.]
    assert values[r.FALLBACK]==[90.,128.,64.,128.]


def test_cap_events_track_inclusive_threshold_and_error_direction_separately():
    events=r.cap_events([64.,64.,65.,65.],[65.,66.,65.,65.],[65.,64.,64.,66.])['64']
    assert events=={'actual_accept':2,'actual_reject':2,'corrected_false_accept':1,'new_false_accept':0,'corrected_false_reject':0,'new_false_reject':1}


def test_fewer_false_accepts_cannot_offset_new_false_reject():
    models={n:[64.,64.] for n in r.NAMES};models[r.PRIMARY]=[66.,66.]
    m=r.panel_metrics({'models':models,'actual_lut4':[100.,64.]})
    assert m['checks'][r.PRIMARY]['caps_no_worse_current']['64']=={'false_accept':True,'false_reject':False}
    assert not r.passes(m['checks'][r.PRIMARY])
    assert m['checks'][r.PRIMARY]['maximum_underprediction_no_worse_current']


def test_accuracy_requires_both_metrics_and_predeclared_tolerance():
    ref={'mae_lut4':1.,'positive_mape_percent':2.}
    assert all(r.accuracy(ref,ref).values())
    assert not any(r.accuracy(ref,ref,True).values())
    assert not r.accuracy(ref,{'mae_lut4':.8,'positive_mape_percent':None})['positive_mape_percent']
