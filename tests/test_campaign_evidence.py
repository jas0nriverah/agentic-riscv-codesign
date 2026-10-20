"""Campaign boundary/charging tests; fixtures are not processor evidence."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from isaforge import campaign_evidence as e, codesign as c


class CampaignContracts(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'target'; self.root.mkdir()

    def receipt(self,name,text='native output',seconds=1,failure=None):
        path=self.root/name; path.parent.mkdir(parents=True,exist_ok=True); path.write_text(text)
        return dict(log=name,log_sha256=c.sha(path),elapsed_seconds=seconds,
                    returncode=1 if failure else 0,expected_returncode=0,failure=failure)

    def baseline(self):
        c.seal(self.root/'plan.json',dict(context_id='context',source_bindings={},inputs={},memory_partition=e.partition.PARTITION))
        c.seal(self.root/'discovery/discovery.json',dict(pool=[dict(name='candidate_00',candidate_id='id')]))
        path=self.root/'measurements/baseline'; path.mkdir(parents=True)
        c.seal(path/'measurement.json',dict(elapsed_seconds=2,artifacts={}))
        initial=[self.receipt('discovery/profile.log')]
        c.seal(self.root/'commands.json',initial)
        public=[dict(candidate_id='id',formula='xor(in0,in1)')]
        before=dict(context_id='context',artifacts={n:c.sha(self.root/n) for n in e.BASELINE_FILES},
                    receipts=initial,pool_names=['candidate_00'],public_sha256=c.digest(public))
        return before,public

    def test_target_labels_rejected_before_any_file_reads(self):
        path=self.root/'measurements/candidate_00/measurement.json'
        path.parent.mkdir(parents=True); path.write_text('sealed labels')
        with patch.object(c,'unseal',side_effect=AssertionError('Opened target')):
            with self.assertRaisesRegex(ValueError,'candidate measurements already exist'):
                e.baseline_public(self.root)

    def test_prelabel_failed_attempt_also_rejected_before_reads(self):
        (self.root/'measurements/candidate_00/attempt-000').mkdir(parents=True)
        with patch.object(c,'unseal',side_effect=AssertionError('Opened target')):
            with self.assertRaisesRegex(ValueError,'Candidate attempt exists'):
                e.baseline_public(self.root)

    def test_receipt_prefix_and_raw_hash_must_both_survive(self):
        before,_=self.baseline()
        suffix=self.receipt('measurements/candidate_00/attempt-000/build.log')
        c.seal(self.root/'commands.json',before['receipts']+[suffix])
        self.assertEqual(len(e._chronology(self.root,before)),2)
        c.seal(self.root/'commands.json',[suffix]+before['receipts'])
        with self.assertRaisesRegex(ValueError,'prefix differs'): e._chronology(self.root,before)
        c.seal(self.root/'commands.json',before['receipts']+[suffix])
        (self.root/suffix['log']).write_text('changed')
        with self.assertRaisesRegex(ValueError,'log changed'): e._chronology(self.root,before)

    def test_frozen_baseline_and_candidate_only_suffix_enforced(self):
        before,_=self.baseline()
        suffix=self.receipt('analysis/unpaid-target.log')
        c.seal(self.root/'commands.json',before['receipts']+[suffix])
        with self.assertRaisesRegex(ValueError,'post-freeze native scope'): e._chronology(self.root,before)
        (self.root/'plan.json').write_text('changed')
        with self.assertRaisesRegex(ValueError,'baseline changed'): e._chronology(self.root,before)

    def test_duplicate_native_log_receipts_rejected(self):
        row=self.receipt('profile.log')
        c.seal(self.root/'commands.json',[row,row])
        with self.assertRaisesRegex(ValueError,'Duplicate native receipt'): e._receipts(self.root)

    def test_failed_attempt_is_charged_and_has_no_successful_label(self):
        before,public=self.baseline()
        failed=self.root/'measurements/candidate_00/attempt-000/failure.json'
        failed.parent.mkdir(parents=True)
        c.write(failed,dict(error='compile failure',elapsed_seconds=7))
        suffix=self.receipt('measurements/candidate_00/attempt-000/compile.log',seconds=6,failure='exit1')
        c.seal(self.root/'commands.json',before['receipts']+[suffix])
        rows,audit=e.outcomes(self.root,before,public)
        self.assertEqual(rows,[dict(public[0],status='failed',measurement_seconds=7,error='compile failure')])
        self.assertEqual(audit['target_candidate_wall_seconds'],7)
        self.assertEqual(audit['native_command_seconds'],7)
        self.assertEqual(len(audit['failed_attempts']),1)
        self.assertNotIn('speedup',rows[0])

    def test_retry_cannot_be_hidden_behind_one_candidate_charge(self):
        before,public=self.baseline()
        for number in (0,1):
            (self.root/f'measurements/candidate_00/attempt-{number:03d}').mkdir(parents=True)
        suffix=self.receipt('measurements/candidate_00/attempt-000/compile.log')
        c.seal(self.root/'commands.json',before['receipts']+[suffix])
        with self.assertRaisesRegex(ValueError,'retries need separately charged protocol'):
            e.outcomes(self.root,before,public)

    def report(self,offset):
        return dict(runs=[dict(policy=policy,seed=seed,area_delta_lut4_cap=64,
            curve=[dict(budget=3,best_speedup=1.1+(offset if policy=='normalized_xgb' else 0),
                        regret=.2-(offset if policy=='normalized_xgb' else 0),target_measurement_seconds=3)])
            for policy in ('frequency','merit','calibrated_latency','latency_cost_heuristic','normalized_xgb')
            for seed in (0,1)])

    def test_pairing_averages_seeds_within_workload_then_workloads(self):
        result=e.paired_summary({'workload-a':self.report(.02),'workload-b':self.report(-.01)})
        selected=[r for r in result['aggregate'] if r['policy']=='normalized_xgb' and r['comparator']=='calibrated_latency'][0]
        self.assertAlmostEqual(selected['mean_workload_speedup_difference'],.005)
        self.assertEqual(selected['independent_workloads'],2)
        self.assertEqual((selected['workload_mean_wins'],selected['workload_mean_losses']),(1,1))
        self.assertFalse(result['seed_repetitions_are_independent'])

    def test_incomplete_paired_seed_grid_is_rejected(self):
        report=self.report(0); report['runs'].pop()
        with self.assertRaisesRegex(ValueError,'Incomplete paired endpoints'):
            e.paired_summary({'workload':report})

    def test_prediction_replay_uses_history_before_any_target_outcome(self):
        from isaforge import budgeted_selection as model
        history=[dict(candidate_id='h',workload_group='historical',benchmark='old',formula='add(in0,in1)')]
        public=[dict(candidate_id='target',formula='xor(in0,in1)',benchmark='new')]
        protocol=dict(target_workload='new-workload',historical_training_ids=['h'],excluded_related_ids=[],seeds=[0])
        frozen=dict(seed=0,raw=[1],inference_seconds=5)
        c.seal(self.root/'public.json',public); c.seal(self.root/'history.json',history)
        c.seal(self.root/'protocol.json',protocol); c.seal(self.root/'predictions.json',[frozen])
        with patch.object(model,'zero_shot',return_value=dict(frozen,inference_seconds=999)) as fitted:
            result=e.verify_predictions(self.root,history)
            fitted.assert_called_once_with(history,public,0)
        self.assertEqual(result['target_outcomes_used'],0)
        history[0]['workload_group']='new-workload'
        with self.assertRaisesRegex(ValueError,'Target workload in refit history'):
            e.verify_predictions(self.root,history)

    def test_extended_dispatch_checks_exact_entrypoint_partition_and_ceiling(self):
        from isaforge import extended_workload as extended
        plan=dict(workload='edn',pool_size=6,memory_partition=dict(extended.PARTITION),
                  compiler_flags=list(extended.bounded.compact.FLAGS),
                  build_variant=dict(required_entrypoint=extended.SOURCE),simulation_cycle_limit=800000000)
        self.assertIs(e._adapter(plan),extended)
        plan['simulation_cycle_limit']=200000000
        with self.assertRaisesRegex(ValueError,'cycle limit'): e._adapter(plan)
        plan['simulation_cycle_limit']=800000000
        plan['memory_partition']=e.partition.PARTITION
        with self.assertRaisesRegex(ValueError,'memory/compiler'): e._adapter(plan)

    def test_newly_consumed_extended_history_uses_its_adapter_audit(self):
        from isaforge import extended_workload as extended
        plan=dict(workload='edn',context_id='context',pool_size=6,memory_partition=dict(extended.PARTITION),
                  compiler_flags=list(extended.bounded.compact.FLAGS),
                  build_variant=dict(required_entrypoint=extended.SOURCE),simulation_cycle_limit=800000000)
        discovery=dict(pool=[dict(name='candidate_00')]); baseline=dict(elapsed_seconds=1)
        public=[dict(candidate_id='id',benchmark='embench-edn:context',formula='add(in0,in1)')]
        def unseal(path):
            if Path(path).name=='plan.json': return plan
            if Path(path).name=='discovery.json': return discovery
            return baseline
        with patch.object(c,'unseal',side_effect=unseal), \
             patch.object(extended,'audit',return_value=dict(native_seconds=3)) as audit, \
             patch.object(e.partition,'audit',side_effect=AssertionError('Canonical audit used')), \
             patch.object(e,'_public',return_value=public),patch.object(e,'_calibration',return_value={}), \
             patch.object(e,'_outcome',return_value=dict(public[0],measurement_seconds=2)), \
             patch.object(e,'_receipts',return_value=[]),patch.object(e.prior_inputs,'context',return_value={}):
            rows,_,cost=e.history_rows([self.root])
        audit.assert_called_once_with(self.root.resolve())
        self.assertEqual(rows[0]['workload_group'],'embench-edn')
        self.assertEqual(cost['candidate_labels'],1)

    def test_export_requires_evaluated_consumed_campaign(self):
        with self.assertRaisesRegex(ValueError,'Evaluate campaign before exporting'):
            e.export_corpus(self.root,[self.root],self.root/'export.json')

    def test_qualified_adapter_keeps_plan_partitions_independent(self):
        from isaforge import qualified_workload as qualified
        plan=dict(workload='ud',pool_size=6,memory_partition=qualified.partition_spec(),
                  compiler_flags=list(qualified.bounded.compact.FLAGS),
                  build_variant=dict(required_entrypoint=qualified.SOURCE),simulation_cycle_limit=800000000)
        first=e._adapter(plan)
        plan['memory_partition']=qualified.partition_spec(7168,7424)
        second=e._adapter(plan)
        self.assertEqual(first.PARTITION['stack_floor'],7296)
        self.assertEqual(second.PARTITION['stack_floor'],7424)
        self.assertIn('floor==7296',first.monitor_source())
        self.assertIn('floor==7424',second.monitor_source())
        plan['memory_partition']['stack_bytes']=999
        with self.assertRaisesRegex(ValueError,'partition'): e._adapter(plan)


if __name__=='__main__': unittest.main()
