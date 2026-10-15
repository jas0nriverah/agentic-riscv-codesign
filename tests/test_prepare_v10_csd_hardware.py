"""Synthetic integrity/proof tests; no measurements, fits or feature extraction."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('prepare_v10_csd_hardware', ROOT / 'scripts/prepare_v10_csd_hardware.py')
p = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(p)
SYNTHETIC_AMENDMENT = {'schema': 'synthetic-premeasurement-amendment', 'new_area_outcomes_read': False}


def put(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + '\n')


def proof_fixture(pair):
    certificate = p.congruence_certificate(pair['formula'], pair['rewritten_formula'])
    query = p.formula_query(certificate['lemma_original_formula'], certificate['lemma_rewritten_formula'], operand_lemma=True).to_smt2()
    whole = p.formula_query(pair['formula'], pair['rewritten_formula']).to_smt2()
    import z3
    return {'schema': 'isaforge-v10-csd-source-proof-v2', 'original_formula': pair['formula'],
        'rewritten_formula': pair['rewritten_formula'], 'method': 'universal QF_BV32 operand lemma plus exact whole-expression AST congruence',
        'inputs': ['in0:32', 'in1:32'], 'assumptions': [], 'timeout_ms': 5000, 'result': 'unsat',
        'query_smt2': query, 'query_sha256': p.digest(query.encode()), 'solver_version': z3.get_version_string(),
        'congruence': certificate, 'query_scope': 'universal unconstrained word:32; no range or reachability assumptions',
        'whole_expression_query_smt2': whole, 'whole_expression_query_sha256': p.digest(whole.encode()),
        'whole_expression_query_status': 'diagnostic-only; not solved in amended preparation'}


def fixture(root):
    # Integrity fixture claims UNSAT; only test_real_source_proof below executes a solver.
    import z3
    root = Path(root).resolve()
    pairs = p.fixed_pairs()
    (root / 'source-candidates.json').write_bytes((ROOT / p.V9 / 'candidates.json').read_bytes())
    put(root / 'tools.json', {'solver': {'version': z3.get_version_string()}})
    put(root / 'premeasurement-amendment.json', SYNTHETIC_AMENDMENT)
    for pair in pairs:
        suffix = pair['pair_id'].split(':')[1]
        directory = root / 'rtl' / suffix
        directory.mkdir(parents=True)
        pair['arms'] = {}
        for arm, formula in [('original', pair['formula']), ('csd', pair['rewritten_formula'])]:
            path = directory / (arm + '.v')
            path.write_text(p.generate_rtl(formula))
            pair['arms'][arm] = {'formula': formula, 'rtl': p.record(path, root)}
        path = directory / 'miter.v'
        path.write_text(p.miter_rtl(pair))
        pair['miter_rtl'] = p.record(path, root)
        path = directory / 'proof.json'
        put(path, proof_fixture(pair))
        pair['proof'] = p.record(path, root)
    recipe = p.fixed_recipe()
    recipe['tools'] = p.record(root / 'tools.json', root)
    put(root / 'recipe.json', recipe)
    put(root / 'pairs.json', pairs)
    sources = [ROOT / 'scripts/prepare_v10_csd_hardware.py']
    files = sorted(x for x in root.rglob('*') if x.is_file()) + sources
    manifest = {'schema': p.SCHEMA, 'status': 'prepared-inputs-only', 'repository': os.path.relpath(ROOT, root),
        'new_measurements': 0, 'model_fits': 0, 'new_measurement_outcomes_read': False, 'universal_source_proofs': 32,
        'recipe': p.record(root / 'recipe.json', root),
        'tools': p.record(root / 'tools.json', root), 'pairs': p.record(root / 'pairs.json', root),
        'amendment': p.record(root / 'premeasurement-amendment.json', root),
        'source_candidates': p.record(root / 'source-candidates.json', root),
        'source_files': [os.path.relpath(x, root) for x in sources], 'files': [p.record(x, root) for x in files]}
    put(root / 'preparation.json', manifest)
    return manifest, recipe, pairs, sources


def rebind(root, manifest, path):
    entry = p.record(path, root)
    manifest['files'] = [entry if x['path'] == entry['path'] else x for x in manifest['files']]
    for key in ('recipe', 'tools', 'pairs', 'source_candidates'):
        if manifest[key]['path'] == entry['path']:
            manifest[key] = entry
    put(root / 'preparation.json', manifest)


class FixedStudyTests(unittest.TestCase):
    def test_exact32_grid_original_id_and_order(self):
        source = p.read(ROOT / p.V9 / 'candidates.json')
        pairs = p.fixed_pairs(source)
        self.assertEqual(pairs, p.fixed_pairs(source))
        self.assertEqual(len(pairs), 32)
        self.assertEqual({x['constant_u32'] for x in pairs}, set(p.CONSTANTS))
        self.assertEqual({x['context'] for x in pairs}, set(p.CONTEXTS))
        self.assertEqual([x['formula'] for x in pairs], [x['formula'] for x in source if 'constant_u32' in x])
        self.assertEqual(len({x['pair_id'] for x in pairs}), 32)
        for pair in pairs:
            suffix = hashlib.sha256(pair['formula'].encode()).hexdigest()
            self.assertEqual(pair['pair_id'], 'v10-csd:' + suffix)
            self.assertEqual(pair['source_candidate_id'], 'v9-coverage:' + suffix)

    def test_changed_missing_duplicate_original_source_rejected(self):
        source = p.read(ROOT / p.V9 / 'candidates.json')
        for rows in (source[1:], [*source, source[0]], [dict(source[0], operation_count=99), *source[1:]]):
            with self.assertRaises(ValueError): p.fixed_pairs(rows)

    def test_csd_reconstruction_nonadjacent_and_bounds(self):
        for constant in p.CONSTANTS:
            digits = p.csd_digits(constant)
            self.assertEqual(sum(sign * 2**position for position, sign in digits), constant)
            self.assertLessEqual(len(digits), 5)
            self.assertTrue(all(a[0] - b[0] > 1 for a, b in zip(digits, digits[1:])))
        self.assertEqual(p.csd_digits(511), ((9, 1), (0, -1)))
        self.assertEqual(len(p.csd_digits(341)), 5)
        for constant in (0, -1, 3, 2048, True):
            with self.assertRaises(ValueError): p.csd_digits(constant)

    def test_single_rewrite_exact_context_and_511_form(self):
        pairs = p.fixed_pairs()
        direct = next(x for x in pairs if x['constant_u32'] == 511 and x['context'] == 'direct_product')
        self.assertEqual(direct['rewritten_formula'], 'sub(slli(in0,9),in0)')
        for pair in pairs:
            self.assertNotIn('mul(', pair['rewritten_formula'])
            self.assertNotIn('sub(0,', pair['rewritten_formula'])
            if pair['context'] == 'masked_sub_before_product':
                self.assertIn('sub(andi(in0,63),in1)', pair['rewritten_formula'])

    def test_invalid_signed_and_shift_immediate_semantics(self):
        invalid = ['addi(in0,2048)', 'andi(in0,-2049)', 'slli(in0,32)', 'slli(in0,-1)',
                   'srai(in0,1)', 'mulh(in0,in1)', 'or(in0,in1)', 'add( in0,in1)']
        for formula in invalid:
            with self.assertRaises(ValueError): p.validate_formula(formula)
        for formula in ('addi(in0,-2048)', 'andi(in0,2047)', 'slli(in0,31)'):
            p.validate_formula(formula)
        for formula in ('mul(in0,511)', 'mul(in0,addi(0,44))', 'add(in0,in1)',
                        'mul(mul(in0,addi(0,511)),addi(0,511))'):
            with self.assertRaises(ValueError): p.rewrite(formula, 511)

    def test_fixed_recipe_complete_physical_and_reporting_scope(self):
        recipe = p.fixed_recipe()
        self.assertEqual(recipe['fresh_synthesis_jobs'], 64)
        self.assertEqual(recipe['source_equivalence']['timeout_ms'], 5000)
        self.assertEqual(recipe['rtl_equivalence']['timeout_seconds'], 60)
        self.assertIn('sat -timeout 60 -verify -prove trigger 0 -show-inputs -show-outputs', recipe['rtl_equivalence']['script_commands'])
        self.assertEqual(recipe['measurement']['vectors_per_arm'], 2148)
        self.assertFalse(recipe['reporting']['filtering'])
        self.assertFalse(recipe['reporting']['replacements'])

    def test_miter_uses_actual_bytes_only_module_names_change(self):
        pair = p.fixed_pairs()[0]
        text = p.miter_rtl(pair)
        for arm, formula in [('original_arm', pair['formula']), ('csd_arm', pair['rewritten_formula'])]:
            self.assertIn(p.generate_rtl(formula).replace('module candidate(', f'module {arm}(', 1), text)
        self.assertIn('assign trigger = |(original_result ^ csd_result);', text)

    def test_real_source_proof_and_wrong_rewrite_counterexample(self):
        pair = next(x for x in p.fixed_pairs() if x['constant_u32'] == 511 and x['context'] == 'masked_sub_before_product')
        proof = p.prove_equivalence(pair['formula'], pair['rewritten_formula'])
        p.validate_proof(proof, pair)
        wrong = p.prove_equivalence(pair['formula'], pair['rewritten_formula'].replace(',9)', ',8)'))
        self.assertEqual(wrong['result'], 'sat')
        self.assertIn('counterexample', wrong)

    def test_exact_congruence_rejects_wrong_context_constant_operand_and_rewrite(self):
        rows = p.fixed_pairs()
        after = next(x for x in rows if x['context'] == 'add_after_product' and x['constant_u32'] == 11)
        before = next(x for x in rows if x['context'] == 'sub_before_product' and x['constant_u32'] == 11)
        wrong_context = after['rewritten_formula'][:-4] + 'in0)'
        with self.assertRaisesRegex(ValueError, 'context AST'): p.congruence_certificate(after['formula'], wrong_context)
        wrong_operand = before['rewritten_formula'].replace('sub(in0,in1)', 'sub(in1,in0)')
        with self.assertRaisesRegex(ValueError, 'foreign operand'): p.congruence_certificate(before['formula'], wrong_operand)
        wrong_constant = p.rewrite('mul(in0,addi(0,44))', 44)
        self.assertEqual(p.prove_equivalence('mul(in0,addi(0,11))', wrong_constant)['result'], 'sat')
        for pair in rows:
            certificate = p.congruence_certificate(pair['formula'], pair['rewritten_formula'])
            self.assertEqual(certificate['constant_u32'], pair['constant_u32'])
            self.assertEqual(certificate['replacement_path'], [0] if pair['context'] == 'add_after_product' else [])

    def test_poisoned_congruence_or_diagnostic_query_cannot_certify(self):
        pair = p.fixed_pairs()[0]
        for kind in ('operand', 'constant', 'context-path', 'diagnostic', 'assumed-range'):
            proof = proof_fixture(pair)
            if kind == 'operand': proof['congruence']['operand_formula'] = 'in1'
            elif kind == 'constant': proof['congruence']['constant_u32'] = 44
            elif kind == 'context-path': proof['congruence']['replacement_path'] = [1]
            elif kind == 'diagnostic': proof['whole_expression_query_smt2'] = '(check-sat)'
            else: proof['query_scope'] = 'assume word<64'
            with self.assertRaises(ValueError): p.validate_proof(proof, pair)

    def test_unknown_or_missing_proof_fails_closed(self):
        pair = p.fixed_pairs()[0]
        for updates in ({'result': 'unknown'}, {'result': 'sat'}, {'assumptions': ['in0<8']},
                        {'timeout_ms': 10000}, {'rewritten_formula': 'add(in0,in1)'}, {'query_smt2': '(check-sat)'}):
            proof = dict(proof_fixture(pair), **updates)
            with self.assertRaises(ValueError): p.validate_proof(proof, pair)


class IntegrityTests(unittest.TestCase):
    def test_tool_validation_checks_binary_data_solver_and_executing_runtime(self):
        for kind in ('valid', 'binary', 'data', 'new-data', 'solver', 'python', 'platform'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                root = Path(directory).resolve()
                executables = {}
                for key, name in [('yosys', 'yosys'), ('abc', 'yosys-abc'), ('yosys_config', 'yosys-config')]:
                    path = root / name; path.write_text('synthetic binary')
                    executables[key] = {'path': str(path), 'sha256': p.sha(path), 'version': 'fixture'}
                data = root / 'share'; data.mkdir(); (data / 'cell.v').write_text('cell')
                inventory = p.tree_inventory(data)
                solver_path = root / 'solver.py'; solver_path.write_text('solver')
                solver = {'version': 'fixture', 'files': [{'path': str(solver_path), 'sha256': p.sha(solver_path)}]}
                python = Path(sys.executable).resolve()
                tools = {'schema': 'isaforge-v10-csd-tools-v1', 'executables': executables,
                    'yosys_data': {'path': str(data), 'files': inventory, 'tree_sha256': p.digest(p.encoded(inventory))},
                    'solver': solver, 'python': {'path': str(python), 'sha256': p.sha(python), 'version': sys.version},
                    'platform': p.platform_identity()}
                if kind == 'binary': (root / 'yosys-abc').write_text('tampered')
                elif kind == 'data': (data / 'cell.v').write_text('changed')
                elif kind == 'new-data': (data / 'added.v').write_text('new')
                elif kind == 'solver': solver_path.write_text('changed')
                elif kind == 'python': tools['python']['version'] = 'different'
                elif kind == 'platform': tools['platform']['release'] = 'different'
                with mock.patch.object(p, 'solver_inventory', return_value=solver):
                    if kind == 'valid': p.validate_tools(tools)
                    else:
                        with self.assertRaises(ValueError): p.validate_tools(tools)

    def test_valid_synthetic_preparation_and_reauthenticated_tamper(self):
        for kind in ('valid', 'dropped', 'order', 'rewritten', 'rtl', 'miter', 'proof', 'recipe', 'failure'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                manifest, recipe, pairs, sources = fixture(root)
                if kind == 'dropped': pairs.pop()
                elif kind == 'order': pairs.reverse()
                elif kind == 'rewritten': pairs[0]['rewritten_formula'] = 'sub(in0,in1)'
                elif kind in ('rtl', 'miter'):
                    entry = pairs[0]['arms']['csd']['rtl'] if kind == 'rtl' else pairs[0]['miter_rtl']
                    path = root / entry['path']
                    path.write_text(path.read_text() + '// changed\n')
                    entry['sha256'] = p.sha(path)
                    rebind(root, manifest, path)
                elif kind == 'proof':
                    path = root / pairs[0]['proof']['path']
                    proof = p.read(path); proof['result'] = 'unknown'; put(path, proof)
                    pairs[0]['proof']['sha256'] = p.sha(path)
                    rebind(root, manifest, path)
                elif kind == 'recipe':
                    recipe['measurement']['dsp'] = True
                    put(root / 'recipe.json', recipe); rebind(root, manifest, root / 'recipe.json')
                elif kind == 'failure': put(root / 'preparation-failure.json', {'status': 'failed-closed'})
                put(root / 'pairs.json', pairs); rebind(root, manifest, root / 'pairs.json')
                with mock.patch.object(p, 'required_sources', return_value=sources), \
                     mock.patch.object(p, 'amendment_record', return_value=SYNTHETIC_AMENDMENT):
                    if kind == 'valid': self.assertEqual(len(p.validate_preparation(root)[2]), 32)
                    else:
                        with self.assertRaises(ValueError): p.validate_preparation(root)

    def test_unbound_changed_runtime_or_historical_input_rejected(self):
        for kind in ('missing-source', 'duplicate-binding', 'historical'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                manifest, _, _, sources = fixture(root)
                if kind == 'missing-source': manifest['files'].pop()
                elif kind == 'duplicate-binding': manifest['files'].append(manifest['files'][0])
                else:
                    path = root / 'source-candidates.json'
                    rows = p.read(path); rows[0]['operation_count'] = 99; put(path, rows)
                    rebind(root, manifest, path)
                put(root / 'preparation.json', manifest)
                with mock.patch.object(p, 'required_sources', return_value=sources), \
                     mock.patch.object(p, 'amendment_record', return_value=SYNTHETIC_AMENDMENT):
                    with self.assertRaises(ValueError): p.validate_preparation(root)

    def test_data_inventory_detects_new_changed_or_missing_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root / 'a.v').write_text('original')
            before = p.tree_inventory(root)
            (root / 'a.v').write_text('changed')
            self.assertNotEqual(before, p.tree_inventory(root))
            (root / 'a.v').write_text('original'); (root / 'b.v').write_text('new')
            self.assertNotEqual(before, p.tree_inventory(root))
            (root / 'b.v').unlink(); (root / 'a.v').unlink()
            self.assertNotEqual(before, p.tree_inventory(root))

    def test_failed_run_retains_proof_and_blocks_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'new'
            pair = p.fixed_pairs()[0]
            proof = dict(proof_fixture(pair), result='unknown', reason_unknown='synthetic timeout')
            with mock.patch.object(p, 'required_sources', return_value=[ROOT / 'scripts/prepare_v10_csd_hardware.py']), \
                 mock.patch.object(p, 'tool_inventory', return_value={}), \
                 mock.patch.object(p, 'amendment_record', return_value=SYNTHETIC_AMENDMENT), \
                 mock.patch.object(p, 'prove_equivalence', return_value=proof):
                with self.assertRaises(ValueError): p.run(root)
                self.assertTrue((root / 'preparation-failure.json').is_file())
                self.assertFalse((root / 'preparation.json').exists())
                retained = list((root / 'proofs').glob('*.json'))
                self.assertEqual(len(retained), 1)
                self.assertEqual(p.read(retained[0])['reason_unknown'], 'synthetic timeout')
                with self.assertRaisesRegex(ValueError, 'Output already exists'): p.run(root)


if __name__ == '__main__': unittest.main()
