"""Read-only saved-preflight replay and tiny synthetic V11c poison fixtures.

No native processes. Frozen V11b streaming/ELF tests remain a separate suite.
"""
import copy
import gzip
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import audit_v11c_recovery as a

PREFLIGHT = a.ROOT/'results/2026-10-16-v11c-dtc-recovery/preflight'


def startup_fixture(folder):
    # Six tiny retained files, not a workload or decompressed trace copy.
    for path in PREFLIGHT.iterdir(): (folder/path.name).write_bytes(path.read_bytes())
    tools=a.read(folder/'tools.json');receipt=a.read(folder/'receipt.json')
    plan={'programs':{'fac':{'elf':{'sha256':receipt['elf_sha256']},'original_record':{'captured_outputs':[154,5]}}}}
    reseal(folder,receipt,plan)
    return tools,receipt,plan


def reseal(folder,receipt,plan):
    (folder/'receipt.json').write_text(json.dumps(receipt))
    p=folder/'receipt.json';plan['preflight']={'path':'preflight/receipt.json','sha256':a.sha(p),'bytes':p.stat().st_size}


class DtcProfileTests(unittest.TestCase):
    def test_fixed_policy_is_shared_unchanged(self):
        policy=a.expected_policy()
        self.assertEqual(policy['programs'],list(a.NAMES));self.assertEqual(policy['recover'],['ammunition','pm'])
        self.assertEqual(policy['workers'],1);self.assertEqual(policy['retries'],0)
        self.assertEqual(policy['capture_seconds'],300);self.assertEqual(policy['offline_seconds'],1800)

    def test_explicit_dtc_tool_environment_and_dependencies(self):
        tools=a.read(PREFLIGHT/'tools.json');a.validate_dtc_tools(tools)
        for kind in ('missing','path','version','dependency','hash'):
            with self.subTest(kind=kind):
                t=copy.deepcopy(tools)
                if kind=='missing':del t['executables']['dtc']
                elif kind=='path':t['environment']['PATH']='/usr/bin:/bin'
                elif kind=='version':t['executables']['dtc']['version']='different'
                elif kind=='dependency':del t['dependencies']['dtc']
                else:t['executables']['dtc']['sha256']='not-a-hash'
                with self.assertRaises(ValueError):a.validate_dtc_tools(t)

    def test_exact_executed_snapshot_and_narrow_reviewed_source_pair(self):
        old=(PREFLIGHT/'runner-source.py').read_text();new=(a.ROOT/'scripts/recover_v11c_transfer.py').read_text();tools=a.read(PREFLIGHT/'tools.json')
        result=a.verify_startup_source(old,new,tools)
        self.assertTrue(result['executed_startup_function_unchanged'])
        self.assertEqual(result['changed_nonstartup_functions'],['failure_evidence','sources'])
        self.assertTrue(result['satisfied_extra_dependency_guard'])
        for altered_old,altered_new in ((old+'\n# poison',new),(old,new+'\n# poison'),(old,new.replace("'-m16'","'-m32'"))):
            with self.assertRaises(ValueError):a.verify_startup_source(altered_old,altered_new,tools)

    def test_preserved_failure_binding_cannot_drop_or_redefine_history(self):
        root=a.ROOT/a.FAILED;report=a.read(root/'run/input-review/independent-failure-audit.json')
        record=dict(root=a.FAILED,freeze_commit='92bd7c52f5363c02dd19733941950d914db8f062',preparation_sha256=a.sha(root/'preparation.json'),completion_sha256=a.FAILED_SHA,evidence_manifest_sha256=a.sha(root/'run/attempt-0000/evidence-manifest.json'),metadata_archive_sha256=a.sha(root/'run/attempt-0000/metadata.zip'),independent_failure_audit_sha256=a.FAILED_REPORT_SHA,captures=2,retired_commits=0,new_labels=0,amendment='Environment-only: add pinned dtc to controlled PATH; unchanged programs, ELFs, budgets, ROI, extraction, endpoint and ordering.')
        bindings={p:None for p in root.rglob('*') if p.is_file()}
        with patch.object(a.failure_audit,'inspect',return_value=report):
            a.verify_failure_binding(record,bindings)
            for key,value in [('retired_commits',1),('completion_sha256','changed'),('root','other')]:
                with self.assertRaises(ValueError):a.verify_failure_binding({**record,key:value},bindings)
            del bindings[root/'completion.json']
            with self.assertRaises(ValueError):a.verify_failure_binding(record,bindings)


