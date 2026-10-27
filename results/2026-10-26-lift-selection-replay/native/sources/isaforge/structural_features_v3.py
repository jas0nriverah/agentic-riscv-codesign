"""Formula-only bit-cone and composition features for development model v3.

This is an abstract circuit, not a synthesis netlist or a technology mapper. In
particular LUT and carry sharing are only proxies. All counts are nonnegative
and independent of benchmark names, measured labels, and execution frequency.
The frozen v2 symbol abstraction is reused without changing its source.
"""
from __future__ import annotations

from collections import Counter
from functools import lru_cache
from typing import Iterable

from .area_model_v2 import _constant, _csd_terms, _symbols, _widths
from .features import Expression, parse_formula
from .rtl import evaluate_formula

MASK = (1 << 32) - 1
SCHEMA_VERSION = 3
RESOURCE_NAMES = (
    'v3_logic_output_bits', 'v3_adder_sum_bits', 'v3_compare_variable_bits',
    'v3_compare_constant_count', 'v3_compare_constant_inverted_bits', 'v3_barrel_live_muxes',
    'v3_mul_variable_partial_products', 'v3_mul_constant_adder_bits',
)
# Raw bit/gate units; these are elementary starting values, not measured fits.
RESOURCE_PRIOR = (1., 1., 1., 1., 1., 1., 2., 1.)
FEATURE_GROUPS = {
    'resources': RESOURCE_NAMES,
    'algebra': ('v3_normalized_node_reduction', 'v3_proven_zero_lut',
                'v3_output_constant_bits', 'v3_output_direct_wire_bits'),
    'graph': ('v3_live_ops', 'v3_dead_ops', 'v3_live_edges', 'v3_shared_live_ops',
              'v3_max_fanout', 'v3_live_depth', 'v3_live_demand_bits',
              'v3_demand_span_sum', 'v3_operand_unknown_bits', 'v3_reconvergent_edges'),
    'adder': ('v3_adder_sum_bits_max', 'v3_adder_carry_bits',
              'v3_adder_carry_run_max', 'v3_adder_carry_start_sum',
              'v3_adder_constant_count', 'v3_adder_constant_popcount',
              'v3_adder_constant_transitions', 'v3_adder_constant_trailing_zeros',
              'v3_adder_output_token_reuse'),
    'barrel': ('v3_barrel_live_muxes_max', 'v3_barrel_live_stages',
               'v3_barrel_constant_data_count', 'v3_barrel_source_bits',
               'v3_barrel_control_bits', 'v3_barrel_muxes_saved_by_equal_branches'),
    'comparator': ('v3_compare_constant_width', 'v3_compare_constant_popcount',
                   'v3_compare_constant_transitions', 'v3_compare_constant_trailing_zeros',
                   'v3_compare_boolean_operand_count', 'v3_compare_signed_count',
                   'v3_compare_polarity_folds'),
    'multiplier': ('v3_mul_occupied_columns', 'v3_mul_peak_column_height',
                   'v3_mul_compressor_bits', 'v3_mul_high_half_count',
                   'v3_mul_signed_operand_count', 'v3_mul_constant_csd_terms',
                   'v3_mul_output_demand_span', 'v3_mul_repeated_operand_count'),
    'composition': tuple(f'v3_edge_{parent}_{child}' for parent in
                         ('logic', 'adder', 'shift', 'compare', 'multiply') for child in
                         ('logic', 'adder', 'shift', 'compare', 'multiply')),
}
FEATURE_NAMES = tuple(name for names in FEATURE_GROUPS.values() for name in names)


def _family(op: str) -> str:
    if op in ('and', 'andi', 'or', 'ori', 'xor', 'xori'): return 'logic'
    if op in ('add', 'addi', 'sub'): return 'adder'
    if op in ('sll', 'slli', 'srl', 'srli', 'sra', 'srai'): return 'shift'
    if op in ('slt', 'slti', 'sltu', 'sltiu'): return 'compare'
    if op in ('mul', 'mulh', 'mulhu', 'mulhsu'): return 'multiply'
    return 'wire'


