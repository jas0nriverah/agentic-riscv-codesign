"""Read-only adapter boundary tests; no hardware tools or target labels fitted."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from isaforge import codesign as c, prospective_inputs as inputs


class ProspectiveInputContracts(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'target'; self.root.mkdir()

    def test_candidate_files_rejected_before_any_reads(self):
        path=self.root/'measurements/candidate_00/measurement.json'
        path.parent.mkdir(parents=True); path.write_text('SEALED TARGET DO NOT READ')
        with patch.object(c,'unseal',side_effect=AssertionError('Opened outcomes')):
            with self.assertRaisesRegex(ValueError,'candidate measurements already exist'):
                inputs.authenticate_baseline(self.root)

    def test_only_baseline_measurement_allowed(self):
        path=self.root/'measurements/baseline/measurement.json'
        path.parent.mkdir(parents=True); path.write_text('baseline contents irrelevant to name check')
        inputs.reject_candidate_measurements(self.root)
        nested=self.root/'measurements/candidate_01/attempt/measurement.json'
        nested.parent.mkdir(parents=True); nested.write_text('sealed')
        with self.assertRaises(ValueError): inputs.reject_candidate_measurements(self.root)

    def context_fixture(self):
        (self.root/'inputs').mkdir()
        for name in ('picorv32.v','soc_top.v','pcpi_single.v'):
            (self.root/'inputs'/name).write_text(name)
        for name in ('plan.json','commands.json','discovery/discovery.json','measurements/baseline/measurement.json'):
            path=self.root/name; path.parent.mkdir(parents=True,exist_ok=True); path.write_text('{}')
        return dict(compiler_flags=['-Os'],configuration=dict(ram_bytes=8192,stack_bytes=3840),
                    inputs={'soc_link.ld':'modified-linker'},source_bindings={},tools={'gcc':{'sha256':'compiler'}},
                    context_id='target-context',memory_partition=dict(stack_bytes=3840,stack_floor=4352))

    def test_context_identity_binds_flags_linker_and_partition(self):
        plan=self.context_fixture(); first=inputs.context(self.root,plan,[])
        self.assertEqual(first['stack_bytes'],3840)
        self.assertEqual(first['ram_bytes'],8192)
        self.assertEqual(first['compiler_flags'],['-Os'])
        for field,value in [('compiler_flags',['-O2']),('memory_partition',{'stack_bytes':4096})]:
            changed={**plan,field:value}
            self.assertNotEqual(inputs.context(self.root,changed,[])['hardware_context_id'],first['hardware_context_id'])
        changed={**plan,'inputs':{'soc_link.ld':'original-linker'}}
        self.assertNotEqual(inputs.context(self.root,changed,[])['hardware_context_id'],first['hardware_context_id'])

    def test_command_and_wall_categories_are_not_added(self):
        plan=self.context_fixture()
        receipts=[dict(log=log,elapsed_seconds=seconds) for log,seconds in
                  [('discovery/profile.json',2),('guard-controls/guard.json',3),
                   ('measurements/baseline/native.log',5),('measurements/candidate_00/native.log',7)]]
        provenance=inputs.context(self.root,plan,receipts)['baseline_provenance']
        self.assertEqual(provenance['setup_command_seconds'],5)
        self.assertEqual(provenance['baseline_command_seconds'],5)
        self.assertEqual(provenance['all_command_seconds'],17)
        self.assertNotIn('total_seconds',provenance)

    def test_evaluate_audits_partition_then_preserves_discovery_ids(self):
        plan=self.context_fixture(); plan['workload']='slre'
        benchmark='embench-slre:target-context'
        c.seal(self.root/'plan.json',plan)
        c.seal(self.root/'discovery/discovery.json',{'pool':[{'candidate_id':'discovery-id','name':'candidate_00'}]})
        c.seal(self.root/'measurements/baseline/measurement.json',{'resources':{'lut4_count':100},'performance':{'cycles':120}})
        c.seal(self.root/'measurements/candidate_00/measurement.json',{'speedup':1.2,'resources':{'lut4_count':120},
            'timing_feasible':True,'elapsed_seconds':3,'performance':{'cycles':100}})
        frozen=Path(self.temp.name)/'frozen'; frozen.mkdir()
        provenance={'prospective_input_source_sha256':c.sha(c.ROOT/inputs.SOURCE),
            'artifacts':{name:c.sha(self.root/name) for name in
                         ('plan.json','discovery/discovery.json','measurements/baseline/measurement.json')}}
        c.seal(frozen/'protocol.json',{'area_cap':228,'contexts':{benchmark:{'baseline_provenance':provenance}}})
        c.seal(frozen/'public.json',[{'candidate_id':'discovery-id','benchmark':benchmark,'formula':'add(in0,in1)'}])
        with patch.object(inputs.partition,'audit') as audited, patch.object(inputs.selection,'evaluate',return_value={'ok':True}) as evaluate:
            self.assertEqual(inputs.evaluate_workload(frozen,self.root),{'ok':True})
            audited.assert_called_once_with(self.root.resolve())
            outcomes=evaluate.call_args.args[1]
            self.assertEqual(outcomes[0]['candidate_id'],'discovery-id')
            self.assertEqual(outcomes[0]['area_cap'],228)
            self.assertEqual(outcomes[0]['candidate_cycles'],100)


if __name__=='__main__': unittest.main()
