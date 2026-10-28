import math
import pytest
from scripts import evaluate_grouped_feasibility_calibration as m


def test_one_class_and_small_group_fallback_preserve_raw_scores():
    for records in ([dict(group=str(i),label=1,score=.8) for i in range(6)],
                    [dict(group='one',label=i%2,score=.3+.2*(i%2)) for i in range(10)]):
        fit=m.fit_calibrator(records)
        assert fit['kind']=='identity'
        assert m.apply_calibrator(fit,[0,.1,.9,1])==[0,.1,.9,1]


def test_group_balanced_positive_calibration_is_monotone_and_finite():
    records=[dict(group=str(g),label=i%2,score=.2 if i%2==0 else .7)
             for g in range(6) for i in range(8)]
    fit=m.fit_calibrator(records)
    assert fit['kind']=='logistic' and fit['slope']>0
    values=m.apply_calibrator(fit,[0,.1,.5,.9,1])
    assert values==sorted(values) and all(math.isfinite(x) and 0<=x<=1 for x in values)


def test_nonpositive_fit_falls_back_instead_of_reversing_order():
    records=[dict(group=str(g),label=i%2,score=.9 if i%2==0 else .1)
             for g in range(6) for i in range(8)]
    fit=m.fit_calibrator(records)
    assert fit['kind']=='identity' and fit['reason']=='nonpositive_slope'


def test_outer_and_inner_splits_exclude_group_and_all_target_families():
    def row(i,g,f):return dict(candidate_id=i,workload_group=g,formula=f)
    rows=[row('a','outer','add(in0,in1)'),row('b','inner','add(in0,in1)'),
          row('c','inner','xor(in0,in1)'),row('d','other','xor(in0,in1)'),
          row('e','other','sub(in0,in1)')]
    train,target,failed,excluded=m.split(rows,[],'outer')
    assert {r['candidate_id'] for r in train}=={'c','d','e'}
    inner,valid,_,_=m.split(train,[],'inner')
    assert [r['candidate_id'] for r in inner]==['e']
    assert [r['candidate_id'] for r in valid]==['c']
    assert excluded==['b']


def test_invalid_prediction_score_rejected():
    with pytest.raises(ValueError):m.apply_calibrator(dict(kind='identity'),[float('nan')])