def _affine(node: Expression) -> tuple[dict[str, tuple[Expression, int]], int]:
    """Collect additive atoms over Z/(2**32), without assuming independence."""
    if not node.children and isinstance(node.value, int): return {}, node.value & MASK
    if node.value not in ('add', 'addi', 'sub') or not node.children:
        return {node.canonical(): (node, 1)}, 0
    left, lc = _affine(node.children[0]); right, rc = _affine(node.children[1])
    result = dict(left)
    sign = -1 if node.value == 'sub' else 1
    for key, (atom, coefficient) in right.items():
        coefficient = (result.get(key, (atom, 0))[1] + sign * coefficient) & MASK
        if coefficient: result[key] = atom, coefficient
        else: result.pop(key, None)
    return result, (lc + sign * rc) & MASK


@lru_cache(maxsize=32768)
def _normalize(node: Expression) -> Expression:
    """Sound algebraic simplifications only; no label-dependent rewrite rules."""
    if not node.children: return node
    children = tuple(_normalize(c) for c in node.children)
    result = Expression(node.value, children)
    if node.value == 'lui': return children[0]
    if all(not c.children and isinstance(c.value, int) for c in children):
        return Expression(evaluate_formula(result, 0, 0))
    if node.value in ('add', 'addi', 'sub'):
        atoms, constant = _affine(result)
        if not atoms: return Expression(constant)
        if len(atoms) == 1:
            atom, coefficient = next(iter(atoms.values()))
            if coefficient == 1:
                return atom if constant == 0 else Expression('addi', (atom, Expression(constant)))
        # Combining adjacent constants also preserves variable association.
        a, b = children
        if (not b.children and isinstance(b.value, int) and a.value == 'addi'
                and not a.children[1].children and isinstance(a.children[1].value, int)):
            sign = -1 if node.value == 'sub' else 1
            return _normalize(Expression('addi', (a.children[0], Expression(
                (int(a.children[1].value) + sign * b.value) & MASK))))
    if len(children) == 2 and children[0] == children[1]:
        if node.value in ('xor', 'sub', 'slt', 'sltu'): return Expression(0)
        if node.value in ('and', 'or'): return children[0]
        if node.value == 'add': return Expression('slli', (children[0], Expression(1)))
    if node.value in ('sltu', 'sltiu'):
        a, b = children
        asy, bsy = _symbols(a), _symbols(b)
        ca, cb = _constant(asy), _constant(bsy)
        if _widths(asy)[0] <= 1 and cb is not None:
            if cb == 0: return Expression(0)
            if cb == 1: return _normalize(Expression('xori', (a, Expression(1))))
            return Expression(1)
        if ca is not None and _widths(bsy)[0] <= 1:
            return b if ca == 0 else Expression(0)
    # The symbol abstraction can prove masks, shifts, and constant products.
    symbols = _symbols(result)
    constant = _constant(symbols)
    if constant is not None: return Expression(constant)
    for child in children:
        if symbols == _symbols(child): return child
    return result


def _wire_token(token: object) -> bool:
    return isinstance(token, int) or isinstance(token, tuple) and token[0] == 'input'


def proven_zero_lut(formula: str) -> bool:
    """Prove the result consists only of constants and direct input-bit wires.

    Sign copies and permutations are wires. Inversion, comparisons, and any
    opaque computation are deliberately excluded, even if mapping uses zero
    LUTs plus carry cells. False means unproved, rather than nonzero cost.
    """
    return all(_wire_token(t) for t in _symbols(_normalize(parse_formula(formula))))


class _BitCircuit:
    """Small interned Boolean DAG for carry identity and mux cone counting."""
    def __init__(self):
        self.nodes: dict[tuple, tuple] = {}
        self.keys: dict[tuple, tuple] = {}

    def gate(self, kind: str, *args):
        key = (kind,) + args
        if key not in self.keys:
            token = ('v3gate', len(self.keys))
            self.keys[key] = token
            self.nodes[token] = key
        return self.keys[key]

    def invert(self, a):
        if isinstance(a, int): return 1 - a
        if a in self.nodes and self.nodes[a][0] == 'not': return self.nodes[a][1]
        return self.gate('not', a)

    def binary(self, kind, a, b):
        if kind == 'xor':
            if a == b: return 0
            if a == 0: return b
            if b == 0: return a
            if a == 1: return self.invert(b)
            if b == 1: return self.invert(a)
        elif kind == 'and':
            if a == 0 or b == 0: return 0
            if a == 1 or a == b: return b
            if b == 1: return a
        else:
            if a == 1 or b == 1: return 1
            if a == 0 or a == b: return b
            if b == 0: return a
        if a == self.invert(b): return 1 if kind in ('xor', 'or') else 0
        # Stable ordering shares commutative gates without integer/string sorting.
        if repr(a) > repr(b): a, b = b, a
        return self.gate(kind, a, b)

    def mux(self, control, low, high, stage):
        if isinstance(control, int): return high if control else low
        if low == high: return low
        if low == 0 and high == 1: return control
        if low == 1 and high == 0: return self.invert(control)
        return self.gate(f'mux{stage}', control, low, high)

    def cone(self, outputs) -> tuple[set[tuple], set[object]]:
        seen: set[tuple] = set(); leaves: set[object] = set()
        def visit(token):
            if isinstance(token, int): return
            if token not in self.nodes:
                leaves.add(token); return
            if token in seen: return
            seen.add(token)
            for arg in self.nodes[token][1:]: visit(arg)
        for output in outputs: visit(output)
        return seen, leaves


