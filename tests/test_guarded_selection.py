"""Guarded selection chronology/cost contracts; fixtures are not measured evidence."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from isaforge import guarded_selection as s, codesign as c


class GuardedSelectionContracts(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name); self.target=self.base/'target'; self.output=self.base/'selection'
        self.target.mkdir(); self.corpus_path=self.base/'corpus.json'
        self.public=[dict(candidate_id='t',benchmark='fresh:context',formula='add(in0,in1)')]
        self.history=dict(rows=[dict(candidate_id='h1',workload_group='embench-old1',measurement_seconds=2),
            dict(candidate_id='h2',workload_group='embench-old2',measurement_seconds=3)],
            failed_attempts=[dict(measurement_seconds=7)],contexts={},
            independent_workload_groups=['embench-old1','embench-old2'])
        c.seal(self.corpus_path,self.history)
        self.costs=dict(verified_candidate_wall_seconds=5,failed_candidate_wall_seconds=7,total_candidate_wall_seconds=12)
        receipts=[dict(log='discovery/profile.json')]
        for name,value in (('plan.json',{}),('discovery/discovery.json',{}),('measurements/baseline/measurement.json',{})):
            c.seal(self.target/name,value)
        self.before=dict(workload='embench-fresh',context_id='context',pool_names=['candidate_00'],receipts=receipts,
            artifacts={name:c.sha(self.target/name) for name in
                       ('plan.json','discovery/discovery.json','measurements/baseline/measurement.json')})
        protocol=dict(schema='isaforge-guarded-measurement-protocol-v1',context_id='context',
            attempts_per_candidate=1,pool_names=['candidate_00'],baseline_receipts=receipts,
            area_caps=[32,64,128],clock_mhz=12.0,scope='dataset-expansion')
        c.seal(self.target/'evaluation-protocol.json',protocol)

    def model_freeze(self,training,public,contexts,output,**kwargs):
        output.mkdir()
        c.seal(output/'public.json',public)
        c.seal(output/'history.json',training)
        return {}

    def freeze(self,scope='prospective'):
        with patch.object(s,'CORPUS',self.corpus_path),patch.object(s,'SOURCES',(s.SOURCE,)), \
             patch.object(s.native,'baseline_public',return_value=(self.public,{},self.before)), \
             patch.object(s,'authenticate_history',return_value=(self.history,self.costs)), \
             patch.object(s.prior,'_calibration',return_value={'native_command_seconds':1}), \
             patch.object(s.model,'freeze',side_effect=self.model_freeze) as fit:
            result=s.freeze(self.target,self.output,scope=scope)
        return result,fit.call_args

    def audit(self):
        return dict(context_id='context',public=self.public,
            outcomes=[dict(self.public[0],status='failed',measurement_seconds=11,error='disk preflight')],
            attempt_collection_complete=True,unattempted=[],candidate_wall_seconds_complete=True,
            reference_censored_candidates=['candidate_00'],
            best_verified_references=[dict(area_delta_lut4_cap=64,best_verified_speedup=1.0,complete_pool_reference=False)])

    def evaluate(self,audit,*,verify=False):
        with patch.object(s,'CORPUS',self.corpus_path), \
             patch.object(s,'authenticate_history',return_value=(self.history,self.costs)), \
             patch.object(s.prior,'verify_predictions',return_value={'target_outcomes_used':0}) as refit, \
             patch.object(s.evidence,'audit',return_value=audit), \
             patch.object(s.model,'evaluate',return_value={'frozen_model_result':True}) as scored:
            result=s.evaluate(self.output,self.target,verify=verify)
        return result,scored,refit

    def test_prospective_rejects_any_existing_source_family_before_model_fit(self):
        self.before['workload']='embench-old1'
        with self.assertRaisesRegex(ValueError,'new source workload'):
            self.freeze()
        self.assertFalse(self.output.exists())

    def test_engineering_scope_excludes_whole_target_and_discloses_all_historical_cost(self):
        self.before['workload']='embench-old1'
        result,call=self.freeze('engineering-validation')
        self.assertEqual([r['candidate_id'] for r in call.args[0]],['h2'])
        self.assertEqual(call.kwargs['scope'],'consumed-data development')
        self.assertEqual(call.kwargs['cost_provenance']['total_candidate_wall_seconds'],12)
        self.assertEqual(result['whole_target_excluded_ids'],['h1'])
        self.assertEqual(result['historical_costs']['failed_candidate_wall_seconds'],7)
        self.assertEqual(result['target_labels_read'],0)

    def test_preexisting_candidate_ledger_rejected_before_baseline_or_history_reads(self):
        c.seal(self.target/'attempt-ledger/candidate_00.json',{'status':'started'})
        with patch.object(s.native,'baseline_public',side_effect=AssertionError('Opened baseline')), \
             patch.object(s,'authenticate_history',side_effect=AssertionError('Opened history')):
            with self.assertRaisesRegex(ValueError,'preceded prediction freeze'):
                s.freeze(self.target,self.output)

    def test_existing_native_protocol_must_precede_selection_freeze(self):
        (self.target/'evaluation-protocol.json').unlink()
        with self.assertRaises((FileNotFoundError,ValueError)): self.freeze()
        self.assertFalse(self.output.exists())

    def test_protocol_tampering_and_incomplete_attempts_never_enter_paid_replay(self):
        self.freeze()
        for key,value in (('attempt_collection_complete',False),('candidate_wall_seconds_complete',False),
                          ('unattempted',['candidate_00'])):
            audit=self.audit(); audit[key]=value
            with self.assertRaisesRegex(ValueError,'All frozen candidates require terminal attempts'):
                self.evaluate(audit)
        protocol=c.unseal(self.target/'evaluation-protocol.json'); protocol['area_caps']=[128]
        c.seal(self.target/'evaluation-protocol.json',protocol)
        with self.assertRaisesRegex(ValueError,'Frozen evaluation protocol changed'):
            self.evaluate(self.audit())

    def test_unknown_failed_attempt_is_charged_and_censor_annotation_survives(self):
        self.freeze()
        result,scored,refit=self.evaluate(self.audit())
        self.assertEqual(scored.call_args.args[1][0]['measurement_seconds'],11)
        self.assertEqual(result['reference_censored_candidates'],['candidate_00'])
        self.assertFalse(result['best_verified_references'][0]['complete_pool_reference'])
        self.assertEqual(result['prediction_refit']['target_outcomes_used'],0)
        self.assertEqual(result['historical_costs']['total_candidate_wall_seconds'],12)
        self.assertEqual(refit.call_args.args[1],self.history['rows'])
        repeated,_,_=self.evaluate(self.audit(),verify=True)
        self.assertEqual(result,repeated)

    def test_unknown_duration_or_changed_historical_failure_cost_cannot_be_scored(self):
        self.freeze()
        for elapsed in (float('nan'),float('inf'),None,0):
            audit=self.audit(); audit['outcomes'][0]['measurement_seconds']=elapsed
            with self.assertRaisesRegex(ValueError,'Finite positive charged attempt durations'):
                self.evaluate(audit)
        self.costs['failed_candidate_wall_seconds']=8
        with self.assertRaisesRegex(ValueError,'historical labels/costs changed'):
            self.evaluate(self.audit())

    def test_expanded_corpus_is_compared_to_authenticated_archive_export(self):
        from scripts import reproduce_budget_campaign as old
        corpus=dict(rows=[dict(candidate_id=str(i),measurement_seconds=2) for i in range(27)],
            failed_attempts=[dict(measurement_seconds=3) for _ in range(3)],contexts={},
            successful_labels=27,independent_workload_groups=list('abcde'),historical_costs={},campaign_audits={})
        c.seal(self.corpus_path,corpus)
        with patch.object(s,'CORPUS',self.corpus_path),patch.object(old,'replay') as replay, \
             patch.object(s.prior,'export_corpus',return_value=corpus):
            derived,costs=s.authenticate_history(self.base/'historical-raw')
            self.assertEqual(costs['total_candidate_wall_seconds'],63)
            self.assertEqual(costs['verified_candidate_wall_seconds'],54)
            self.assertEqual(costs['failed_candidate_wall_seconds'],9)
            replay.assert_called_once()
        changed=copy.deepcopy(corpus); changed['failed_attempts'][0]['measurement_seconds']=100
        with patch.object(s,'CORPUS',self.corpus_path),patch.object(old,'replay'), \
             patch.object(s.prior,'export_corpus',return_value=changed):
            with self.assertRaisesRegex(ValueError,'Archived expanded history differs: failed_attempts'):
                s.authenticate_history(self.base/'historical-raw')


if __name__=='__main__': unittest.main()
