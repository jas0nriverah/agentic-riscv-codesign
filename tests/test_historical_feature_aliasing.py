"""Representation ambiguity and authenticated deterministic historical reporting."""
import copy
import json

import pytest

from isaforge.features import extract_features
from scripts.report_historical_feature_aliasing import (
    analyze, artifacts, authenticate, compare, encoded, ordered_ast_paths, sha)


def row(identity, formula, area):
    return dict(candidate_id=identity, workload_group='fixture', formula=formula,
        **extract_features(dict(formula=formula, size=3, runs=10, places=1,
                                saved=20, savedPercent=1.0)),
        status='success', correctness_verified=True, device_fits=True,
        area_delta_lut4=area, routed_fmax_min_mhz=65.0)


def test_operator_order_collision_is_visible_and_public_ast_separates_it():
    rows = [row('shift_input', 'add(in0,slli(in1,2))', 70),
            row('shift_result', 'slli(add(in0,in1),2)', 40)]
    result = compare(rows)
    assert result['feasibility_structural_numeric']['mixed_feasibility_groups'] == 1
    assert result['feasibility_structural_numeric']['opposite_label_pairs'] == 1
    assert result['proposed_structural_plus_ordered_ast']['unique_vectors'] == 2
    assert result['proposed_structural_plus_ordered_ast']['mixed_feasibility_groups'] == 0
    # Outcomes cannot influence the representation, even when labels are reversed.
    changed = copy.deepcopy(rows)
    changed[0]['area_delta_lut4'], changed[1]['area_delta_lut4'] = 40, 70
    other = compare(changed)
    assert (other['feasibility_structural_numeric']['mixed_groups'][0]['descriptor_sha256'] ==
            result['feasibility_structural_numeric']['mixed_groups'][0]['descriptor_sha256'])


def test_operand_position_and_immediate_are_explicit_and_outcome_free():
    left = ordered_ast_paths('xor(in0,srli(in1,8))')
    right = ordered_ast_paths('xor(srli(in0,8),in1)')
    assert left != right
    assert ordered_ast_paths('xor(in0,srli(in1,8))') != ordered_ast_paths('xor(in0,srli(in1,7))')
    immediate = next(item for item in left if item['kind'] == 'constant')
    assert immediate == dict(path=[1, 1], parent_operator='srli',
                             operand_position=1, kind='constant', value=8)
    assert left == ordered_ast_paths(' xor( in0, srli(in1, 8) ) ')


def test_unknown_outcomes_cannot_become_false_feasibility_labels():
    unknown = row('a', 'add(in0,slli(in1,2))', 70)
    unknown['status'] = 'failed'
    with pytest.raises(ValueError, match='Only known'):
        compare([unknown])


def test_authentication_rejects_member_tampering_and_path_escape(tmp_path):
    (tmp_path / 'corpus.json').write_bytes(b'{}\n')
    manifest = tmp_path / 'manifest.json'
    manifest.write_bytes(encoded({'corpus.json': sha(tmp_path / 'corpus.json')}))
    expected = sha(manifest)
    (tmp_path / 'manifest.json.sha256').write_text(expected + '\n')
    authenticate(tmp_path, expected)
    (tmp_path / 'corpus.json').write_bytes(b'{"changed":true}\n')
    with pytest.raises(ValueError, match='member hash mismatch'):
        authenticate(tmp_path, expected)
    manifest.write_bytes(encoded({'../outside.json': 'a' * 64}))
    expected = sha(manifest)
    (tmp_path / 'manifest.json.sha256').write_text(expected + '\n')
    with pytest.raises(ValueError, match='Invalid historical manifest member'):
        authenticate(tmp_path, expected)


def test_historical_result_and_artifacts_are_exact_under_row_permutation():
    summary = analyze()
    structural = summary['descriptors']['feasibility_structural_numeric']
    proposed = summary['descriptors']['proposed_structural_plus_ordered_ast']
    assert summary['successful_historical_rows'] == 122
    assert structural['unique_vectors'] == 108
    assert structural['mixed_feasibility_groups'] == 2
    assert structural['mixed_feasibility_rows'] == 8
    assert structural['opposite_label_pairs'] == 6
    assert proposed['mixed_feasibility_groups'] == 0
    assert artifacts(summary) == artifacts(json.loads(encoded(summary)))
    rows = [row('b', 'add(in0,slli(in1,2))', 70),
            row('a', 'slli(add(in0,in1),2)', 40)]
    assert compare(rows) == compare(list(reversed(rows)))
