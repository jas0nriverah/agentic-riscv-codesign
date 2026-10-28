"""Source-only checks; no estimator fits or retrospective experiment execution."""
import copy
import unittest
from scripts import evaluate_workload_transfer as transfer


def context():
    return dict(hardware_inputs={'soc.v':'a'*64},compiler_flags=['-O2'],
        linker_input_sha256='b'*64,memory_partition={'ram_bytes':8192},clock_mhz=12.,
        baseline_provenance=dict(compiler_sha256='c'*64,
            source_bindings={key:'d'*64 for key in transfer.CODEGEN}))


def row(identifier, formula='add(in0,in1)', benchmark='old'):
    return dict(candidate_id=identifier,formula=formula,benchmark=benchmark,
        area_delta_lut4=30,routed_fmax_min_mhz=20.,device_fits=True,
        latency_features={'estimated_speedup':1.1},saved=10,runs=10)


class WorkloadTransferTests(unittest.TestCase):
    def test_exact_formula_preserves_constants_order_roles(self):
        self.assertEqual(transfer.exact_key(row('a',' add(in0, in1) ')), 'add(in0,in1)')
        keys=[transfer.exact_key(row('a',f)) for f in ('sub(in0,in1)','sub(in1,in0)','addi(in0,1)','addi(in0,2)')]
        self.assertEqual(len(set(keys)),4)

    def test_unknown_context_never_hits(self):
        target=row('t',benchmark='target')
        pred=transfer.cache_predictions([row('a')],[target],{'old':context()})[0]
        self.assertFalse(pred['hit']);self.assertEqual(pred['exact_training_ids'],['a'])
        self.assertIsNone(transfer.compatibility({}))

    def test_compatible_records_aggregate_conservatively(self):
        a=row('a');b=row('b');b.update(area_delta_lut4=70,routed_fmax_min_mhz=10.,device_fits=False)
        contexts={'old':context(),'target':context()}
        pred=transfer.cache_predictions([a,b],[row('t',benchmark='target')],contexts)[0]
        self.assertEqual(pred['historical_max_area'],70)
        self.assertEqual(pred['historical_min_fmax'],10.)
        self.assertFalse(pred['historical_all_device_fit']);self.assertTrue(pred['historically_infeasible'])
        contexts['target']['compiler_flags']=['-O3']
        self.assertFalse(transfer.cache_predictions([a,b],[row('t',benchmark='target')],contexts)[0]['hit'])

    def test_missing_codegen_nohit_and_source_binding_matters(self):
        original=context(); changed=copy.deepcopy(original)
        del changed['baseline_provenance']['source_bindings'][transfer.CODEGEN[0]]
        self.assertIsNone(transfer.compatibility(changed))
        changed=copy.deepcopy(original);changed['hardware_inputs']['soc.v']='e'*64
        self.assertNotEqual(transfer.compatibility(changed),transfer.compatibility(original))

    def test_known_infeasible_last_unknown_latency_fallback(self):
        a=row('a');b=row('b');b['latency_features']['estimated_speedup']=1.2
        cache=[dict(candidate_id='a',historically_infeasible=False),dict(candidate_id='b',historically_infeasible=True)]
        orders=transfer.policy_orders([a,b],{'a':0.,'b':1.},{'a':0.,'b':1.},cache)
        self.assertEqual(orders['exact_cache_latency'],['a','b'])
        self.assertEqual(orders['calibrated_latency'],['b','a'])
        self.assertEqual(len([k for k in orders if k.startswith('random:')]),5)

    def test_failure_remains_charged_unknown(self):
        from scripts import evaluate_feasibility_model_families as screen
        failed=dict(candidate_id='f',measurement_seconds=9.)
        result=screen._evaluate_group('cache',[failed],{}, {'f':failed},1.1,True,seed=0,budget=1)
        self.assertEqual(result['measurement_seconds'],9.)
        self.assertEqual(result['failed_or_unresolved_attempts'],1)
        self.assertIsNone(result['cycle_reduction_regret'])

    def test_split_excludes_whole_workload_and_family(self):
        rows=[dict(row('t'),workload_group='target'),dict(row('same'),workload_group='other'),
              dict(row('different','xor(in0,in1)'),workload_group='other')]
        ordinary,*_=transfer.split(rows,[],'target','workload_only')
        strict,*_=transfer.split(rows,[],'target','workload_and_family')
        self.assertEqual([r['candidate_id'] for r in ordinary],['same','different'])
        self.assertEqual([r['candidate_id'] for r in strict],['different'])

if __name__=='__main__':unittest.main()