class StartupTests(unittest.TestCase):
    def test_clean_saved_fac_startup_and_exact_source_snapshots(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);f=root/'preflight';f.mkdir();tools,row,plan=startup_fixture(f)
            actual=a.verify_preflight(root,tools,plan)
            self.assertEqual(actual['captured_outputs'],[154,5]);self.assertEqual(actual['new_trace_captures'],0)

    def test_startup_failure_scope_identity_and_cleanup_poisons(self):
        for key,value in [('returncode',True),('complete',False),('new_trace_captures',1),('new_labels',True),('captured_outputs',[153,5]),('elf_sha256','other'),('cleanup_errors',['ownedgroup']),('remaining_owned_children',['pid']),('timeout_seconds',61),('elapsed_seconds',float('inf'))]:
            with self.subTest(key=key),tempfile.TemporaryDirectory() as d:
                root=Path(d);f=root/'preflight';f.mkdir();tools,row,plan=startup_fixture(f);row[key]=value;reseal(f,row,plan)
                with self.assertRaises(ValueError):a.verify_preflight(root,tools,plan)

    def test_reauthenticated_stdout_command_and_source_poison(self):
        for kind in ('stdout','command','source','helper','extra'):
            with self.subTest(kind=kind),tempfile.TemporaryDirectory() as d:
                root=Path(d);f=root/'preflight';f.mkdir();tools,row,plan=startup_fixture(f)
                if kind=='stdout':
                    (f/'stdout.log').write_text(json.dumps(dict(kind='external-output',upstream_status=0,values=[153,5])));row['stdout_sha256']=a.sha(f/'stdout.log')
                elif kind=='command':row['command'][1]='--log-commits'
                elif kind=='source':
                    p=f/'runner-source.py';p.write_text(p.read_text()+'\n# reauthenticated poison');row['runner_sha256']=a.sha(p)
                elif kind=='helper':
                    p=f/'helper-source.py';p.write_text('poison');row['helper_sha256']=a.sha(p)
                else:(f/'extra.log').write_text('unexpected')
                reseal(f,row,plan)
                with self.assertRaises(ValueError):a.verify_preflight(root,tools,plan)

    def test_c_worker_schema_and_canonical_generated_prefix(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d);(base/'decode-worker.log').write_text('saved')
            root=a.ROOT/'results/synthetic';runner=a.ROOT/'scripts/recover_v11c_transfer.py'
            row=dict(schema='isaforge-v11c-owned-worker-v1',program='pm',phase='decode',complete=True,returncode=0,primary_error=None,cleanup_errors=[],remaining_owned_children=[],timeout_seconds=1800,elapsed_seconds=1,started_at_utc='2026-10-16T00:00:00+00:00',completed_at_utc='2026-10-16T00:00:01+00:00',runner_sha256=a.sha(runner),claim_sha256='claim',log_sha256=a.sha(base/'decode-worker.log'),command=['python',str(runner),'worker','--root',str(root),'--program','pm','--phase','decode','--claim-sha256','claim'])
            a.verify_worker(row,'pm','decode',base,root,'claim')
            row['schema']='isaforge-v11b-owned-worker-v1'
            with self.assertRaises(ValueError):a.verify_worker(row,'pm','decode',base,root,'claim')
        self.assertEqual(a.PREFIX,'generated/v11-spooled-recovery/dtc-attempt-0000')


if __name__=='__main__':unittest.main()
