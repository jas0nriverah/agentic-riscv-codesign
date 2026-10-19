"""V5 range soundness, multiplier identities and independent bit-vector proofs."""
import itertools
import json
import random
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

from isaforge.features import Expression, parse_formula
from isaforge.rtl import generate_rtl
from isaforge.structural_features_v5 import (
    FEATURE_NAMES, feature_dict, feature_matrix, normalize_formula,
    proven_zero_lut, rewrite_metadata, unsigned_ranges,
)

MASK = (1 << 32)-1
BOUNDARIES = (0, 1, 2, 3, 127, 128, 129, 0x7fffffff, 0x80000000, MASK)


def oracle(node: Expression, x: int, y: int) -> int:
    """Independent arithmetic oracle; does not import production evaluation."""
    if not node.children:
        return (node.value if isinstance(node.value, int) else x if node.value == 'in0' else y) & MASK
    operands = [oracle(child, x, y) for child in node.children]
    a, b = operands[0], operands[1] if len(operands) > 1 else 0
    signed = lambda value: value if value < (1 << 31) else value-(1 << 32)
    op = node.value
    if op == 'lui': value = a
    elif op in ('add', 'addi'): value = a+b
    elif op == 'sub': value = a-b
    elif op in ('and', 'andi'): value = a & b
    elif op in ('or', 'ori'): value = a | b
    elif op in ('xor', 'xori'): value = a ^ b
    elif op in ('sll', 'slli'): value = a << (b & 31)
    elif op in ('srl', 'srli'): value = a >> (b & 31)
    elif op in ('sra', 'srai'): value = signed(a) >> (b & 31)
    elif op in ('slt', 'slti'): value = int(signed(a) < signed(b))
    elif op in ('sltu', 'sltiu'): value = int(a < b)
    elif op == 'mul': value = a*b
    elif op == 'mulh': value = (signed(a)*signed(b)) // (1 << 32)
    elif op == 'mulhu': value = (a*b) // (1 << 32)
    elif op == 'mulhsu': value = (signed(a)*b) // (1 << 32)
    else: raise AssertionError(op)
    return value & MASK


def assert_sound(formula, random_count=32):
    original = parse_formula(formula)
    normalized = normalize_formula(formula)
    replacement = parse_formula(normalized)
    assert normalize_formula(normalized) == normalized
    rng = random.Random(20261015)
    pairs = list(itertools.product(BOUNDARIES, repeat=2))
    pairs.extend((rng.getrandbits(32), rng.getrandbits(32)) for _ in range(random_count))
    ranges = unsigned_ranges(original)
    assert ranges and all(0 <= low <= high <= MASK for low, high in ranges)
    for x, y in pairs:
        value = oracle(original, x, y)
        assert value == oracle(replacement, x, y), (formula, normalized, x, y)
        assert any(low <= value <= high for low, high in ranges), (formula, value, ranges)


def generated_formulas():
    """New development variants covering families rather than observed literals."""
    formulas = []
    for width in (1, 2, 7, 16, 31, 32):
        for control in ('srai(in0,31)', 'srai(addi(in0,37),31)', 'srai(xori(in0,-1),31)'):
            a = f'andi(in1,{(1 << width)-1})'
            formulas.extend((f'mul({a},{control})', f'mul({control},{a})'))
    for op, mask, constant, distance in itertools.product(
            ('mulh', 'mulhu', 'mulhsu'), (3, 127, 1023, 65535),
            (-1, -17, 5, 257, 2147483647), (1, 7, 16, 31)):
        formulas.append(f'srli({op}(andi(in1,{mask}),{constant}),{distance})')
    for high_bit, shift in itertools.product((1, 3, 7, 15, 30), (1, 8, 16, 31)):
        mask = (1 << high_bit) | 1
        a, b = f'andi(in1,{mask})', f'srai(in0,{shift})'
        for op in ('mulhu', 'mulhsu'):
            formulas.extend((f'{op}({a},{b})', f'srli({op}({a},{b}),{high_bit})'))
    formulas.extend((
        'srli(mulhsu(andi(in1,129),srai(in0,16)),7)',
        'srli(mulhsu(andi(in1,128),srai(in0,16)),7)',
        'srli(mulhsu(andi(in1,511),-129),31)',
        'mulhsu(srai(in0,31),andi(in1,255))',  # Asymmetric signedness.
        'mulhsu(andi(in1,2147483649),srai(in0,31))',  # Negative first operand.
        'srai(mulh(andi(in0,255),-17),31)',
        'srli(mulhu(andi(in0,65535),-1),16)',
        'srli(mulhu(andi(in0,65535),srai(in1,1)),3)',  # Bound condition fails.
        'srli(mulhu(andi(in0,131073),srai(in1,16)),17)',  # Off by one beyond bound.
        'addi(andi(in0,3),-2)', 'sub(andi(in0,7),andi(in1,15))',
        'mul(andi(in0,7),srai(in1,31))',
    ))
    return sorted(set(formulas))


