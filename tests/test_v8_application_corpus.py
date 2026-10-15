"""Input-only corpus identity semantics; synthetic records, no target labels."""
from copy import deepcopy
import math
import numpy as np
import pytest
from isaforge import v8_application_corpus as corpus
from isaforge import area_model_v8 as v8


def record(formula,normalized=None,rewritten=None):
    return {'formula':formula,'normalized_formula':normalized or formula,
        'v7_combined_normalized_formula':rewritten or formula,'values':[0.]*455}


def candidate(formula='add(in0,in1)',trace=100):
    return {'formula':formula,'traceTotalInstructions':trace,'runs':4,'overlapSafeSaved':4,
        'occurrences':[{'blockStart':'0x10','pcs':['0x10','0x14'],'blockRuns':4,'size':2,'selectedForSavings':True}]}


def spec(name='fixture',family='family',trace=100,primary=True):
    return {'benchmark':name,'family':family,'primary_family':primary,'traceTotalInstructions':trace}


def test_program_memberships_are_retained_and_occurrences_not_reweighted():
    rows=corpus.application_rows([(spec('one'),[candidate()]),(spec('two'),[candidate()])])
    assert len(rows)==2 and rows[0]['formula']==rows[1]['formula']
    assert rows[0]['candidate_id']!=rows[1]['candidate_id']
    assert rows[0]['occurrences']==candidate()['occurrences'] and rows[0]['overlapSafeSaved']==4


def test_duplicate_canonical_formula_and_empty_pool_are_errors():
    with pytest.raises(ValueError,match='canonical formula'):
        corpus.application_rows([(spec(),[candidate(),candidate(' add( in0, in1 ) ')])])
    with pytest.raises(ValueError,match='coverage failure'):corpus.application_rows([(spec(),[])])


@pytest.mark.parametrize('mutation',[{'runs':True},{'runs':-1},{'overlapSafeSaved':101},{'traceTotalInstructions':99},{'occurrences':[]}])
def test_invalid_dynamic_candidate_evidence_is_rejected(mutation):
    row={**candidate(),**mutation}
    with pytest.raises(ValueError):corpus.application_rows([(spec(),[row])])


def test_vector_digest_uses_exact_finite_values_and_canonical_zero():
    assert corpus.vector_key([0.,-0.])==corpus.vector_key([-0.,0.])
    assert corpus.vector_key([0.])!=corpus.vector_key([0.,0.])
    assert corpus.vector_key([1.])!=corpus.vector_key([np.nextafter(1.,2.)])
    for value in (float('nan'),float('inf')):
        with pytest.raises(ValueError):corpus.vector_key([value])


def test_feature_collision_is_not_reported_as_verified_functional_identity():
    ledger=corpus.novelty_ledger([record('add(in0,in1)')],[record('sub(in0,in1)')])
    row=ledger['records'][0]
    assert row['matches']['mapping217_vector']==['add(in0,in1)']
    assert row['no_declared_identity_match'] is True and row['strict_no_declared_match'] is False
    assert ledger['primary_rows_removed']==0 and 'does not prove functional novelty' in ledger['scope']


def test_normalized_alias_and_skeleton_are_separate_channels():
    old=record('addi(in0,1)');fresh=record('addi(in0,2)',rewritten='addi(in0,1)')
    row=corpus.novelty_ledger([old],[fresh])['records'][0]
    assert row['matches']['canonical']==[]
    assert row['matches']['original_or_normalized']==['addi(in0,1)']
    assert row['no_declared_identity_match'] is False


def test_view_vector_channels_follow_explicit_indices():
    old=record('add(in0,in1)');fresh=record('sub(in0,in1)');fresh['values'][194]=1
    row=corpus.novelty_ledger([old],[fresh])['records'][0]
    assert row['matches']['mapping217_vector'] and row['matches']['legacy_rewritten336_vector']
    assert row['matches']['legacy_original336_vector']==[]


def test_duplicate_consumed_and_fresh_registries_rejected():
    row=record('add(in0,in1)')
    with pytest.raises(ValueError,match='canonical unique'):corpus.novelty_ledger([row,deepcopy(row)],[])
    with pytest.raises(ValueError,match='canonical unique'):corpus.novelty_ledger([],[row,deepcopy(row)])


def test_append_keeps_original_prefix_and_complete_semantic_proof():
    source={'formula':'sub(ori(in0,255),in0)','normalized_formula':'sub(ori(in0,255),in0)','values':[0.]*336}
    original=deepcopy(source);result=corpus.append_rewritten(source)
    assert source==original and result['values'][:336]==source['values'] and len(result['values'])==455
    assert result['v7_modes']['combined']['metadata']['certificate']['steps']
    assert result['v7_combined_normalized_formula']!=source['formula']


def test_trace_boolean_is_not_accepted_as_integer_one():
    with pytest.raises(ValueError):corpus.application_rows([(spec(trace=1),[candidate(trace=True)])])


def test_appended_record_cannot_mutate_cached_solver_or_input():
    source={'formula':'sub(ori(in0,255),in0)','normalized_formula':'sub(ori(in0,255),in0)','values':[0.]*336,'nested':{'identity':'original'}}
    observed=deepcopy(v8.semantic.solver_identity());first=corpus.append_rewritten(source)
    first['nested']['identity']='POISON';first['v7_modes']['combined']['metadata']['solver']['native_libraries_sha256'].clear()
    assert source['nested']['identity']=='original' and v8.semantic.solver_identity()==observed
    assert corpus.append_rewritten(source)['v7_modes']['combined']['metadata']['solver']['native_libraries_sha256']
