#!/usr/bin/env python3
"""Seal32 original/CSD implementation pairs; prove formulas, never measure area."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from isaforge.features import Expression, parse_formula
from isaforge.rtl import generate_rtl

SCHEMA = 'isaforge-v10-csd-hardware-preparation-v1'
CONSTANTS = (11, 44, 85, 340, 341, 511, 1364, 2044)
CONTEXTS = ('direct_product', 'add_after_product', 'sub_before_product', 'masked_sub_before_product')
V9 = 'results/2026-10-15-v9-coverage-development'
V9_CANDIDATES_SHA256 = '74b1ef78b3d97ab34c940f464345bef21fd8f2441a3e09d6cb21daaa686a5354'
PROOF_TIMEOUT_MS = 60000
RTL_TIMEOUT_SECONDS = 60
VERIFY_SEED = 2026101522
FAILED_PREPARATION_COMMIT = '05b19728803d96a5754ed695f543a97fc49ba1b1'
FAILED_PREPARATION = 'results/2026-10-15-v10-csd-hardware'
IMPLEMENTATION_FAILURE_COMMIT = '978025afd18c49226f6b04414b885c90daca5483'
IMPLEMENTATION_FAILURE = 'results/2026-10-15-v10a-csd-hardware'
LEMMA_TIMEOUT_COMMIT = '7204c571c6274d0bd0bdb2ccdfe1200ef96c105e'
LEMMA_TIMEOUT_PREPARATION = 'results/2026-10-15-v10b-csd-hardware'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def digest(data): return hashlib.sha256(data).hexdigest()
def read(path): return json.loads(Path(path).read_text())
def now(): return datetime.now(timezone.utc).isoformat()
def encoded(value): return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write((json.dumps(value, indent=2, allow_nan=False) + '\n').encode())


def record(path, root):
    path = Path(path).resolve()
    return {'path': os.path.relpath(path, Path(root).resolve()), 'sha256': sha(path)}


def checked(entry, root):
    require(isinstance(entry, dict) and set(entry) == {'path', 'sha256'}, 'Invalid file binding')
    require(isinstance(entry['path'], str) and not Path(entry['path']).is_absolute(), 'Relative file binding required')
    path = (Path(root) / entry['path']).resolve()
    require(path.is_file() and sha(path) == entry['sha256'], 'Changed bound file: ' + entry['path'])
    return path


def validate_formula(formula, *, rewritten=False):
    root = parse_formula(formula)
    require(root.canonical() == formula, 'Canonical formula required')
    count = 0
    pending = [root]
    while pending:
        node = pending.pop()
        if not node.children:
            require(node.value in ('in0', 'in1') or type(node.value) is int, 'Invalid operand')
            continue
        count += 1
        allowed = {'add', 'sub', 'and', 'addi', 'andi', 'slli'} | (set() if rewritten else {'mul'})
        require(node.value in allowed, 'Operation outside fixed unsigned low-product grammar')
        if node.value in ('addi', 'andi'):
            require(-2048 <= node.children[1].value <= 2047, 'Invalid signed12 immediate')
        elif node.value == 'slli':
            require(0 <= node.children[1].value <= 31, 'Invalid shift immediate')
        pending.extend(node.children)
    require(count <= 32, 'Formula exceeds32 operation bound')
    return root


def csd_digits(constant):
    require(type(constant) is int and constant in CONSTANTS, 'Constant outside fixed positive encodable grid')
    digits = []
    position = 0
    remaining = constant
    while remaining:
        digit = (1 if remaining == 1 else 2 - remaining % 4) if remaining % 2 else 0
        if digit:
            digits.append((position, digit))
        remaining = (remaining - digit) // 2
        position += 1
    require(sum(d * (1 << p) for p, d in digits) == constant, 'Invalid CSD reconstruction')
    require(1 <= len(digits) <= 5 and max(p for p, _ in digits) <= 11, 'CSD bound exceeded')
    require(digits[-1][1] == 1 and all(b[0] - a[0] > 1 for a, b in zip(digits, digits[1:])), 'Nonadjacent CSD required')
    return tuple(reversed(digits))


def op(name, a, b): return Expression(name, (a, b))


def constant_product(operand, constant):
    digits = csd_digits(constant)
    def term(position):
        return operand if position == 0 else op('slli', operand, Expression(position))
    result = term(digits[0][0])
    for position, sign in digits[1:]:
        result = op('add' if sign == 1 else 'sub', result, term(position))
    return result


def rewrite(formula, constant):
    root = validate_formula(formula)
    replacements = 0
    def visit(node):
        nonlocal replacements
        if node.value == 'mul':
            require(node.children[1].canonical() == f'addi(0,{constant})', 'Exact original constant operand required')
            require(not any(n.value == 'mul' for n in walk(node.children[0])), 'Nested multiplication forbidden')
            replacements += 1
            return constant_product(node.children[0], constant)
        return Expression(node.value, tuple(visit(c) for c in node.children))
    output = visit(root).canonical()
    require(replacements == 1, 'Exactly one original product required')
    validate_formula(output, rewritten=True)
    return output


def walk(node):
    yield node
    for child in node.children:
        yield from walk(child)


def fixed_pairs(source_rows=None):
    output = []
    originals = []
    for constant in CONSTANTS:
        for context, formula in zip(CONTEXTS, (
            f'mul(in0,addi(0,{constant}))',
            f'add(mul(in0,addi(0,{constant})),in1)',
            f'mul(sub(in0,in1),addi(0,{constant}))',
            f'mul(sub(andi(in0,63),in1),addi(0,{constant}))',
        )):
            suffix = digest(formula.encode())
            node = validate_formula(formula)
            original = {'formula': formula, 'context': context, 'constant_u32': constant,
                'candidate_id': 'v9-coverage:' + suffix,
                'operation_count': sum(bool(n.children) for n in walk(node))}
            originals.append(original)
            output.append({'pair_id': 'v10-csd:' + suffix, 'source_candidate_id': original['candidate_id'],
                'formula': formula, 'context': context, 'constant_u32': constant,
                'operation_count': original['operation_count'], 'rewritten_formula': rewrite(formula, constant)})
    if source_rows is not None:
        selected = [r for r in source_rows if 'constant_u32' in r]
        require(selected == originals, 'Original32 V9 source rows differ from exact fixed grid')
    require(len({r['pair_id'] for r in output}) == 32, 'Exactly32 stable distinct pairs required')
    return output


def formula_query(original, rewritten, *, operand_lemma=False):
    import z3
    left, right = validate_formula(original), validate_formula(rewritten, rewritten=True)
    # SMT let aliases contain context-local allocation IDs. Isolate each query
    # so unrelated earlier proofs/GC cannot change its exact serialization.
    context = z3.Context()
    inputs = {name: z3.BitVec('word' if operand_lemma and name == 'in0' else name, 32, ctx=context)
              for name in ('in0', 'in1')}
    def encode(node):
        if not node.children:
            return z3.BitVecVal(node.value, 32, ctx=context) if type(node.value) is int else inputs[node.value]
        a, b = (encode(child) for child in node.children)
        if node.value in ('add', 'addi'): return a + b
        if node.value == 'sub': return a - b
        if node.value in ('and', 'andi'): return a & b
        if node.value == 'mul': return a * b
        if node.value == 'slli': return a << b
        raise ValueError('Unsupported proof operation')
    solver = z3.SolverFor('QF_BV', ctx=context)
    solver.set(timeout=PROOF_TIMEOUT_MS)
    solver.add(encode(left) != encode(right))
    return solver


def congruence_certificate(original, rewritten):
    """Check one exact subtree substitution; abstract only identical operand ASTs.

    A universal identity for the unconstrained word remains true when that word
    is instantiated by ANY32-bit operand expression. Equality is preserved by
    every identical enclosing operation. No reachability/range premise is used.
    """
    before, after = validate_formula(original), validate_formula(rewritten, rewritten=True)
    replacements = []
    def compare(left, right, path):
        if left.value != 'mul':
            require(left.value == right.value and len(left.children) == len(right.children),
                'Whole-context AST node changed outside the product')
            for index, (a, b) in enumerate(zip(left.children, right.children)):
                compare(a, b, [*path, index])
            return
        operand, constant_node = left.children
        require(constant_node.value == 'addi' and constant_node.children[0] == Expression(0)
            and type(constant_node.children[1].value) is int, 'Exact decoded constant product required')
        constant = constant_node.children[1].value
        require(constant in CONSTANTS, 'Lemma constant outside fixed grid')
        require(not any(n.value == 'mul' for n in walk(operand)), 'Nested product forbidden')
        word = Expression('in0')
        def abstract(node):
            if node == operand:
                return word
            if node.value in ('add', 'sub') and len(node.children) == 2:
                return op(node.value, *(abstract(c) for c in node.children))
            if node.value == 'slli' and node.children[0] == operand:
                require(0 <= node.children[1].value <= 31, 'Invalid lemma shift')
                return op('slli', word, node.children[1])
            raise ValueError('Rewritten product contains a changed or foreign operand')
        lemma_after = abstract(right).canonical()
        replacements.append({'replacement_path': path, 'operand_formula': operand.canonical(),
            'constant_u32': constant, 'original_product': left.canonical(), 'rewritten_product': right.canonical(),
            'lemma_original_formula': f'mul(in0,addi(0,{constant}))', 'lemma_rewritten_formula': lemma_after})
    compare(before, after, [])
    require(len(replacements) == 1, 'Exactly one context-preserving replacement required')
    return {'schema': 'isaforge-v10-csd-congruence-v1', **replacements[0],
        'checked': 'All enclosing/unmodified AST nodes identical; each term uses the exact original operand AST',
        'logical_rule': 'Universal word identity instantiated with operand, then equality congruence through identical whole context'}


def prove_equivalence(original, rewritten):
    import z3
    certificate = congruence_certificate(original, rewritten)
    solver = formula_query(certificate['lemma_original_formula'], certificate['lemma_rewritten_formula'], operand_lemma=True)
    query = solver.to_smt2()
    whole_query = formula_query(original, rewritten).to_smt2()  # retained, not solved again
    started = time.monotonic()
    result = solver.check()
    proof = {'schema': 'isaforge-v10-csd-source-proof-v2', 'original_formula': original,
        'rewritten_formula': rewritten, 'method': 'universal QF_BV32 operand lemma plus exact whole-expression AST congruence',
        'inputs': ['in0:32', 'in1:32'], 'assumptions': [], 'timeout_ms': PROOF_TIMEOUT_MS,
        'result': str(result), 'elapsed_seconds': time.monotonic() - started,
        'query_smt2': query, 'query_sha256': digest(query.encode()), 'solver_version': z3.get_version_string(),
        'query_scope': 'universal unconstrained word:32; no range or reachability assumptions',
        'congruence': certificate, 'whole_expression_query_smt2': whole_query,
        'whole_expression_query_sha256': digest(whole_query.encode()),
        'whole_expression_query_status': 'diagnostic-only; not solved in amended preparation'}
    if result == z3.sat:
        proof['counterexample'] = {'word': solver.model().eval(z3.BitVec('word', 32, ctx=solver.ctx), model_completion=True).as_long()}
    elif result == z3.unknown:
        proof['reason_unknown'] = solver.reason_unknown()
    return proof


def validate_proof(proof, pair):
    require(proof.get('schema') == 'isaforge-v10-csd-source-proof-v2'
        and proof.get('original_formula') == pair['formula']
        and proof.get('rewritten_formula') == pair['rewritten_formula']
        and proof.get('method') == 'universal QF_BV32 operand lemma plus exact whole-expression AST congruence'
        and proof.get('inputs') == ['in0:32', 'in1:32'] and proof.get('assumptions') == []
        and proof.get('timeout_ms') == PROOF_TIMEOUT_MS and proof.get('result') == 'unsat',
        'Universal source proof absent or failed')
    require(digest(proof['query_smt2'].encode()) == proof['query_sha256'], 'Proof query hash differs')
    certificate = congruence_certificate(pair['formula'], pair['rewritten_formula'])
    require(proof.get('congruence') == certificate, 'Whole-context congruence certificate differs')
    require(formula_query(certificate['lemma_original_formula'], certificate['lemma_rewritten_formula'], operand_lemma=True).to_smt2()
        == proof['query_smt2'] and proof.get('query_scope') == 'universal unconstrained word:32; no range or reachability assumptions',
        'Proof query does not encode the exact unconstrained operand lemma')
    whole = formula_query(pair['formula'], pair['rewritten_formula']).to_smt2()
    require(proof.get('whole_expression_query_smt2') == whole
        and proof.get('whole_expression_query_sha256') == digest(whole.encode())
        and proof.get('whole_expression_query_status') == 'diagnostic-only; not solved in amended preparation',
        'Original whole-expression diagnostic query differs')


def miter_rtl(pair):
    original = generate_rtl(pair['formula']).replace('module candidate(', 'module original_arm(', 1)
    csd = generate_rtl(pair['rewritten_formula']).replace('module candidate(', 'module csd_arm(', 1)
    top = '''module pair_miter(input wire [31:0] in0, in1, output wire trigger);
wire [31:0] original_result, csd_result;
original_arm original_instance(.in0(in0), .in1(in1), .result(original_result));
csd_arm csd_instance(.in0(in0), .in1(in1), .result(csd_result));
assign trigger = |(original_result ^ csd_result);
endmodule
'''
    return original + csd + top


def tree_inventory(directory):
    directory = Path(directory).resolve()
    require(directory.is_dir(), 'Tool data directory unavailable')
    return [{'path': p.relative_to(directory).as_posix(), 'sha256': sha(p), 'bytes': p.stat().st_size}
        for p in sorted(directory.rglob('*')) if p.is_file()]


def executable(name, args):
    found = shutil.which(name)
    require(found is not None, 'Required executable unavailable: ' + name)
    path = Path(found).resolve()
    run = subprocess.run([str(path), *args], capture_output=True, text=True, timeout=20, check=True)
    return {'path': str(path), 'sha256': sha(path), 'version': (run.stdout + run.stderr).strip()}


def solver_inventory():
    import z3
    module = Path(z3.__file__).resolve().parent
    files = sorted({*module.rglob('*.py'), *(p for p in (module / 'lib').glob('libz3*') if p.is_file())})
    require(any(p.name.startswith('libz3') for p in files), 'Native Z3 library required')
    return {'version': z3.get_version_string(), 'files': [{'path': str(p), 'sha256': sha(p)} for p in files]}


def platform_identity():
    return {'system': platform.system(), 'release': platform.release(), 'machine': platform.machine(),
        'mac_version': platform.mac_ver()[0]}


def tool_inventory():
    yosys = executable('yosys', ['-V'])
    abc = executable('yosys-abc', ['-q', 'version'])
    config = executable('yosys-config', ['--datdir'])
    data_path = Path(config['version']).resolve()
    data_files = tree_inventory(data_path)
    require(data_files and (data_path / 'ice40/cells_sim.v').is_file(), 'Complete Yosys data required')
    return {'schema': 'isaforge-v10-csd-tools-v1', 'executables': {'yosys': yosys, 'abc': abc, 'yosys_config': config},
        'yosys_data': {'path': str(data_path), 'files': data_files, 'tree_sha256': digest(encoded(data_files))},
        'solver': solver_inventory(),
        'python': {'path': str(Path(sys.executable).resolve()), 'sha256': sha(Path(sys.executable).resolve()), 'version': sys.version},
        'platform': platform_identity(),
        'limitations': 'OS shared-library/cache dependencies are identified by platform, not a portable hermetic container. No compiler/Verilator: collector uses Yosys eval and strict mapped-netlist interpretation.'}


def validate_tools(tools):
    require(tools.get('schema') == 'isaforge-v10-csd-tools-v1', 'Tool inventory schema differs')
    require(set(tools['executables']) == {'yosys', 'abc', 'yosys_config'}, 'Complete executable inventory required')
    for entry in [*tools['executables'].values(), tools['python'], *tools['solver']['files']]:
        require(Path(entry['path']).is_absolute() and sha(entry['path']) == entry['sha256'], 'Tool/runtime file changed')
    data = tools['yosys_data']
    require(tree_inventory(data['path']) == data['files'] and digest(encoded(data['files'])) == data['tree_sha256'],
        'Yosys data inventory changed')
    require(Path(tools['executables']['abc']['path']).name == 'yosys-abc', 'Explicit Yosys ABC required')
    require(tools['solver'] == solver_inventory(), 'Executing Z3 runtime differs from inventory')
    require(tools['python']['path'] == str(Path(sys.executable).resolve()) and tools['python']['version'] == sys.version,
        'Executing Python runtime differs from inventory')
    require(tools['platform'] == platform_identity(), 'Executing platform differs from inventory')


def required_sources(repository=ROOT):
    repository = Path(repository).resolve()
    return [repository / 'scripts/prepare_v10_csd_hardware.py', repository / 'tests/test_prepare_v10_csd_hardware.py',
        repository / 'scripts/measure_v10_csd_hardware.py', repository / 'tests/test_measure_v10_csd_hardware.py',
        repository / 'docs/v10-csd-hardware-protocol.md', *sorted((repository / 'isaforge').glob('*.py'))]


def amendment_record(repository=ROOT):
    """Authenticate the preserved failed attempt/source before any new labels."""
    repository = Path(repository).resolve()
    previous = repository / FAILED_PREPARATION
    paths = [previous / name for name in ('failure-review.json', 'preparation-failure.json', 'preparation-first.log')]
    paths.extend(sorted((previous / 'proofs').glob('*.json')))
    require(len(paths) == 6, 'Exact preserved first attempt requires three proof records')
    evidence = []
    for path in paths:
        relative = path.relative_to(repository).as_posix()
        historical = subprocess.check_output(['git', 'show', FAILED_PREPARATION_COMMIT + ':' + relative], cwd=repository)
        require(digest(historical) == sha(path), 'Preserved failure differs from committed evidence')
        evidence.append({'path': relative, 'sha256': digest(historical)})
    review = read(previous / 'failure-review.json')
    require(review.get('new_area_measurements') == review.get('native_rtl_proof_jobs') == review.get('new_model_fits') == 0,
        'Amendment must precede all new hardware outcomes')
    for entry in review['sources']:
        historical = subprocess.check_output(['git', 'show', FAILED_PREPARATION_COMMIT + ':' + entry['path']], cwd=repository)
        require(digest(historical) == entry['sha256'], 'Original failed source lineage differs')
    implementation_root = repository / IMPLEMENTATION_FAILURE
    implementation_paths = [implementation_root / name for name in
        ('implementation-failure-review.json', 'preparation-failure.json', 'preparation-first.log')]
    implementation_paths.extend(sorted((implementation_root / 'proofs').glob('*.json')))
    require(len(implementation_paths) == 8, 'Exact implementation failure requires five successful lemma records')
    implementation_evidence = []
    for path in implementation_paths:
        relative = path.relative_to(repository).as_posix()
        historical = subprocess.check_output(['git', 'show', IMPLEMENTATION_FAILURE_COMMIT + ':' + relative], cwd=repository)
        require(digest(historical) == sha(path), 'Preserved implementation failure differs from committed evidence')
        implementation_evidence.append({'path': relative, 'sha256': digest(historical)})
    implementation_review = read(implementation_root / 'implementation-failure-review.json')
    require(implementation_review.get('new_area_measurements') == implementation_review.get('native_rtl_proof_jobs')
        == implementation_review.get('new_model_fits') == 0, 'Implementation fix must precede new hardware outcomes')
    for entry in implementation_review['sources']:
        historical = subprocess.check_output(['git', 'show', IMPLEMENTATION_FAILURE_COMMIT + ':' + entry['path']], cwd=repository)
        require(digest(historical) == entry['sha256'], 'Failed implementation source lineage differs')
    timeout_root = repository / LEMMA_TIMEOUT_PREPARATION
    timeout_paths = [timeout_root / name for name in ('failure-review.json', 'preparation-failure.json', 'preparation-first.log')]
    timeout_paths.extend(sorted((timeout_root / 'proofs').glob('*.json')))
    require(len(timeout_paths) == 28, 'Exact source-lemma timeout attempt requires25 proof records')
    timeout_evidence = []
    for path in timeout_paths:
        relative = path.relative_to(repository).as_posix()
        historical = subprocess.check_output(['git', 'show', LEMMA_TIMEOUT_COMMIT + ':' + relative], cwd=repository)
        require(digest(historical) == sha(path), 'Preserved source-lemma timeout differs from committed evidence')
        timeout_evidence.append({'path': relative, 'sha256': digest(historical)})
    timeout_review = read(timeout_root / 'failure-review.json')
    require(timeout_review.get('new_area_measurements') == timeout_review.get('native_rtl_proof_jobs')
        == timeout_review.get('new_model_fits') == 0, 'Uniform budget amendment must precede hardware outcomes')
    for entry in timeout_review['sources']:
        historical = subprocess.check_output(['git', 'show', LEMMA_TIMEOUT_COMMIT + ':' + entry['path']], cwd=repository)
        require(digest(historical) == entry['sha256'], 'Source-lemma timeout source lineage differs')
    return {'schema': 'isaforge-v10a-premeasurement-amendment-v1',
        'status': 'parent-approved-premeasurement-proof-composition-amendment',
        'previous_commit': FAILED_PREPARATION_COMMIT, 'previous_root': FAILED_PREPARATION,
        'previous_evidence': evidence, 'previous_source_files': review['sources'],
        'implementation_fix': {'commit': IMPLEMENTATION_FAILURE_COMMIT, 'root': IMPLEMENTATION_FAILURE,
            'evidence': implementation_evidence, 'source_files': implementation_review['sources'],
            'change': 'Dedicated Z3 Context perquery for exact stable serialization; no relaxed identity check',
            'proof_method_budget_cohort_rtl_gate_changed': False},
        'uniform_lemma_budget_amendment': {'commit': LEMMA_TIMEOUT_COMMIT, 'root': LEMMA_TIMEOUT_PREPARATION,
            'evidence': timeout_evidence, 'source_files': timeout_review['sources'],
            'reason': 'First24 lemmas UNSAT; direct1364 returnedunknown/timeout at5000ms, beforeanyhardwareoutcomes',
            'old_timeout_ms': 5000, 'new_timeout_ms': PROOF_TIMEOUT_MS, 'scope': 'all32 pairs uniformly, not selective',
            'maximum_further_timeout_increments': 0, 'method_encoding_inputs_rewrites_rtl_gate_changed': False},
        'reason': 'Third full-expression query timed out at fixed5000ms; retained with no area/nativeRTL/fits and no silent retry',
        'change': 'Universal unconstrained-word product lemma plus exact AST substitution/congruence; full expression queries retained diagnostic-only',
        'unchanged': ['same32 original formulas and CSD rewrites', '60s actual RTL pair miter',
            '64 fresh paired synthesis jobs', '2148 physical verification samples perarm', 'all32 complete primary endpoint'],
        'new_area_outcomes_read': False, 'native_rtl_jobs': 0, 'model_fits': 0}


def fixed_recipe():
    return {'schema': 'isaforge-v10-csd-hardware-recipe-v1', 'scope': 'Consumed32-case hardware development study; no area predictor fit',
        'pairs': 32, 'arms': ['original', 'csd'], 'fresh_synthesis_jobs': 64, 'model_fits': 0,
        'constants': list(CONSTANTS), 'contexts': list(CONTEXTS),
        'rewrite': {'method': 'nonadjacent signed digits; highest positive term then descending add/subtract',
            'max_nonzero_digits': 5, 'max_shift': 11, 'max_output_operations': 32, 'alternatives_per_original': 1},
        'source_equivalence': {'logic': 'QF_BV32 unconstrained-word lemma + exact whole-context AST congruence',
            'timeout_ms': PROOF_TIMEOUT_MS, 'required_result': 'unsat', 'input_assumptions': [],
            'whole_expression_queries': 'retained diagnostic-only, not solved again', 'amendment_commit': FAILED_PREPARATION_COMMIT},
        'rtl_equivalence': {'pairs': 32, 'timeout_seconds': RTL_TIMEOUT_SECONDS,
            'script_commands': ['prep -top pair_miter -flatten', 'check -assert',
                'sat -timeout 60 -verify -prove trigger 0 -show-inputs -show-outputs'],
            'scope': 'Universal actual emitted original-vs-csd RTL miter; mandatory before any optimization claim'},
        'measurement': {'workers': 2, 'verification_seed': VERIFY_SEED, 'random_vectors': 2048, 'boundary_vectors': 100,
            'vectors_per_arm': 2148, 'timeout_seconds_per_arm': 360,
            'synthesis_commands': ['synth_ice40 -top candidate', 'check -assert'],
            'dsp': False, 'carry': True, 'mapped_verification': '2148 samples perarm via strict raw SB_LUT4/SB_CARRY interpreter; not universal',
            'original_rtl_verification': '2148 Yosys eval samples perarm against independent original u32 oracle'},
        'reporting': {'primary': 'paired csd LUT4 minus original LUT4 on all32 pairs',
            'summaries': ['all32 mean', 'median', 'minimum', 'maximum', 'wins/ties/losses', '8constants x4contexts full matrix'],
            'carry': 'descriptive counts and deltas, separate from LUT4', 'failed_pairs': 'retain all; complete primary pending',
            'filtering': False, 'replacements': False, 'timing_cpu_power_claims': False,
            'historical_original_labels': 'development context only; all64 arms measured fresh'}}


def validate_preparation(root):
    root = Path(root).resolve()
    require(not (root / 'preparation-failure.json').exists(), 'Failed preparation cannot be released')
    manifest = read(root / 'preparation.json')
    require(manifest.get('schema') == SCHEMA and manifest.get('status') == 'prepared-inputs-only'
        and manifest.get('new_measurements') == 0 and manifest.get('model_fits') == 0
        and manifest.get('new_measurement_outcomes_read') is False and manifest.get('universal_source_proofs') == 32,
        'Input-only complete32-proof preparation required')
    entries = manifest['files']
    paths = [checked(e, root) for e in entries]
    require(len(paths) == len(set(paths)), 'Duplicate preparation bindings')
    bindings = {path: entry for path, entry in zip(paths, entries)}
    def bound(entry):
        path = checked(entry, root)
        require(bindings.get(path) == entry, 'Reference absent from flat bindings')
        return path
    recipe = read(bound(manifest['recipe']))
    tools = read(bound(manifest['tools']))
    expected_recipe = fixed_recipe()
    expected_recipe['tools'] = manifest['tools']
    require(recipe == expected_recipe, 'Fixed recipe differs')
    pairs = read(bound(manifest['pairs']))
    require(read(bound(manifest['amendment'])) == amendment_record(ROOT), 'Premeasurement amendment lineage differs')
    expected = fixed_pairs(read(bound(manifest['source_candidates'])))
    require(sha(bound(manifest['source_candidates'])) == V9_CANDIDATES_SHA256, 'Historical V9 candidate file differs')
    require(len(pairs) == len(expected) == 32, 'Complete32 pairs required')
    for pair, base in zip(pairs, expected):
        require(set(pair) == set(base) | {'arms', 'proof', 'miter_rtl'} and all(pair[k] == v for k, v in base.items()),
            'Fixed pair order/identity/rewrite differs')
        require(set(pair['arms']) == {'original', 'csd'}, 'Both fixed arms required')
        for arm, formula in (('original', base['formula']), ('csd', base['rewritten_formula'])):
            entry = pair['arms'][arm]
            require(set(entry) == {'formula', 'rtl'} and entry['formula'] == formula, 'Arm formula differs')
            require(bound(entry['rtl']).read_text() == generate_rtl(formula), 'Sealed RTL differs from exact emitter')
        require(bound(pair['miter_rtl']).read_text() == miter_rtl(base), 'Actual RTL miter differs')
        proof = read(bound(pair['proof']))
        validate_proof(proof, base)
        require(proof['solver_version'] == tools['solver']['version'], 'Proof solver differs from sealed runtime')
    repository = (root / manifest['repository']).resolve()
    require(repository == ROOT, 'Preparation repository differs from executing source')
    require(all(p.resolve() in bindings for p in required_sources(repository)), 'Runtime source inventory incomplete')
    require(set(manifest['source_files']) == {os.path.relpath(p.resolve(), root) for p in required_sources(repository)},
        'Required source list differs')
    return manifest, recipe, pairs


def run(root, *, repository=ROOT):
    root, repository = Path(root).resolve(), Path(repository).resolve()
    require(not root.exists(), 'Output already exists; preserve prior preparation attempts')
    sources = required_sources(repository)
    require(all(p.is_file() for p in sources), 'Required collector/tests/protocol sources must exist before preparation')
    source = repository / V9 / 'candidates.json'
    require(sha(source) == V9_CANDIDATES_SHA256, 'Historical V9 candidates changed')
    pairs = fixed_pairs(read(source))
    initial_source_hashes = {p: sha(p) for p in sources}
    tools = tool_inventory()
    amendment = amendment_record(repository)
    root.mkdir(parents=True)
    try:
        write(root / 'tools.json', tools)
        write(root / 'premeasurement-amendment.json', amendment)
        with (root / 'source-candidates.json').open('xb') as stream:
            stream.write(source.read_bytes())
        for pair in pairs:
            suffix = pair['pair_id'].split(':')[1]
            proof = prove_equivalence(pair['formula'], pair['rewritten_formula'])
            proof_path = root / 'proofs' / (suffix + '.json')
            write(proof_path, proof)  # retain failures before failing closed
            validate_proof(proof, pair)
            pair['proof'] = record(proof_path, root)
            pair['arms'] = {}
            for arm, formula in (('original', pair['formula']), ('csd', pair['rewritten_formula'])):
                path = root / 'rtl' / suffix / (arm + '.v')
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open('x') as stream:
                    stream.write(generate_rtl(formula))
                pair['arms'][arm] = {'formula': formula, 'rtl': record(path, root)}
            path = root / 'rtl' / suffix / 'miter.v'
            with path.open('x') as stream:
                stream.write(miter_rtl(pair))
            pair['miter_rtl'] = record(path, root)
        recipe = fixed_recipe()
        recipe['tools'] = record(root / 'tools.json', root)
        write(root / 'recipe.json', recipe)
        write(root / 'pairs.json', pairs)
        require(all(sha(p) == h for p, h in initial_source_hashes.items()) and sha(source) == V9_CANDIDATES_SHA256,
            'Source changed during preparation')
        validate_tools(tools)
        files = sorted(p for p in root.rglob('*') if p.is_file())
        manifest = {'schema': SCHEMA, 'status': 'prepared-inputs-only', 'created_at_utc': now(),
            'repository': os.path.relpath(repository, root), 'new_measurements': 0, 'model_fits': 0,
            'new_measurement_outcomes_read': False, 'universal_source_proofs': 32,
            'universal_actual_rtl_proofs': 'pending collection stage',
            'recipe': record(root / 'recipe.json', root), 'tools': record(root / 'tools.json', root),
            'pairs': record(root / 'pairs.json', root), 'source_candidates': record(root / 'source-candidates.json', root),
            'amendment': record(root / 'premeasurement-amendment.json', root),
            'source_files': [os.path.relpath(p.resolve(), root) for p in sources],
            'files': [record(p, root) for p in [*files, *sources]]}
        write(root / 'preparation.json', manifest)
        validate_preparation(root)
        return manifest
    except Exception as error:
        write(root / 'preparation-failure.json', {'created_at_utc': now(), 'error': str(error),
            'status': 'failed-closed', 'new_measurements': 0, 'model_fits': 0})
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--validate-only', action='store_true')
    args = parser.parse_args()
    if args.validate_only:
        manifest, recipe, pairs = validate_preparation(args.root)
        validate_tools(read(checked(manifest['tools'], args.root)))
        print(json.dumps({'status': 'valid', 'pairs': len(pairs), 'fresh_jobs': recipe['fresh_synthesis_jobs']}))
    else:
        print(json.dumps(run(args.root), indent=2))
