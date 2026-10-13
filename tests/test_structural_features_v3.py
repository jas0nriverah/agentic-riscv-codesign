"""Tests for circuit distinctions and sound wire proofs, without fitted labels."""
import math

import numpy as np
import pytest

from isaforge.features import parse_formula
from isaforge.rtl import evaluate_formula
from isaforge.structural_features_v3 import (
    FEATURE_GROUPS, FEATURE_NAMES, RESOURCE_NAMES, RESOURCE_PRIOR,
    _BitCircuit, _add_bits, _barrel, _normalize, feature_dict, feature_matrix,
    proven_zero_lut,
)


def test_schema_is_stable_nonnegative_and_formula_only():
    assert len(FEATURE_NAMES) == len(set(FEATURE_NAMES))
    assert tuple(n for group in FEATURE_GROUPS.values() for n in group) == FEATURE_NAMES
    assert FEATURE_GROUPS['resources'] == RESOURCE_NAMES
    assert len(RESOURCE_NAMES) == len(RESOURCE_PRIOR)
    assert all(p > 0 for p in RESOURCE_PRIOR)
    formulas = ['add(in0,in1)', 'mul(srai(slli(in0,16),16),in1)',
                'sll(lui(-1),in0)', 'sltiu(in0,256)', 'andi(sra(in0,in1),1)']
    for formula in formulas:
        result = feature_dict(formula)
        assert tuple(result) == FEATURE_NAMES
        assert all(isinstance(v, float) and math.isfinite(v) and v >= 0 for v in result.values())
        assert result == feature_dict(' ' + formula.replace(',', ' , ') + ' ')
    matrix = feature_matrix(iter(formulas))
    assert matrix.shape == (len(formulas), len(FEATURE_NAMES))
    np.testing.assert_array_equal(matrix[0], list(feature_dict(formulas[0]).values()))
    assert feature_matrix([]).shape == (0, len(FEATURE_NAMES))
    with pytest.raises(ValueError): feature_dict({'formula': formulas[0], 'lut4_count': 99})


def test_sparse_adder_and_repeated_outputs_are_costed_by_carry_structure():
    full = feature_dict('add(in0,in1)')
    high = feature_dict('add(slli(in0,31),in1)')
    repeated = feature_dict('addi(srli(in0,31),-1)')
    truncated = feature_dict('andi(addi(in0,64),255)')
    assert full['v3_adder_sum_bits'] == 32
    assert high['v3_adder_sum_bits'] == 1
    assert repeated['v3_adder_sum_bits'] == 1
    assert repeated['v3_adder_output_token_reuse'] == 31
    assert truncated['v3_adder_sum_bits'] == 2
    assert high['v3_adder_carry_bits'] == 0  # Carry beyond bit 31 is discarded.
    assert full['v3_adder_carry_run_max'] == 31


def test_narrow_variable_shift_has_a_full_backward_mux_cone():
    narrow = feature_dict('andi(sra(in0,in1),1)')
    full = feature_dict('sra(in0,in1)')
    constant = feature_dict('sll(addi(0,1),in0)')
    assert narrow['v3_barrel_live_muxes'] == 31
    assert narrow['v3_barrel_live_stages'] == 5
    assert narrow['v3_barrel_source_bits'] == 32
    assert full['v3_barrel_live_muxes'] > narrow['v3_barrel_live_muxes']
    assert constant['v3_barrel_constant_data_count'] == 1
    assert constant['v3_barrel_live_muxes'] < full['v3_barrel_live_muxes']
    assert feature_dict('slli(in0,17)')['v3_barrel_live_muxes'] == 0


def test_comparator_constant_and_polarity_are_distinct_from_variable_comparison():
    variable = feature_dict('sltu(in0,in1)')
    constant = feature_dict('sltiu(in0,256)')
    complement = feature_dict('xori(sltiu(in0,256),1)')
    assert variable['v3_compare_variable_bits'] == 32
    assert constant['v3_compare_variable_bits'] == 0
    assert constant['v3_compare_constant_count'] == 1
    assert constant['v3_compare_constant_trailing_zeros'] == 8
    left_constant = feature_dict('sltu(0,in0)')
    assert left_constant['v3_compare_constant_inverted_bits'] == 32
    assert constant['v3_compare_constant_inverted_bits'] == 0
    assert complement['v3_compare_polarity_folds'] == 1
    assert complement['v3_logic_output_bits'] == 0
    assert not proven_zero_lut('xori(sltiu(in0,7),1)')


def test_multiplier_column_occupancy_tracks_width_and_truncation():
    full = feature_dict('mul(in0,in1)')
    narrow = feature_dict('mul(andi(in0,255),andi(in1,255))')
    truncated = feature_dict('andi(mul(in0,in1),255)')
    signed = feature_dict('mul(srai(slli(in0,16),16),in1)')
    high = feature_dict('mulhu(in0,in1)')
    assert full['v3_mul_variable_partial_products'] == 528
    assert narrow['v3_mul_variable_partial_products'] == 64
    assert truncated['v3_mul_variable_partial_products'] == 36
    assert signed['v3_mul_variable_partial_products'] == 392
    assert high['v3_mul_variable_partial_products'] == 1024
    assert high['v3_mul_high_half_count'] == 1
    assert narrow['v3_mul_peak_column_height'] == 8
    assert narrow['v3_mul_occupied_columns'] == 15
    assert full['v3_mul_compressor_bits'] > narrow['v3_mul_compressor_bits'] > 0


