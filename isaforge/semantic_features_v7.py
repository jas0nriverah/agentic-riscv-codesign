"""Bounded RV32 semantic descriptors, separate from original implementation cost.

Only exact structural correlation patterns and modular affine islands rewrite.
Every changed local expression has a QF_BV32 proof; recursive congruence composes
these into an original-to-final certificate. Missing/unknown solvers and budgets
fall back, never alter labels or implement an original-circuit zero override.
"""
from __future__ import annotations
from collections import Counter
from dataclasses import asdict, dataclass
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import time

from .features import Expression, parse_formula

SCHEMA = 'isaforge-semantic-features-v7-v1'
MASK = (1 << 32)-1
MODULUS = 1 << 32
MODES = ('bit', 'affine', 'combined')
BIT_NAMES = tuple('v7_bit_'+name for name in (
    'or_sub_count', 'sub_and_count', 'mul_possible_one_bits', 'mul_unsigned_width_sum',
    'mul_interpreted_width_sum', 'mul_signed_unknown_sign_count', 'output_unknown_bits', 'normalized_ops'))
AFFINE_NAMES = tuple('v7_affine_'+name for name in (
    'island_count', 'cancelled_atom_count', 'repeated_atom_occurrences', 'coefficient_digit_sum',
    'mul_possible_one_bits', 'mul_interpreted_width_sum', 'output_unknown_bits', 'normalized_ops'))
FEATURE_NAMES_BY_MODE = {'bit': BIT_NAMES, 'affine': AFFINE_NAMES, 'combined': BIT_NAMES+AFFINE_NAMES}
FEATURE_NAMES = FEATURE_NAMES_BY_MODE['combined']


@dataclass(frozen=True)
class Budget:
    max_atoms: int = 16
    max_island_ops: int = 64
    max_output_ops: int = 128
    growth_factor: int = 2
    growth_extra: int = 32
    max_passes: int = 4
    proof_timeout_ms: int = 500

    def __post_init__(self):
        limits = (16, 64, 128, 2, 32, 4, 500)
        if any(type(v) is not int or not 1 <= v <= maximum
               for v, maximum in zip(asdict(self).values(), limits)):
            raise ValueError('Budget must be positive and cannot exceed the fixed safety limits')


class BudgetExceeded(ValueError):
    pass


class ProofError(ValueError):
    """A SAT local miter is a correctness defect, never a benign fallback."""
    pass


def source_hashes():
    return {name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
            for name in ("semantic_features_v7.py", "features.py")}


def _op(name, a, b): return Expression(name, (a, b))
def _literal(n): return Expression(n & MASK)
def _constant(node): return (node.value & MASK) if not node.children and isinstance(node.value, int) else None

def _ops(node):
    return int(bool(node.children))+sum(_ops(c) for c in node.children)


def _affine(node):
    return bool(node.children) and (node.value in ('add', 'addi', 'sub') or
        (node.value in ('sll', 'slli') and _constant(node.children[1]) is not None))


def _digits(value):
    """Canonical signed nonadjacent digits for a coefficient modulo 2**32."""
    value &= MASK
    if value >= (1 << 31): value -= MODULUS
    sign = -1 if value < 0 else 1
    value = abs(value); result = []; position = 0
    while value:
        if value & 1:
            digit = 2-(value & 3); result.append((position, sign*digit)); value -= digit
        value >>= 1; position += 1
    return result


def _collect(node, budget):
    coefficients = Counter(); atoms = {}; occurrences = Counter(); operations = set(); constant = 0
    def visit(current, scale):
        nonlocal constant
        literal = _constant(current)
        if literal is not None:
            constant = (constant+scale*literal) & MASK
        elif _affine(current):
            operations.add(current.canonical())
            if len(operations) > budget.max_island_ops: raise BudgetExceeded('affine unique-operation budget')
            a, b = current.children
            if current.value in ('sll', 'slli'):
                visit(a, (scale << (_constant(b) & 31)) & MASK)
            else:
                visit(a, scale); visit(b, (-scale if current.value == 'sub' else scale) & MASK)
        else:
            key = current.canonical(); atoms[key] = current; occurrences[key] += 1
            coefficients[key] = (coefficients[key]+scale) & MASK
            if len(atoms) > budget.max_atoms: raise BudgetExceeded('affine opaque-atom budget')
    visit(node, 1)
    return coefficients, atoms, occurrences, constant


