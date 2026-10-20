"""Archive/preregistration contracts; fixtures launch no processor/toolchain jobs."""
import copy
from contextlib import ExitStack
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from isaforge import codesign as c
from scripts import reproduce_budget_campaign as r
from scripts.reproduce_codesign import pack_archive, restore_archive


class BudgetArchiveContracts(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.selection=self.root/'generated/selection'
        self.prereg=self.root/'results/prereg'

    def preregistration(self):
        self.selection.mkdir(parents=True)
        c.seal(self.selection/'target/protocol.json',{'target_labels_read':0})
        c.seal(self.selection/'target-baseline.json',{'receipts':[]})
        artifacts={p.name:c.sha(p) for p in (self.selection/'target').iterdir()}
        c.seal(self.selection/'cohort.json',{'targets':{'target':dict(
            baseline_snapshot='target-baseline.json',selection_artifacts=artifacts)}})
        shutil.copytree(self.selection,self.prereg/'selection')
        c.seal(self.prereg/'manifest.json',{p.relative_to(self.prereg).as_posix():c.sha(p)
            for p in sorted(self.prereg.rglob('*')) if p.is_file()})

    def git(self,*args):
        result=subprocess.run(['git',*args],cwd=self.root,capture_output=True,check=False)
        self.assertEqual(result.returncode,0,result.stderr.decode())
        return result.stdout.decode().strip()

    def commit(self):
        self.git('init','-q')
        self.git('add','results/prereg')
        self.git('-c','user.name=Fixture','-c','user.email=fixture@example.invalid',
                 '-c','commit.gpgsign=false','-c','core.hooksPath=/dev/null',
                 'commit','-q','-m','prelabel fixture')
        return self.git('rev-parse','HEAD')

    def test_prelabel_manifest_must_cover_all_frozen_artifacts(self):
        self.preregistration()
        self.assertEqual(r.check_prelabel(self.selection,self.prereg),c.sha(self.prereg/'manifest.json'))
        entries=c.unseal(self.prereg/'manifest.json')
        for remove in (set(entries),{'selection/target/protocol.json'}):
            c.seal(self.prereg/'manifest.json',{k:v for k,v in entries.items() if k not in remove})
            with self.assertRaisesRegex(ValueError,'complete frozen selection inventory'):
                r.check_prelabel(self.selection,self.prereg)

    def test_prelabel_bytes_cannot_be_replaced_after_commit(self):
        self.preregistration(); commit=self.commit()
        with patch.object(r,'ROOT',self.root):
            r.check_prelabel_commit(self.prereg,commit)
            entries=c.unseal(self.prereg/'manifest.json')
            # A freshly resealed local manifest still must match the committed bytes.
            c.seal(self.prereg/'manifest.json',dict(entries,amendment='different manifest bytes'))
            with self.assertRaisesRegex(ValueError,'Git commit manifest differs'):
                r.check_prelabel_commit(self.prereg,commit)

    def test_commit_must_exist_and_contain_this_preregistration(self):
        self.preregistration(); self.commit()
        with patch.object(r,'ROOT',self.root):
            with self.assertRaisesRegex(ValueError,'does not contain'):
                r.check_prelabel_commit(self.prereg,'0'*40)
            with self.assertRaisesRegex(ValueError,'Exact pushed prelabel'):
                r.check_prelabel_commit(self.prereg,'HEAD')
            with self.assertRaisesRegex(ValueError,'inside the checkout'):
                r.check_prelabel_commit(self.root.parent,'0'*40)

    def failure(self):
        root=self.root/'failed'; root.mkdir()
        plan=dict(workload='fixture',source_bindings={},inputs={})
        plan['context_id']=c.digest(plan); c.seal(root/'plan.json',plan)
        log=root/'discovery/compile.log'; log.parent.mkdir(); log.write_text('compile failed')
        receipt=dict(log='discovery/compile.log',log_sha256=c.sha(log),elapsed_seconds=3,
                     returncode=1,expected_returncode=0,failure='exit1')
        c.seal(root/'commands.json',[receipt])
        c.seal(root/'qualification-failure.json',dict(context_id=plan['context_id'],
            candidate_labels_read=0,reason='linker program limit'))
        return root,plan,receipt

    def test_failed_qualification_round_trips_and_resume_is_read_only(self):
        root,_,_=self.failure()
        expected=r.failed_cost(root)
        self.assertEqual((expected['candidate_labels'],expected['command_seconds']),(0,3))
        snapshot=self.root/'snapshot'; snapshot.mkdir()
        record=pack_archive(root,snapshot/'failed.tar.gz')
        restored=self.root/'restored'
        restore_archive(snapshot,record,restored)
        self.assertEqual(r.failed_cost(restored),expected)
        original={p.relative_to(restored).as_posix():c.sha(p) for p in restored.rglob('*') if p.is_file()}
        # A replay can reuse the authenticated extraction without overwriting it.
        restore_archive(snapshot,record,restored)
        self.assertEqual(original,{p.relative_to(restored).as_posix():c.sha(p) for p in restored.rglob('*') if p.is_file()})
        (restored/'discovery/compile.log').write_text('changed failure')
        with self.assertRaisesRegex(ValueError,'Restored evidence changed'):
            restore_archive(snapshot,record,restored)

    def test_candidate_failure_cannot_be_reclassified_as_qualification(self):
        root,_,receipt=self.failure()
        attempt=root/'measurements/candidate_00/attempt-000'; attempt.mkdir(parents=True)
        with self.assertRaisesRegex(ValueError,'candidate attempt'):
            r.failed_cost(root)
        shutil.rmtree(root/'measurements')
        log=root/'measurements/candidate_00/compile.log'; log.parent.mkdir(parents=True); log.write_text('failed candidate')
        c.seal(root/'commands.json',[dict(receipt,log='measurements/candidate_00/compile.log',log_sha256=c.sha(log))])
        # Removing directories cannot launder a candidate command into setup cost.
        original=r.evidence._receipts(root,allow_failures=True)
        shutil.rmtree(root/'measurements')
        with patch.object(r.evidence,'_receipts',return_value=original):
            with self.assertRaisesRegex(ValueError,'candidate receipt'):
                r.failed_cost(root)

    def test_qualification_context_and_record_remain_bound(self):
        root,plan,_=self.failure()
        plan['workload']='different'; c.seal(root/'plan.json',plan)
        with self.assertRaisesRegex(ValueError,'context digest differs'):
            r.failed_cost(root)

    def pool_failure(self, executable_count=1):
        root,plan,_=self.failure()
        plan.pop('context_id'); plan['pool_size']=6; plan['context_id']=c.digest(plan)
        c.seal(root/'plan.json',plan)
        c.seal(root/'qualification-failure.json',dict(context_id=plan['context_id'],candidate_labels_read=0,
            phase='candidate pool qualification',eligible_formula_count=1,reason='Too few calibrated executable candidates'))
        attempt=root/'discovery/attempt-000'
        for folder in ('marked','original','profile'): (attempt/folder).mkdir(parents=True)
        (attempt/'program.s').write_text('assembly source')
        (attempt/'marked.S').write_text('derived marked assembly')
        for name in ('marked/firmware.hex','original/firmware.hex'): (attempt/name).write_text('00000013\n')
        (attempt/'marked/disassembly.txt').write_text('fixture disassembly')
        (attempt/'marked/symbols.txt').write_text('fixture symbols')
        raw=dict(markers=2,region_counts={'0':2})
        profile=attempt/'profile/simulation.json'; c.write(profile,raw)
        receipt=dict(log=profile.relative_to(root).as_posix(),log_sha256=c.sha(profile),elapsed_seconds=3,
            returncode=0,expected_returncode=0,failure=None)
        c.seal(root/'commands.json',[receipt])
        calibration=dict(rule_matches_all=True,semantic_checks_passed=True,stock_trap_control_passed=True,
            rows=[dict(op='pcpi',immediate=None,cycles=5),dict(op='add',immediate=None,cycles=3)])
        (root/'inputs').mkdir(); c.write(root/'inputs/latency-calibration.json',calibration)
        program={0:{'op':'add'}}
        derived=dict(executable_candidates=[dict(occurrences=[dict(pcs=['0x0'])]) for _ in range(executable_count)])
        stack=ExitStack()
        adapter=SimpleNamespace(validate_memory=lambda raw:None)
        stack.enter_context(patch.object(r.evidence,'_adapter',return_value=adapter))
        stack.enter_context(patch.object(r.evidence,'_observations'))
        stack.enter_context(patch.object(r.evidence,'_calibration',return_value=calibration))
        stack.enter_context(patch.object(r.evidence,'validate_isa',return_value={'custom_static_sites':0}))
        stack.enter_context(patch.object(r.evidence,'validate_execution',return_value={'instructions':3}))
        stack.enter_context(patch.object(r.evidence.lowering,'mark_assembly',return_value=('derived marked assembly',[])))
        stack.enter_context(patch.object(r.evidence.lowering,'read_program',return_value=program))
        stack.enter_context(patch.object(r.evidence.lowering,'map_sites',return_value={}))
        extracted=stack.enter_context(patch.object(r.evidence.partition,'EXTRACT',return_value=derived))
        return root,stack,extracted

    def test_successful_profile_can_still_fail_independently_verified_pool_qualification(self):
        root,stack,extracted=self.pool_failure()
        with stack:
            cost=r.failed_cost(root)
        self.assertEqual(cost['phase'],'candidate pool qualification')
        self.assertEqual(cost['eligible_formula_count'],1)
        self.assertEqual(cost['command_seconds'],3)
        self.assertEqual(extracted.call_args.args[-1],6)

    def test_pool_record_cannot_launder_a_successful_full_pool(self):
        root,stack,_=self.pool_failure(executable_count=6)
        with stack:
            with self.assertRaisesRegex(ValueError,'actually has the declared calibrated candidate pool'):
                r.failed_cost(root)

    def test_pool_record_count_and_marked_assembly_must_match_recomputation(self):
        root,stack,_=self.pool_failure(executable_count=2)
        with stack:
            with self.assertRaisesRegex(ValueError,'count differs from recomputation'):
                r.failed_cost(root)
            (root/'discovery/attempt-000/marked.S').write_text('changed marked assembly')
            with self.assertRaisesRegex(ValueError,'marked assembly differs'):
                r.failed_cost(root)

    def test_unqualified_successful_native_commands_are_not_failures(self):
        root,_,receipt=self.failure()
        c.seal(root/'commands.json',[dict(receipt,returncode=0,failure=None)])
        with self.assertRaisesRegex(ValueError,'Missing failed native qualification command'):
            r.failed_cost(root)

    def diagnostic(self):
        root=self.root/'diagnostic'; root.mkdir()
        inputs=root/'inputs'; inputs.mkdir()
        for name in ('soc_start.S','embench_firmware.c','embench_memory.c','program.c','beebsc.c','soc_link.ld'):
            (inputs/name).write_text('unchanged diagnostic input '+name)
        plan=dict(workload='fixture',source_bindings={},inputs={p.name:c.sha(p) for p in inputs.iterdir()},
            compiler_flags=['-Os'],tools={'gcc':{'path':'/toolchain/gcc'}},
            diagnostic='Exact original link with map emission; no simulator/candidate labels')
        plan['context_id']=c.digest(plan); c.seal(root/'plan.json',plan)
        # Receipts keep their original absolute paths when archives move.
        original_inputs=Path('/original/qualified/inputs'); original=Path('/original/diagnostic')
        argv=['/toolchain/gcc','-Os','-I',str(original_inputs),'-Wl,--no-relax','-Wl,--gc-sections',
            '-Wl,-T,'+str(original_inputs/'soc_link.ld'),
            *[str(original_inputs/name) for name in ('soc_start.S','embench_firmware.c','embench_memory.c','program.c','beebsc.c')],
            '-lgcc','-Wl,-Map,'+str(original/'diagnostic.map'),'-o',str(original/'diagnostic.elf')]
        (root/'compile.log').write_text('program exceeds declared linker limit')
        receipt=dict(argv=argv,cwd=str(original),log='compile.log',log_sha256=c.sha(root/'compile.log'),
            elapsed_seconds=.25,returncode=1,expected_returncode=1,failure=None)
        c.seal(root/'commands.json',[receipt])
        (root/'diagnostic.map').write_text('  0x00001ba0                        _program_end = .\n')
        summary=dict(workload='fixture',context_id=plan['context_id'],candidate_labels_read=0,
            map_sha256=c.sha(root/'diagnostic.map'),program_end=['0x00001ba0                        _program_end = .'])
        c.seal(root/'diagnostic-summary.json',summary)
        return root,receipt

    def test_static_diagnostic_authenticates_map_exact_argv_and_cost(self):
        root,receipt=self.diagnostic()
        expected=r.diagnostic_cost(root)
        self.assertEqual((expected['commands'],expected['command_seconds'],expected['candidate_labels']),(1,.25,0))
        snapshot=self.root/'diagnostic-snapshot'; snapshot.mkdir()
        archive=pack_archive(root,snapshot/'diagnostic.tar.gz')
        restored=self.root/'restored-diagnostic'; restore_archive(snapshot,archive,restored)
        self.assertEqual(r.diagnostic_cost(restored),expected)
        changed=copy.deepcopy(receipt); changed['argv'].insert(2,'-DCHANGED_PROGRAM=1')
        c.seal(root/'commands.json',[changed])
        with self.assertRaisesRegex(ValueError,'compiler prefix differs'):
            r.diagnostic_cost(root)

    def test_static_diagnostic_rejects_changed_map_and_candidate_output(self):
        root,receipt=self.diagnostic()
        (root/'diagnostic.map').write_text('different map')
        with self.assertRaisesRegex(ValueError,'map changed'): r.diagnostic_cost(root)
        (root/'diagnostic.map').write_text('  0x00001ba0                        _program_end = .\n')
        receipt['argv'][-1]='/original/diagnostic/candidate_00.elf'
        c.seal(root/'commands.json',[receipt])
        with self.assertRaisesRegex(ValueError,'exact failed original link'):
            r.diagnostic_cost(root)

    def test_static_diagnostic_cannot_contain_measurement_attempts(self):
        root,_=self.diagnostic()
        (root/'measurements/baseline/attempt-000').mkdir(parents=True)
        with self.assertRaisesRegex(ValueError,'measurements or candidate attempts'):
            r.diagnostic_cost(root)

    def test_replay_keeps_diagnostics_and_failed_qualification_costs_separate(self):
        self.preregistration(); commit=self.commit()
        failed,_,_=self.failure(); diagnostic,_=self.diagnostic()
        snapshot=self.root/'snapshot'; snapshot.mkdir()
        shutil.copytree(self.selection,snapshot/'selection')
        archives={}
        for name,source in (('qualification-failure-0',failed),('link-diagnostic-0',diagnostic)):
            archives[name]=pack_archive(source,snapshot/(name+'.tar.gz'))
        c.seal(snapshot/'archive-manifest.json',archives)
        c.seal(snapshot/'qualification-costs.json',[r.failed_cost(failed)])
        c.seal(snapshot/'diagnostic-costs.json',[r.diagnostic_cost(diagnostic)])
        c.seal(snapshot/'source-manifest.json',{})
        c.seal(snapshot/'provenance.json',dict(preregistration='results/prereg',prelabel_commit=commit,
            preregistration_manifest_sha256=c.sha(self.prereg/'manifest.json'),history_manifests={}))
        c.seal(snapshot/'manifest.json',{p.relative_to(snapshot).as_posix():c.sha(p)
            for p in sorted(snapshot.rglob('*')) if p.is_file()})
        with patch.object(r,'ROOT',self.root),patch.object(r,'restore_history',return_value=[]), \
             patch.object(r.evidence,'evaluate',return_value={'targets':{},'audits':{}}) as evaluate:
            result=r.replay(snapshot,self.root/'replay')
        self.assertEqual(result['failed_qualification_command_seconds'],3)
        self.assertEqual(result['static_link_diagnostic_command_seconds'],.25)
        self.assertEqual(result['candidate_attempts'],0)
        self.assertEqual(result['new_native_jobs'],0)
        evaluate.assert_called_once_with(snapshot/'selection',[],history_roots=[],verify=True)

    def test_pack_checks_preregistration_before_opening_outcomes(self):
        self.preregistration()
        c.seal(self.prereg/'manifest.json',{})
        with patch.object(r.evidence,'evaluate',side_effect=AssertionError('Opened target labels')):
            with self.assertRaisesRegex(ValueError,'complete frozen selection inventory'):
                r.pack(self.selection,[],[],self.root/'snapshot',self.prereg,'0'*40)

    def test_pack_cannot_double_charge_duplicate_native_roots(self):
        root=self.root/'one-native-run'
        with patch.object(r.evidence,'evaluate',side_effect=AssertionError('Opened target labels')):
            with self.assertRaisesRegex(ValueError,'double-count costs'):
                r.pack(self.selection,[],[root,root],self.root/'snapshot',self.prereg,'0'*40)
            with self.assertRaisesRegex(ValueError,'double-count costs'):
                r.pack(self.selection,[root],[],self.root/'snapshot',self.prereg,'0'*40,diagnostics=[root])

    def test_replay_rejects_corrupted_archive_before_policy_evaluation(self):
        self.preregistration(); commit=self.commit()
        failed,_,_=self.failure(); snapshot=self.root/'snapshot'; snapshot.mkdir()
        shutil.copytree(self.selection,snapshot/'selection')
        record=pack_archive(failed,snapshot/'failed.tar.gz')
        c.seal(snapshot/'archive-manifest.json',{'qualification-failure-0':record})
        c.seal(snapshot/'qualification-costs.json',[r.failed_cost(failed)])
        c.seal(snapshot/'source-manifest.json',{})
        c.seal(snapshot/'provenance.json',dict(preregistration='results/prereg',prelabel_commit=commit,
            preregistration_manifest_sha256=c.sha(self.prereg/'manifest.json'),history_manifests={}))
        c.seal(snapshot/'manifest.json',{p.relative_to(snapshot).as_posix():c.sha(p)
            for p in sorted(snapshot.rglob('*')) if p.is_file()})
        (snapshot/'failed.tar.gz').write_bytes(b'changed archive')
        with patch.object(r,'ROOT',self.root), \
             patch.object(r.evidence,'evaluate',side_effect=AssertionError('Opened target labels')):
            with self.assertRaisesRegex(ValueError,'Manifest checksum differs'):
                r.replay(snapshot,self.root/'replay')


if __name__=='__main__': unittest.main()
