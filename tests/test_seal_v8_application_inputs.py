"""Portable materialization tests with synthetic files; no circuits/models/labels."""
from contextlib import ExitStack,redirect_stdout
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('seal_v8_under_test',ROOT/'scripts/seal_v8_application_inputs.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
import measure_v8_applications as collector

class MaterializationGuards(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.base=Path(self.temp.name).resolve()
    def put(self,path,value):
        path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,indent=2)+'\n');return path
    def file(self,name,data=b'retained-first-native-evidence'):
        p=self.base/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data);return p
    def index(self,path,files):return self.put(path,{'files':files})
    def test_dropped_file_requires_exact_member_digest_and_size(self):
        p=self.file('outside/input.bin');index=self.index(self.base/'archive-index.json',[{'path':'relocated/input.bin','sha256':m.sha(p),'bytes':p.stat().st_size}])
        result=m.dropped_input_coverage([p],[],[index],{})
        self.assertEqual(result[0]['status'],'exact-bytes-in-published-archive')
        self.assertEqual(result[0]['archive_matches'][0]['member'],'relocated/input.bin')
        for record in ({'path':'x','sha256':'0'*64,'bytes':p.stat().st_size},{'path':'x','sha256':m.sha(p),'bytes':p.stat().st_size+1}):
            self.index(index,[record])
            with self.assertRaisesRegex(ValueError,'Uncovered dropped input'):m.dropped_input_coverage([p],[],[index],{})
    def test_uncovered_external_payload_cannot_silently_disappear(self):
        p=self.file('outside/new-unarchived.bin')
        with self.assertRaisesRegex(ValueError,'Uncovered dropped input'):m.dropped_input_coverage([p],[],[],{})
    def test_exceptions_are_path_and_digest_specific(self):
        p=self.file('outside/tool');exception={str(p):{'sha256':m.sha(p),'scope':'pinned native tool'}}
        rows=m.dropped_input_coverage([p],[],[],exception)
        self.assertEqual(rows[0]['status'],'explicit-nondistributed-dependency-or-failed-partial')
        p.write_bytes(b'changed')
        with self.assertRaises(ValueError):m.dropped_input_coverage([p],[],[],exception)
        with self.assertRaises(ValueError):m.dropped_input_coverage([p],[],[],{str(p)+'other':{'sha256':m.sha(p)}})
    def test_kept_flat_and_duplicate_bindings_are_not_miscounted(self):
        p=self.file('inside/flat')
        self.assertEqual(m.dropped_input_coverage([p,p],[p],[],{}),[])

    def package(self,directory,archive_name='evidence.zip',member='retained.json',data=b'first-proof-fallback-original'):
        directory.mkdir(parents=True,exist_ok=True);archive=directory/archive_name
        with zipfile.ZipFile(archive,'w') as stream:stream.writestr(member,data)
        manifest=self.put(directory/'evidence-manifest.json',{'archive':{'path':archive.name,'sha256':m.sha(archive)},'members':{member:{'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)}}})
        return archive,manifest
    def test_archive_index_normalizes_member_dict_and_authenticates_bytes(self):
        archive,manifest=self.package(self.base/'repo/evidence');out=self.base/'repo/indexes/evidence.json'
        with patch.object(collector,'ROOT',self.base/'repo'):m.archive_index(manifest,archive,out)
        record=m.read(out);self.assertEqual(record['files'][0]['path'],'retained.json')
        self.assertEqual(record['files'][0]['bytes'],len(b'first-proof-fallback-original'))
        changed=m.read(manifest);changed['members']['retained.json']['sha256']='0'*64;self.put(manifest,changed)
        with patch.object(collector,'ROOT',self.base/'repo'):
            with self.assertRaises(ValueError):m.archive_index(manifest,archive,out)
    def test_archive_identity_must_match_original_manifest(self):
        archive,manifest=self.package(self.base/'repo/evidence');archive.write_bytes(archive.read_bytes()+b'tamper')
        with self.assertRaisesRegex(ValueError,'archive hash'):m.archive_index(manifest,archive,self.base/'repo/index.json')

    def fixture(self):
        root=self.base/'repository';app=self.base/'application';training=self.base/'training';consumed=self.base/'consumed'
        for d in (root,app,training,consumed):d.mkdir()
        sources={'fixture.py':'fixed-runtime'}
        fallback={'records':[{'formula':'addi(in0,1)','v7_modes':{'combined':{'status':'fallback-original','normalized_formula':'addi(in0,1)','proof_engine':{'reason':'shared-500ms-exhausted'}}}}]}
        files=[]
        for name,value in [('rows.json',[{'formula':'addi(in0,1)'}]),('programs.json',[{'benchmark':'synthetic'}]),('features.json',fallback),('novelty.json',{'retained':True})]:files.append(self.put(app/name,value))
        prepared={'runtime_source_sha256':sources,'files':[m.record(p,app) for p in files],**{k:m.record(app/n,app) for k,n in [('rows','rows.json'),('programs','programs.json'),('features','features.json'),('novelty','novelty.json')]}}
        self.put(app/'input-preparation.json',prepared)
        verified=self.put(training/'verified-training.json',{'fixture':'checked-training-bytes'})
        self.put(training/'training-data.json',{'fixture':'unverified-legacy-path-must-not-be-copied'})
        self.put(training/'preparation.json',{'runtime_source_sha256':sources,'files':[],'training_data':m.record(verified,training)})
        self.put(consumed/'start.json',{'runtime_source_sha256':sources,'files':[]});self.put(consumed/'features.json',{'records':[]})
        self.put(consumed/'completion.json',{'start':m.record(consumed/'start.json',consumed),'features':m.record(consumed/'features.json',consumed)})
        v7=root/'results/2026-10-14-development-semantics-v7/evidence';self.package(v7,'evidence.tar.gz')
        fixture=root/'benchmarks/application-v8';runtime,rm=self.package(fixture/'runtime')
        feature,fm=self.package(fixture/'features');feature.rename(fixture/'feature-evidence.zip');fmeta=m.read(fm);fmeta['archive']['path']='feature-evidence.zip';self.put(fixture/'feature-evidence-manifest.json',fmeta)
        self.put(fixture/'cohort-preflight.json',{'tools':{},'programs':{'mpeg2':{'partial_trace':{'path':'generated/mpeg.partial','sha256':'0'*64}}}})
        audit=self.put(fixture/'runtime-audit.json',{'status':'passed'})
        review=self.put(self.base/'independent-review.json',{'status':'approved-for-input-seal','input_preparation_sha256':m.sha(app/'input-preparation.json'),'training_preparation_sha256':m.sha(training/'preparation.json'),'consumed_completion_sha256':m.sha(consumed/'completion.json'),'runtime_audit_sha256':m.sha(audit)})
        for name in ['scripts/seal_v8_application_inputs.py','scripts/measure_v6.py','scripts/evaluate_v6.py','docs/v8-application-pilot-protocol.md']:
            p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('synthetic fixture source')
        for folder in ['isaforge','tests']:(root/folder).mkdir()
        return root,app,training,consumed,runtime,rm,audit,review,sources
    def test_materialization_retains_first_fallback_and_checked_training_file(self):
        root,app,training,consumed,runtime,rm,audit,review,sources=self.fixture();out=root/'results/sealed'
        original=(app/'features.json').read_bytes();verified=(training/'verified-training.json').read_bytes()
        with ExitStack() as stack:
            stack.enter_context(patch.object(m,'ROOT',root));stack.enter_context(patch.object(m,'__file__',str(root/'scripts/seal_v8_application_inputs.py')))
            stack.enter_context(patch.object(collector,'ROOT',root));stack.enter_context(patch.object(m.v8,'source_hashes',return_value=sources));stack.enter_context(redirect_stdout(io.StringIO()))
            m.run(out,app,training,consumed,runtime,rm,audit,review)
        self.assertEqual((out/'features.json').read_bytes(),original)
        self.assertEqual((out/'training/training-data.json').read_bytes(),verified)
        with zipfile.ZipFile(out/'prelabel-audit.zip') as stream:self.assertEqual(stream.read('application/features.json'),original)
        seal=m.read(out/'input-seal.json');self.assertTrue(seal['first_native_feature_extraction_retained']);self.assertEqual(seal['new_estimator_fits'],0)
        coverage=m.read(out/'materialization-coverage.json');self.assertEqual(coverage['uncovered_inputs'],0)

    def test_input_mutation_during_copy_cannot_replace_first_native_proof(self):
        root,app,training,consumed,runtime,rm,audit,review,sources=self.fixture();out=root/'results/mutated'
        copyfile=m.shutil.copyfile
        def mutate_then_copy(source,destination,*args,**kwargs):
            if Path(source)==app/'features.json':
                self.put(app/'features.json',{'records':[{'replaced_first_native_proof':True}]})
            return copyfile(source,destination,*args,**kwargs)
        with ExitStack() as stack:
            stack.enter_context(patch.object(m,'ROOT',root));stack.enter_context(patch.object(m,'__file__',str(root/'scripts/seal_v8_application_inputs.py')))
            stack.enter_context(patch.object(collector,'ROOT',root));stack.enter_context(patch.object(m.v8,'source_hashes',return_value=sources));stack.enter_context(redirect_stdout(io.StringIO()))
            stack.enter_context(patch.object(m.shutil,'copyfile',side_effect=mutate_then_copy))
            with self.assertRaises(ValueError):m.run(out,app,training,consumed,runtime,rm,audit,review)
        self.assertFalse((out/'input-seal.json').exists())

if __name__=='__main__':unittest.main()
