"""Arithmetic audit contracts; these tests do not establish model improvement."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from scripts import analyze_model_readiness as a


class FrozenModelReadiness(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.output = Path(cls.temp.name)/'analysis'
        # No ML packages or subprocesses are needed to inspect frozen evidence.
        with patch.dict(sys.modules, {'xgboost': None, 'sklearn': None}), \
             patch.object(a.c.subprocess, 'run', side_effect=AssertionError('Native job forbidden')), \
             patch.object(a.c.SpeedupPredictor, 'fit', side_effect=AssertionError('Model fit forbidden')):
            cls.result = a.analyze(cls.output)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_authenticated_inputs_and_sealed_outputs(self):
        self.assertEqual(a.c.unseal(self.output/'metrics.json'), self.result)
        manifest = a.c.unseal(self.output/'manifest.json')
        for name, expected in manifest.items():
            self.assertEqual(a.c.sha(self.output/name), expected)
        self.assertEqual(len(self.result['provenance']['input_sha256']), 13)
        for name, expected in self.result['provenance']['input_sha256'].items():
            self.assertEqual(a.c.sha(a.ROOT/name), expected)

    def test_unknown_outcomes_never_become_infeasibility(self):
        for name, count in (('edn', 1), ('ud', 2)):
            for cap in self.result['targets'][name]['first_query_factor_rankings'].values():
                item = cap['oracle_area_diagnostic']
                self.assertIsNone(item['ranking'])
                self.assertEqual(len(item['unavailable_candidate_ids']), count)
                self.assertIn('not infeasibility', item['reason'])
        for cap in self.result['targets']['sha256']['first_query_factor_rankings'].values():
            self.assertEqual(len(cap['oracle_area_diagnostic']['ranking']), 6)

    def test_full_first_choice_matches_each_frozen_gp_acquisition(self):
        for target in self.result['targets'].values():
            report = a.c.unseal(a.ROOT/target['frozen_folder']/'report.json')
            for cap, modes in target['first_query_factor_rankings'].items():
                for policy in ('hybrid_gp_zero_shot', 'hybrid_gp_adapt'):
                    run = next(r for r in report['runs'] if r['seed'] == 0 and
                               r['area_delta_lut4_cap'] == int(cap) and r['policy'] == policy)
                    event = next(e for e in run['events'] if e['action'] == 'acquire')
                    first = modes['full']['ranking'][0]
                    self.assertEqual(first['candidate_id'], event['candidate_id'])
                    self.assertAlmostEqual(first['score'][0], event['score'][0], places=15)

    def test_factor_invariants_and_sha_area_diagnostic(self):
        self.assertTrue(all(self.result['arithmetic_ablation_summary'].values()))
        cap = self.result['targets']['sha256']['first_query_factor_rankings']['64']
        self.assertEqual(cap['full']['ranking'][0]['candidate_id'],
                         'bcd0ec956735a53f06729244ac30a20902eef7816465a1feda965b76e802811d')
        self.assertEqual(cap['oracle_area_diagnostic']['ranking'][0]['candidate_id'],
                         '6fc88a473c484e02a5a3b8a85d639fbc64d60a05b0558fc796404a6884ff9f5e')

    def test_corpus_scope_and_failures(self):
        corpus = self.result['corpus']
        self.assertEqual(corpus['group_counts'], {'embench-aha-mont64': 6, 'embench-crc32': 6,
            'embench-edn': 5, 'embench-nettle-sha256': 6, 'embench-slre': 6, 'embench-ud': 4})
        self.assertEqual(corpus['failed_classes'], {'infrastructure_unknown': 1,
            'memory_contract_failure': 1, 'self_check_failure': 1})
        self.assertEqual(corpus['reference_censored_attempts'], 1)
        self.assertEqual(corpus['cycle_delta_equals_analytic_rows'], 33)
        self.assertTrue(corpus['all_speedups_above_one'])
        self.assertTrue(corpus['all_device_fit'] and corpus['all_timing_feasible'])
        self.assertEqual(corpus['measured_added_programs'], ['embench-slre', 'embench-ud'])
        self.assertEqual(len(corpus['measured_original_programs']), 4)
        self.assertEqual(len(corpus['constant_hardware_fields']), 13)

    def test_zero_sigma_and_missing_area_preserved(self):
        self.assertEqual(a.probability_below(64, 0, 64), 1)
        self.assertEqual(a.probability_below(65, 0, 64), 0)
        self.assertFalse(a.known_hardware(dict(status='failed')))
        folder = a.ROOT/a.TARGETS['sha256']
        public, history, predictions, report = [a.c.unseal(folder/(n+'.json'))
            for n in ('public', 'history', 'predictions', 'report')]
        report = copy.deepcopy(report)
        for run in report['runs']:
            for event in run['events']:
                if event['action'] == 'acquire':
                    for p in event['hardware_predictions']: p['area_delta_lut4_std'] = 0
        values = a.target_metrics(public, history, predictions, report)['paid_area_updates']
        for event in values:
            for p in event['estimates']:
                self.assertEqual(p['gp_area_std'], 0)
                self.assertIsNone(p['standardized_area_error'])
                self.assertIn('zero predictive', p['standardized_error_note'])

    def test_fresh_output_required(self):
        with self.assertRaisesRegex(ValueError, 'fresh'):
            a.analyze(self.output)
        with self.assertRaises(SystemExit): a.main([])

    def test_analysis_cannot_write_into_frozen_parent_selection(self):
        for folder in a.INPUT_ROOTS:
            with self.assertRaisesRegex(ValueError, 'outside frozen selector'):
                a.analyze(a.ROOT/folder/'readiness-analysis-test-output')

    def test_tampered_frozen_json_rejected_before_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); source = root/'corpus.json'; output = root/'out'
            a.c.seal(source, {})
            source.write_text('{"tampered": true}')
            with patch.object(a, 'ROOT', root), patch.object(a, 'CORPUS', 'corpus.json'):
                with self.assertRaisesRegex(ValueError, 'Cached record changed'): a.analyze(output)
            self.assertFalse(output.exists())


if __name__ == '__main__': unittest.main()
