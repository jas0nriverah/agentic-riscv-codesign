"""Input admission guards; no program execution, target labels or models."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('v8collector',ROOT/'scripts/collect_v8_applications.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class AdmissionGuards(unittest.TestCase):
    def test_reassigned_family_fails_before_evidence_reads(self):
        manifest=m.read(m.DEFAULT);wrong=copy.deepcopy(manifest)
        wrong['programs']['bitcount']['family'],wrong['programs']['fft']['family']='fft','bitcount'
        with patch.object(m,'checked_path',side_effect=AssertionError('must reject assignment first')):
            with self.assertRaisesRegex(ValueError,'family/role'):m.validate(wrong)

    def test_record_hash_and_path_escape_are_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d).resolve();p=root/'record';p.write_text('retained')
            with patch.object(m,'ROOT',root):
                record={'path':'record','sha256':m.sha(p)};self.assertEqual(m.checked_path(record),p)
                p.write_text('mutated')
                with self.assertRaises(ValueError):m.checked_path(record)
                with self.assertRaises(ValueError):m.checked_path({'path':'../escape','sha256':'0'*64})

    def test_extra_unmanifested_c_source_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d).resolve();source=root/'bench/example';source.mkdir(parents=True);p=source/'main.c';p.write_text('int x;')
            record={'upstream_directory':'bench/example','upstream_source_sha256':{'bench/example/main.c':m.sha(p)}}
            self.assertEqual(m.sources(root,record),source)
            (source/'extra.c').write_text('int extra;')
            with self.assertRaisesRegex(ValueError,'extra'):m.sources(root,record)

    def test_status_and_duplicate_stdout_fail_closed(self):
        valid=json.dumps({'kind':'external-output','upstream_status':0,'values':[1,2]})
        self.assertEqual(m.output(valid),[1,2])
        for text in (valid+'\n'+valid,valid.replace('"upstream_status": 0','"upstream_status": 1')):
            with self.assertRaises(ValueError):m.output(text)

    def test_existing_attempt_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as d:
            with patch.object(m,'build',side_effect=AssertionError('must not execute')):
                with self.assertRaises(FileExistsError):m.reproduce({},Path(d),Path(d),{})

if __name__=='__main__':unittest.main()
