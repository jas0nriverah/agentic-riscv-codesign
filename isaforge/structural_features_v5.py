"""Formula-only V5 semantics and original implementation descriptors.

Ranges are unions of unsigned RV32 intervals; signed interpretation is explicit
at each arithmetic operation. Proofs run before V4's constant-product expansion.
Semantic simplification describes a second representation, not the mapped cost
of the original RTL. Callers must retain original graph features and labels.
"""
from __future__ import annotations

from collections import Counter
from functools import lru_cache
from typing import Iterable

from .features import Expression, parse_formula
from .area_model_v2 import _constant, _symbols
from . import structural_features_v4 as v4

WIDTH = 32
MODULUS = 1 << WIDTH
MASK = MODULUS - 1
SCHEMA_VERSION = 5
EXTRA_NAMES = (
    'v5_original_ops', 'v5_normalized_ops', 'v5_original_formula_length',
    'v5_normalized_formula_length', 'v5_expanded_ops', 'v5_removed_ops',
    'v5_original_mul_count', 'v5_original_mulh_count', 'v5_original_mulhu_count',
    'v5_original_mulhsu_count', 'v5_original_mul_signed_operands',
    'v5_original_mul_unsigned_second_operands', 'v5_original_mul_constant_operands',
    'v5_original_mul_constant_popcount', 'v5_original_mul_constant_digits',
    'v5_original_mul_operand_support_bits', 'v5_original_mul_distinct_symbols',
    'v5_original_mul_repeated_symbols', 'v5_original_mul_demand_bits',
    'v5_original_mul_demand_start', 'v5_original_mul_demand_span',
    'v5_original_range_width', 'v5_normalized_range_width',
    'v5_range_constant_rewrites', 'v5_conditional_negate_rewrites',
    'v5_high_sign_product_rewrites', 'v5_sparse_high_slice_rewrites',
    'v5_shift_and_rewrites', 'v5_proven_wire_or_constant',
)
FEATURE_NAMES = tuple('v5_norm_' + n for n in v4.FEATURE_NAMES) + EXTRA_NAMES
REWRITE_NAMES = (
    'range_constant', 'conditional_negate', 'high_sign_product',
    'sparse_high_slice', 'shift_and',
)


def _literal(value: int) -> Expression:
    return Expression(value & MASK)


def _op(op: str, a: Expression, b: Expression) -> Expression:
    return Expression(op, (a, b))


def _merged(intervals):
    """Merge intervals; cap analysis complexity with a sound enclosing interval."""
    result = []
    for low, high in sorted(intervals):
        if result and low <= result[-1][1] + 1:
            result[-1] = (result[-1][0], max(high, result[-1][1]))
        else:
            result.append((low, high))
    if len(result) > 8:
        return ((result[0][0], result[-1][1]),)
    return tuple(result)


def _wrapped(low: int, high: int):
    """Enclose a mathematical integer interval modulo 2**32 without overflow."""
    if high - low >= MASK:
        return ((0, MASK),)
    start, stop = low & MASK, high & MASK
    if low // MODULUS == high // MODULUS:
        return ((start, stop),)
    return ((0, stop), (start, MASK))


def _interpreted(intervals, signed):
    if not signed:
        return intervals
    result = []
    for low, high in intervals:
        if low < (1 << 31):
            result.append((low, min(high, (1 << 31)-1)))
        if high >= (1 << 31):
            result.append((max(low, 1 << 31)-MODULUS, high-MODULUS))
    return _merged(result)


def _known_range_bits(intervals):
    """Only a common binary prefix is fixed throughout a contiguous interval."""
    zero = one = MASK
    for low, high in intervals:
        variable = (1 << (low ^ high).bit_length()) - 1
        zero &= (MASK ^ low) & (MASK ^ variable)
        one &= low & (MASK ^ variable)
    return zero, one


