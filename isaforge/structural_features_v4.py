"""Versioned RV32 normalization and sparse multiplier resource features.

The rewrites are algebraic and formula-only. They change the representation fed
into an estimator, not the recorded synthesis labels or the frozen v3 sources.
Resource counts remain unmapped circuit proxies, not a technology mapper.
"""
from __future__ import annotations

from collections import Counter
from functools import lru_cache
from typing import Iterable

from .area_model_v2 import _constant, _symbols
from .features import Expression, parse_formula
from .rtl import evaluate_formula
from . import structural_features_v3 as v3

MASK = (1 << 32) - 1
SCHEMA_VERSION = 4
EXTRA_NAMES = (
    'v4_original_ops', 'v4_normalized_ops', 'v4_normalized_formula_length',
    'v4_removed_multiply_ops', 'v4_normalized_node_reduction',
    'v4_mul_operand_support_bits', 'v4_mul_operand_support_holes',
    'v4_mul_support_partial_terms', 'v4_mul_partial_product_gate_reuse',
    'v4_mul_live_compressor_bits', 'v4_mul_final_adder_bits',
    'v4_mul_low_half_count', 'v4_mul_demand_start_sum',
)
FEATURE_NAMES = tuple(v3.FEATURE_NAMES) + EXTRA_NAMES
RESOURCE_NAMES = tuple(v3.RESOURCE_NAMES) + (
    'v4_mul_live_compressor_bits', 'v4_mul_final_adder_bits',
)
RESOURCE_PRIOR = tuple(v3.RESOURCE_PRIOR) + (1., 1.)


def _literal(value: int) -> Expression:
    return Expression(value & MASK)


def _op(op: str, a: Expression, b: Expression) -> Expression:
    return Expression(op, (a, b))


def _shift(a: Expression, distance: int, signed=False) -> Expression:
    """A right shift with a mathematical distance, including distance 32."""
    if distance == 0:
        return a
    if distance >= 32:
        return _op('srai', a, _literal(31)) if signed else _literal(0)
    return _op('srai' if signed else 'srli', a, _literal(distance))


def _left(a: Expression, distance: int) -> Expression:
    if distance == 0:
        return a
    if distance >= 32:
        return _literal(0)
    return _op('slli', a, _literal(distance))


def _digits(value: int) -> tuple[tuple[int, int], ...]:
    """Signed nonadjacent digits as (position, coefficient), exactly in Z."""
    sign = -1 if value < 0 else 1
    value = abs(value)
    result = []
    position = 0
    while value:
        if value & 1:
            digit = 2 - (value & 3)
            result.append((position, sign * digit))
            value -= digit
        value >>= 1
        position += 1
    return tuple(result)


def _interval(node: Expression, signed: bool) -> tuple[int, int]:
    """Sound enclosing interval from known bits, including an unknown sign."""
    tokens = _symbols(node)
    minimum = sum((t == 1) << i for i, t in enumerate(tokens))
    maximum = sum((t != 0) << i for i, t in enumerate(tokens))
    if not signed:
        return minimum, maximum
    sign = tokens[31]
    if sign == 0:
        return minimum, maximum
    if sign == 1:
        return minimum - (1 << 32), maximum - (1 << 32)
    return (minimum & 0x7fffffff) - (1 << 31), maximum & 0x7fffffff


def _high_constant(a: Expression, constant: int, signed_a: bool) -> Expression:
    """High word of a*constant using exact two-word add/sub with carries.

    The caller limits the signed digit count, so this does not expand arbitrary
    constants into enormous formulas. A digit at bit 32 is allowed internally;
    it is never emitted as an RV32 shift instruction (whose distance wraps).
    """
    low = high = _literal(0)
    for position, digit in _digits(constant):
        term_low = _left(a, position)
        term_high = (_shift(a, 32 - position, signed_a) if position < 32
                     else _left(a, position - 32))
        if digit > 0:
            next_low = _op('add', low, term_low)
            carry = _op('sltu', next_low, low)
            high = _op('add', _op('add', high, term_high), carry)
        else:
            next_low = _op('sub', low, term_low)
            borrow = _op('sltu', low, term_low)
            high = _op('sub', _op('sub', high, term_high), borrow)
        low = next_low
    return high


