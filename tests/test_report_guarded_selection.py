"""Presentation contracts for synthetic completed reports; no native evidence."""
import copy
import csv
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from isaforge import codesign as c
from scripts import report_guarded_selection as r


def audit_fixture():
    public=[dict(candidate_id='ok',formula='add(in0,in1)',benchmark='embench-fixture:ctx'),
            dict(candidate_id='unknown',formula='xor(in0,in1)',benchmark='embench-fixture:ctx')]
    return dict(public=public,pool_names=['candidate_00','candidate_01'],outcomes=[
        dict(public[0],candidate_cycles=900,speedup=1000/900,area=1032,area_delta_lut4=32,
             routed_fmax_min_mhz=60,measurement_seconds=40,measurement_record_seconds=39),
        dict(public[1],status='failed',measurement_seconds=31,error='disk preflight',
             failure_class='infrastructure_unknown',reference_censored=True)],
        failed_or_interrupted=[dict(name='candidate_01',status='failed',classification='infrastructure_unknown',
            elapsed_seconds=31,error='disk preflight',correctness_verified=None,reference_censored=True)],
        unattempted=[],charged_candidate_attempts=2,candidate_wall_seconds=71,
        candidate_wall_seconds_complete=True,baseline_wall_seconds=50,native_command_seconds=100,native_command_count=20)


def report_fixture(scope='prospective'):
    references=[dict(area_delta_lut4_cap=cap,best_verified_speedup=1.0,selected_name=None,
                     complete_pool_reference=False) for cap in (32,64,128)]
    runs=[dict(policy=policy,seed=seed,area_delta_lut4_cap=cap,
        curve=[dict(budget=budget,best_speedup=1.0,target_measurement_seconds=10.0*budget,
                    inference_seconds=.1,regret=0,failed_attempts=0) for budget in (1,2,3)])
        for policy in r.LABELS for seed in range(5) for cap in (32,64,128)]
    summary=[dict(policy=policy,area_delta_lut4_cap=cap,budget=budget,mean_best_speedup=1.0,
        mean_regret=0.0,oracle_hits=5,mean_target_measurement_seconds=10.0*budget,mean_failed_attempts=0)
        for policy in r.LABELS for cap in (32,64,128) for budget in (1,2,3)]
    return dict(schema='isaforge-guarded-selection-report-v1',scope=scope,raw_audit=audit_fixture(),
        selection=dict(runs=runs,summary=summary),best_verified_references=references,
        reference_censored_candidates=['candidate_01'],historical_costs=dict(successful_labels=27,
            failed_attempts=3,total_candidate_attempts=30,verified_candidate_wall_seconds=1647.956297294,
            failed_candidate_wall_seconds=50.196657040,total_candidate_wall_seconds=1698.152954334))


