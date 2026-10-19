"""Independent semantic checks for v4's new multiplier and algebra rewrites."""
import itertools
import math
import random

import numpy as np
import pytest

from isaforge.features import Expression, parse_formula
from isaforge.structural_features_v4 import (
    FEATURE_NAMES, RESOURCE_NAMES, RESOURCE_PRIOR,
    feature_dict, feature_matrix, normalize_formula, proven_zero_lut,
)

MASK = (1 << 32)-1
BOUNDARIES = (0, 1, 2, 3, 7, 31, 32, 1023, 2047, 0x7fffffff,
              0x80000000, 0x80000001, 0xfffffffe, MASK)


def independent_rv32(node: Expression, x: int, y: int) -> int:
    """Separate arithmetic oracle; no normalizer or production RTL evaluator."""
    if not node.children:
        return (node.value if isinstance(node.value, int) else x if node.value == 'in0' else y) & MASK
    operands = [independent_rv32(c, x, y) for c in node.children]
    a, b = operands[0], operands[1] if len(operands) > 1 else 0
    signed = lambda v: v if v < (1 << 31) else v-(1 << 32)
    op = node.value
    if op == 'lui': result = a
    elif op in ('add', 'addi'): result = a+b
    elif op == 'sub': result = a-b
    elif op in ('and', 'andi'): result = a & b
    elif op in ('or', 'ori'): result = a | b
    elif op in ('xor', 'xori'): result = a ^ b
    elif op in ('sll', 'slli'): result = a << (b % 32)
    elif op in ('srl', 'srli'): result = a >> (b % 32)
    elif op in ('sra', 'srai'): result = signed(a) >> (b % 32)
    elif op in ('slt', 'slti'): result = int(signed(a) < signed(b))
    elif op in ('sltu', 'sltiu'): result = int(a < b)
    elif op == 'mul': result = a*b
    elif op == 'mulh': result = (signed(a)*signed(b)) // (1 << 32)
    elif op == 'mulhu': result = (a*b) // (1 << 32)
    elif op == 'mulhsu': result = (signed(a)*b) // (1 << 32)
    else: raise AssertionError(op)
    return result & MASK


def assert_equivalent(formula, random_count=32):
    original = parse_formula(formula)
    normalized = normalize_formula(formula)
    replacement = parse_formula(normalized)
    assert normalize_formula(normalized) == normalized
    rng = random.Random(20261013)
    vectors = list(itertools.product(BOUNDARIES, repeat=2))
    vectors.extend((rng.getrandbits(32), rng.getrandbits(32)) for _ in range(random_count))
    for x, y in vectors:
        assert independent_rv32(original, x, y) == independent_rv32(replacement, x, y), (formula, normalized, x, y)


def test_stable_schema_and_formula_only_nonnegative_features():
    assert len(set(FEATURE_NAMES)) == len(FEATURE_NAMES)
    assert set(RESOURCE_NAMES) <= set(FEATURE_NAMES)
    assert len(RESOURCE_NAMES) == len(RESOURCE_PRIOR)
    formulas = ['mul(in0,in1)', 'mulh(in0,in1)', 'mulhsu(in0,in1)',
                'mul(andi(in0,2147483651),andi(in1,3221225477))',
                'srli(mulh(andi(in0,2047),-1),13)', 'xor(xor(in0,in1),in1)']
    for formula in formulas:
        values = feature_dict(formula)
        assert tuple(values) == FEATURE_NAMES
        assert all(isinstance(v, float) and math.isfinite(v) and v >= 0 for v in values.values())
        assert values == feature_dict(' '+formula.replace(',', ' , ')+' ')
    matrix = feature_matrix(iter(formulas))
    assert matrix.shape == (len(formulas), len(FEATURE_NAMES))
    np.testing.assert_array_equal(matrix[0], list(feature_dict(formulas[0]).values()))
    assert feature_matrix([]).shape == (0, len(FEATURE_NAMES))
    with pytest.raises(ValueError):
        feature_dict({'formula': 'mul(in0,in1)', 'lut4_count': 999})


@pytest.mark.parametrize('formula', [
    'srli(mul(andi(in1,1023),andi(in0,2147483648)),30)',
    'addi(mulh(xori(in0,3),-2047),13)',
    'srli(mulh(andi(in0,2047),-1),13)',
    'srli(mulhu(addi(in1,7),andi(in0,1)),30)',
    'xor(andi(xor(in1,in0),-1),in1)',
    'mul(andi(in0,3221225472),andi(in1,3221225472))',
    'xor(xori(in0,-1),xor(in1,xori(in0,7)))',
    'slli(slli(in0,17),17)', 'srli(srli(in0,31),1)',
    'srai(srai(in0,17),17)', 'slli(in0,32)',
])
def test_regressions_preserve_rv32_semantics(formula):
    assert_equivalent(formula)