def _xor(node: Expression) -> Expression:
    parity: dict[str, Expression] = {}
    constant = 0

    def collect(n):
        nonlocal constant
        if n.value in ('xor', 'xori') and n.children:
            for child in n.children:
                collect(child)
        elif not n.children and isinstance(n.value, int):
            constant ^= n.value & MASK
        else:
            key = n.canonical()
            if key in parity:
                del parity[key]
            else:
                parity[key] = n

    collect(node)
    atoms = [parity[key] for key in sorted(parity)]
    if not atoms:
        return _literal(constant)
    # A balanced deterministic tree keeps the parser depth bounded even when
    # an already balanced input contains many distinct XOR atoms.
    def combine(items):
        if len(items) == 1:
            return items[0]
        middle = len(items) // 2
        return _op('xor', combine(items[:middle]), combine(items[middle:]))
    result = combine(atoms)
    return _op('xori', result, _literal(constant)) if constant else result


def _bounded_rewrite(original: Expression, rewritten: Expression) -> Expression:
    # Preserve the public grammar's length/depth contract when a carry expression
    # repeats a large operand. The fallback remains semantics-equivalent.
    if len(rewritten.canonical()) > 14000:
        return original
    def depth(n):
        return 0 if not n.children else 1 + max(depth(c) for c in n.children)
    return original if depth(rewritten) > 110 else rewritten


@lru_cache(maxsize=32768)
def _normalize(node: Expression) -> Expression:
    if not node.children:
        return _literal(node.value) if isinstance(node.value, int) else node
    current = Expression(node.value, tuple(_normalize(c) for c in node.children))
    current = v3._normalize(current)
    if not current.children:
        return current
    op = str(current.value)
    if op in ('xor', 'xori'):
        return _xor(current)
    if op == 'lui':
        return current.children[0]
    a, b = current.children
    ca, cb = _constant(_symbols(a)), _constant(_symbols(b))
    if ca is not None and cb is not None:
        return _literal(evaluate_formula(current, 0, 0))
    if op in ('sll', 'slli', 'srl', 'srli', 'sra', 'srai') and cb is not None:
        distance = cb & 31
        if not distance:
            return a
        kind = {'sll': 'slli', 'srl': 'srli', 'sra': 'srai'}.get(op, op)
        if a.value == kind and a.children and isinstance(a.children[1].value, int):
            combined = distance + (a.children[1].value & 31)
            result = (_left(a.children[0], combined) if kind == 'slli'
                      else _shift(a.children[0], combined, kind == 'srai'))
            return _normalize(result)
        return Expression(kind, (a, _literal(distance)))
    if op not in ('mul', 'mulh', 'mulhu', 'mulhsu'):
        return current
    if op != 'mul':
        signed_a = op in ('mulh', 'mulhsu')
        signed_b = op == 'mulh'
        amin, amax = _interval(a, signed_a)
        bmin, bmax = _interval(b, signed_b)
        products = (amin*bmin, amin*bmax, amax*bmin, amax*bmax)
        minimum, maximum = min(products) >> 32, max(products) >> 32
        if minimum == maximum:
            return _literal(minimum)
        if cb is not None:
            constant = cb - (1 << 32) if signed_b and cb & (1 << 31) else cb
            variable, signed_variable = a, signed_a
        elif ca is not None:
            constant = ca - (1 << 32) if signed_a and ca & (1 << 31) else ca
            variable, signed_variable = b, signed_b
        else:
            return current
        if len(_digits(constant)) <= 3:
            rewritten = _bounded_rewrite(current, _high_constant(variable, constant, signed_variable))
            return current if rewritten == current else _normalize(rewritten)
        return current
    if ca is not None or cb is not None:
        variable, constant = (b, ca) if ca is not None else (a, cb)
        assert constant is not None
        signed_constant = constant - (1 << 32) if constant & (1 << 31) else constant
        digits = _digits(signed_constant)
        if len(digits) <= 4:
            result = _literal(0)
            for position, digit in digits:
                result = _op('add' if digit > 0 else 'sub', result, _left(variable, position))
            rewritten = _bounded_rewrite(current, result)
            return current if rewritten == current else _normalize(rewritten)
    supports = [[i for i, t in enumerate(_symbols(child)) if t != 0] for child in (a, b)]
    trailing = [min(support, default=32) for support in supports]
    if sum(trailing) >= 32:
        return _literal(0)
    if sum(trailing):
        inner = _op('mul', _shift(a, trailing[0]), _shift(b, trailing[1]))
        rewritten = _bounded_rewrite(current, _left(inner, sum(trailing)))
        if rewritten != current:
            return _normalize(rewritten)
    # A variable operand with one possible one-bit is a shift and Boolean gate
    # mask, not a dense-width multiplier. Arithmetic shift replicates that bit.
    for variable, singleton in ((a, b), (b, a)):
        support = [i for i, token in enumerate(_symbols(singleton)) if token != 0]
        if len(support) == 1:
            position = support[0]
            mask = _op('srai', _left(singleton, 31-position), _literal(31))
            result = _op('and', _left(variable, position), mask)
            rewritten = _bounded_rewrite(current, result)
            return current if rewritten == current else _normalize(rewritten)
    return current