def test_schema_preserves_original_multiplier_information():
    formula = 'xori(mul(xori(in0,17),1073741823),2147483647)'
    values = feature_dict(formula)
    assert tuple(values) == FEATURE_NAMES
    assert len(set(FEATURE_NAMES)) == len(FEATURE_NAMES)
    assert all(np.isfinite(value) and value >= 0 for value in values.values())
    assert values['v5_original_mul_count'] == 1
    assert values['v5_original_mul_constant_popcount'] == 30
    assert values['v5_original_mul_constant_digits'] == 2
    assert values['v5_norm_v3_mul_variable_partial_products'] == 0
    assert 'mul(' not in normalize_formula(formula)
    assert rewrite_metadata(formula)['original_formula'] == formula
    assert feature_dict(' '+formula.replace(',', ' , ')+' ') == values
    np.testing.assert_array_equal(feature_matrix([formula])[0], list(values.values()))
    assert feature_matrix([]).shape == (0, len(FEATURE_NAMES))
    with pytest.raises(ValueError):
        feature_dict({'formula': formula, 'lut4_count': 999})


def test_range_proofs_run_before_high_constant_expansion():
    for bits, distance in ((9, 31), (13, 16), (7, 8)):
        formula = f'srli(mulhsu(andi(in1,{(1 << bits)-1}),-129),{distance})'
        assert normalize_formula(formula) == 'lui(0)'
        assert rewrite_metadata(formula)['rewrite_counts']['range_constant']
        assert proven_zero_lut(formula)
        assert_sound(formula)
    # Downstream masks/OR combine range prefixes with known operand bits.
    for formula in (
        'andi(mulhsu(andi(in1,127),-129),4294967168)',
        'ori(mulhsu(andi(in1,127),-129),127)',
        'xori(andi(mulhu(andi(in0,31),-1),4294967264),17)',
    ):
        assert proven_zero_lut(formula)
        assert_sound(formula)
    # A signed negative high product must NOT be folded to unsigned zero.
    formula = 'srli(mulh(andi(in1,511),-129),31)'
    assert not proven_zero_lut(formula)
    assert_sound(formula)
    assert oracle(parse_formula(normalize_formula(formula)), 0, 1) == 1


def test_repeated_sign_word_becomes_conditional_negation():
    formula = 'mul(andi(in1,65535),srai(in0,31))'
    assert 'mul(' not in normalize_formula(formula)
    assert 'sub(' in normalize_formula(formula)
    assert rewrite_metadata(formula)['rewrite_counts']['conditional_negate'] == 1
    values = feature_dict(formula)
    assert values['v5_original_mul_repeated_symbols'] == 31
    assert values['v5_original_mul_distinct_symbols'] == 17
    assert_sound(formula, random_count=512)


def test_sparse_high_product_requires_lower_nonzero_bit():
    formula = 'srli(mulhsu(andi(in1,129),srai(in0,16)),7)'
    normalized = normalize_formula(formula)
    assert 'mul' not in normalized
    assert rewrite_metadata(formula)['rewrite_counts']['sparse_high_slice'] == 1
    for x, y in itertools.product((0, 0x7fffffff, 0x80000000, MASK), (0, 1, 128, 129)):
        expected = ((x >> 31) & (y >> 7) & y) & 1
        assert oracle(parse_formula(normalized), x, y) == expected
    assert_sound(formula, random_count=512)


