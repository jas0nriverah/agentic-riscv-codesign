"""Partial ledger/authentication fixtures are not measured research results."""
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from isaforge import codesign as c, guarded_evidence as e
from isaforge.workload_experiment import artifact_hashes


class GuardedEvidenceContracts(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'run'; self.root.mkdir()
        self.commands=[dict(log='measurements/baseline/build.log',elapsed_seconds=1,failure=None,returncode=0,expected_returncode=0)]
        plan=dict(source_bindings={e.SOURCE:c.sha(c.ROOT/e.SOURCE)},inputs={})
        plan['context_id']=c.digest(plan); self.plan=plan
        c.seal(self.root/'plan.json',plan)
        self.protocol=dict(schema='isaforge-guarded-measurement-protocol-v1',context_id=plan['context_id'],
            attempts_per_candidate=1,maximum_candidate_attempts=1,pool_names=['candidate_00'],
            discovery_sha256='discovery',baseline_sha256='baseline',scope='engineering-validation',
            clock_mhz=12.,route_seeds=[1,2,3],area_caps=[32,64,128],baseline_receipts=list(self.commands),source_bindings=plan['source_bindings'])
        c.seal(self.root/'evaluation-protocol.json',self.protocol)

    def ledger(self,name='candidate_00',status='failed',elapsed=3,start=1,end=1,error='Less than 2 GiB free'):
        base=self.root/'measurements'/name; base.mkdir(parents=True,exist_ok=True)
        if status=='success': c.seal(base/'measurement.json',{'record':'verified-fixture'})
        row=dict(schema='isaforge-guarded-attempt-v1',context_id=self.plan['context_id'],name=name,
            evaluation_id=c.digest([self.plan['context_id'],'discovery',name]),started_at_utc='2026-10-21T00:00:00Z',
            receipt_start=start,receipt_prefix_sha256=c.digest(self.commands[:start]),status=status,
            elapsed_seconds=elapsed,artifacts=artifact_hashes(base))
        if status!='started': row.update(receipt_end=end,error=error)
        if status=='success': row['record_sha256']=c.sha(base/'measurement.json')
        c.seal(self.root/'attempt-ledger'/(name+'.json'),row)
        return row

    def run_audit(self):
        from isaforge import guarded_workload as native
        self.ledger('baseline','success',2,0,1)
        pool=[dict(name='candidate_00',candidate_id='id',formula='add(in0,in1)')]
        public=[dict(candidate_id='id',benchmark='workload',formula='add(in0,in1)')]
        with patch.object(native,'check_plan'),patch.object(native,'authenticate_discovery',return_value={'pool':pool}), \
             patch.object(native,'adapter_for_plan',return_value=SimpleNamespace()), \
             patch.object(e.prior,'_receipts',return_value=self.commands),patch.object(e.prior,'_observations'), \
             patch.object(e,'_baseline',return_value=({'elapsed_seconds':1},{})), \
             patch.object(e.prior,'_calibration',return_value={}),patch.object(e.prior,'_public',return_value=public):
            return e.audit(self.root)

    def test_failed_preflight_with_no_native_receipt_is_still_charged(self):
        self.ledger()
        result=self.run_audit()
        self.assertEqual(result['charged_candidate_attempts'],1)
        self.assertEqual(result['candidate_wall_seconds'],3)
        self.assertTrue(result['candidate_wall_seconds_complete'])
        self.assertEqual(result['failed_or_interrupted'][0]['classification'],'infrastructure_unknown')
        self.assertTrue(result['attempt_collection_complete'])
        self.assertTrue(all(not r['complete_pool_reference'] for r in result['best_verified_references']))
        self.assertEqual(result['outcomes'][0]['status'],'failed')
        self.assertNotIn('speedup',result['outcomes'][0])

    def test_hard_interruption_retains_unknown_wall_time(self):
        self.ledger(status='started',elapsed=None)
        result=self.run_audit()
        self.assertEqual(result['charged_candidate_attempts'],1)
        self.assertFalse(result['candidate_wall_seconds_complete'])
        self.assertFalse(result['attempt_collection_complete'])
        self.assertEqual(result['failed_or_interrupted'][0]['elapsed_seconds'],None)
        self.assertEqual(result['outcomes'],[])

    def test_truncated_interrupted_raw_output_remains_archivable_unknown(self):
        self.ledger(status='started',elapsed=None)
        raw=self.root/'measurements/candidate_00/attempt-000/simulation/simulation.json'
        raw.parent.mkdir(parents=True); raw.write_text('{"status":')
        result=self.run_audit()
        failure=result['failed_or_interrupted'][0]
        self.assertTrue(failure['reference_censored'])
        self.assertTrue(failure['incomplete_raw_simulation'])
        self.assertIsNone(failure['elapsed_seconds'])

    def test_unattempted_pool_is_partial_and_baseline_is_available(self):
        result=self.run_audit()
        self.assertEqual(result['charged_candidate_attempts'],0)
        self.assertEqual(result['unattempted'],['candidate_00'])
        self.assertEqual(result['reference_censored_candidates'],['candidate_00'])
        self.assertTrue(all(r['best_verified_speedup']==1 and r['baseline_retained'] for r in result['best_verified_references']))

    def test_ledger_receipt_prefix_and_span_are_authenticated(self):
        row=self.ledger(); row['receipt_prefix_sha256']='changed'
        c.seal(self.root/'attempt-ledger/candidate_00.json',row)
        with self.assertRaisesRegex(ValueError,'receipt prefix'): e._ledger(self.root,'candidate_00',self.protocol,self.commands)
        row['receipt_prefix_sha256']=c.digest(self.commands); row['receipt_end']=2
        c.seal(self.root/'attempt-ledger/candidate_00.json',row)
        with self.assertRaisesRegex(ValueError,'receipt end'): e._ledger(self.root,'candidate_00',self.protocol,self.commands)

    def test_terminal_artifact_inventory_cannot_drop_or_add_files(self):
        self.ledger()
        base=self.root/'measurements/candidate_00'
        (base/'unbound.txt').write_text('unbound')
        with self.assertRaisesRegex(ValueError,'artifact membership'): e._ledger(self.root,'candidate_00',self.protocol,self.commands)

    def test_failure_cannot_smuggle_a_success_record(self):
        row=self.ledger(); base=self.root/'measurements/candidate_00'
        c.seal(base/'measurement.json',{'speedup':2})
        row['artifacts']=artifact_hashes(base); c.seal(self.root/'attempt-ledger/candidate_00.json',row)
        with self.assertRaisesRegex(ValueError,'Unsuccessful ledger'): e._ledger(self.root,'candidate_00',self.protocol,self.commands)

    def test_multiple_native_attempts_are_rejected(self):
        row=self.ledger(); base=self.root/'measurements/candidate_00'
        for number in (0,1): (base/f'attempt-{number:03d}').mkdir()
        row['artifacts']=artifact_hashes(base); c.seal(self.root/'attempt-ledger/candidate_00.json',row)
        with self.assertRaisesRegex(ValueError,'Multiple native attempts'): e._ledger(self.root,'candidate_00',self.protocol,self.commands)

    def test_success_record_hash_and_elapsed_are_required(self):
        row=self.ledger(status='success'); row['record_sha256']='changed'
        c.seal(self.root/'attempt-ledger/candidate_00.json',row)
        with self.assertRaisesRegex(ValueError,'record changed'): e._ledger(self.root,'candidate_00',self.protocol,self.commands)
        row['record_sha256']=c.sha(self.root/'measurements/candidate_00/measurement.json'); row['elapsed_seconds']=None
        c.seal(self.root/'attempt-ledger/candidate_00.json',row)
        with self.assertRaisesRegex(ValueError,'wall time missing'): e._ledger(self.root,'candidate_00',self.protocol,self.commands)

    def test_scope_and_unknown_ledger_names_are_rejected(self):
        self.ledger(name='candidate_99')
        with self.assertRaisesRegex(ValueError,'outside declared pool'): self.run_audit()

    def test_zero_command_ledgers_do_not_hide_extra_receipts(self):
        self.ledger()
        self.commands.append(dict(log='measurements/candidate_00/build.log',elapsed_seconds=2))
        with self.assertRaisesRegex(ValueError,'lack a charged attempt'): self.run_audit()

    def test_path_traversal_is_rejected(self):
        for path in ('../other','/tmp/other'):
            with self.assertRaises(ValueError): e._path(self.root,path)

    def test_active_native_lock_blocks_audit_without_starting_tools(self):
        import fcntl
        with (self.root/'.native.lock').open('w') as stream:
            fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB)
            with self.assertRaisesRegex(ValueError,'evaluator is active'):
                with e._read_lock(self.root): pass

    def test_known_attempt_duration_cannot_undercharge_native_span(self):
        self.commands.append(dict(log='measurements/candidate_00/compile.log',elapsed_seconds=5))
        self.ledger(elapsed=3,end=2)
        with self.assertRaisesRegex(ValueError,'shorter than its native commands'):
            e._ledger(self.root,'candidate_00',self.protocol,self.commands)

    def test_snapshot_cannot_be_created_inside_native_root(self):
        with self.assertRaisesRegex(ValueError,'outside native experiment'):
            e.pack(self.root,self.root/'snapshot')

    def test_portable_archive_replay_keeps_partial_report_and_starts_no_tools(self):
        result=dict(context_id=self.plan['context_id'],protocol_sha256=c.sha(self.root/'evaluation-protocol.json'),
                    source_bindings=self.plan['source_bindings'],charged_candidate_attempts=0,
                    attempt_collection_complete=False,new_native_jobs=0)
        snapshot=Path(self.temp.name)/'snapshot'; restored=Path(self.temp.name)/'restored'
        with patch.object(e,'_audit',return_value=result),patch.object(e.subprocess,'run',side_effect=AssertionError('Native process')):
            e.pack(self.root,snapshot)
            replayed=e.replay(snapshot,restored)
        self.assertEqual(replayed,result)
        self.assertEqual(c.sha(restored/'evaluation-protocol.json'),result['protocol_sha256'])
        (snapshot/'audit.json').write_text('changed')
        with self.assertRaisesRegex(ValueError,'Manifest checksum'):
            e.replay(snapshot,restored)


if __name__=='__main__': unittest.main()