@pytest.mark.parametrize('formula', [
    'addi(addi(in0,-16),16)', 'sub(add(in0,in1),in1)',
    'add(sub(in0,in1),in1)', 'sub(addi(in0,-1),4294967295)',
    'add(sub(in0,in0),in1)', 'add(in0,in0)', 'srai(slli(in0,16),16)',
    'and(in0,in0)', 'xor(in0,in0)', 'mul(in0,8)',
    'mulhu(andi(in0,65535),andi(in1,65535))',
    'add(andi(in0,65535),slli(in1,16))',
])
def test_exact_algebraic_or_bit_wiring_proof(formula):
    assert proven_zero_lut(formula)
    result = feature_dict(formula)
    assert result['v3_proven_zero_lut'] == 1
    assert not any(result[name] for name in RESOURCE_NAMES)


def test_affine_cancellation_also_applies_to_identical_nontrivial_atoms():
    formula = 'sub(add(xor(in0,in1),slli(in0,4)),xor(in0,in1))'
    normalized = _normalize(parse_formula(formula))
    assert normalized.canonical() == 'slli(in0,4)'
    assert proven_zero_lut(formula)
    assert feature_dict(formula)['v3_normalized_node_reduction'] == 3


def test_normalization_preserves_rv32_semantics_and_does_not_prove_inversion_wiring():
    rng = np.random.default_rng(20261013)
    formulas = [
        'addi(addi(in0,-16),16)', 'sub(add(in0,in1),in1)',
        'sub(addi(in0,-1),4294967295)', 'addi(addi(in0,2147483647),1)',
        'sub(add(in0,in1),in0)', 'add(sub(in0,in1),in1)',
        'sub(add(xor(in0,in1),slli(in0,4)),xor(in0,in1))',
        'add(in0,in0)', 'srai(slli(in0,16),16)', 'mul(in0,8)',
        'sltiu(sltiu(in0,256),1)', 'sltu(0,sltiu(in0,256))',
        'sltiu(andi(in0,1),2)', 'sltu(1,andi(in0,1))',
    ]
    for formula in formulas:
        normalized = _normalize(parse_formula(formula))
        for a, b in rng.integers(0, 2**32, size=(80, 2), dtype=np.uint64):
            assert evaluate_formula(formula, int(a), int(b)) == evaluate_formula(normalized, int(a), int(b))
    for formula in ['xori(in0,-1)', 'sltiu(in0,1)', 'add(in0,in1)', 'mul(in0,in1)']:
        assert not proven_zero_lut(formula)


def _evaluate_bits(circuit, token, a, b):
    if isinstance(token, int): return token
    if token not in circuit.nodes:
        assert token[0] == 'input'
        return ((a if token[1] == 'in0' else b) >> token[2]) & 1
    kind, *args = circuit.nodes[token]
    vals = [_evaluate_bits(circuit, t, a, b) for t in args]
    if kind == 'not': return 1 - vals[0]
    if kind == 'xor': return vals[0] ^ vals[1]
    if kind == 'and': return vals[0] & vals[1]
    if kind == 'or': return vals[0] | vals[1]
    return vals[2] if vals[0] else vals[1]


def test_boolean_circuits_match_real_add_sub_and_barrel_semantics():
    from isaforge.area_model_v2 import _symbols
    a = _symbols(parse_formula('addi(in0,0)')); b = _symbols(parse_formula('addi(in1,0)'))
    circuits = []
    for op in ('add', 'sub'):
        c, outputs, _ = _add_bits(a, b, op == 'sub'); circuits.append((op, c, outputs))
    for op in ('sll', 'srl', 'sra'):
        c, outputs, _ = _barrel(a, b, op); circuits.append((op, c, outputs))
    rng = np.random.default_rng(20261013)
    for op, c, outputs in circuits:
        for x, y in rng.integers(0, 2**32, size=(8, 2), dtype=np.uint64):
            value = sum(_evaluate_bits(c, t, int(x), int(y)) << i for i, t in enumerate(outputs))
            assert value == evaluate_formula(f'{op}(in0,in1)', int(x), int(y))


def test_shared_dag_and_operator_composition_are_not_tree_counts():
    result = feature_dict('add(xor(in0,in1),xor(in0,in1))')
    assert result['v3_logic_output_bits'] == 31
    assert result['v3_shared_live_ops'] == 0  # Normalized x+x is a single shift.
    assert result['v3_edge_shift_logic'] == 1
    graph = feature_dict('xor(addi(in0,1),slli(addi(in0,1),4))')
    assert graph['v3_shared_live_ops'] == 1
    assert graph['v3_max_fanout'] == 2
    assert graph['v3_reconvergent_edges'] == 2
