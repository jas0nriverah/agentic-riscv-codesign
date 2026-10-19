"""Input grouping, cross-cohort leakage protection and acquisition reproducibility."""
from collections import Counter

import pytest

from isaforge.v5_corpus import (DEVELOPMENT_SEED, TEST_SEED, equivalence_key,
    generate, group_components, repair_test_inputs, seal_inputs, signatures)


def row(formula, scope='known_families'):
    return {'formula': formula, 'evaluation_scope': scope}


def record(formula, values):
    return {'formula': formula, 'values': values}


def test_transitive_components_join_vectors_normalization_and_verified_proof():
    a = 'add(in0,in1)'
    b = 'add(in1,in0)'
    c = 'sub(in0,in1)'
    d = 'add(in0,sub(0,in1))'
    proof = {'formula_a': c, 'formula_b': d, 'status': 'proved',
             'method': 'algebraic_identity', 'evidence_sha256': 'a' * 64}
    # c and d are a modulo-2^32 algebraic identity. Proof evidence is supplied
    # by the caller; this layer validates its provenance shape.
    components = group_components([row(a), row(b), row(c), row(d)],
        [record(a, [1, 2]), record(c, [1, 2])], [proof])
    assert len(set(components.values())) == 1
    assert components == group_components([row(d), row(c), row(b), row(a)],
        [record(c, [1, 2]), record(a, [1, 2])], [proof])


def test_sampled_agreement_does_not_qualify_as_proof():
    a, b = 'add(in0,in1)', 'sub(in0,in1)'
    with pytest.raises(ValueError, match='samples are insufficient'):
        group_components([row(a), row(b)], verified_equivalences=[{
            'formula_a': a, 'formula_b': b, 'status': 'sampled',
            'method': 'oracle_fingerprint', 'evidence_sha256': 'a' * 64}])


def test_skeleton_partitions_remain_explicit_and_can_be_joined_for_validation():
    a, b = 'addi(in0,3)', 'addi(in1,7)'
    assert signatures(a)['original_skeleton'] == signatures(b)['original_skeleton']
    assert len(set(group_components([row(a), row(b)]).values())) == 2
    assert len(set(group_components([row(a), row(b)], include_skeletons=True).values())) == 1
    assert equivalence_key('and(in0,in1)') == equivalence_key('and(in1,in0)')
    assert equivalence_key('mulhsu(in0,in1)') != equivalence_key('mulhsu(in1,in0)')


@pytest.mark.parametrize('features', [[True], [float('nan')], [], ['1']])
def test_component_features_must_be_complete_numeric_vectors(features):
    with pytest.raises(ValueError, match='Features require'):
        group_components([row('add(in0,in1)')], [record('add(in0,in1)', features)])


def test_sealing_rejects_exact_features_and_normalized_identity():
    a, b = 'add(in0,in1)', 'sub(in0,in1)'
    with pytest.raises(ValueError, match='Strong-component'):
        seal_inputs([row(a)], [row(b)], [record(a, [1])], [record(b, [1])])
    with pytest.raises(ValueError, match='Strong-component'):
        seal_inputs([row(a)], [row('add(in1,in0)')], [record(a, [1])], [record('add(in1,in0)', [2])])
    with pytest.raises(ValueError, match='complete unique feature'):
        seal_inputs([row(a)], [row(b)], [], [record(b, [1])])
    seal = seal_inputs([row(a)], [row(b)], [record(a, [1])], [record(b, [2])])
    assert seal['cross_cohort_component_count'] == 0
    assert seal['status'] == 'sealed'


def test_sealing_rejects_seen_skeleton_in_unseen_scope():
    a, b = 'addi(in0,3)', 'addi(in1,7)'
    with pytest.raises(ValueError, match='development-seen skeleton'):
        seal_inputs([row(a)], [row(b, 'unseen_compositions')], [record(a, [1])], [record(b, [2])])


def test_current_extractor_normalization_is_sealed_in_addition_to_v4():
    a, b = 'add(in0,in1)', 'sub(in0,in1)'
    fa = {**record(a, [1]), 'normalized_formula': 'xor(in0,in1)'}
    fb = {**record(b, [2]), 'normalized_formula': 'xor(in0,in1)'}
    with pytest.raises(ValueError, match='Strong-component'):
        seal_inputs([row(a)], [row(b)], [fa], [fb])
    fb['normalized_formula'] = 'xor(in0,addi(in1,7))'
    fa['normalized_formula'] = 'xor(in1,addi(in0,3))'
    with pytest.raises(ValueError, match='current-normalizer development-seen skeleton'):
        seal_inputs([row(a)], [row(b, 'unseen_compositions')], [fa], [fb])


def test_generated_pools_are_deterministic_balanced_and_unlabelled():
    old = {'add(in0,in1)', 'xor(in0,in1)'}
    development = generate(old, 64, DEVELOPMENT_SEED, 'development')
    assert development == generate(old, 64, DEVELOPMENT_SEED, 'development')
    excluded = old | {r['formula'] for r in development}
    test = generate(excluded, 32, TEST_SEED, 'test')
    assert len({r['formula'] for r in development + test}) == 96
    assert Counter(r['evaluation_scope'] for r in test) == {
        'known_families': 16, 'unseen_compositions': 16}
    assert set(Counter(r['stratum'] for r in test).values()) == {4}
    assert not {equivalence_key(f) for f in excluded} & {r['equivalence_key'] for r in test}
    original = {signatures(f)['original_skeleton'] for f in excluded}
    normalized = {signatures(f)['normalized_skeleton'] for f in excluded}
    for r in test:
        if r['evaluation_scope'] == 'unseen_compositions':
            assert r['original_skeleton'] not in original
            assert r['normalized_skeleton'] not in normalized
        assert not {'lut4_count', 'carry_count', 'predicted_lut4', 'correctness_verified'} & r.keys()


def test_complete_known_multiplication_pool_covers_all_regimes_and_variants():
    rows = generate({'add(in0,in1)'}, 256, TEST_SEED, 'test')
    mul = [r for r in rows if r['stratum'] == 'multiplication' and r['evaluation_scope'] == 'known_families']
    assert len(mul) == 16
    assert set(Counter(r['operand_regime'] for r in mul).values()) == {2}
    assert len(Counter(r['operand_regime'] for r in mul)) == 8
    assert Counter(r['multiply_variant'] for r in mul) == dict.fromkeys(('mul', 'mulh', 'mulhu', 'mulhsu'), 4)


@pytest.mark.parametrize('count', [0, 15, 31, True, 32.0])
def test_reject_invalid_pool_size(count):
    with pytest.raises(ValueError):
        generate(set(), count, TEST_SEED, 'test')


@pytest.mark.parametrize('marker', ['freeze.json', 'training-start.json',
                                  'label-release.json', 'corpus/test/dataset.json'])
def test_input_repair_is_forbidden_after_fitting_release_or_test_labels(tmp_path, marker):
    path = tmp_path / marker
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{}')
    with pytest.raises(ValueError, match='only before fitting'):
        repair_test_inputs(tmp_path, tmp_path/'cache')


@pytest.mark.parametrize('attempts', [0, 9, True])
def test_input_repair_cannot_expand_declared_retry_budget(tmp_path, attempts):
    with pytest.raises(ValueError, match='between one and eight'):
        repair_test_inputs(tmp_path, tmp_path/'cache', max_attempts=attempts)
