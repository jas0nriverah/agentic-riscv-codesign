"""Reporting semantics; synthetic fixtures do not add processor evidence."""
import csv
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from isaforge import codesign as c
from scripts import report_budget_campaign as r


class CampaignReportContracts(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)

    def failure(self, name, error, raw=None, seconds=7.0):
        base=self.root/'measurements'/name
        attempt=base/'attempt-000'; attempt.mkdir(parents=True)
        c.write(attempt/'failure.json',dict(error=error,elapsed_seconds=seconds))
        if raw is not None: c.write(attempt/'simulation/simulation.json',raw)
        return base

    def test_infrastructure_failure_has_unknown_correctness_and_charged_time(self):
        base=self.failure('candidate_disk',"ValueError('Less than 2 GiB free')",seconds=31.322581916)
        value=r.failed_candidate(base)
        self.assertEqual(value['failure_class'],'infrastructure_unknown')
        self.assertIsNone(value['correctness_verified'])
        self.assertTrue(value['reference_censored'])
        self.assertEqual(value['measurement_seconds'],31.322581916)

    def test_raw_self_check_failure_is_specific_to_recorded_run(self):
        base=self.failure('candidate_selfcheck',"ValueError('Command exited 7')",raw=dict(
            words=[1230192966,0,1000,200,0],markers=2,partial_report_bits=0,stack_violations=0))
        value=r.failed_candidate(base)
        self.assertEqual(value['failure_class'],'self_check_failure')
        self.assertFalse(value['correctness_verified'])
        self.assertFalse(value['reference_censored'])
        self.assertEqual(value['observed_unverified_cycles'],1000)
        self.assertIn('recorded run',value['correctness'])

    def test_exit_seven_without_complete_raw_report_does_not_prove_self_check_failure(self):
        base=self.failure('candidate_timeout',"ValueError('Command exited 7')",raw=dict(
            words=[],markers=0,partial_report_bits=0,stack_violations=0))
        value=r.failed_candidate(base)
        self.assertEqual(value['failure_class'],'outcome_unknown')
        self.assertIsNone(value['correctness_verified'])
        self.assertTrue(value['reference_censored'])

    def test_guard_observation_is_known_memory_contract_failure(self):
        base=self.failure('candidate_guard',"ValueError('Command exited 10')",raw=dict(
            words=[],markers=0,stack_violations=2,first_violation={'kind':'ram-write','address':5956}))
        value=r.failed_candidate(base)
        self.assertEqual(value['failure_class'],'memory_contract_failure')
        self.assertFalse(value['correctness_verified'])
        self.assertFalse(value['reference_censored'])

    def successful_record(self, name='candidate_ok'):
        return dict(name=name,performance={'cycles':900},speedup=1000/900,added_lut4=32,
            resources=dict(lut4_count=1032,flip_flop_count=696,carry_count=297),
            routes=[dict(limiting_internal_fmax_mhz=v) for v in (14.0,13.0,15.0)],
            timing_feasible=True,elapsed_seconds=40.0)

    def candidate_fixture(self):
        c.seal(self.root/'discovery/discovery.json',dict(pool=[
            dict(name='candidate_ok',formula='add(in0,in1)'),
            dict(name='candidate_disk',formula='xor(in0,in1)')]))
        c.seal(self.root/'measurements/candidate_ok/measurement.json',self.successful_record())
        self.failure('candidate_disk',"ValueError('Less than 2 GiB free')",seconds=31.322581916)

    def test_candidate_table_preserves_verified_resources_and_nullable_unknown_feasibility(self):
        self.candidate_fixture()
        verified,unknown=r.candidate_rows(self.root,'embench-demo')
        self.assertEqual((verified['cycles'],verified['lut4'],verified['added_lut4'],
                          verified['flip_flops'],verified['carry_cells'],verified['min_fmax_mhz']),
                         (900,1032,32,696,297,13.0))
        self.assertTrue(verified['feasible_at_64'])
        self.assertIsNone(unknown['feasible_at_64'])
        self.assertEqual(unknown['speedup'],'')
        reference=r.reference_status([verified,unknown])
        self.assertFalse(reference['complete_for_recorded_pool'])
        self.assertEqual(reference['censored_candidates'],['candidate_disk'])
        self.assertIn('Lower bound',reference['interpretation'])
        self.assertNotIn('oracle',reference['label'].lower())

    def test_tied_models_are_explicitly_not_a_selection_win(self):
        points=[dict(policy=k,mean_best_speedup=1.0) for k in
                ('calibrated_latency','raw_regression','ranking','normalized_xgb','hybrid_gp_zero_shot','hybrid_gp_adapt')]
        self.assertIn('no learned selection win',r.primary_comparison(points))

    def test_export_uses_verified_reference_terms_and_preserves_historical_cost(self):
        self.candidate_fixture()
        c.seal(self.root/'measurements/baseline/measurement.json',dict(
            performance={'cycles':1000},resources={'lut4_count':1000}))
        snapshot=self.root/'snapshot'; raw=self.root/'raw'; output=self.root/'output'
        # The presenter normally consumes the authenticated restored raw roots.
        target=raw/'target-demo'; target.mkdir(parents=True)
        import shutil
        shutil.copytree(self.root/'measurements',target/'measurements')
        shutil.copytree(self.root/'discovery',target/'discovery')
        summary=[dict(policy=k,budget=budget,area_delta_lut4_cap=64,mean_best_speedup=1.0,
                      oracle_hits=5,mean_regret=0.0,mean_target_measurement_seconds=31.322581916)
                 for k in r.LABELS for budget in (1,2,3)]
        report=dict(targets={'embench-demo':dict(summary=summary,
            oracles=[dict(area_delta_lut4_cap=64,speedup=1.0)])},
            historical_costs=dict(candidate_labels=18,candidate_wall_seconds=793.926327))
        c.seal(snapshot/'selection/campaign-report.json',report)
        with patch.object(r,'replay',return_value={'new_native_jobs':0}):
            r.build(snapshot,raw,output)
        text=(output/'results.md').read_text()
        self.assertIn('lower bound',text.lower())
        self.assertIn('no learned selection win',text)
        self.assertIn('793.926327',text)
        self.assertNotIn('measured oracle',text.lower())
        with (output/'policy-endpoints.csv').open() as stream:
            endpoint=next(csv.DictReader(stream))
        self.assertIn('verified_reference_hits',endpoint)
        self.assertIn('mean_gap_to_verified_reference',endpoint)
        self.assertNotIn('oracle_hits',endpoint)
        self.assertEqual(endpoint['reference_complete'],'False')


if __name__=='__main__': unittest.main()