def test_deep_formula_preserves_global_grammar_contract():
    formula = 'mul(andi(in0,255),srai(in1,31))'
    for _ in range(120):
        formula = f'addi({formula},1)'
    assert_sound(formula, random_count=8)


def test_new_family_variants_have_sound_ranges_and_normalization():
    for formula in generated_formulas():
        assert_sound(formula)


def test_random_compositions_preserve_wrapping_and_signed_ranges():
    rng = random.Random(51607)
    constants = (0, 1, 2, 17, -1, -129, 0x7fffffff, 0x80000000, MASK)
    operations = ('add', 'sub', 'and', 'or', 'xor', 'mul', 'mulh', 'mulhu',
                  'mulhsu', 'slt', 'sltu', 'sll', 'srl', 'sra')
    def expression(depth):
        if depth == 0 or rng.randrange(4) == 0:
            return rng.choice(('in0', 'in1', str(rng.choice(constants))))
        op = rng.choice(operations)
        return f'{op}({expression(depth-1)},{expression(depth-1)})'
    for _ in range(256):
        formula = expression(4)
        if '(' not in formula:
            formula = f'ori({formula},0)'
        assert_sound(formula, random_count=48)


def test_broad_previous_corpus_is_now_development():
    root = Path(__file__).resolve().parents[1] / 'results/2026-10-13-v4'
    rows = json.loads((root/'development-data.json').read_text())
    rows += json.loads((root/'corpus/test/candidates.json').read_text())
    assert len(rows) == 1545
    for row in rows:
        assert_sound(row['formula'], random_count=64)


FORMAL_FORMULAS = (
    'mul(in0,srai(in1,31))',
    'mul(andi(in0,255),srai(in1,31))',
    'mul(srai(xori(in0,-1),31),andi(in1,127))',
    'srli(mulhsu(andi(in1,63),-17),16)',
    'srli(mulhu(andi(in0,31),srai(in1,8)),3)',
    'srli(mulhsu(andi(in1,129),srai(in0,16)),7)',
    'srli(mulhsu(andi(in1,128),srai(in0,16)),7)',
    'mulhsu(andi(in0,127),srai(in1,31))',
    'srli(mulh(andi(in1,255),-17),31)',
)


@pytest.mark.skipif(shutil.which('yosys') is None, reason='Formal RTL proof requires Yosys')
@pytest.mark.parametrize('formula', FORMAL_FORMULAS)
def test_formal_rewrite_equivalence(formula, tmp_path):
    """SAT proves all2**64 inputs for each concrete32-bit family instance.

    The normalizer implements algebraic generalizations, not a SAT lookup table.
    These proofs check emitted RTL too. Boundary/random tests cover many more
    instances; no claim is made of an automatic proof for the entire grammar.
    """
    normalized = normalize_formula(formula)
    rtl = (
        'module proof(input [31:0] in0,in1, output mismatch);\n'
        'wire [31:0] original,normalized;\n'
        'old_candidate a(in0,in1,original);\n'
        'new_candidate b(in0,in1,normalized);\n'
        'assign mismatch = |(original ^ normalized);\nendmodule\n'
        + generate_rtl(formula, 'old_candidate')
        + generate_rtl(normalized, 'new_candidate')
    )
    source = tmp_path/'proof.v'
    source.write_text(rtl)
    script = tmp_path/'proof.ys'
    script.write_text(f'read_verilog "{source}"\nsynth -top proof -flatten -noabc\n'
                      'sat -timeout 20 -verify -prove mismatch 0 -show-inputs\n')
    run = subprocess.run(['yosys', '-Q', '-T', '-s', str(script)], capture_output=True,
                         text=True, timeout=30)
    log = run.stdout + run.stderr
    (tmp_path/'proof.log').write_text(log)
    assert run.returncode == 0, log[-4000:]
    assert 'SAT proof finished - no model found: SUCCESS!' in log
