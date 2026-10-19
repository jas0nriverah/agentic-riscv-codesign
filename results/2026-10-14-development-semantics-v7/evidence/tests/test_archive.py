import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import tarfile,io,json,hashlib

MODULE=Path(__file__).resolve().parents[1]/'package_v7_evidence.py'
spec=importlib.util.spec_from_file_location('package_v7_evidence',MODULE);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class PackageContracts(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.repo=self.root/'checkout';self.repo.mkdir();(self.repo/'input').write_text('bound')
        self.pack=self.root/'package';self.pack.mkdir()
    def evidence(self,kind='regular',duplicate=False):
        data={'prepared/pre-score-freeze.json':b'{"original":"seal"}\n','reviews/parent-fit-review.json':b'{"approved":true}\n'}
        archive=self.pack/'evidence.tar.gz'
        with tarfile.open(archive,'w:gz') as tar:
            for name,value in data.items():
                entry=tarfile.TarInfo(name);entry.size=len(value)
                if kind=='symlink':entry.type=tarfile.SYMTYPE;entry.linkname='/tmp/outside'
                tar.addfile(entry,io.BytesIO(value) if kind=='regular' else None)
                if duplicate:tar.addfile(entry,io.BytesIO(value))
        records=[{'path':k,'bytes':len(v),'sha256':hashlib.sha256(v).hexdigest()} for k,v in data.items()]
        manifest={'schema':m.SCHEMA,'archive':{'path':archive.name,'bytes':archive.stat().st_size,'sha256':m.sha(archive)},
            'files':records,'file_count':len(records),'uncompressed_bytes':sum(len(v) for v in data.values()),
            'repository_dependencies':[{'original_path':'/old/repo/input','repository_path':'input','sha256':m.sha(self.repo/'input')}],
            'pre_score_freeze_sha256':records[0]['sha256'],'parent_review_sha256':records[1]['sha256']}
        path=self.pack/'evidence-manifest.json';m.write(path,manifest);return path,manifest
    def test_verify_and_restore_preserve_exact_bytes(self):
        path,manifest=self.evidence();m.verify(path,self.repo)
        restored=m.restore(path,self.repo,self.root/'restored')
        self.assertEqual((restored/'prepared/pre-score-freeze.json').read_bytes(),b'{"original":"seal"}\n')
        self.assertEqual(m.check_restored(restored,self.repo)['pre_score_freeze_sha256'],manifest['pre_score_freeze_sha256'])
    def test_safe_names_reject_traversal_and_absolute(self):
        for name in ('../x','/tmp/x','x/../y','x\\y','./x','x//y',''):
            with self.subTest(name=name),self.assertRaises(ValueError):m.safe_name(name)
    def test_symlink_archive_is_rejected(self):
        path,_=self.evidence('symlink')
        with self.assertRaises(ValueError):m.verify(path,self.repo)
    def test_duplicate_archive_member_is_rejected(self):
        path,_=self.evidence(duplicate=True)
        with self.assertRaises(ValueError):m.verify(path,self.repo)
    def test_clean_checkout_mutation_is_rejected(self):
        path,_=self.evidence();(self.repo/'input').write_text('changed')
        with self.assertRaises(ValueError):m.verify(path,self.repo)
    def test_restored_evidence_mutation_is_rejected(self):
        path,_=self.evidence();restored=m.restore(path,self.repo,self.root/'restored')
        (restored/'reviews/parent-fit-review.json').write_text('{}')
        with self.assertRaises(ValueError):m.check_restored(restored,self.repo)
    def test_existing_destination_and_checkout_destination_rejected(self):
        path,_=self.evidence()
        for destination in (self.repo,self.repo/'restored',self.pack):
            with self.subTest(destination=destination),self.assertRaises(ValueError):m.restore(path,self.repo,destination)
    def test_escaping_dependency_alias_is_rejected(self):
        path,manifest=self.evidence();manifest['repository_dependencies'][0]['repository_path']='../input';m.write(path,manifest)
        with self.assertRaises(ValueError):m.verify(path,self.repo)
    def test_score_preserves_explicit_virtualenv_interpreter_symlink(self):
        path,_=self.evidence();restored=m.restore(path,self.repo,self.root/'restored')
        link=self.root/'virtualenv/bin/python';link.parent.mkdir(parents=True);link.symlink_to(Path(m.sys.executable))
        with mock.patch.object(m.subprocess,'run') as run:
            m.score(restored,self.repo,self.root/'scores',python=link)
        self.assertEqual(run.call_args.args[0][0],str(link.absolute()))
        self.assertNotEqual(run.call_args.args[0][0],str(link.resolve()))
    def test_score_defaults_to_current_interpreter_without_checkout_venv(self):
        path,_=self.evidence();restored=m.restore(path,self.repo,self.root/'restored')
        self.assertFalse((self.repo/'.venv').exists())
        with mock.patch.object(m.subprocess,'run') as run:
            m.score(restored,self.repo,self.root/'scores')
        self.assertEqual(run.call_args.args[0][0],str(Path(m.sys.executable).absolute()))
    def test_repository_aliases_preserve_original_plan_and_require_hash(self):
        plan={'input_sha256':{str(self.repo/'input'):m.sha(self.repo/'input')}};before=json.dumps(plan)
        result=m.portable_dependencies(plan,self.repo);self.assertEqual(result[0]['repository_path'],'input');self.assertEqual(json.dumps(plan),before)
        plan['input_sha256'][str(self.repo/'input')]='wrong'
        with self.assertRaises(ValueError):m.portable_dependencies(plan,self.repo)

if __name__=='__main__':unittest.main()
