"""Synthetic release/evidence tests; no compiler, synthesis or model fits."""
import copy
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT)]
import measure_v13_coverage as m

class ContractTests(unittest.TestCase):
    def test_policy(self):
        self.assertEqual((m.COUNT,m.SEED,m.POLICY['workers'],m.POLICY['retries']),(48,2026101529,2,0))
        self.assertEqual(len(m.vectors()),2148)
        self.assertEqual(m.vectors(),m.vectors())
        self.assertEqual(len(set(m.vectors()[:100])),100)
    def test_counts(self):
        for value in (True,1.0,-1,'1',None):
            with self.subTest(value=value),self.assertRaises(ValueError):m.integer(value)
        self.assertEqual(m.integer(0),0)
    def test_utc(self):
        with self.assertRaises(ValueError):m.utc('2026-10-15T00:00:00')
        self.assertIsNotNone(m.utc('2026-10-15T00:00:00+00:00'))
    def test_duplicate_json(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'x';p.write_text('{"x":1,"x":2}')
            with self.assertRaises(ValueError):m.read(p)
    def test_immutable_write(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'x';m.write(p,[])
            with self.assertRaises(FileExistsError):m.write(p,{})
    def test_cleanup_failure_preserved(self):
        class Owner:
            def cancel(self):raise PermissionError('injected')
        failures=[{'stage':'original','error':'primary'}];m.safe_cancel(Owner(),failures)
        self.assertEqual([f['stage'] for f in failures],['original','cleanup'])
    def test_source_closure(self):
        paths={p.relative_to(ROOT).as_posix() for p in m.required_sources()}
        self.assertTrue({'scripts/measure_v6.py','scripts/measure_v10_csd_hardware.py','isaforge/v4_validation.py','isaforge/rtl.py','tests/test_measure_v13_coverage.py'}<=paths)
    def test_hash_guard(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'x';p.write_text('x');bindings={p:m.sha(p)};m.check_hashes(bindings);p.write_text('y')
            with self.assertRaises(ValueError):m.check_hashes(bindings)
    def test_prepare_wrong_count(self):
        import prepare_v13_coverage as prep
        with tempfile.TemporaryDirectory() as d,patch.object(prep,'validate_preparation',return_value=({'schema':prep.SCHEMA},{},[])):
            with self.assertRaisesRegex(ValueError,'Exactly48'):m.prepared_inputs(d)
    def test_no_retry(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'measurements').mkdir()
            with patch.object(m,'validate_approval',return_value=([],{}, {},{},{})),self.assertRaisesRegex(ValueError,'Single fresh'):
                m.collect(root,root/'measurement-approval.json')
    def test_free_space_guard(self):
        with tempfile.TemporaryDirectory() as d,patch.object(m.shutil,'disk_usage') as du:
            du.return_value.free=0
            with self.assertRaisesRegex(ValueError,'4GiB'):m.guard(Path(d),Path(d))

class VerificationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.folder=Path(self.tmp.name)
        self.formulas=['add(in0,in1)']*48
        (self.folder/'verification.v').write_text(m.verification_source(self.formulas))
        lines=[' '.join(f'{v:08x}' for v in [a,b,*[m.evaluate_formula(f,a,b) for f in self.formulas]]) for a,b in m.vectors()]
        (self.folder/'vectors.txt').write_text('\n'.join(lines)+'\n')
        self.proof={'verified':True,'formula_count':48,'vectors_per_formula':2148,'total_comparisons':103104,'random_seed':m.SEED,
                    'v4_validation_override_sha256':m.sha(ROOT/'isaforge/v4_validation.py'),
                    'rtl_sha256':m.sha(self.folder/'verification.v'),'vectors_sha256':m.sha(self.folder/'vectors.txt'),
                    'signed_overflow_workaround_applied':False}
    def test_exact_vector_replay(self):m.validate_verification(self.proof,self.folder,self.formulas)
    def test_wrong_expected_vector_reauthenticated(self):
        p=self.folder/'vectors.txt';s=p.read_text();p.write_text(s.replace('00000000','00000001',1));self.proof['vectors_sha256']=m.sha(p)
        with self.assertRaisesRegex(ValueError,'Expected vectors'):m.validate_verification(self.proof,self.folder,self.formulas)
    def test_wrong_rtl_reauthenticated(self):
        p=self.folder/'verification.v';p.write_text(p.read_text()+'//wrong\n');self.proof['rtl_sha256']=m.sha(p)
        with self.assertRaisesRegex(ValueError,'batch RTL'):m.validate_verification(self.proof,self.folder,self.formulas)
    def test_partial_and_bool_counts(self):
        for key,value in [('total_comparisons',103103),('formula_count',True),('random_seed',m.SEED+1),('verified',False)]:
            with self.subTest(key=key),self.assertRaises(ValueError):m.validate_verification({**self.proof,key:value},self.folder,self.formulas)

class MetricTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.folder=Path(self.tmp.name).resolve();self.formula='add(in0,in1)'
        (self.folder/'candidate.v').write_text(m.generate_rtl(self.formula))
        (self.folder/'ice40.ys').write_text(f'read_verilog "{self.folder/"candidate.v"}"\nsynth_ice40 -top candidate\ncheck -assert\nwrite_json "{self.folder/"ice40-netlist.json"}"\nstat\n')
        (self.folder/'ice40.log').write_text('synthetic')
        m.write(self.folder/'ice40-netlist.json',{'modules':{'candidate':{'cells':{'x':{'type':'SB_LUT4'},'y':{'type':'SB_CARRY'}}}}})
        self.tools={'executables':{'yosys':{'version':'synthetic','sha256':'tool','path':'/synthetic/yosys'}}}
        self.metric={'formula':self.formula,'tool':'synthetic','measurement_source':'rtl_synthesis','rtl_sha256':m.sha(self.folder/'candidate.v'),
                     'script_sha256':m.sha(self.folder/'ice40.ys'),'log_sha256':m.sha(self.folder/'ice40.log'),'netlist_sha256':m.sha(self.folder/'ice40-netlist.json'),
                     'command':['/synthetic/yosys','-s',str(self.folder/'ice40.ys')],'ice40_cell_types':{'SB_LUT4':1,'SB_CARRY':1},'ice40_lut4_count':1,'ice40_carry_count':1}
    def validate(self,metric):
        with patch.object(m,'abc_invocations',return_value=[]),patch.object(m,'data_invocations',return_value={}):
            return m.validate_metric(metric,self.folder,self.formula,self.tools)
    def test_recount(self):self.assertEqual(self.validate(self.metric)['ice40_lut4_count'],1)
    def test_wrong_recount(self):
        with self.assertRaises(ValueError):self.validate({**self.metric,'ice40_lut4_count':2})
    def test_bool_recount(self):
        with self.assertRaises(ValueError):self.validate({**self.metric,'ice40_carry_count':True})
    def test_reauthenticated_recipe_change(self):
        p=self.folder/'ice40.ys';p.write_text(p.read_text().replace('synth_ice40','synth_ice40 -abc9'))
        with self.assertRaisesRegex(ValueError,'recipe'):self.validate({**self.metric,'script_sha256':m.sha(p)})
    def test_original_identity(self):
        p=self.folder/'candidate.v';p.write_text('wrong')
        with self.assertRaisesRegex(ValueError,'original RTL'):self.validate({**self.metric,'rtl_sha256':m.sha(p)})

class ArchiveTests(unittest.TestCase):
    def fixture(self,root,complete=False):
        scratch=root/'scratch';stage=root/'measurements'/m.ATTEMPT;scratch.mkdir();stage.mkdir(parents=True)
        (scratch/'candidate.v').write_text('raw');(scratch/'obj_dir').mkdir();(scratch/'obj_dir/x.o').write_bytes(b'objects')
        done={'complete':complete}
        for n,k in [('verification.json','verification_sha256'),('labels.json','labels_sha256'),('unique-measurements.json','unique_measurements_sha256')]:m.write(stage/n,[]);done[k]=m.sha(stage/n)
        m.write(stage/'completion.json',done);m.archive(scratch,stage,done);return scratch,stage
    def test_failed_archive_replay_and_no_objects(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.fixture(root);result=m.verify_archive(root)
            self.assertFalse(result['complete']);self.assertNotIn('obj_dir/x.o',[r['path'] for r in result['files']])
    def test_tampered_stage(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);_,stage=self.fixture(root);(stage/'labels.json').write_text('[1]')
            with self.assertRaises(ValueError):m.verify_archive(root)
    def test_tampered_zip(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);_,stage=self.fixture(root);p=stage/'raw-evidence.zip';p.write_bytes(p.read_bytes()+b'wrong')
            with self.assertRaises(ValueError):m.verify_archive(root)


class CollectorFlowTests(unittest.TestCase):
    def run_synthetic(self,fail_verify=False,fail_formula=None,fail_archive=False):
        import threading
        context=tempfile.TemporaryDirectory();self.addCleanup(context.cleanup);repo=Path(context.name);root=repo/'result';root.mkdir()
        formulas=[f'addi(in0,{i})' for i in range(48)];candidates=[{'candidate_id':str(i),'formula':f} for i,f in enumerate(formulas)]
        for n in ('preparation','recipe','candidates','measurement-plan','measurement-tools','measurement-approval'):m.write(root/(n+'.json'),{})
        tools={'executables':{'yosys':{'path':'/synthetic/yosys','version':'synthetic'}}};calls=[];lock=threading.Lock()
        class Owner:
            def __init__(self,*a):pass
            def cancel(self):pass
        def worker(payload,log,owner,timeout):
            with lock:calls.append(payload['kind'])
            folder=Path(payload['folder']);folder.mkdir(parents=True,exist_ok=True);Path(log).parent.mkdir(parents=True,exist_ok=True);Path(log).write_text('synthetic')
            if payload['kind']=='verify':
                if fail_verify:raise RuntimeError('synthetic verification failed')
                return {'verified':True}
            if payload['formula']==fail_formula:raise RuntimeError('synthetic map failed')
            return {'formula':payload['formula'],'ice40_lut4_count':7,'ice40_carry_count':2,'rtl_sha256':'synthetic'}
        patches=[patch.object(m,'ROOT',repo),patch.object(m,'validate_approval',return_value=(candidates,{},tools,{'freeze_commit':'a'*40},{})),
                 patch.object(m,'guard'),patch.object(m,'validate_tools'),patch.object(m,'HardwareWorkers',Owner),patch.object(m,'required_sources',return_value=[]),
                 patch.object(m,'run_owned',side_effect=worker),patch.object(m,'validate_verification'),patch.object(m,'validate_metric',side_effect=lambda x,*a:x)]
        if fail_archive:patches.append(patch.object(m,'archive',side_effect=OSError('synthetic archive failure')))
        from contextlib import ExitStack
        with ExitStack() as stack:
            for p in patches:stack.enter_context(p)
            try:result=m.collect(root,root/'measurement-approval.json')
            except RuntimeError:result=m.read(root/'measurements/completion.json')
            if not fail_archive:m.verify_archive(root)
        return root,result,calls
    def test_failed_verification_blocks_every_map_and_retains(self):
        root,result,calls=self.run_synthetic(fail_verify=True)
        self.assertEqual(calls,['verify']);self.assertFalse(result['complete']);self.assertEqual(result['new_physical_measurements'],0)
        self.assertTrue((root/'measurements/attempt-0000/raw-evidence.zip').is_file())
    def test_exact48_success_no_fits(self):
        root,result,calls=self.run_synthetic();self.assertTrue(result['complete']);self.assertEqual(Counter(calls),{'verify':1,'map':48})
        self.assertEqual(result['verified_comparisons'],103104);self.assertEqual(result['new_estimator_fits'],0)
    def test_one_failed_mapping_no_replacement_or_retry(self):
        root,result,calls=self.run_synthetic(fail_formula='addi(in0,7)');self.assertFalse(result['complete'])
        self.assertEqual(Counter(calls),{'verify':1,'map':48});self.assertEqual(result['new_physical_measurements'],47)

    def test_archive_failure_cannot_release_complete(self):
        root,result,calls=self.run_synthetic(fail_archive=True)
        self.assertFalse(result['complete']);self.assertEqual(result['failures'][-1]['stage'],'archive')
        self.assertEqual(Counter(calls),{'verify':1,'map':48})

class ApprovalTests(unittest.TestCase):
    def fixture(self,repo):
        root=repo/'result';root.mkdir();(repo/'tests').mkdir()
        (repo/'tests/test_measure_v13_coverage.py').write_text('synthetic tests')
        for n in ('preparation','recipe','candidates','measurement-plan','measurement-tools'):m.write(root/(n+'.json'),{})
        source=repo/'source.py';source.write_text('sealed source')
        manifest={'created_at_utc':'2026-10-15T10:00:00+00:00'};plan={'created_at_utc':'2026-10-15T10:01:00+00:00'}
        review={'status':'approved-v13-coverage-measurements','collector_sha256':m.sha(m.__file__),
                'collector_tests_sha256':m.sha(repo/'tests/test_measure_v13_coverage.py'),'freeze_commit':'a'*40,
                'reviewed_at_utc':'2026-10-15T10:02:00+00:00'}
        for key,n in [('preparation_sha256','preparation'),('recipe_sha256','recipe'),('candidates_sha256','candidates'),
                      ('measurement_plan_sha256','measurement-plan'),('tools_sha256','measurement-tools')]:review[key]=m.sha(root/(n+'.json'))
        m.write(root/'measurement-approval.json',review)
        return root,review,(manifest,{},[],plan,{}, {source:m.sha(source)}),source
    def test_git_and_review_bindings(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as d:
            repo=Path(d);root,review,state,source=self.fixture(repo)
            with patch.object(m,'ROOT',repo),patch.object(m,'validate_plan',return_value=state),patch.object(m.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout=source.read_bytes())):
                self.assertEqual(m.validate_approval(root,root/'measurement-approval.json')[3]['freeze_commit'],'a'*40)
            with patch.object(m,'ROOT',repo),patch.object(m,'validate_plan',return_value=state),patch.object(m.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout=b'changed')):
                with self.assertRaisesRegex(ValueError,'Git'):m.validate_approval(root,root/'measurement-approval.json')
    def test_review_before_plan_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            repo=Path(d);root,review,state,source=self.fixture(repo);review['reviewed_at_utc']='2026-10-15T10:00:30+00:00'
            (root/'measurement-approval.json').write_text(json.dumps(review))
            with patch.object(m,'ROOT',repo),patch.object(m,'validate_plan',return_value=state),self.assertRaisesRegex(ValueError,'precedes'):
                m.validate_approval(root,root/'measurement-approval.json')
    def test_no_native_without_release(self):
        with tempfile.TemporaryDirectory() as d,patch.object(m,'validate_approval',side_effect=ValueError('no parent approval')),patch.object(m,'HardwareWorkers',side_effect=AssertionError('native')):
            with self.assertRaisesRegex(ValueError,'parent approval'):m.collect(d,Path(d)/'measurement-approval.json')
            self.assertFalse((Path(d)/'label-release.json').exists())

if __name__=='__main__':unittest.main()
