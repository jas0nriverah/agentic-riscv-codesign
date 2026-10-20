"""Synthetic contract fixtures only; these are not experimental observations."""
import copy

import pytest

from isaforge import codesign as c
from isaforge import speedup_corpus as corpus


def sample(workload, formula, processor='processor'):
    identity={'workload':workload,'processor_id':processor,'formula':formula,'implementation_sha256':'fixture'}
    return {**dict.fromkeys(c.FEATURE_COLUMNS,0),'candidate_id':c.digest(identity),
            'sample_identity':identity,'workload':workload,'workload_group':workload,
            'benchmark':workload+':fixture-input','formula':formula,'candidate_family':corpus.family(formula),
            'processor_id':processor,'label_kind':corpus.LABEL_KIND,'measurement_source':'synthesis_estimate',
            'baseline_cycles':100,'candidate_cycles':80,'baseline_period_ns':10,'candidate_period_ns':10,
            'speedup':1.25,'area':10,'area_cap':20,'measurement_seconds':1,
            'correctness_verified':True,'custom_execution_count':100,'timing_feasible':True}


def test_a_single_workload_cannot_claim_generalization(tmp_path):
    rows=[sample('crc32','andi(xor(in0,in1),255)'),sample('crc32','slli(in0,2)')]
    assert not corpus.readiness(rows)['cross_workload_ready']
    with pytest.raises(ValueError,match='at least three'):
        corpus.evaluate(rows,tmp_path/'evaluation')
    assert not (tmp_path/'evaluation').exists()


def test_identity_config_and_measured_label_boundaries():
    rows=[sample('a','addi(in0,1)'),sample('b','xor(in0,in1)')]
    corpus.validate(rows)
    for key,value in [('label_kind','synthetic'),('speedup',999),('correctness_verified',False),
                      ('custom_execution_count',0),('processor_id','other'),('candidate_family','unrelated')]:
        bad=copy.deepcopy(rows);bad[1][key]=value
        with pytest.raises(ValueError):corpus.validate(bad)
    with pytest.raises(ValueError,match='unique'):corpus.validate(rows+rows)


def test_holdout_excludes_entire_workload_family_and_related_candidate_shapes():
    rows=[sample('crc-a','andi(xor(in0,in1),255)'),sample('crc-b','add(in0,in1)'),
          sample('different','andi(xor(in1,in0),127)'),sample('different','sub(in0,in1)')]
    rows[0]['workload_group']=rows[1]['workload_group']='crc-source-family'
    train,test,excluded=corpus.split(rows,'crc-source-family')
    assert [r['workload'] for r in test]==['crc-a','crc-b']
    assert [r['formula'] for r in train]==['sub(in0,in1)']
    assert excluded==[rows[2]['candidate_id']]


@pytest.mark.parametrize('word',['02000033','0001','0000202f','00000053','0200100b','c8002073'])
def test_isa_gate_rejects_incompatible_libraries_extensions_and_custom_forms(word):
    with pytest.raises(ValueError):corpus.validate_isa(f'  0: {word} instruction\n')


def test_isa_gate_accepts_base_counter_and_declared_custom_instruction():
    result=corpus.validate_isa('0: 00000013 nop\n4: c0002573 rdcycle\n8: 0200000b custom\n')
    assert result['instruction_words_checked']==3 and result['custom_static_sites']==1


def test_next_cohort_acquisition_breaks_equal_upper_scores_by_predicted_mean(monkeypatch):
    rows=[sample('a','addi(in0,1)'),sample('a','xor(in0,in1)')]
    tools=corpus.TransferTools(rows,lambda r:r,1,20,0,[])
    def predictions(ids):
        return [dict(candidate_id=i,upper=2,mean=1.5 if i==rows[1]['candidate_id'] else 1.1) for i in ids]
    monkeypatch.setattr(tools,'predict',predictions)
    result=corpus.run_transfer_policy(tools,'active_learning')
    assert result['measured_candidate_ids']==[rows[1]['candidate_id']]


def test_cross_workload_evaluation_freezes_feature_only_predictions_and_charges_queries(tmp_path,monkeypatch):
    rows=[sample('a','addi(in0,1)'),sample('a','xor(in0,in1)'),
          sample('b','slli(in0,1)'),sample('b','sub(in0,in1)'),
          sample('c','andi(in0,255)'),sample('c','or(in0,in1)')]
    calls=[]
    class Model:
        warnings=['test fixture, no trained-model evidence']
        def __init__(self,seed):pass
        def fit(self,training):self.ids={r['candidate_id'] for r in training};return self
        def predict(self,data):
            assert not self.ids & {r['candidate_id'] for r in data}
            assert all(set(r)=={'candidate_id','benchmark','formula',*c.FEATURE_COLUMNS} for r in data)
            calls.append(len(self.ids))
            return [dict(candidate_id=r['candidate_id'],mean=1.1,lower=1.0,upper=1.2,std=.1) for r in data]
    monkeypatch.setattr(corpus,'SpeedupPredictor',Model)
    result=corpus.evaluate(rows,tmp_path/'evaluation',seeds=(0,),budgets=(1,))
    assert len(result['folds'])==3 and all(n==4 for n in calls)
    assert len(list((tmp_path/'evaluation').glob('*-predictions.json')))==3
    assert all(row['measurements_used']==1 for fold in result['folds'] for row in fold['selection_with_paid_target_adaptation'])