def _root_formula(node: Expression) -> str:
    # The shared parser/RTL emitter deliberately require an operation at root.
    if node.children:
        return node.canonical()
    return (Expression('lui', (node,)).canonical() if isinstance(node.value, int)
            else _op('ori', node, _literal(0)).canonical())


@lru_cache(maxsize=16384)
def normalize_formula(formula: str) -> str:
    """Return a valid canonical formula equivalent under exact RV32 semantics."""
    return _root_formula(_normalize(parse_formula(formula)))


def proven_zero_lut(formula: str) -> bool:
    """Prove only direct wiring/constants, never infer zero from fitted area."""
    return all(v3._wire_token(t) for t in _symbols(_normalize(parse_formula(formula))))


def _nodes(root):
    nodes = {}
    def collect(n):
        key = n.canonical()
        if key in nodes:
            return
        nodes[key] = n
        for child in n.children:
            collect(child)
    collect(root)
    return nodes


def _product_columns(node, high):
    """An unsigned/sign-extended product modulo 2**(high+1).

    Constants are removed before AND counting. Interning and identical-term
    carries retain squaring and repeated sign-bit correlations. Compression and
    the final row addition are still structural proxies rather than LUT mapping.
    """
    a, b = [_symbols(c) for c in node.children]
    if node.value != 'mul':
        a += (a[31] if node.value in ('mulh', 'mulhsu') else 0,) * 32
        b += (b[31] if node.value == 'mulh' else 0,) * 32
    circuit = v3._BitCircuit()
    columns = [Counter() for _ in range(high+2)]
    gates = set()
    terms = 0
    for i, x in enumerate(a):
        if x == 0 or i > high:
            continue
        for j, y in enumerate(b):
            if y == 0 or i+j > high:
                continue
            token = circuit.binary('and', x, y)
            if token == 0:
                continue
            terms += 1
            columns[i+j][token] += 1
            if token in circuit.nodes and circuit.nodes[token][0] == 'and':
                gates.add(token)
    occupied = sum(bool(c) for c in columns[:-1])
    peak = max((sum(c.values()) for c in columns[:-1]), default=0)
    compressors = final_bits = 0
    carrying = False
    for column in range(high+1):
        counts = columns[column]
        tokens = []
        for token, count in counts.items():
            # t+t = 2*t is exact, including constant one and sign copies.
            if count // 2:
                columns[column+1][token] += count // 2
            if count & 1:
                tokens.append(token)
        while len(tokens) > 2:
            x, y, z = tokens.pop(), tokens.pop(), tokens.pop()
            pair = circuit.binary('xor', x, y)
            total = circuit.binary('xor', pair, z)
            carry = circuit.binary('or', circuit.binary('and', x, y),
                                   circuit.binary('and', pair, z))
            if total != 0:
                tokens.append(total)
            if carry != 0:
                columns[column+1][carry] += 1
            compressors += 1
        # Row-adder support, including the incoming lower-column carry.
        active = len(tokens) + int(carrying)
        final_bits += int(active >= 2)
        carrying = active >= 2
    return len(gates), terms, occupied, peak, compressors, final_bits