def _add_bits(a: tuple, b: tuple, subtract: bool):
    circuit = _BitCircuit(); carry = int(subtract); outputs = []; carries = []
    for x, y in zip(a, b):
        if subtract: y = circuit.invert(y)
        pair = circuit.binary('xor', x, y)
        outputs.append(circuit.binary('xor', pair, carry))
        carry = circuit.binary('or', circuit.binary('and', x, y),
                               circuit.binary('and', pair, carry))
        carries.append(carry)
    return circuit, outputs, carries


def _barrel(a: tuple, b: tuple, op: str):
    circuit = _BitCircuit(); stages = [a]; equal = 0
    for stage in range(5):
        prior = stages[-1]; distance = 1 << stage; outputs = []
        for bit in range(32):
            source = bit - distance if op in ('sll', 'slli') else bit + distance
            shifted = prior[source] if 0 <= source < 32 else (
                prior[31] if op in ('sra', 'srai') else 0)
            equal += int(not isinstance(b[stage], int) and prior[bit] == shifted)
            outputs.append(circuit.mux(b[stage], prior[bit], shifted, stage))
        stages.append(tuple(outputs))
    return circuit, stages[-1], equal


def _transitions(value: int) -> int:
    return ((value ^ (value >> 1)) & MASK).bit_count()


def _trailing_zeros(value: int) -> int:
    return (value & -value).bit_length() - 1 if value else 32


def _operation_count(node: Expression) -> int:
    seen = set()
    def visit(n):
        if not n.children or n.canonical() in seen: return
        seen.add(n.canonical())
        for child in n.children: visit(child)
    visit(node)
    return len(seen)


