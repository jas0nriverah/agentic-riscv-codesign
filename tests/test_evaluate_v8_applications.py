"""Pure synthetic metric/measurement-budget contracts; no real labels or fits."""
from copy import deepcopy
import importlib.util
from pathlib import Path
import sys
import pytest

PATH=Path(__file__).resolve().parents[1]/'scripts/evaluate_v8_applications.py'
spec=importlib.util.spec_from_file_location('evaluate_v8_applications',PATH)
e=importlib.util.module_from_spec(spec);sys.modules[spec.name]=e;spec.loader.exec_module(e)


def fixture():
    programs=[{'benchmark':n,'family':f,'primary_family':primary,'traceTotalInstructions':1000} for n,f,primary in (
        ('small','A',True),('video1','video',True),('video2','video',True),('related','related',False))]
    definitions={'small':[('addi(in0,1)',0)],'video1':[('add(in0,in1)',50),('sub(in0,in1)',100)],
        'video2':[('xor(in0,in1)',10)],'related':[('addi(in0,2)',0)]}
    rows=[];measure={};predictions={m:[] for m in e.MODELS}
    for p in programs:
        for i,(formula,y) in enumerate(definitions[p['benchmark']]):
            row={**p,'candidate_id':str(i),'formula':formula,'overlapSafeSaved':(i+1)*20,'runs':(2-i)*10};rows.append(row);measure[formula]=y
            for m in e.MODELS:
                # Main errors: baseline A=10,video programs20&40 ->family30;
                # challenger A=0,video programs10&20 ->family15. Related999ignored.
                error=999 if not p['primary_family'] else ({'small':10,'video1':20,'video2':40}[p['benchmark']])
                if m=='legacy_rewritten336':error=0 if p['benchmark']=='small' else error/2
                predictions[m].append({'benchmark':p['benchmark'],'candidate_id':str(i),'formula':formula,'predicted_lut4':y+error,'upper_lut4':None})
    labels=[{'formula':f,'lut4_count':y} for f,y in measure.items()]
    return programs,rows,labels,predictions


def test_equal_family_then_program_then_formula_weights_and_related_control():
    p,r,y,pred=fixture();out=e.evaluate(r,y,pred,expected_programs=p)
    assert out['scores']['mapping_v6']['primary_equal_family_mae_lut4']==20
    assert out['scores']['legacy_rewritten336']['primary_equal_family_mae_lut4']==7.5
    assert out['primary']['difference_lut4']==-12.5
    assert out['primary']['paired_family_differences_lut4']=={'A':-10,'video':-15}
    assert out['primary']['leave_one_family_out_difference_lut4']=={'A':-15,'video':-10}
    assert out['counts']=={'primary_families':2,'all_families':3,'programs':4,'application_formula_rows':5,'unique_original_formula_labels':5}
    assert out['scores']['mapping_v6']['by_program']['related']['mae_lut4']==999


def test_zero_positive_mape_tails_bias_and_cap_boundaries():
    value=e.error_metrics([0,32,33],[2.,33.,32.])
    assert value['positive_target_count']==2 and value['zero_target_count']==1 and value['zero_mae_lut4']==2
    assert value['positive_mape_percent']==pytest.approx((1/32+1/33)/2*100)
    assert value['signed_bias_lut4']==pytest.approx(2/3)
    assert value['caps']['32']['false_accept_count']==value['caps']['32']['false_reject_count']==1
    assert value['maximum_underprediction_lut4']==1 and value['worst_absolute_error_lut4']==2
    assert e.error_metrics([0],[0.])['positive_mape_percent'] is None


def test_order_never_reads_measured_outcomes_and_queries_equal_budget():
    candidates=[e.PublicCandidate('a','add(in0,in1)',80,10,63.),e.PublicCandidate('b','sub(in0,in1)',60,20,1.)]
    queried=[]
    def measure(f):queried.append(f);return {'add(in0,in1)':65,'sub(in0,in1)':20}[f]
    result=e.selection_case(candidates,measure,cap=64,budget=1,strategy='predicted_area_feasible_merit',seed=e.RANDOM_SEEDS[0],trace_count=1000)
    assert queried==['add(in0,in1)'] and result['candidate_measurements']==1
    assert result['selected_candidate_id'] is None and result['selected_overlapSafeSaved']==0
    queried.clear();result=e.selection_case(candidates,measure,cap=64,budget=5,strategy='merit',seed=e.RANDOM_SEEDS[0],trace_count=1000)
    assert result['candidate_measurements']==len(queried)==2 and result['selected_candidate_id']=='b'
    assert result['selected_actual_lut4']<=64 and result['attempted_actual_area_violations']==1


def test_zero_savings_baseline_wins_even_if_measured_feasible():
    candidate=e.PublicCandidate('a','addi(in0,1)',0,1,0.)
    result=e.selection_case([candidate],lambda _:0,cap=64,budget=1,strategy='merit',seed=1,trace_count=100)
    assert result['selected_candidate_id'] is None and result['selected_overlapSafeSaved']==0


def test_seeded_random_order_is_row_order_invariant_and_every_seed_retained():
    p,r,y,pred=fixture();out=e.evaluate(r,y,pred,expected_programs=p)
    aggregate=out['selection']['aggregates']['mapping_v6/random/cap64/budget1']
    assert set(aggregate['per_seed_primary_equal_family_normalized_regret_percent'])=={str(s) for s in e.RANDOM_SEEDS}
    candidates=[e.PublicCandidate(str(i),f'addi(in0,{i})',i,i,0.) for i in range(8)]
    for seed in e.RANDOM_SEEDS:assert e.acquisition_order(candidates,'random',64,seed)==e.acquisition_order(list(reversed(candidates)),'random',64,seed)
    assert len({tuple(c.candidate_id for c in e.acquisition_order(candidates,'random',64,s)) for s in e.RANDOM_SEEDS})>1