def _rebuild(collected, limit=None):
    coefficients, atoms, _, constant = collected; terms = []
    term_count = int(bool(constant)); cost = 0
    for key in atoms:
        for position, sign in _digits(coefficients[key]):
            term_count += 1; cost += _ops(atoms[key])+int(position != 0)+int(sign < 0)
    cost += max(0, term_count-1)
    if limit is not None and cost > limit: raise BudgetExceeded("affine reconstruction budget")
    for key in sorted(atoms):
        for position, sign in _digits(coefficients[key]):
            # NAF may reach bit31 but never emits a shift by32.
            term = atoms[key] if position == 0 else _op('slli', atoms[key], _literal(position))
            terms.append(term if sign > 0 else _op('sub', _literal(0), term))
    if constant: terms.append(_literal(constant))
    def balanced(items):
        if not items: return _literal(0)
        if len(items) == 1: return items[0]
        middle = len(items)//2
        return _op('add', balanced(items[:middle]), balanced(items[middle:]))
    return balanced(terms)


def _masked_operand(node, operations):
    if node.value not in operations or not node.children: return None
    a, b = node.children
    if _constant(b) is not None: return a, _constant(b)
    if _constant(a) is not None: return b, _constant(a)
    return None


def _correlation(node):
    if node.value != 'sub' or not node.children: return None
    left, right = node.children
    first = _masked_operand(left, ('or', 'ori'))
    if first is not None and first[0] == right:
        x, mask = first
        return _op('andi', _op('xori', x, _literal(MASK)), _literal(mask)), 'or_sub', [x]
    second = _masked_operand(right, ('and', 'andi'))
    if second is not None and second[0] == left:
        x, mask = second
        return _op('andi', x, _literal(MASK ^ mask)), 'sub_and', [x]
    return None


