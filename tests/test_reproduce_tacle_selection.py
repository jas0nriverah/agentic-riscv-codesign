"""No numeric or policy change is permitted by the JSON proof amendment."""
import copy

import pytest

from isaforge import codesign as c
from scripts import reproduce_tacle_selection as adapter


def proof():
    return dict(event=dict(score=(.123,1.004),candidate_id='candidate',charged_before_query=0,
        hardware_predictions=[dict(mean=31.25,std=.2)],paid_target_ids_before_query=[]),
        policy='hybrid_gp_adapt_count_semantic',training_ids=['history'],model_state_sha256='state')


def test_canonical_proof_changes_exactly_tuple_representation(tmp_path):
    original = proof(); saved = copy.deepcopy(original)
    c.seal(tmp_path/'proof.json',original)
    decoded = c.unseal(tmp_path/'proof.json')
    assert original != decoded
    assert adapter.canonical_proof(original) == decoded
    assert c.digest(original) == c.digest(decoded)
    assert original == saved and isinstance(original['event']['score'],tuple)
    decoded['event']['score'][0] += 1e-8
    assert c.digest(original) != c.digest(decoded)


@pytest.mark.parametrize('score',[(1.,),('bad',2.),(True,1.),(float('nan'),2.)])
def test_invalid_scores_are_not_sanitized(score):
    item = proof(); item['event']['score'] = score
    with pytest.raises(ValueError):
        adapter.canonical_proof(item)


def test_scope_normalizes_callback_and_result_without_changing_policy(monkeypatch):
    calls = []
    def original(case,provider,*,policy,seed,area_cap,on_acquire):
        calls.append((case,policy,seed,area_cap))
        on_acquire(proof())
        return dict(acquisition_proofs=[proof()],curve=[{'best_speedup':1.01}],events=[{'score':(.123,1.004)}])
    monkeypatch.setattr(adapter.frozen,'count_search',original)
    observed = []
    with adapter.normalized_proofs():
        result = adapter.frozen.count_search('case',lambda row:None,policy='fixed',seed=0,area_cap=64,on_acquire=observed.append)
        assert isinstance(observed[0]['event']['score'],list)
        assert result['acquisition_proofs'] == observed
        assert isinstance(result['events'][0]['score'],tuple)
        assert result['curve'] == [{'best_speedup':1.01}]
    assert adapter.frozen.count_search is original
    assert calls == [('case','fixed',0,64)]


def test_nested_scope_restores_frozen_function_after_exception(monkeypatch):
    original = object()
    monkeypatch.setattr(adapter.frozen,'count_search',original)
    with pytest.raises(RuntimeError):
        with adapter.normalized_proofs():
            outer = adapter.frozen.count_search
            with adapter.normalized_proofs():
                assert adapter.frozen.count_search is not outer
            assert adapter.frozen.count_search is outer
            raise RuntimeError('restore')
    assert adapter.frozen.count_search is original
