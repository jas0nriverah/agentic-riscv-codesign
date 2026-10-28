"""Local retrieval and leakage tests; no claimed LLM quality measurements."""
import copy
import json
import pytest
from isaforge.agent_memory import MODES, HistoricalMemory, MemoryAugmentedPolicy
from isaforge.bounded_selector import MatchedBaselinePolicy, ReplaySelectionSession, run_selector
from test_budgeted_selection import history, measured, predictions, public


def memory():
    return HistoricalMemory(history(), target_groups={'target'}, target_formulas={'sub(in0,in1)'})


@pytest.mark.parametrize('mode', ['lexical', 'semantic', 'hybrid'])
def test_retrieval_is_repeatable_and_source_linked(mode):
    m = memory()
    hits = m.search('xor slli', mode)
    assert hits and hits == memory().search('xor slli', mode)
    assert all(h['record']['candidate_id'] in m.ids and len(h['record_sha256']) == 64 for h in hits)
    hits[0]['record']['formula'] = 'mutated'
    assert 'mutated' not in json.dumps(m.records)


def test_target_exclusion_before_fit():
    rows = history(); rows[0]['workload_group'] = 'target'
    with pytest.raises(ValueError, match='contaminated'):
        HistoricalMemory(rows, target_groups={'target'}, target_formulas=set())
    with pytest.raises(ValueError, match='contaminated'):
        HistoricalMemory(history(), target_groups=set(), target_formulas={history()[0]['formula']})


def test_no_unknown_query_matches_or_singleton_fake_semantics():
    assert memory().search('zzzzneverobserved', 'hybrid') == []
    m = HistoricalMemory(history()[:1], target_groups=set(), target_formulas=set())
    assert m.search('xor', 'semantic') == []
    assert m.search('xor', 'lexical')


def test_no_retrieval_and_empty_history():
    assert memory().search('xor', 'none') == []
    assert HistoricalMemory([], target_groups=set(), target_formulas=set()).search('xor') == []


def test_knowledge_graph_retrieval_returns_typed_source_paths():
    m = memory()
    hits = m.search_graph(['add(in0,slli(in1,1))'], target_groups={'target'}, k=3)
    assert hits and all(hit['record']['workload_group'] != 'target' for hit in hits)
    assert hits[0]['matched_operators'] == ['slli']
    predicates = {edge['predicate'] for edge in hits[0]['evidence_triples']}
    assert {'uses_operator', 'measured_on', 'has_measurement'} <= predicates
    assert len(hits[0]['record_sha256']) == 64
    assert m.graph.manifest['schema'] == 'isaforge-candidate-evidence-graph-v1'
    assert m.graph.manifest['graph_sha256'] == memory().graph.manifest['graph_sha256']


def test_knowledge_graph_rejects_related_formula_family_before_retrieval():
    related = 'xor(in1,slli(in0,1))'
    with pytest.raises(ValueError, match='contaminated'):
        HistoricalMemory(history(), target_groups=set(), target_formulas={related})


def test_knowledge_graph_empty_roster_has_no_hits():
    assert memory().search_graph([], target_groups={'target'}) == []
    with pytest.raises(ValueError, match='bounded k'):
        memory().search_graph([], target_groups={'target'}, k=0)


@pytest.mark.parametrize('mode', MODES)
def test_memory_policy_finalizes_after_all_candidates_are_attempted(tmp_path, mode):
    target = [public('t1')]
    training = history()
    session = ReplaySelectionSession(target, training, predictions(training, target, 0),
        lambda row: measured(row), area_cap=64, budget=1,
        ledger_path=tmp_path/'ledger.json')
    policy = MemoryAugmentedPolicy(MatchedBaselinePolicy('merit'), mode=mode)
    result = run_selector(session, policy)

    assert result['status'] == 'finalized'
    assert result['selected_id'] == 't1'
    assert result['charged_attempts'] == 1
    assert result['model_calls'] == 2
    assert all(event['status'] == 'complete' for event in result['model_events'])
    if mode == 'knowledge_graph':
        trace = result['model_events'][-1]['memory_trace']
        assert trace['graph_query_formulas'] == []
        assert trace['hits'] == trace['returned_ids'] == []


@pytest.mark.parametrize('mode', MODES)
@pytest.mark.parametrize('changed_field,changed_value', [
    ('benchmark', 'old1:ctx'),
    ('formula', 'xor(in1,slli(in0,7))'),
])
def test_memory_policy_rejects_changed_target_split_even_when_attempted(
        mode, changed_field, changed_value):
    class InspectingPolicy:
        identity = dict(provider='test-only')

        def __init__(self):
            self.requests = []

        def choose(self, request):
            self.requests.append(request)
            return dict(tool='finalize', arguments=dict(candidate_id=None))

    wrapped = InspectingPolicy()
    policy = MemoryAugmentedPolicy(wrapped, mode=mode)
    request = dict(historical_measurements=history(),
        candidates=[public('t1'), public('t2', 'sub(in0,in1)')],
        attempted_candidate_ids=[])
    original = copy.deepcopy(request)
    policy.choose(request)
    # Candidate order is immaterial; paid attempts may change between calls.
    request['candidates'].reverse()
    request['attempted_candidate_ids'] = ['t1', 't2']
    policy.choose(request)
    assert original['candidates'][0] == request['candidates'][1]
    request['candidates'][0][changed_field] = changed_value
    with pytest.raises(ValueError, match='target candidate roster changed'):
        policy.choose(request)
    assert len(wrapped.requests) == 2
    assert policy.last_memory_trace == {}