@lru_cache(maxsize=16384)
def _feature_values(formula: str) -> tuple[float, ...]:
    original = parse_formula(formula); root = _normalize(original)
    values = dict.fromkeys(FEATURE_NAMES, 0.)
    root_symbols = _symbols(root)
    values['v3_normalized_node_reduction'] = max(0, _operation_count(original) - _operation_count(root))
    values['v3_proven_zero_lut'] = float(all(_wire_token(t) for t in root_symbols))
    values['v3_output_constant_bits'] = sum(isinstance(t, int) for t in root_symbols)
    values['v3_output_direct_wire_bits'] = sum(not isinstance(t, int) and _wire_token(t) for t in root_symbols)
    nodes: dict[str, Expression] = {}; references: Counter[str] = Counter()
    def collect(node):
        key = node.canonical(); references[key] += 1
        if key in nodes: return
        nodes[key] = node
        for child in node.children: collect(child)
    collect(root)
    demanded: dict[str, int] = {}
    barrel_cache: dict[str, tuple] = {}
    def demand(node, bits):
        key = node.canonical(); symbols = _symbols(node)
        bits &= sum(1 << bit for bit, token in enumerate(symbols) if not isinstance(token, int))
        new = bits & ~demanded.get(key, 0)
        if not new: return
        demanded[key] = demanded.get(key, 0) | bits
        if not node.children: return
        family = _family(str(node.value)); a = node.children[0]
        if family == 'wire': demand(a, new); return
        b = node.children[1]; asy, bsy = _symbols(a), _symbols(b)
        if symbols == asy: demand(a, new); return
        if symbols == bsy: demand(b, new); return
        if family == 'logic': demand(a, new); demand(b, new)
        elif family == 'shift':
            circuit, outputs, equal = barrel_cache.setdefault(key, _barrel(asy, bsy, str(node.value)))
            _, leaves = circuit.cone(outputs[i] for i in range(32) if new & (1 << i))
            demand(a, sum(1 << i for i, token in enumerate(asy) if token in leaves))
            demand(b, 31)
        elif family == 'adder':
            # Sum/carry fan-in is conservatively the lower prefix. Bit-level
            # identity removes untouched output bits from resource cost below.
            demand(a, (1 << new.bit_length()) - 1); demand(b, (1 << new.bit_length()) - 1)
        elif node.value == 'mul':
            for variable, constant in ((a, b), (b, a)):
                c = _constant(_symbols(constant))
                if c is not None and c and c & (c - 1) == 0:
                    demand(variable, new >> (c.bit_length() - 1)); return
            demand(a, (1 << new.bit_length()) - 1); demand(b, (1 << new.bit_length()) - 1)
        else: demand(a, MASK); demand(b, MASK)
    demand(root, MASK)
    live = {key for key, n in nodes.items() if n.children and demanded.get(key, 0)}
    values['v3_live_ops'] = len(live)
    values['v3_dead_ops'] = sum(bool(n.children) for n in nodes.values()) - len(live)
    values['v3_shared_live_ops'] = sum(references[k] > 1 for k in live)
    values['v3_max_fanout'] = max((references[k] for k in live), default=0)
    def depth(node):
        if node.canonical() not in live: return 0
        return 1 + max((depth(c) for c in node.children), default=0)
    values['v3_live_depth'] = depth(root)
    for key in live:
        node = nodes[key]; bits = demanded[key]; family = _family(str(node.value))
        sy = _symbols(node); child_sy = [_symbols(c) for c in node.children]
        values['v3_live_demand_bits'] += bits.bit_count()
        values['v3_demand_span_sum'] += bits.bit_length()
        values['v3_operand_unknown_bits'] += sum(sum(not isinstance(t, int) for t in ts) for ts in child_sy)
        for child in node.children:
            ck = child.canonical()
            if ck not in live: continue
            values['v3_live_edges'] += 1
            values['v3_reconvergent_edges'] += int(references[ck] > 1)
            child_family = _family(str(child.value))
            name = f'v3_edge_{family}_{child_family}'
            if name in values: values[name] += 1
        if family == 'wire': continue
        a, b = child_sy
        if family == 'logic':
            unique = {sy[i] for i in range(32) if bits & (1 << i) and sy[i] not in (a[i], b[i])}
            # Complementing a Boolean comparator output may be absorbed in
            # carry polarity. Count it separately; this is a resource heuristic.
            fold = node.value in ('xor', 'xori') and any(
                _family(str(c.value)) == 'compare' for c in node.children) and any(
                _constant(ts) == 1 for ts in child_sy)
            values['v3_compare_polarity_folds'] += int(fold)
            values['v3_logic_output_bits'] += 0 if fold else len(unique)
        elif family == 'adder':
            circuit, sums, carries = _add_bits(a, b, node.value == 'sub')
            upto = bits.bit_length()
            # A sum shared across several bits maps once; direct wires cost 0.
            nonwire = {t for t in sums[:upto] if not isinstance(t, int) and t not in a and t not in b}
            values['v3_adder_sum_bits'] += len(nonwire)
            values['v3_adder_sum_bits_max'] = max(values['v3_adder_sum_bits_max'], len(nonwire))
            variable_carries = [i for i, t in enumerate(carries[:max(0, upto - 1)]) if not isinstance(t, int)]
            values['v3_adder_carry_bits'] += len(variable_carries)
            run = longest = 0
            for i in range(max(0, upto - 1)):
                run = run + 1 if i in variable_carries else 0; longest = max(longest, run)
            values['v3_adder_carry_run_max'] = max(values['v3_adder_carry_run_max'], longest)
            values['v3_adder_carry_start_sum'] += min(variable_carries, default=0)
            values['v3_adder_output_token_reuse'] += sum(not isinstance(t, int) for t in sums[:upto]) - len(set(t for t in sums[:upto] if not isinstance(t, int)))
            for operand in (a, b):
                c = _constant(operand)
                if c is None: continue
                values['v3_adder_constant_count'] += 1
                values['v3_adder_constant_popcount'] += c.bit_count()
                values['v3_adder_constant_transitions'] += _transitions(c)
                values['v3_adder_constant_trailing_zeros'] += _trailing_zeros(c)
        elif family == 'shift':
            circuit, outputs, equal = barrel_cache[key]
            gates, leaves = circuit.cone(outputs[i] for i in range(32) if bits & (1 << i))
            muxes = [t for t in gates if circuit.nodes[t][0].startswith('mux')]
            values['v3_barrel_live_muxes'] += len(muxes)
            values['v3_barrel_live_muxes_max'] = max(values['v3_barrel_live_muxes_max'], len(muxes))
            values['v3_barrel_live_stages'] += len({circuit.nodes[t][0] for t in muxes})
            values['v3_barrel_constant_data_count'] += int(_constant(a) is not None)
            values['v3_barrel_source_bits'] += len({t for t in a if t in leaves and not isinstance(t, int)})
            values['v3_barrel_control_bits'] += len({t for t in b[:5] if t in leaves and not isinstance(t, int)})
            values['v3_barrel_muxes_saved_by_equal_branches'] += equal
        elif family == 'compare':
            constants = [_constant(ts) for ts in child_sy]
            if all(c is None for c in constants):
                values['v3_compare_variable_bits'] += max(_widths(a)[0], _widths(b)[0])
            else:
                values['v3_compare_constant_count'] += 1
                # iCE40 carry comparison is asymmetric: a constant on the
                # left requires variable operand inversion for carry inputs.
                # This models that width, without pretending to map the RTL.
                if constants[0] is not None:
                    values['v3_compare_constant_inverted_bits'] += sum(
                        not isinstance(t, int) for t in b)
                for c in constants:
                    if c is None: continue
                    values['v3_compare_constant_width'] += c.bit_length()
                    values['v3_compare_constant_popcount'] += c.bit_count()
                    values['v3_compare_constant_transitions'] += _transitions(c)
                    values['v3_compare_constant_trailing_zeros'] += _trailing_zeros(c)
            values['v3_compare_boolean_operand_count'] += sum(_widths(ts)[0] <= 1 for ts in child_sy)
            values['v3_compare_signed_count'] += int(node.value in ('slt', 'slti'))
        elif family == 'multiply':
            aw, asign = _widths(a); bw, bsign = _widths(b)
            signed_a = node.value in ('mul', 'mulh', 'mulhsu'); signed_b = node.value in ('mul', 'mulh')
            aw = min(aw, asign) if signed_a else aw; bw = min(bw, bsign) if signed_b else bw
            high = bits.bit_length() - 1 + (32 if node.value != 'mul' else 0)
            values['v3_mul_high_half_count'] += int(node.value != 'mul')
            values['v3_mul_signed_operand_count'] += int(signed_a) + int(signed_b)
            values['v3_mul_output_demand_span'] += bits.bit_length()
            values['v3_mul_repeated_operand_count'] += int(a == b)
            ca, cb = _constant(a), _constant(b)
            if ca is None and cb is None:
                heights = Counter(i + j for i in range(aw) for j in range(bw) if i + j <= high)
                values['v3_mul_variable_partial_products'] += sum(heights.values())
                values['v3_mul_occupied_columns'] += len(heights)
                values['v3_mul_peak_column_height'] = max(values['v3_mul_peak_column_height'], max(heights.values(), default=0))
                # Reduce each column to two rows, carrying compressed terms to
                # the next column; a reusable full-adder/compressor proxy.
                incoming = 0
                for column in range(high + 1):
                    compressors = max(0, (heights[column] + incoming - 1) // 2)
                    values['v3_mul_compressor_bits'] += compressors
                    incoming = compressors
            else:
                c, width = (ca, bw) if ca is not None else (cb, aw)
                assert c is not None
                signed_constant = c - (1 << 32) if c & (1 << 31) else c
                values['v3_mul_constant_csd_terms'] += _csd_terms(signed_constant)
                lanes = [max(0, min(width, high - i + 1)) for i in range(32) if c & (1 << i)]
                values['v3_mul_constant_adder_bits'] += max(0, sum(lanes) - max(lanes, default=0))
    return tuple(float(values[name]) for name in FEATURE_NAMES)


def feature_dict(formula: str) -> dict[str, float]:
    """Return the stable formula-only schema (all values finite/nonnegative)."""
    canonical = parse_formula(formula).canonical()
    return dict(zip(FEATURE_NAMES, _feature_values(canonical)))


def feature_matrix(formulas: Iterable[str]):
    """Convert strings to a matrix in FEATURE_NAMES order; no row metadata."""
    import numpy as np
    values = [_feature_values(parse_formula(formula).canonical()) for formula in formulas]
    return np.asarray(values, dtype=float).reshape((-1, len(FEATURE_NAMES)))
