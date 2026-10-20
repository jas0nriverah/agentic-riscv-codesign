"""Synthetic contracts; fixtures are not measured application evidence."""
import copy

import pytest

from isaforge import codesign as c
from isaforge.features import extract_features
from isaforge.latency_features import candidate_features, instruction_latency, latency_table
from scripts import analyze_speedup_model as analysis
from scripts.reproduce_model_analysis import canonical_results


def calibration():
    rows=[dict(op=op,immediate=None,cycles=4) for op in ('add','xor','andi')]
    rows += [dict(op=op,immediate=n,cycles=4+n//4+n%4)
             for op in ('slli','srli','srai') for n in range(32)]
    rows.append(dict(op='pcpi',immediate=None,cycles=5))
    return dict(rows=rows,rule_matches_all=True,semantic_checks_passed=True,stock_trap_control_passed=True)


def occurrence(pcs=('0x10','0x14'),runs=10):
    return dict(pcs=list(pcs),size=len(pcs),blockRuns=runs)


@pytest.mark.parametrize('amount,expected',[(0,4),(1,5),(4,5),(31,14)])
def test_operand_dependent_shift_latency(amount,expected):
    assert instruction_latency(dict(op='srli',imm=amount),latency_table(calibration()))==expected


@pytest.mark.parametrize('op,imm',[('srl',1),('mul',None),('lw',None),('pcpi',None),
                                  ('srli',True),('srli',-1),('srli',32),('srli',None)])
def test_unsupported_operations_and_invalid_shift_amounts_fail_closed(op,imm):
    with pytest.raises(ValueError): instruction_latency(dict(op=op,imm=imm),latency_table(calibration()))


def test_distinct_dag_nodes_and_dynamic_occurrences_not_expression_tree():
    candidate=dict(formula='add(add(in0,in1),add(in0,in1))',occurrences=[occurrence()],
                   speedup=float('nan'),area=-1,candidate_cycles=-1)
    result=candidate_features(candidate,{16:dict(op='add'),20:dict(op='add')},1000,100,calibration())
    assert result['dynamic_software_cycles']==80
    assert result['estimated_saved_cycles']==30
    assert result['estimated_speedup']==1000/970
    assert result['estimated_cycle_reduction']==0.03
    assert result['replacement_execution_fraction']==0.1


def test_each_occurrence_uses_its_own_distinct_size_and_count():
    candidate=dict(occurrences=[occurrence(),occurrence(('0x20','0x24','0x28'),5)])
    program={16:dict(op='add'),20:dict(op='add'),32:dict(op='srli',imm=31),
             36:dict(op='slli',imm=1),40:dict(op='add')}
    result=candidate_features(candidate,program,1000,100,calibration())
    assert result['estimated_saved_cycles']==30+90
    assert (result['occurrence_size_min'],result['occurrence_size_max'])==(2,3)


@pytest.mark.parametrize('occurrences,instructions',[
    ([occurrence(),occurrence()],100),
    ([occurrence(('0x10','0x10'))],100),
    ([occurrence()],19),
    ([occurrence(runs=True)],100),
    ([occurrence(('0x11','0x14'))],100),
])
def test_impossible_or_overlapping_occurrences_rejected(occurrences,instructions):
    with pytest.raises(ValueError):
        candidate_features(dict(occurrences=occurrences),{16:dict(op='add'),20:dict(op='add')},
                           1000,instructions,calibration())


def row(identity, estimate, speedup=1.1, area=10, timing=True):
    formula='add(in0,slli(in1,1))'
    return {**extract_features(dict(formula=formula,size=2,runs=10,places=1,saved=10,savedPercent=10)),
            'candidate_id':identity,'benchmark':'fixture:input','formula':formula,
            'latency_features':dict(estimated_speedup=estimate),
            'speedup':speedup,'area':area,'timing_feasible':timing,
            'measurement_source':'synthesis_estimate','measurement_seconds':1.0}


def test_real_provider_interface_budget_and_final_choice():
    rows=[row('a',1.5,speedup=0.9),row('b',1.4,area=21),row('c',1.3,timing=False),row('d',1.2,speedup=1.1)]
    labels={r['candidate_id']:r for r in rows}; calls=[]
    def provider(public):
        assert 'speedup' not in public and 'area' not in public and 'timing_feasible' not in public
        calls.append(public['candidate_id']); return copy.deepcopy(labels[public['candidate_id']])
    limited=analysis.latency_search(rows,provider,20,3,0)
    assert calls==['a','b','c'] and limited[-1]['best_speedup']==1.0
    calls.clear()
    full=analysis.latency_search(rows,provider,20,4,0)
    assert calls==['a','b','c','d'] and full[-1]['best_speedup']==1.1
    assert full[-1]['selected_id']=='d' and full[-1]['target_measurement_seconds']==4
    assert full[-1]['best_speedup']!=sum(r['speedup'] for r in rows)


def test_public_label_poisoning_cannot_change_query_order():
    public=[row('a',1.2),row('b',1.3)]
    labels={r['candidate_id']:copy.deepcopy(r) for r in public}
    for r in public: r['speedup']=float('nan'); r['area']=float('nan')
    outcome=analysis.latency_search(public,lambda r:labels[r['candidate_id']],20,1,4)
    assert outcome[0]['measured_ids']==['b']


def test_calibration_report_must_match_raw_evidence(tmp_path,monkeypatch):
    measured=calibration(); fake=copy.deepcopy(measured); fake['rows'][0]['cycles']=42
    c.seal(tmp_path/'report.json',fake)
    monkeypatch.setattr(analysis,'audit_calibration',lambda root:measured)
    with pytest.raises(ValueError,match='differs from raw'):
        analysis.authenticated_calibration(tmp_path)


def test_calibration_source_changes_rejected(tmp_path,monkeypatch):
    measured=calibration(); c.seal(tmp_path/'report.json',measured)
    c.write(tmp_path/'plan.json',dict(source_bindings={'isaforge/model.py':'0'*64}))
    monkeypatch.setattr(analysis,'audit_calibration',lambda root:measured)
    with pytest.raises(ValueError,match='source changed'):
        analysis.authenticated_calibration(tmp_path)


def test_support_check_uses_public_features_not_outcomes():
    source=[row('a',1.2),row('b',1.3)]; target=row('c',1.4)
    target.update(runs=50,speedup=float('nan'),area=float('nan'))
    result=analysis.support(source,[target])[0]
    assert result['changed_training_constants']==['runs']
    assert result['outside_training_ranges']==['runs']


def test_replay_json_roundtrip_preserves_every_scientific_value():
    original=dict(range=(1.0,1.2),analysis_seconds=0.1,coverage=0.2)
    stored=dict(range=[1.0,1.2],analysis_seconds=0.3,coverage=0.2)
    assert canonical_results(original)==canonical_results(stored)
    stored['coverage']=0.3
    assert canonical_results(original)!=canonical_results(stored)


@pytest.mark.parametrize('target,expected',[('calibration.json','Calibration changed'),
                                           ('corpus.json','Pilot artifact changed')])
def test_analysis_rejects_resealed_mutations(tmp_path,target,expected):
    root=tmp_path/'analysis'; pilot=tmp_path/'pilot'; root.mkdir(); pilot.mkdir()
    for path,value in ((root/'public-predictions.json',[]),(root/'baseline-inputs.json',[]),
                       (root/'calibration.json',calibration()),(pilot/'public.json',[]),
                       (pilot/'corpus.json',{'rows':[]})):
        c.seal(path,value)
    protocol=dict(source_bindings={},packages={},baseline_bindings={},
                  predictions_sha256=c.sha(root/'public-predictions.json'),
                  baseline_inputs_sha256=c.sha(root/'baseline-inputs.json'),
                  calibration_sha256=c.sha(root/'calibration.json'),
                  pilot_public_sha256=c.sha(pilot/'public.json'),
                  pilot_artifacts={'corpus.json':c.sha(pilot/'corpus.json')})
    c.seal(root/'protocol.json',protocol)
    c.seal((root if target=='calibration.json' else pilot)/target,{'tampered':True})
    with pytest.raises(ValueError,match=expected): analysis.analyze(root,pilot)