def test_oracle_regret_and_zero_oracle_handling():
    p,r,y,pred=fixture()
    for row in r:
        if row['benchmark']=='small':row['overlapSafeSaved']=0
    out=e.evaluate(r,y,pred,expected_programs=p)
    for result in out['selection']['details']:
        assert result['normalized_regret_percent_trace_instructions']>=0
        assert result['candidate_measurements']<=result['budget']
        if result['benchmark']=='small':
            assert result['oracle_overlapSafeSaved']==0 and result['retained_oracle_savings_fraction'] is None
            assert result['normalized_regret_percent_trace_instructions']==0
        if result['selected_candidate_id'] is not None:assert result['selected_actual_lut4']<=result['cap_lut4']


def test_missing_declared_pool_and_missing_measurements_never_silently_drop_family():
    p,r,y,pred=fixture()
    with pytest.raises(ValueError,match='empty declared'):e.evaluate([v for v in r if v['benchmark']!='small'],y,pred,expected_programs=p)
    with pytest.raises(ValueError,match='complete original'):e.evaluate(r,y[:-1],pred,expected_programs=p)


@pytest.mark.parametrize('field,value',[('primary_family',1),('traceTotalInstructions',True),('traceTotalInstructions',999),('overlapSafeSaved',-1),('runs',1.5),('overlapSafeSaved',1001)])
def test_invalid_boolean_trace_or_integer_public_fields_rejected(field,value):
    p,r,y,pred=fixture();r[0][field]=value
    with pytest.raises(ValueError):e.evaluate(r,y,pred,expected_programs=p)


@pytest.mark.parametrize('value',[True,-1,1.5,float('nan')])
def test_label_integer_contract_rejected(value):
    p,r,y,pred=fixture();y[0]['lut4_count']=value
    with pytest.raises(ValueError):e.evaluate(r,y,pred,expected_programs=p)


@pytest.mark.parametrize('value',[True,-1,float('nan'),float('inf')])
def test_invalid_prediction_rejected(value):
    p,r,y,pred=fixture();pred['mapping_v6'][0]['predicted_lut4']=value
    with pytest.raises(ValueError):e.evaluate(r,y,pred,expected_programs=p)


def test_prediction_identity_coverage_and_inherited_bound_rejected():
    p,r,y,pred=fixture();missing=deepcopy(pred);missing['mapping_v6'].pop()
    with pytest.raises(ValueError,match='cover every'):e.evaluate(r,y,missing,expected_programs=p)
    wrong=deepcopy(pred);wrong['mapping_v6'][0]['formula']='addi(in0,999)'
    with pytest.raises(ValueError,match='identity'):e.evaluate(r,y,wrong,expected_programs=p)
    bound=deepcopy(pred);bound['mapping_v6'][0]['upper_lut4']=99
    with pytest.raises(ValueError,match='upper bounds'):e.evaluate(r,y,bound,expected_programs=p)


def test_duplicate_formula_measurement_and_program_formula_rows_rejected():
    p,r,y,pred=fixture()
    with pytest.raises(ValueError,match='physical label'):e.evaluate(r,y+[y[0]],pred,expected_programs=p)
    duplicate={**r[0],'candidate_id':'different'}
    with pytest.raises(ValueError,match='canonical formula'):e.evaluate(r+[duplicate],y,pred,expected_programs=p)


def shared_formula_fixture():
    p,r,y,pred=fixture();related=next(row for row in r if row['benchmark']=='related');related['formula']='addi(in0,1)'
    y=[row for row in y if row['formula']!='addi(in0,2)']
    for values in pred.values():
        primary=next(row for row in values if row['benchmark']=='small');other=next(row for row in values if row['benchmark']=='related')
        other['formula']=primary['formula'];other['predicted_lut4']=primary['predicted_lut4']
    return p,r,y,pred


def test_shared_formula_labels_measured_once_but_application_rows_retained():
    p,r,y,pred=shared_formula_fixture();out=e.evaluate(r,y,pred,expected_programs=p)
    assert out['counts']['application_formula_rows']==5 and out['counts']['unique_original_formula_labels']==4
    pred['mapping_v6'][-1]['predicted_lut4']+=1
    with pytest.raises(ValueError,match='identical point'):e.evaluate(r,y,pred,expected_programs=p)


def test_canonical_formula_ties_and_infeasible_nearest_cap_fallback():
    candidates=[e.PublicCandidate('z','add(in0,in1)',20,10,60.),e.PublicCandidate('a','sub(in0,in1)',20,10,1.),
        e.PublicCandidate('q','xor(in0,in1)',100,5,66.),e.PublicCandidate('b','or(in0,in1)',1,5,65.)]
    assert [r.formula for r in e.acquisition_order(candidates,'predicted_area_feasible_merit',64,1)]==['add(in0,in1)','sub(in0,in1)','or(in0,in1)','xor(in0,in1)']
    assert e.acquisition_order(candidates,'frequency',64,1)[0].formula=='add(in0,in1)'
    result=e.selection_case(candidates[:2],lambda f:60 if f.startswith('add') else 1,cap=64,budget=2,strategy='merit',seed=1,trace_count=100)
    assert result['selected_candidate_id']=='z' # Canonical tie, not lower actual area or smaller ID.
    assert result['candidate_measurements']==2 # Never stop at the first feasible candidate.
