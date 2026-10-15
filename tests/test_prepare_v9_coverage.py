"""Synthetic input-only coverage preparation tests; never collect target labels."""
from pathlib import Path
import hashlib
import importlib.util
import json
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('prepare_v9_coverage', ROOT / 'scripts/prepare_v9_coverage.py')
p = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(p)


def put(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + '\n')


def fixture(root):
    candidates = p.fixed_candidates()
    own_source = ROOT / 'scripts/prepare_v9_coverage.py'
    recipe = {'schema': 'isaforge-v9-coverage-recipe-v1', 'original_training_formula_count': 1665,
        'new_training_formula_count': 48, 'model_fits': 1, 'fixed_parameters': p.PARAMETERS,
        'feature_columns': list(p.v6.columns()), 'selected_columns': list(p.v6.mapping_columns()),
        'selected_indices': p.v6.mapping_indices().tolist(),
        'frozen_tool': {'version': 'Yosys synthetic fixture', 'executable_sha256': 'a' * 64},
        'measurement': {'workers': 2, 'verification_seed': 2026101519, 'vectors_per_formula': 2148,
            'original_rtl_only': True, 'new_measurement_count': 48},
        'training_script': 'scripts/train_v9_coverage.py', 'collector_script': 'scripts/measure_v9_coverage.py',
        'required_sources': ['scripts/prepare_v9_coverage.py']}
    put(root / 'candidates.json', candidates)
    put(root / 'recipe.json', recipe)
    manifest = {'schema': p.SCHEMA, 'status': 'prepared-inputs-only', 'new_labels_read': False,
        'model_fits': 0, 'candidates': p.record(root / 'candidates.json', root), 'recipe': p.record(root / 'recipe.json', root),
        'files': [p.record(root / 'candidates.json', root), p.record(root / 'recipe.json', root), p.record(own_source, root)]}
    put(root / 'preparation.json', manifest)
    return manifest, recipe, candidates


def rebind(root, manifest, name):
    record = p.record(root / name, root)
    manifest['files'] = [record if r['path'] == name else r for r in manifest['files']]
    if name in ('recipe.json', 'candidates.json'):
        manifest['recipe' if name == 'recipe.json' else 'candidates'] = record
    put(root / 'preparation.json', manifest)


