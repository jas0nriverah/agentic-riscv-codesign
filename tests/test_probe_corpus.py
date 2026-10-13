import hashlib
import json

import pytest

from isaforge.probe_corpus import (STRATA, collect_probe, excluded_formulas, formula_shape,
                                   freeze_candidates, generate_candidates)


def test_novel_deterministic_balanced_graph_acquisition():
    first = generate_candidates(set())
    excluded = {r['formula'] for r in first[:30]}
    rows = generate_candidates(excluded)
    assert rows == generate_candidates(excluded)
    assert len(rows) == len({r['formula'] for r in rows}) == 192
    assert not excluded.intersection(r['formula'] for r in rows)
    assert {s: sum(r['stratum'] == s for r in rows) for s in STRATA} == dict.fromkeys(STRATA, 24)
    assert all(2 <= formula_shape(r['formula'])[0] <= 4 and 1 <= formula_shape(r['formula'])[1] <= 2 for r in rows)
    assert not any('lut4_count' in r or 'predicted_lut4' in r for r in rows)
    assert rows != generate_candidates(excluded, seed=42)


def test_shared_diamond_counts_nodes_instead_of_tree_occurrences():
    assert formula_shape('add(andi(xor(in0,in1),255),srli(xor(in0,in1),3))') == (4, 2)


def test_canonical_duplicate_exclusion_ignores_whitespace(tmp_path):
    path = tmp_path / 'old.json'
    path.write_text(json.dumps([{'formula': ' add ( in0 , in1 ) ', 'lut4_count': 123},
                               {'formula': 'add(in0,in1)', 'lut4_count': 999}]))
    assert excluded_formulas([path]) == {'add(in0,in1)'}


def test_freeze_resumes_exactly_and_rejects_tampering(tmp_path):
    excluded = tmp_path / 'old.json'
    excluded.write_text(json.dumps([{'formula': 'add(in0,in1)', 'lut4_count': 123}]))
    output = tmp_path / 'probe'
    candidates, frozen = freeze_candidates([excluded], output, count=16, expected_excluded_count=1)
    assert freeze_candidates([excluded], output, count=16, expected_excluded_count=1) == (candidates, frozen)
    assert hashlib.sha256((output / 'candidates.json').read_bytes()).hexdigest() == frozen['candidate_sha256']
    assert not (output / 'dataset.json').exists()
    with pytest.raises(ValueError, match='changed'):
        freeze_candidates([excluded], output, count=16, seed=99)
    (output / 'candidates.json').write_text('[]')
    with pytest.raises(ValueError, match='changed'):
        freeze_candidates([excluded], output, count=16)


def test_exclusion_union_size_is_a_freeze_precondition(tmp_path):
    path = tmp_path / 'old.json'
    path.write_text('[{"formula":"add(in0,in1)"}]')
    with pytest.raises(ValueError, match='union'):
        freeze_candidates([path], tmp_path / 'probe', expected_excluded_count=713)
    assert not (tmp_path / 'probe').exists()


def test_mutated_in_memory_pool_rejected_before_measurement(tmp_path):
    path = tmp_path / 'old.json'
    path.write_text('[{"formula":"add(in0,in1)"}]')
    output = tmp_path / 'probe'
    candidates, frozen = freeze_candidates([path], output, count=16)
    candidates[0]['formula'] = 'mul(in0,in1)'
    with pytest.raises(ValueError, match='integrity'):
        collect_probe(candidates, frozen, output)
    assert not (output / 'verification').exists()


@pytest.mark.parametrize('count', [True, 0, 7, 193, -8])
def test_invalid_counts_rejected(count):
    with pytest.raises(ValueError):
        generate_candidates(set(), count=count)
