"""Exporter schema/provenance fixtures are not native measurements."""
import csv
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from isaforge import codesign as c
from scripts import export_guarded_corpus as e


class GuardedCorpusExportContracts(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name); self.selection=self.root/'selection'; self.target=self.root/'target'
        self.output=self.root/'export'; self.old_path=self.root/'old-corpus.json'
        self.old=self.row('old','embench-old',3)
        self.new=self.row('new','embench-sha256',4); self.new['measurement_record_seconds']=3.5
        old_failed=self.failed('old-failed','embench-old',2,'old failure')
        new_failed=self.failed('new-failed','embench-sha256',3,'new infrastructure failure')
        self.history=dict(rows=[self.old],failed_attempts=[old_failed],contexts={'old':{}},independent_workload_groups=['embench-old'])
        self.costs=dict(total_candidate_wall_seconds=5,total_candidate_attempts=2)
        self.checked=dict(public=[self.new,new_failed],outcomes=[self.new,new_failed],
            attempt_collection_complete=True,candidate_wall_seconds_complete=True,unattempted=[],
            charged_candidate_attempts=2,candidate_wall_seconds=7,context_id='new-context',
            reference_censored_candidates=['new-failed'])
        self.report=dict(historical_costs=self.costs,raw_audit=self.checked)
        self.annotations=[dict(workload='embench-old',formula=old_failed['formula'],failure_reason='old failure',
            measurement_seconds=2,failure_class='infrastructure_unknown',reference_censored=True,correctness_verified=None)]
        c.seal(self.selection/'protocol.json',dict(target_workload='embench-sha256',source_bindings={}))
        c.seal(self.selection/'model/protocol.json',dict(contexts={'new':{}},source_bindings={},packages={}))
        c.seal(self.selection/'report.json',self.report)
        c.seal(self.target/'evaluation-protocol.json',dict(context_id='new-context'))
        c.seal(self.old_path,self.history)

    def row(self,identity,group,seconds):
        row={key:1 for key in e.FIELDS}
        row.update(candidate_id=identity,benchmark=group+':context',formula='add(in0,in1)',
            workload_group=group,candidate_family='add(input,input)',latency_features={'baseline_cycles':1000},
            measurement_seconds=seconds,measurement_source='synthesis_estimate',
            correctness_verified=True,timing_feasible=True,device_fits=True)
        return row

    def failed(self,identity,group,seconds,error):
        row=self.row(identity,group,seconds)
        for key in ('speedup','candidate_cycles','area_delta_lut4','area','area_cap','routed_fmax_min_mhz',
                    'correctness_verified','timing_feasible','device_fits','baseline_cycles',
                    'baseline_period_ns','candidate_period_ns','measurement_source'):
            row.pop(key)
        row.update(status='failed',error=error,failure_class='infrastructure_unknown',reference_censored=True)
        return row

    def run_export(self):
        with patch.object(e.selection,'authenticate_history',return_value=(self.history,self.costs)) as history, \
             patch.object(e.selection,'evaluate',return_value=self.report) as verify, \
             patch.object(e.selection,'CORPUS',self.old_path), \
             patch.object(e,'history_interpretations',return_value=(self.annotations,'history-manifest')):
            result=e.export(self.selection,self.target,self.output,history_raw_root='history-raw')
            history.assert_called_once_with('history-raw')
            verify.assert_called_once_with(self.selection.resolve(),self.target.resolve(),history_raw_root='history-raw',verify=True)
        return result

    def test_export_authenticates_keeps_censoring_and_distinguishes_timer_scopes(self):
        old_hash=c.sha(self.old_path); result=self.run_export()
        self.assertEqual(result['successful_labels'],2)
        self.assertEqual(len(result['failed_attempts']),2)
        self.assertEqual(result['total_candidate_attempt_wall_seconds'],12)
        self.assertEqual(result['total_candidate_attempts'],4)
        self.assertEqual(c.sha(self.old_path),old_hash)
        old,new=result['rows']
        self.assertIsNone(old['measurement_record_seconds'])
        self.assertEqual(new['measurement_record_seconds'],3.5)
        self.assertEqual(new['measurement_seconds'],4)
        self.assertIn('ledger',new['measurement_timer_scope'])
        self.assertTrue(all(r['reference_censored'] for r in result['failed_attempts']))
        self.assertTrue(all(r['correctness_verified'] is None for r in result['failed_attempts']))
        self.assertTrue(all('speedup' not in r for r in result['failed_attempts']))
        with (self.output/'verified-labels.csv').open() as stream: rows=list(csv.DictReader(stream))
        self.assertEqual(json.loads(rows[1]['latency_features']),{'baseline_cycles':1000})
        provenance=c.unseal(self.output/'provenance.json')
        self.assertEqual(provenance['source_bindings'][e.SOURCE],c.sha(e.ROOT/e.SOURCE))
        self.assertTrue(provenance['replay_verified'])
        for name,digest in c.unseal(self.output/'manifest.json').items(): self.assertEqual(c.sha(self.output/name),digest)

    def test_fresh_output_required_before_any_authentication_or_target_reads(self):
        self.output.mkdir()
        with patch.object(e.selection,'authenticate_history',side_effect=AssertionError('Read inputs')), \
             patch.object(e.selection,'evaluate',side_effect=AssertionError('Opened target')):
            with self.assertRaisesRegex(ValueError,'fresh corpus'):
                e.export(self.selection,self.target,self.output)

    def test_partial_or_unknown_cost_collection_cannot_be_exported_as_complete(self):
        for field,value in [('attempt_collection_complete',False),('candidate_wall_seconds_complete',False),
                            ('unattempted',['candidate_00'])]:
            previous=self.checked[field]; self.checked[field]=value
            with self.assertRaisesRegex(ValueError,'Complete charged guarded pool'): self.run_export()
            self.checked[field]=previous
        self.assertFalse(self.output.exists())

    def test_old_failure_classification_must_match_authenticated_identity(self):
        self.annotations[0]['failure_reason']='another failure'
        with self.assertRaisesRegex(ValueError,'Historical failure identity'): self.run_export()

    def test_failed_attempt_cannot_gain_a_performance_label(self):
        self.checked['outcomes'][1]['speedup']=1.2
        with self.assertRaisesRegex(ValueError,'invented labels'): self.run_export()

    def test_duplicate_identity_between_old_and_new_is_rejected(self):
        self.checked['outcomes'][0]['candidate_id']='old'
        with self.assertRaisesRegex(ValueError,'Duplicate corpus'): self.run_export()

    def test_historical_auth_failure_never_reads_new_target(self):
        with patch.object(e.selection,'authenticate_history',side_effect=ValueError('bad historical archive')), \
             patch.object(e.selection,'evaluate',side_effect=AssertionError('Target opened')):
            with self.assertRaisesRegex(ValueError,'bad historical archive'):
                e.export(self.selection,self.target,self.output)


if __name__=='__main__': unittest.main()