def _multiply_resources(root):
    nodes = _nodes(root)
    demanded = {}
    def demand(node, bits):
        key = node.canonical()
        symbols = _symbols(node)
        bits &= sum(1 << i for i, t in enumerate(symbols) if not isinstance(t, int))
        new = bits & ~demanded.get(key, 0)
        if not new:
            return
        demanded[key] = demanded.get(key, 0) | bits
        if not node.children:
            return
        a = node.children[0]
        if len(node.children) == 1:
            demand(a, new)
            return
        b = node.children[1]
        asy, bsy = _symbols(a), _symbols(b)
        if symbols == asy:
            demand(a, new)
            return
        if symbols == bsy:
            demand(b, new)
            return
        family = v3._family(str(node.value))
        if family == 'logic':
            demand(a, new); demand(b, new)
        elif family == 'shift':
            circuit, outputs, _ = v3._barrel(asy, bsy, str(node.value))
            _, leaves = circuit.cone(outputs[i] for i in range(32) if new & (1 << i))
            demand(a, sum(1 << i for i, t in enumerate(asy) if t in leaves))
            demand(b, 31)
        elif family == 'adder' or node.value == 'mul':
            prefix = (1 << new.bit_length()) - 1
            demand(a, prefix); demand(b, prefix)
        else:
            demand(a, MASK); demand(b, MASK)
    demand(root, MASK)
    result = dict.fromkeys((
        'v3_mul_variable_partial_products', 'v3_mul_constant_adder_bits',
        'v3_mul_occupied_columns', 'v3_mul_peak_column_height', 'v3_mul_compressor_bits',
        'v4_mul_operand_support_bits', 'v4_mul_operand_support_holes',
        'v4_mul_support_partial_terms', 'v4_mul_partial_product_gate_reuse',
        'v4_mul_live_compressor_bits', 'v4_mul_final_adder_bits',
        'v4_mul_low_half_count', 'v4_mul_demand_start_sum',
    ), 0.)
    for key, node in nodes.items():
        bits = demanded.get(key, 0)
        if not bits or node.value not in ('mul', 'mulh', 'mulhu', 'mulhsu'):
            continue
        high = bits.bit_length()-1 + (0 if node.value == 'mul' else 32)
        gates, terms, occupied, peak, compressors, final = _product_columns(node, high)
        result['v3_mul_variable_partial_products'] += gates
        result['v3_mul_occupied_columns'] += occupied
        result['v3_mul_peak_column_height'] = max(result['v3_mul_peak_column_height'], peak)
        result['v3_mul_compressor_bits'] += compressors
        result['v4_mul_support_partial_terms'] += terms
        result['v4_mul_partial_product_gate_reuse'] += max(0, terms-gates)
        result['v4_mul_live_compressor_bits'] += compressors
        result['v4_mul_final_adder_bits'] += final
        result['v4_mul_low_half_count'] += int(node.value == 'mul')
        result['v4_mul_demand_start_sum'] += (bits & -bits).bit_length()-1
        for child in node.children:
            support = [i for i, t in enumerate(_symbols(child)) if t != 0]
            result['v4_mul_operand_support_bits'] += len(support)
            result['v4_mul_operand_support_holes'] += max(support, default=-1)+1-len(support)
    return result


@lru_cache(maxsize=16384)
def _feature_values(formula: str) -> tuple[float, ...]:
    original = parse_formula(formula)
    root = _normalize(original)
    values = v3.feature_dict(_root_formula(root))
    values.update(dict.fromkeys(EXTRA_NAMES, 0.))
    values.update(_multiply_resources(root))
    before, after = _nodes(original), _nodes(root)
    original_ops = sum(bool(n.children) for n in before.values())
    normalized_ops = sum(bool(n.children) for n in after.values())
    values['v4_original_ops'] = original_ops
    values['v4_normalized_ops'] = normalized_ops
    values['v4_normalized_formula_length'] = len(_root_formula(root))
    values['v4_normalized_node_reduction'] = max(0, original_ops-normalized_ops)
    multiply = lambda nodes: sum(n.value in ('mul', 'mulh', 'mulhu', 'mulhsu') for n in nodes.values())
    values['v4_removed_multiply_ops'] = max(0, multiply(before)-multiply(after))
    return tuple(float(values[name]) for name in FEATURE_NAMES)


def feature_dict(formula: str) -> dict[str, float]:
    """Nonnegative formula-only schema; old multiplier width proxies corrected."""
    canonical = parse_formula(formula).canonical()
    return dict(zip(FEATURE_NAMES, _feature_values(canonical)))


def feature_matrix(formulas: Iterable[str]):
    import numpy as np
    return np.asarray([_feature_values(parse_formula(f).canonical()) for f in formulas],
                      dtype=float).reshape((-1, len(FEATURE_NAMES)))