@lru_cache(maxsize=65536)
def unsigned_ranges(node: Expression) -> tuple[tuple[int, int], ...]:
    """Sound nonwrapping unsigned output intervals, including wrapped arithmetic.

    Bit-symbol bounds are intersected with arithmetic bounds. Dependencies are
    overapproximated; interval independence can lose proofs but cannot invent
    them. High multiplication keeps mulhsu's second operand unsigned.
    """
    symbols = _symbols(node)
    minimum = sum((token == 1) << bit for bit, token in enumerate(symbols))
    maximum = sum((token != 0) << bit for bit, token in enumerate(symbols))
    fallback = ((minimum, maximum),)
    if not node.children or minimum == maximum:
        return fallback
    op = str(node.value)
    a = unsigned_ranges(node.children[0])
    if op == 'lui':
        return a
    b = unsigned_ranges(node.children[1])
    result = []
    if op in ('add', 'addi', 'sub', 'mul', 'mulh', 'mulhu', 'mulhsu'):
        high_product = op in ('mulh', 'mulhu', 'mulhsu')
        aa = _interpreted(a, op in ('mulh', 'mulhsu')) if high_product else a
        bb = _interpreted(b, op == 'mulh') if high_product else b
        for low_a, high_a in aa:
            for low_b, high_b in bb:
                if op in ('add', 'addi'):
                    low, high = low_a + low_b, high_a + high_b
                elif op == 'sub':
                    low, high = low_a - high_b, high_a - low_b
                else:
                    products = (low_a*low_b, low_a*high_b, high_a*low_b, high_a*high_b)
                    low, high = min(products), max(products)
                    if high_product:
                        low, high = low >> WIDTH, high >> WIDTH
                result.extend(_wrapped(low, high))
    elif op in ('sll', 'slli', 'srl', 'srli', 'sra', 'srai'):
        distance = _constant(_symbols(node.children[1]))
        if distance is None:
            return fallback
        distance &= 31
        if op in ('sra', 'srai'):
            for low, high in _interpreted(a, True):
                result.extend(_wrapped(low >> distance, high >> distance))
        elif op in ('srl', 'srli'):
            result = [(low >> distance, high >> distance) for low, high in a]
        else:
            for low, high in a:
                result.extend(_wrapped(low << distance, high << distance))
    elif op in ('slt', 'slti', 'sltu', 'sltiu'):
        aa, bb = _interpreted(a, op in ('slt', 'slti')), _interpreted(b, op in ('slt', 'slti'))
        if max(high for _, high in aa) < min(low for low, _ in bb):
            result = [(1, 1)]
        elif min(low for low, _ in aa) >= max(high for _, high in bb):
            result = [(0, 0)]
        else:
            result = [(0, 1)]
    elif op in ('and', 'andi', 'or', 'ori', 'xor', 'xori'):
        az, ao = _abstract_masks(node.children[0], a)
        bz, bo = _abstract_masks(node.children[1], b)
        if op in ('and', 'andi'):
            zero, one = az | bz, ao & bo
            # Nonnegative AND also cannot exceed either unsigned operand.
            limit = min(max(high for _, high in a), max(high for _, high in b))
        elif op in ('or', 'ori'):
            zero, one = az & bz, ao | bo
            limit = MASK
        else:
            zero, one = (az & bz) | (ao & bo), (az & bo) | (ao & bz)
            limit = MASK
        result = [(one, min(MASK ^ zero, limit))]
    else:
        return fallback
    # Known-bit bounds can tighten unsigned intervals without losing values.
    return _merged((max(low, minimum), min(high, maximum))
                   for low, high in result if max(low, minimum) <= min(high, maximum))


def _abstract_masks(node, intervals):
    zero, one = _known_range_bits(intervals)
    for bit, token in enumerate(_symbols(node)):
        if token == 0:
            zero |= 1 << bit
        elif token == 1:
            one |= 1 << bit
    return zero, one


def _range_constant(node):
    zero, one = _abstract_masks(node, unsigned_ranges(node))
    return one if zero | one == MASK else None


def _sign_product(node):
    """Prove high(a*unsigned(srai(x,k))) = signmask(x)&(a-[a!=0]).

    For nonnegative a and Amax * 2**(31-k) <= 2**32: the positive
    branch product is below2**32. The negative unsigned branch is a*(2**32-d),
    where1<=d<=2**(31-k), giving high word a-1 for a>0 and0 for a=0.
    Signedness of the FIRST mulhsu operand is checked separately.
    """
    if node.value not in ('mulhu', 'mulhsu'):
        return None
    possibilities = [node.children]
    if node.value == 'mulhu':
        possibilities.append(tuple(reversed(node.children)))
    for a, b in possibilities:
        if b.value not in ('sra', 'srai') or not b.children:
            continue
        distance = _constant(_symbols(b.children[1]))
        if distance is None:
            continue
        distance &= 31
        maximum = max(high for _, high in unsigned_ranges(a))
        if node.value == 'mulhsu' and maximum >= (1 << 31):
            continue
        if maximum * (1 << (31-distance)) <= MODULUS:
            return a, b.children[0], maximum
    return None


def _predecessor_slice(a, maximum, distance):
    """Extract (a-[a!=0])>>d when0<=a<2**(d+1), d>=1.

    The result is the top possible bit AND whether lower bits are nonzero.
    This captures sparse masks without assuming lower bits are independent.
    """
    if distance < 1 or maximum >= (1 << (distance+1)):
        return None
    top = _op('srli', a, _literal(distance))
    lower = _op('andi', a, _literal((1 << distance)-1))
    return _op('and', top, _op('sltu', _literal(0), lower))