def test_sparse_low_multiply_is_one_and_not_dense_partial_products():
    formula = 'srli(mul(andi(in1,1023),andi(in0,2147483648)),30)'
    result = feature_dict(formula)
    assert 'mul(' not in normalize_formula(formula)
    assert result['v3_logic_output_bits'] == 1
    assert result['v3_mul_variable_partial_products'] == 0
    assert result['v4_removed_multiply_ops'] == 1
    assert not proven_zero_lut(formula)
    root = parse_formula(normalize_formula(formula))
    for x, y in itertools.product(BOUNDARIES, repeat=2):
        assert independent_rv32(root, x, y) == (((x >> 31) & y & 1) << 1)


def test_sparse_support_positions_and_truncation_determine_partial_products():
    a, b = 0x80000003, 0xc0000005
    formula = f'mul(andi(in0,{a}),andi(in1,{b}))'
    expected = sum(i+j <= 31 for i in range(32) for j in range(32)
                   if a & (1 << i) and b & (1 << j))
    values = feature_dict(formula)
    assert values['v3_mul_variable_partial_products'] == expected == 8
    assert values['v4_mul_operand_support_holes'] > 40
    truncated = feature_dict(f'andi({formula},7)')
    assert truncated['v3_mul_variable_partial_products'] == 3
    assert feature_dict('mul(in0,in1)')['v3_mul_variable_partial_products'] == 528
    square = feature_dict('mul(in0,in0)')
    assert square['v3_mul_variable_partial_products'] < 528
    assert square['v4_mul_partial_product_gate_reuse'] > 0


def test_proved_zero_and_xor_wire_behavior_are_not_learned_gates():
    for formula in ['xor(andi(xor(in1,in0),-1),in1)',
                    'srli(mulhu(addi(in1,7),andi(in0,1)),30)',
                    'mul(andi(in0,3221225472),andi(in1,3221225472))']:
        assert proven_zero_lut(formula)
        values = feature_dict(formula)
        assert all(values[name] == 0 for name in RESOURCE_NAMES)
    for formula in ['xori(in0,-1)', 'sltu(0,in0)', 'mulh(in0,in1)']:
        assert not proven_zero_lut(formula)


@pytest.mark.parametrize('op', ['mul', 'mulh', 'mulhu', 'mulhsu'])
def test_signed_digit_rewrites_and_high_half_carries(op):
    # Both constant positions exercise asymmetric mulhsu signedness. Bit 32 in
    # the unsigned -1 digit representation exercises non-wrapping term shifts.
    constants = [0, 1, -1, 3, -3, 7, -7, 129, -129, 2047, -2047,
                 0x7fffffff, 0x80000000, 0x80000001, MASK]
    for constant in constants:
        for a, b in [('addi(in0,7)', str(constant)), (str(constant), 'xori(in1,3)')]:
            assert_equivalent(f'{op}({a},{b})', random_count=48)


def test_singleton_variable_products_for_every_bit_position():
    for bit in range(32):
        for mask in [MASK, 0x55555555, 0x80000003]:
            assert_equivalent(f'mul(andi(in0,{mask}),andi(in1,{1 << bit}))', random_count=8)


def test_composed_arithmetic_masks_and_sign_extension():
    rng = random.Random(414)
    operands = ['in0', 'in1', 'andi(in0,65535)', 'srai(slli(in1,16),16)',
                'addi(in0,-33)', 'xori(in1,1431655765)', 'andi(in0,2147483651)']
    constants = [-1, -2047, -129, 65535, 0x80000001, 0x7fffffff]
    for _ in range(90):
        op = rng.choice(['mul', 'mulh', 'mulhu', 'mulhsu'])
        a = rng.choice(operands)
        b = str(rng.choice(constants)) if rng.randrange(2) else rng.choice(operands)
        product = f'{op}({a},{b})'
        formula = rng.choice([f'andi({product},{rng.getrandbits(32)})',
                              f'srli({product},{rng.randrange(32)})',
                              f'xor(addi({product},7),in1)'])
        assert_equivalent(formula, random_count=16)