class CandidateTests(unittest.TestCase):
    def test_exact_grid_immediates_and_counts(self):
        rows = p.fixed_candidates()
        self.assertEqual(rows, p.fixed_candidates())
        self.assertEqual(len(rows), 48)
        constants = {r['constant_u32'] for r in rows if 'constant_u32' in r}
        self.assertEqual(constants, {11, 44, 85, 340, 341, 1364, 511, 2044})
        self.assertEqual({r['shift'] for r in rows if 'shift' in r}, {1, 2, 3, 4, 8, 12, 24, 30})
        self.assertEqual(sum('constant_u32' in r for r in rows), 32)
        self.assertEqual(sum('shift' in r for r in rows), 16)
        self.assertEqual(len({r['candidate_id'] for r in rows}), 48)
        for row in rows:
            self.assertEqual(row['candidate_id'], 'v9-coverage:' + hashlib.sha256(row['formula'].encode()).hexdigest())
            self.assertIn(row['operation_count'], (2, 3, 4))
        self.assertLessEqual(max(constants), 2047)

    def test_coherent_retained_proposal(self):
        proposal = p.read(ROOT / 'results/2026-10-15-development-diagnosis/proposed-experiment-inputs.json')
        self.assertEqual([{k: v for k, v in r.items() if k not in ('candidate_id', 'operation_count')}
                          for r in p.fixed_candidates()], proposal['inputs'])

    def test_canonical_and_declared_aliases_separate_from_skeleton(self):
        consumed = [{'formula': 'addi(in0,7)', 'normalized_formula': 'addi(in0,7)'}]
        proposals = [
            {'formula': 'addi(in0,7)'},
            {'formula': 'add(in0,7)', 'normalized_formula': 'addi(in0,7)'},
            {'formula': 'addi(in0,8)'},
        ]
        report = p.duplicate_report(consumed, proposals)
        self.assertEqual(report['canonical_original_seen_count'], 1)
        self.assertEqual(report['declared_functional_alias_count'], 2)
        self.assertFalse(report['records'][2]['declared_functional_alias'])
        self.assertTrue(report['records'][2]['matches']['ordered_skeleton'])

    def test_internal_commutative_alias_retained(self):
        rows = [{'formula': 'add(in0,in1)'}, {'formula': 'add(in1,in0)'}]
        report = p.duplicate_report([], rows)
        self.assertEqual(report['within_proposal_functional_alias_pairs'], 1)
        self.assertEqual(report['proposed_originals'], 2)

    def test_complete_prior_forms_are_retained(self):
        consumed = [
            {'formula': 'add(in0,7)', 'normalized_formula': 'addi(in0,7)'},
            {'formula': 'add(in0,7)', 'v7_combined_normalized_formula': 'add(7,in0)'},
        ]
        report = p.duplicate_report(consumed, [{'formula': 'add(7,in0)'}])
        self.assertEqual(report['consumed_unique_originals'], 1)
        self.assertEqual(report['declared_functional_alias_count'], 1)

    def test_all_accepted_modes_and_fallback_poison(self):
        # Synthetic stored-form fixture tests status handling, not the proof
        # engine's equivalence certification of these deliberately distinct terms.
        consumed = [{'formula': 'addi(in0,1)', 'v7_combined_normalized_formula': 'addi(in0,9)',
            'v7_modes': {
                'bit': {'normalized_formula': 'addi(in0,7)', 'metadata': {'status': 'accepted'}},
                'affine': {'normalized_formula': 'addi(in0,8)', 'metadata': {'status': 'accepted'}},
                'combined': {'normalized_formula': 'addi(in0,9)', 'metadata': {'status': 'fallback_original'}},
            }}]
        report = p.duplicate_report(consumed, [{'formula': f'addi(in0,{n})'} for n in (7, 8, 9)])
        self.assertTrue(report['records'][0]['declared_functional_alias'])
        self.assertTrue(report['records'][1]['declared_functional_alias'])
        self.assertFalse(report['records'][2]['declared_functional_alias'])

    def test_changed_original_bytes_cannot_be_rebound_as_historical(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'original-training.json'
            put(path, {'rows': [{'formula': 'addi(in0,1)', 'lut4_count': 1}], 'training_provenance': {'unchanged': True}})
            old_digest = p.sha(path)
            p.historical_file(path, {path.resolve(): old_digest})
            put(path, {'rows': [{'formula': 'addi(in0,1)', 'lut4_count': 999}], 'training_provenance': {'unchanged': True}})
            with self.assertRaisesRegex(ValueError, 'Historical frozen input differs'):
                p.historical_file(path, {path.resolve(): old_digest})


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.manifest, self.recipe, self.rows = fixture(self.root)
        self.source_mock = mock.patch.object(p, 'required_sources', return_value=[ROOT / 'scripts/prepare_v9_coverage.py'])
        self.source_mock.start()

    def tearDown(self):
        self.source_mock.stop()
        self.temp.cleanup()

    def test_source_bound_valid_contract(self):
        manifest, recipe, candidates = p.validate_preparation(self.root)
        self.assertEqual(candidates, self.rows)
        self.assertEqual(recipe, self.recipe)

    def test_does_not_access_new_measurements(self):
        (self.root / 'labels.json').write_text('NOT JSON: new target files must stay unread')
        (self.root / 'measurements').mkdir()
        (self.root / 'measurements/labels.json').write_text('FORBIDDEN')
        real_read = p.read
        def guarded(path):
            if Path(path).name == 'labels.json' or 'measurements' in Path(path).parts:
                self.fail('Preparation tried to open a new target file')
            return real_read(path)
        with mock.patch.object(p, 'read', side_effect=guarded):
            p.validate_preparation(self.root)

    def test_tampered_bytes_rejected(self):
        (self.root / 'candidates.json').write_text('[]\n')
        with self.assertRaisesRegex(ValueError, 'Changed bound file'):
            p.validate_preparation(self.root)

    def test_rebound_changed_cohort_rejected(self):
        self.rows[0]['formula'] = 'mul(in0,addi(0,4096))'
        put(self.root / 'candidates.json', self.rows)
        rebind(self.root, self.manifest, 'candidates.json')
        with self.assertRaisesRegex(ValueError, 'Fixed exact48'):
            p.validate_preparation(self.root)

    def test_rebound_retuned_recipe_rejected(self):
        self.recipe['fixed_parameters'] = {**p.PARAMETERS, 'n_estimators': 301}
        put(self.root / 'recipe.json', self.recipe)
        rebind(self.root, self.manifest, 'recipe.json')
        with self.assertRaisesRegex(ValueError, 'Fixed training/schema recipe'):
            p.validate_preparation(self.root)

    def test_unbound_runtime_source_rejected(self):
        self.source_mock.stop()
        self.source_mock = mock.patch.object(p, 'required_sources', return_value=[ROOT / 'scripts/prepare_v9_coverage.py', ROOT / 'isaforge/features.py'])
        self.source_mock.start()
        with self.assertRaisesRegex(ValueError, 'Required source inventory'):
            p.validate_preparation(self.root)

    def test_wrong_seed_rejected(self):
        self.recipe['measurement']['verification_seed'] = 0
        put(self.root / 'recipe.json', self.recipe)
        rebind(self.root, self.manifest, 'recipe.json')
        with self.assertRaisesRegex(ValueError, 'Fixed target measurement'):
            p.validate_preparation(self.root)


if __name__ == '__main__':
    unittest.main()