def _local(node):
    """Return an equivalent replacement plus its proof-family identifier."""
    if not node.children:
        return node, None
    constant = _range_constant(node)
    if constant is not None:
        return _literal(constant), 'range_constant'
    if node.value in ('srl', 'srli'):
        a, b = node.children
        distance = _constant(_symbols(b))
        if distance is not None:
            distance &= 31
            product = _sign_product(a)
            if product is not None:
                variable, sign_source, maximum = product
                sliced = _predecessor_slice(variable, maximum, distance)
                if sliced is not None:
                    sign = _op('srli', sign_source, _literal(31))
                    return _op('and', sliced, sign), 'sparse_high_slice'
            if a.value == 'sub' and a.children[1] == _op('sltu', _literal(0), a.children[0]):
                maximum = max(high for _, high in unsigned_ranges(a.children[0]))
                sliced = _predecessor_slice(a.children[0], maximum, distance)
                if sliced is not None:
                    return sliced, 'sparse_high_slice'
            if a.value in ('and', 'andi') and distance:
                left, right = a.children
                return _op('and', _op('srli', left, _literal(distance)),
                           _op('srli', right, _literal(distance))), 'shift_and'
    if node.value == 'mul':
        for variable, mask in (node.children, tuple(reversed(node.children))):
            tokens = _symbols(mask)
            if tokens[0] not in (0, 1) and all(token == tokens[0] for token in tokens):
                return _op('and', _op('sub', _literal(0), variable), mask), 'conditional_negate'
    product = _sign_product(node)
    if product is not None:
        variable, sign_source, _ = product
        predecessor = _op('sub', variable, _op('sltu', _literal(0), variable))
        sign = _op('srai', sign_source, _literal(31))
        return _op('and', predecessor, sign), 'high_sign_product'
    return node, None


def _prepass(node, counts):
    # Look at the intact downstream slice before rewriting either product child.
    rewritten, rule = _local(node)
    if rewritten != node:
        bounded = v4._bounded_rewrite(node, rewritten)
        if bounded != node:
            counts[rule] += 1
            return _prepass(bounded, counts)
    if not node.children:
        return _literal(node.value) if isinstance(node.value, int) else node
    children = tuple(_prepass(child, counts) for child in node.children)
    current = Expression(node.value, children)
    rewritten, rule = _local(current)
    if rewritten != current:
        bounded = v4._bounded_rewrite(current, rewritten)
        if bounded != current:
            counts[rule] += 1
            return _prepass(bounded, counts)
    return current


@lru_cache(maxsize=16384)
def _normalized(formula):
    root = parse_formula(formula)
    counts = Counter()
    # Each new rule removes a multiplier or folds/delivers a demanded slice.
    # V4 can expose another simplification, so settle both passes to a fixed point.
    for _ in range(16):
        iteration_counts = Counter()
        replacement = v4._normalize(_prepass(root, iteration_counts))
        # A small local expansion may still exceed the complete formula's
        # grammar limit when it sits inside a long ancestor chain.
        try:
            parse_formula(v4._root_formula(replacement))
        except ValueError:
            return v4._root_formula(root), tuple(counts[name] for name in REWRITE_NAMES)
        counts.update(iteration_counts)
        if replacement == root:
            return v4._root_formula(root), tuple(counts[name] for name in REWRITE_NAMES)
        root = replacement
    raise ValueError('V5 normalization did not reach a fixed point')


def normalize_formula(formula: str) -> str:
    """Return a grammar-valid equivalent RV32 formula; never consult labels."""
    canonical = parse_formula(formula).canonical()
    return _normalized(canonical)[0]


def rewrite_metadata(formula: str) -> dict:
    """Original syntax and rule counts, independent of hardware measurements."""
    canonical = parse_formula(formula).canonical()
    normalized, counts = _normalized(canonical)
    return {'original_formula': canonical, 'normalized_formula': normalized,
            'rewrite_counts': dict(zip(REWRITE_NAMES, counts))}


