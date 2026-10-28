"""Local retrieval and leakage tests; no claimed LLM quality measurements."""
import copy
import json
import pytest
from isaforge.agent_memory import HistoricalMemory, MemoryAugmentedPolicy
from test_budgeted_selection import history


def memory():
    return HistoricalMemory(history(), target_groups={'target'}, target_formulas={'different'})


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