class GuardedReportContracts(unittest.TestCase):
    def test_candidate_metrics_and_nullable_infrastructure_correctness(self):
        good,unknown=r.candidate_rows(audit_fixture())
        self.assertEqual((good['cycles'],good['total_lut4'],good['added_lut4'],good['min_fmax_mhz']),
                         (900,1032,32,60))
        self.assertEqual(good['charged_wall_seconds'],40)
        self.assertEqual(good['measurement_record_seconds'],39)
        self.assertIsNone(unknown['correctness_verified'])
        self.assertTrue(unknown['reference_censored'])
        self.assertEqual(unknown['charged_wall_seconds'],31)
        self.assertEqual(unknown['cycles'],'')

    def test_unattempted_or_unknown_duration_is_never_fabricated_zero(self):
        audit=audit_fixture(); audit['outcomes'].pop(); audit['failed_or_interrupted']=[]
        row=r.candidate_rows(audit)[1]
        self.assertEqual(row['status'],'unattempted')
        self.assertIsNone(row['charged_wall_seconds'])
        self.assertIsNone(row['correctness_verified'])
        audit['failed_or_interrupted']=[dict(name='candidate_01',status='started',elapsed_seconds=None,
            correctness_verified=None,reference_censored=True)]
        self.assertIsNone(r.candidate_rows(audit)[1]['charged_wall_seconds'])

    def test_equal_budget_rows_require_all_five_dependent_seeds(self):
        report=report_fixture()
        rows=r.endpoint_rows(report['selection'],report['best_verified_references'],report['historical_costs'])
        self.assertEqual(len(rows),90)
        self.assertEqual(rows[0]['dependent_seed_count'],5)
        self.assertEqual(rows[0]['positive_design_reference_hits'],0)
        self.assertAlmostEqual(rows[0]['history_plus_target_attempt_seconds'],1708.152954334)
        report['selection']['runs'].pop()
        with self.assertRaisesRegex(ValueError,'five distinct dependent seed'):
            r.endpoint_rows(report['selection'],report['best_verified_references'],report['historical_costs'])

    def test_frozen_aggregate_and_complete_endpoint_grid_are_checked(self):
        report=report_fixture(); report['selection']['summary'][0]['mean_best_speedup']=1.1
        with self.assertRaisesRegex(ValueError,'summary differs'):
            r.endpoint_rows(report['selection'],report['best_verified_references'],report['historical_costs'])
        report=report_fixture(); report['selection']['summary'].pop()
        with self.assertRaisesRegex(ValueError,'Complete policy/cap/budget'):
            r.endpoint_rows(report['selection'],report['best_verified_references'],report['historical_costs'])

    def test_build_reads_only_post_collection_report_and_discloses_censoring_cost_and_ties(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)/'selection'; output=Path(folder)/'output'
            c.seal(root/'report.json',report_fixture(scope='engineering-validation'))
            with patch('isaforge.guarded_evidence.audit',side_effect=AssertionError('Opened target')), \
                 patch('isaforge.model.SpeedupPredictor.fit',side_effect=AssertionError('Fitted model')):
                result=r.build(root,output)
            text=(output/'results.md').read_text()
            self.assertIn('lower bound',text)
            self.assertIn('no learned selection win',text)
            self.assertIn('not a held-out source-family ML test',text)
            self.assertIn('five seeds are dependent',text)
            self.assertIn('1698.152954',text)
            self.assertIn('50.196657',text)
            self.assertEqual((result['new_model_fits'],result['new_native_jobs']),(0,0))
            with (output/'candidates.csv').open() as stream:
                rows=list(csv.DictReader(stream))
            self.assertEqual(rows[1]['correctness_verified'],'')
            self.assertEqual(rows[1]['charged_wall_seconds'],'31')
            with (output/'policy-endpoints.csv').open() as stream:
                endpoint=next(csv.DictReader(stream))
            self.assertIn('mean_gap_to_verified_reference',endpoint)
            self.assertNotIn('oracle_hits',endpoint)

    def test_missing_completed_report_and_output_inside_frozen_root_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)/'selection'
            with self.assertRaisesRegex(ValueError,'Completed guarded selection report required'):
                r.build(root,Path(folder)/'output')
            with self.assertRaisesRegex(ValueError,'outside the frozen selection directory'):
                r.build(root,root/'report')

    def test_retained_baseline_analytic_residual_and_frozen_regression_diagnostics_need_no_target(self):
        report=report_fixture()
        report['raw_audit']['public'][0]['latency_features']=dict(baseline_cycles=1000,estimated_saved_cycles=100)
        report['raw_audit']['outcomes'][0]['baseline_cycles']=1000
        report['selection']['diagnostics']=[dict(model=model,seed=seed,mae=mae,interval_coverage=coverage,
            calibrated_confidence=False) for model,mae,coverage in [('raw',.01,.2),('normalized',.001,.6)] for seed in range(5)]
        good,unknown=r.candidate_rows(report['raw_audit'])
        self.assertEqual((good['estimated_saved_cycles'],good['measured_saved_cycles'],good['saved_cycle_residual']),(100,100,0))
        self.assertEqual(unknown['saved_cycle_residual'],'')
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)/'selection'; output=Path(folder)/'output'
            c.seal(root/'report.json',report); c.seal(root/'baseline.json',dict(baseline_lut4=1000))
            with patch('isaforge.guarded_evidence.audit',side_effect=AssertionError('Opened target')), \
                 patch('isaforge.model.SpeedupPredictor.fit',side_effect=AssertionError('Fitted model')):
                r.build(root,output)
            text=(output/'results.md').read_text()
            self.assertIn('1000 cycles; 1000 integrated LUT4',text)
            self.assertIn('minimum routed Fmax: not retained',text)
            self.assertIn('Residual: measured minus estimated',text)
            self.assertIn('Frozen regression diagnostics',text)
            self.assertIn('0.001000000',text)
            self.assertIn('60.0',text)
            with (output/'regression-diagnostics.csv').open() as stream:
                diagnostics={row['model']:row for row in csv.DictReader(stream)}
            self.assertEqual(diagnostics['normalized']['dependent_seed_repetitions'],'5')
            self.assertEqual(diagnostics['normalized']['calibrated_confidence'],'False')


if __name__=='__main__': unittest.main()