def _multiply_demands(root):
    demanded = {}
    def visit(node, bits):
        key = node.canonical()
        new = bits & ~demanded.get(key, 0)
        if not new:
            return
        demanded[key] = demanded.get(key, 0) | bits
        if not node.children:
            return
        if len(node.children) == 1:
            visit(node.children[0], new)
            return
        a, b = node.children
        op = str(node.value)
        if op in ('sll', 'slli', 'srl', 'srli', 'sra', 'srai'):
            distance = _constant(_symbols(b))
            if distance is not None:
                distance &= 31
                if op in ('sll', 'slli'):
                    source = new >> distance
                else:
                    source = (new << distance) & MASK
                    if op in ('sra', 'srai') and new >> (32-distance):
                        source |= 1 << 31
                visit(a, source)
                return
        if op in ('and', 'andi', 'or', 'ori', 'xor', 'xori'):
            constant_a, constant_b = _constant(_symbols(a)), _constant(_symbols(b))
            left, right = new, new
            if op in ('and', 'andi'):
                if constant_b is not None: left &= constant_b
                if constant_a is not None: right &= constant_a
            elif op in ('or', 'ori'):
                if constant_b is not None: left &= MASK ^ constant_b
                if constant_a is not None: right &= MASK ^ constant_a
            visit(a, left); visit(b, right)
        elif op in ('add', 'addi', 'sub', 'mul'):
            prefix = (1 << new.bit_length()) - 1
            visit(a, prefix); visit(b, prefix)
        else:
            visit(a, MASK); visit(b, MASK)
    visit(root, MASK)
    return demanded


def proven_zero_lut(formula):
    """Prove normalized output wiring/constants, not original synthesis cost."""
    return v4.proven_zero_lut(normalize_formula(formula))


@lru_cache(maxsize=16384)
def _feature_values(canonical):
    original = parse_formula(canonical)
    normalized, counts = _normalized(canonical)
    root = parse_formula(normalized)
    values = {'v5_norm_' + name: value for name, value in v4.feature_dict(normalized).items()}
    values.update(dict.fromkeys(EXTRA_NAMES, 0.))
    before, after = v4._nodes(original), v4._nodes(root)
    original_ops = sum(bool(n.children) for n in before.values())
    normalized_ops = sum(bool(n.children) for n in after.values())
    values.update(v5_original_ops=original_ops, v5_normalized_ops=normalized_ops,
                  v5_original_formula_length=len(canonical),
                  v5_normalized_formula_length=len(normalized),
                  v5_expanded_ops=max(0, normalized_ops-original_ops),
                  v5_removed_ops=max(0, original_ops-normalized_ops))
    demanded = _multiply_demands(original)
    for key, node in before.items():
        op = str(node.value)
        if op not in ('mul', 'mulh', 'mulhu', 'mulhsu'):
            continue
        values['v5_original_' + op + '_count'] += 1
        values['v5_original_mul_signed_operands'] += 2 if op == 'mulh' else int(op == 'mulhsu')
        values['v5_original_mul_unsigned_second_operands'] += int(op in ('mulhu', 'mulhsu'))
        tokens = [_symbols(child) for child in node.children]
        varying = [token for operand in tokens for token in operand if not isinstance(token, int)]
        values['v5_original_mul_distinct_symbols'] += len(set(varying))
        values['v5_original_mul_repeated_symbols'] += len(varying)-len(set(varying))
        values['v5_original_mul_operand_support_bits'] += sum(token != 0 for operand in tokens for token in operand)
        for index, operand in enumerate(tokens):
            constant = _constant(operand)
            if constant is None:
                continue
            signed = op == 'mul' or op == 'mulh' or op == 'mulhsu' and index == 0
            integer = constant-MODULUS if signed and constant & (1 << 31) else constant
            values['v5_original_mul_constant_operands'] += 1
            values['v5_original_mul_constant_popcount'] += constant.bit_count()
            values['v5_original_mul_constant_digits'] += len(v4._digits(integer))
        bits = demanded.get(key, 0)
        values['v5_original_mul_demand_bits'] += bits.bit_count()
        values['v5_original_mul_demand_span'] += bits.bit_length()
        values['v5_original_mul_demand_start'] += (bits & -bits).bit_length()-1 if bits else 0
    for label, node in [('original', original), ('normalized', root)]:
        ranges = unsigned_ranges(node)
        values['v5_' + label + '_range_width'] = max(high for _, high in ranges)-min(low for low, _ in ranges)
    for name, count in zip(REWRITE_NAMES, counts):
        values['v5_' + name + '_rewrites'] = count
    values['v5_proven_wire_or_constant'] = float(proven_zero_lut(normalized))
    return tuple(float(values[name]) for name in FEATURE_NAMES)


def feature_dict(formula: str) -> dict[str, float]:
    canonical = parse_formula(formula).canonical()
    return dict(zip(FEATURE_NAMES, _feature_values(canonical)))


def feature_matrix(formulas: Iterable[str]):
    import numpy as np
    return np.asarray([_feature_values(parse_formula(f).canonical()) for f in formulas],
                      dtype=float).reshape((-1, len(FEATURE_NAMES)))