@lru_cache(maxsize=1)
def solver_identity():
    try:
        import z3
    except ImportError:
        return {'available': False}
    library = Path(z3.__file__)
    return {'available': True, 'version': z3.get_version_string(),
            'python_module_sha256': hashlib.sha256(library.read_bytes()).hexdigest(),
            'native_libraries_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted((library.parent/'lib').glob('libz3*')) if p.is_file()}}


def _prove(before, after, atoms, timeout_ms):
    """Universal local proof. Opaque atoms are independent shared RV32 words."""
    identity = solver_identity()
    if not identity['available']: return {'result': 'unavailable', 'solver': identity}
    import z3
    bindings = {a.canonical(): z3.BitVec('opaque_'+str(i), 32)
                for i, a in enumerate(sorted(set(atoms), key=lambda x: x.canonical()))}
    def encode(node):
        key = node.canonical()
        if key in bindings: return bindings[key]
        value = _constant(node)
        if value is not None: return z3.BitVecVal(value, 32)
        a, b = (encode(c) for c in node.children)
        if node.value in ('add', 'addi'): return a+b
        if node.value == 'sub': return a-b
        if node.value in ('sll', 'slli'): return a << (b & 31)
        if node.value in ('and', 'andi'): return a & b
        if node.value in ('or', 'ori'): return a | b
        if node.value in ('xor', 'xori'): return a ^ b
        raise ValueError('Unbound opaque atom in local proof')
    solver = z3.SolverFor('QF_BV'); solver.set(timeout=timeout_ms)
    solver.add(encode(before) != encode(after)); query = solver.to_smt2()
    started = time.perf_counter(); cpu_started = time.process_time()
    result = solver.check()
    return {'result': str(result), 'reason_unknown': solver.reason_unknown() if result == z3.unknown else None,
            'solver': identity, 'elapsed_ms': (time.perf_counter()-started)*1000,
            'cpu_ms': (time.process_time()-cpu_started)*1000, 'query_smt2': query,
            'query_sha256': hashlib.sha256(query.encode()).hexdigest(), 'opaque_atoms': sorted(bindings)}


class _ProofEngine:
    """One shared500ms formula budget, including all modes and rewrite passes."""
    def __init__(self, budget):
        self.budget = budget; self.failed = None; self.cache = {}
        self.wall_ms = 0.; self.cpu_ms = 0.; self.calls = 0; self.hits = 0

    def fail(self, reason):
        if self.failed is None: self.failed = reason

    def prove(self, before, after, atoms):
        key = (before.canonical(), after.canonical(), tuple(sorted(a.canonical() for a in atoms)))
        if key in self.cache:
            self.hits += 1
            return {**self.cache[key], 'reused': True, 'charged_solver_ms': 0.}
        remaining = self.budget.proof_timeout_ms-self.wall_ms
        if remaining < 1:
            self.fail('proof_budget'); return {'result': 'budget', 'scope': 'shared formula proof time'}
        proof = _prove(before, after, atoms, int(remaining)); self.calls += 1
        self.wall_ms += proof.get('elapsed_ms', 0.); self.cpu_ms += proof.get('cpu_ms', 0.)
        proof = {**proof, 'reused': False, 'charged_solver_ms': proof.get('elapsed_ms', 0.)}
        if proof['result'] == 'sat': raise ProofError('SAT semantic rewrite miter: '+str(key))
        if proof['result'] != 'unsat': self.fail('proof_'+proof['result'])
        if self.wall_ms > self.budget.proof_timeout_ms:
            self.fail('proof_budget'); proof = {**proof, 'solver_result': proof['result'], 'result': 'budget'}
        self.cache[key] = proof
        return proof

    def metadata(self):
        return {'scope': 'one input formula, all modes and passes; charge once per formula',
                'solver_seconds': self.cpu_ms/1000, 'solver_wall_seconds': self.wall_ms/1000,
                'unique_solver_calls': self.calls, 'local_cache_hits': self.hits,
                'fallback_reason': self.failed, 'timeout_ms': self.budget.proof_timeout_ms}


def _normalize(node, mode, budget, engine):
    original = node; steps = []; attempts = []; limit = min(budget.max_output_ops, budget.growth_factor*_ops(node)+budget.growth_extra)
    status = 'accepted'; passes = 0
    def propose(before, after, path, kind, atoms):
        if before == after: return before
        if _ops(after) > limit:
            attempts.append({'path': list(path), 'kind': kind, 'before': before.canonical(),
                             'after': after.canonical(), 'proof': {'result': 'budget'}})
            engine.fail('output_budget'); return before
        proof = engine.prove(before, after, atoms)
        event = {'path': list(path), 'kind': kind, 'before': before.canonical(), 'after': after.canonical(), 'proof': proof}
        attempts.append(event)
        event['proof_id'] = hashlib.sha256(json.dumps({'schema': SCHEMA, 'kind': kind, 'before': event['before'],
            'after': event['after'], 'proof_result': proof['result'], 'opaque_atoms': proof.get('opaque_atoms', []),
            'solver': proof.get('solver')}, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        if proof['result'] == 'sat': raise ProofError('SAT semantic rewrite miter: '+event['proof_id'])
        if proof['result'] == 'unsat': steps.append(event); return after
        return before
    def visit(current, path=(), parent_affine=False):
        if engine.failed is not None: return current
        eligible = _affine(current) if mode in ('affine', 'combined') else False
        children = tuple(visit(c, path+(i,), eligible and (current.value not in ('sll', 'slli') or i == 0))
                         for i, c in enumerate(current.children))
        current = Expression(current.value, children)
        if mode in ('bit', 'combined'):
            replacement = _correlation(current)
            if replacement is not None:
                after, kind, atoms = replacement
                current = propose(current, after, path, kind, atoms)
        if mode in ('affine', 'combined') and _affine(current) and not parent_affine:
            try:
                collected = _collect(current, budget)
                current = propose(current, _rebuild(collected, limit), path, 'affine', list(collected[1].values()))
            except BudgetExceeded as error:
                attempts.append({'path': list(path), 'kind': 'affine', 'before': current.canonical(),
                                 'after': current.canonical(), 'proof': {'result': 'budget', 'reason': str(error)}})
                engine.fail(str(error))
        return current
    stable = False
    for passes in range(1, budget.max_passes+1):
        updated = visit(node)
        if _ops(updated) > limit:
            status = 'fallback_output_budget'; engine.fail('output_budget'); break
        if updated == node: stable = True; node = updated; break
        node = updated
    if not stable:
        status = 'fallback_pass_or_output_budget'; engine.fail('pass_or_output_budget'); node = original; steps = []
    if engine.failed is not None:
        status = 'fallback_original'; node = original; steps = []
    if not node.children:
        # Retain the public operation-root grammar even for a semantic wire/constant.
        wrapped = _op('addi', node, _literal(0))
        node = propose(node, wrapped, (), 'root_wrapper', [] if _constant(node) is not None else [node])
        if not node.children:
            status = 'fallback_root_wrapper_proof'; node = original; steps = []
    return node, {'status': status, 'passes': passes, 'steps': steps, 'attempts': attempts,
                  'certificate': {'method': 'recursive congruence plus universal local QF_BV32',
                                  'initial': original.canonical(), 'final': node.canonical(), 'steps': steps}}


def _known(node):
    """Sound independent known-zero/known-one masks; no assumed correlations."""
    literal = _constant(node)
    if literal is not None: return MASK ^ literal, literal
    if not node.children: return 0, 0
    if node.value == 'lui': return _known(node.children[0])
    az, ao = _known(node.children[0]); bz, bo = _known(node.children[1]); op = node.value
    if op in ('and', 'andi'): return az | bz, ao & bo
    if op in ('or', 'ori'): return az & bz, ao | bo
    if op in ('xor', 'xori'): return (az & bz) | (ao & bo), (az & bo) | (ao & bz)
    distance = _constant(node.children[1])
    if op in ('sll', 'slli', 'srl', 'srli', 'sra', 'srai') and distance is not None:
        k = distance & 31
        if op in ('sll', 'slli'): return ((az << k) | ((1 << k)-1)) & MASK, (ao << k) & MASK
        top = (MASK ^ ((1 << (32-k))-1)) if k else 0
        if op in ('srl', 'srli'): return (az >> k) | top, ao >> k
        return (az >> k) | (top if az & (1 << 31) else 0), (ao >> k) | (top if ao & (1 << 31) else 0)
    if op in ('slt', 'slti', 'sltu', 'sltiu'): return MASK ^ 1, 0
    if op in ('add', 'addi', 'sub'):
        zero = one = 0; carry = {int(op == 'sub')}
        if op == 'sub': bz, bo = bo, bz
        for bit in range(32):
            aa = {0} if az >> bit & 1 else ({1} if ao >> bit & 1 else {0, 1})
            bb = {0} if bz >> bit & 1 else ({1} if bo >> bit & 1 else {0, 1})
            sums = {a+b+c for a in aa for b in bb for c in carry}; outputs = {v & 1 for v in sums}
            if outputs == {0}: zero |= 1 << bit
            if outputs == {1}: one |= 1 << bit
            carry = {v >> 1 for v in sums}
        return zero, one
    if op in ('mul', 'mulh', 'mulhu', 'mulhsu'):
        if az == MASK or bz == MASK: return MASK, 0
        if op == 'mul':
            low_a = next((i for i in range(32) if not az >> i & 1), 32)
            low_b = next((i for i in range(32) if not bz >> i & 1), 32)
            return (1 << min(32, low_a+low_b))-1, 0
    return 0, 0


def _operand_rows(node, path=()):
    result = []
    if node.value in ('mul', 'mulh', 'mulhu', 'mulhsu'):
        for index, child in enumerate(node.children):
            zero, one = _known(child); possible = MASK ^ zero
            signed = node.value == 'mulh' or (node.value == 'mulhsu' and index == 0)
            sign = 'zero' if zero & (1 << 31) else ('one' if one & (1 << 31) else 'unknown')
            width = possible.bit_length()
            interpreted = width
            if signed:
                interpreted = (min(32, max(1, width+1)) if sign == 'zero' else
                    min(32, max(1, (MASK ^ one).bit_length()+1)) if sign == 'one' else 32)
            result.append({'path': list(path), 'operation': node.value, 'operand': index, 'formula': child.canonical(),
                'signed': signed, 'sign': sign, 'possible_one_bits': possible.bit_count(),
                'unsigned_width': width, 'interpreted_width': interpreted, 'unsigned_minimum': one,
                'unsigned_maximum': possible})
    for i, child in enumerate(node.children): result.extend(_operand_rows(child, path+(i,)))
    return result


def _summary(original, normalized, mode, budget):
    operands = _operand_rows(normalized); zero, one = _known(normalized)
    support = sum(r['possible_one_bits'] for r in operands)
    width = sum(r['interpreted_width'] for r in operands)
    unknown = 32-(zero | one).bit_count()
    if mode == 'bit':
        patterns = Counter(); seen = set()
        def visit(n):
            key = n.canonical()
            if key in seen: return
            seen.add(key)
            rule = _correlation(n)
            if rule is not None: patterns[rule[1]] += 1
            for child in n.children: visit(child)
        visit(original)
        values = (patterns['or_sub'], patterns['sub_and'], support, sum(r['unsigned_width'] for r in operands),
                  width, sum(r['signed'] and r['sign'] == 'unknown' for r in operands), unknown, _ops(normalized))
    else:
        totals = Counter(); seen_islands = set()
        def visit(n, parent=False):
            island = _affine(n)
            if island and not parent and n.canonical() not in seen_islands:
                seen_islands.add(n.canonical())
                try:
                    coefficients, atoms, occurrences, _ = _collect(n, budget)
                    totals['islands'] += 1; totals['cancelled'] += sum(coefficients[k] == 0 for k in atoms)
                    totals['repeated'] += sum(v-1 for v in occurrences.values())
                    totals['digits'] += sum(len(_digits(c)) for c in coefficients.values())
                except BudgetExceeded: pass
            for i, child in enumerate(n.children): visit(child, island and (n.value not in ('sll', 'slli') or i == 0))
        visit(original)
        values = (totals['islands'], totals['cancelled'], totals['repeated'], totals['digits'], support, width, unknown, _ops(normalized))
    return dict(zip(FEATURE_NAMES_BY_MODE[mode], values))


def analyze_modes(formula, budget=None):
    """Analyze all modes under one proof budget; any rejected proof/budget rolls all back.

    Combined learned columns are exact independent bit+affine concatenation.
    The combined normal form is only for the separately declared legacy control.
    Pattern/island summaries count unique ORIGINAL structural subexpressions;
    occurrences inside an affine island retain their algebraic multiplicity.
    """
    budget = Budget() if budget is None else budget
    if not isinstance(budget, Budget): raise ValueError('budget must be a Budget')
    original = parse_formula(formula); engine = _ProofEngine(budget); normalized = {}; metadata = {}
    for mode in MODES:
        normalized[mode], metadata[mode] = _normalize(original, mode, budget, engine)
    if engine.failed is not None:
        for mode in MODES:
            normalized[mode] = original; metadata[mode]['status'] = 'fallback_original'
            metadata[mode]['discarded_steps'] = metadata[mode]['steps']; metadata[mode]['steps'] = []
            metadata[mode]['certificate'] = {'method': 'identity fallback', 'initial': original.canonical(),
                                            'final': original.canonical(), 'steps': []}
    blocks = {mode: _summary(original, normalized[mode], mode, budget) for mode in ('bit', 'affine')}
    blocks['combined'] = {**blocks['bit'], **blocks['affine']}
    result = {}; runtime = source_hashes()
    for mode in MODES:
        metadata[mode].update({'runtime_source_sha256': runtime, 'budget': asdict(budget), 'solver': solver_identity(), 'proof_engine': engine.metadata(),
            'original_ops': _ops(original), 'normalized_ops': _ops(normalized[mode]),
            'original_multiply_operands': _operand_rows(original),
            'normalized_multiply_operands': _operand_rows(normalized[mode]), 'original_zero_override': False})
        result[mode] = {'schema': SCHEMA, 'mode': mode, 'input_formula': formula, 'original_formula': original.canonical(),
                       'normalized_formula': normalized[mode].canonical(), 'features': blocks[mode], 'metadata': metadata[mode]}
    return result


def analyze_formula(formula, mode='combined', budget=None):
    if mode not in MODES: raise ValueError('Unsupported V7 semantic mode')
    return analyze_modes(formula, budget)[mode]


def normalize_formula(formula, mode='combined', budget=None):
    return analyze_formula(formula, mode, budget)['normalized_formula']


def feature_dict(formula, mode='combined', budget=None):
    return analyze_formula(formula, mode, budget)['features']


def feature_vector(formula, mode='combined', budget=None):
    values = feature_dict(formula, mode, budget)
    return [values[name] for name in FEATURE_NAMES_BY_MODE[mode]]


def feature_matrix(rows, mode='combined', budget=None):
    """Source-only list matrix and proof records; ignore every nonformula field."""
    records = [analyze_formula(row['formula'], mode, budget) for row in rows]
    return [[r['features'][name] for name in FEATURE_NAMES_BY_MODE[mode]] for r in records], records
