"""Synthetic guards and independent numeric checks; no native tools or labels."""
import copy
import importlib.util
import json
import math
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('v11collector',ROOT/'scripts/collect_v11_reserved.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class ReservedInputTests(unittest.TestCase):
    def test_fixed_six_and_five_families(self):
        self.assertEqual(list(m.SPECS),['ammunition','audiobeam','pm','fmref','fac','recursion'])
        self.assertEqual(len({x[1] for x in m.SPECS.values()}),5)
        self.assertEqual(m.SPECS['fac'][1],m.SPECS['recursion'][1])

    def test_integer_oracles_reject_wrong_output_or_input(self):
        self.assertTrue(m.validate_output('fac',[154,5],None)['full_algorithm_independent_oracle'])
        self.assertTrue(m.validate_output('recursion',[89,10],None)['full_algorithm_independent_oracle'])
        for name,values in [('fac',[0,5]),('fac',[154,4]),('recursion',[88,10]),('recursion',[89,9])]:
            with self.assertRaises(ValueError):m.validate_output(name,values,None)

    def test_ammunition_probes_check_all_bytes(self):
        mask=((1<<35)-1)<<(64-13-35)
        values=[0,0,255,255,255,254,0,*mask.to_bytes(8,'big')]
        m.validate_output('ammunition',values,None)
        for i in range(len(values)):
            if i==1:continue # Original overflow state is observed, not inferred.
            bad=values.copy();bad[i]^=1
            with self.assertRaises(ValueError):m.validate_output('ammunition',bad,None)

    def test_pm_checks_global_invariants_and_sampled_order(self):
        word=lambda x:struct.unpack('<i',struct.pack('<f',x))[0]
        good=[12,64,60,12,0,123]+[word(x) for x in [3,2,2,4,3,1,4,5]]
        m.validate_output('pm',good,None)
        for i in range(5):
            bad=good.copy();bad[i]+=1
            with self.assertRaises(ValueError):m.validate_output('pm',bad,None)
        bad=good.copy();bad[11]=word(10)
        with self.assertRaises(ValueError):m.validate_output('pm',bad,None)
        bad=good.copy();bad[6]=word(float('inf'))
        with self.assertRaises(ValueError):m.validate_output('pm',bad,None)

    def test_float32_rounding_and_upstream_byte_compaction(self):
        self.assertEqual(m.f32(16777217),16777216)
        b=m.FloatBuffer()
        for x in [1,2,3,4]:b.append(x)
        original=bytes(b.data);b.pos=1;b.compact()
        self.assertEqual((b.pos,b.length),(0,3))
        self.assertEqual(b.data[:3],original[4:7])
        self.assertEqual(b.data[3:],original[3:])
        # Correct float memmove would copy 12 bytes; upstream copies only3.
        self.assertNotEqual(b.get(0),2)

    def test_initializer_rejects_wrong_shape_and_ignores_comment_numbers(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'input.c';p.write_text('float a[2]={1.0f, /* 999 */ -2e-3f};')
            self.assertEqual(m.array_values(p,'a',2),[1,m.f32(-.002)])
            with self.assertRaises(ValueError):m.array_values(p,'a',3)
            with self.assertRaises(ValueError):m.array_values(p,'other',2)

    def test_fm_numeric_oracle_is_required_not_zero_exit(self):
        expected={'positions':[0,200,66,67,2,66,0,2,-1], 'samples':[.1]*8+[100,200,300,400,500,600]}
        word=lambda x:struct.unpack('<i',struct.pack('<f',x))[0]
        good=expected['positions']+[1,2,3,4]+[word(x) for x in expected['samples']]
        with patch.object(m,'fm_oracle',return_value=expected):
            m.validate_output('fmref',good,None)
            for bad in [good[:21]+[0,0]+good[23:], [0]*27, good[:13]+[word(5)]+good[14:]]:
                with self.assertRaises(ValueError):m.validate_output('fmref',bad,None)

    def test_audio_numeric_and_complete_output_count(self):
        expected={'outputs':[.001]*371,'checksum':1}
        word=lambda x:struct.unpack('<i',struct.pack('<f',x))[0]
        good=[1,5760,3200,123]+[word(.001)]*16+[371]
        with patch.object(m,'audio_oracle',return_value=expected):
            m.validate_output('audiobeam',good,None)
            bad=good.copy();bad[20]=370
            with self.assertRaises(ValueError):m.validate_output('audiobeam',bad,None)
            bad=good.copy();bad[8]=word(.002)
            with self.assertRaises(ValueError):m.validate_output('audiobeam',bad,None)

    def test_snapshot_signed32_types(self):
        for values in [[True,5],[154.0,5],[154,1<<32]]:
            with self.assertRaises(ValueError):m.validate_output('fac',values,None)

    def test_stdout_status_duplicate_missing_rejected(self):
        good=json.dumps({'kind':'external-output','values':[154,5],'upstream_status':0})
        self.assertEqual(m.output(good),[154,5])
        for text in ['',good+'\n'+good,good.replace('"upstream_status": 0','"upstream_status": 1')]:
            with self.assertRaises(ValueError):m.output(text)

    def test_authentication_rejects_reassignment_before_native(self):
        plan={'programs':{n:{'family':f,'directory':'bench/'+g+'/'+n,'compiled_c_files':list(fs),'files':{}}
                          for n,(g,f,fs) in m.SPECS.items()}}
        plan['programs']['ammunition']['family']='new'
        with self.assertRaisesRegex(ValueError,'family'):m.authenticate(plan,Path('/nonexistent'))

    def test_all_six_failures_are_retained_no_substitutions(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'attempt'
            plan={'programs':{n:{'family':s[1],'files':{}} for n,s in m.SPECS.items()},'tools':{'cc':{'path':'synthetic-compiler'}},'runtime_source_sha256':{}}
            with patch.object(m,'authenticate'),patch.object(m,'build',side_effect=RuntimeError('synthetic build failure')) as build:
                report=m.collect(Path(d),out,plan)
                self.assertEqual(build.call_count,6)
                self.assertEqual(set(report['records']),set(m.SPECS))
                self.assertTrue(all(x['status']=='failure-retained' for x in report['records'].values()))
                self.assertEqual(report['all_roi_program_formula_rows'],0)
                self.assertEqual(report['nonempty_families'],[])
                with self.assertRaises(FileExistsError):m.collect(Path(d),out,plan)
                self.assertEqual(build.call_count,6)

    def test_complete_empty_pools_keep_all_helpers_and_no_limit(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'attempt';reference=Path(d)
            plan={'programs':{n:{'family':r[1],'files':{},'directory':n} for n,r in m.SPECS.items()},
                  'tools':{n:{'path':n} for n in ['cc','objdump','spike']},'runtime_source_sha256':{}}
            def build(name,record,reference,folder,opt,cc):
                folder.mkdir(parents=True);elf=folder/(name+'.elf');elf.write_bytes(b'ELF');return elf,{}
            text=json.dumps({'kind':'external-output','upstream_status':0,'values':[0]})
            def trace(spike,elf,path,log,timeout):
                stdout=log.with_suffix('.stdout.log');stdout.write_text(text)
                return {'validated':True,'trace_instructions':7,'program_output':str(stdout)}, {100:4,104:3},set()
            with patch.object(m,'authenticate'),patch.object(m,'build',side_effect=build), \
                 patch.object(m,'command',return_value=({},text)),patch.object(m,'validate_output',return_value={}), \
                 patch.object(m,'collect_trace_external',side_effect=trace), \
                 patch.object(m,'readProgram',return_value={100:{'symbol':'main'},104:{'symbol':'__softfloat_helper'}}), \
                 patch.object(m,'extractCandidates',return_value=[]) as extract, \
                 patch.object(m,'verify_candidates',return_value={'passed':True,'benchmarks':[]}):
                report=m.collect(reference,out,plan)
            self.assertEqual(report['successful_programs'],6)
            self.assertTrue(all(r['status']=='empty' for r in report['records'].values()))
            self.assertEqual(extract.call_count,6)
            for call in extract.call_args_list:
                self.assertEqual(call.kwargs,{'maxSize':4,'limit':None})
                self.assertEqual(call.args[1],{100:4,104:3})
                self.assertEqual(call.args[2],{100,104})

    def test_build_contains_no_synthesis_or_model_command(self):
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d)/'O2';source=Path(d)/'upstream';source.mkdir()
            spec={'directory':'upstream','compiled_c_files':['fac.c']};commands=[]
            def command(args,log,timeout):
                commands.append(args);log.write_text('synthetic')
                if '-o' in args:Path(args[args.index('-o')+1]).write_bytes(b'ELF')
                return {'command':args},''
            with patch.object(m,'command',side_effect=command):m.build('fac',spec,Path(d),folder,'-O2','compiler')
            self.assertTrue(all(c[0]=='compiler' for c in commands))
            self.assertTrue(any('-march=rv32im' in c and '-mabi=ilp32' in c for c in commands))
            self.assertIn('-DUPSTREAM_RUN=fac_main',commands[-1])
            self.assertTrue(all(c[-1]!='-flto' for c in commands))

if __name__=='__main__':unittest.main()
