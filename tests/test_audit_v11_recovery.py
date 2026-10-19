"""Tiny saved-evidence fixtures only: no simulator, compiler or native jobs."""
import copy
import gzip
import hashlib
import io
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import audit_v11_recovery as a


def commit(pc, word, suffix=''):
    return f'core   0: 3 0x{pc:08x} (0x{word:08x}){suffix}\n'


def window(start=10):
    raw = ['banner\n', commit(0x80, 0xc0202573, f' x10 0x{start:x}'),
           commit(0x100, 0x00108093), commit(0x104, 0x00208093),
           commit(0x108, 0xc0202573, f' x10 0x{(start+3)&0xffffffff:x}'), 'HTIF trailer\n']
    decoded = []
    for seq in (2, 3):
        word = (0x00108093, 0x00208093)[seq - 2]
        op, rd, rs1, rs2, imm = a.decode(word)
        decoded.append(json.dumps(dict(pc=f'0x{0x100+(seq-2)*4:08x}', raw=f'0x{word:08x}', op=op, rd=rd, rs1=rs1, rs2=rs2, imm=imm, seq=seq)) + '\n')
    return raw, decoded


def toy_elf(words=(0x00108093, 0x00208093), name=b'toy', aliases=()):
    # Null, executable .text, string table, symbol table; one STT_FUNC symbol.
    text = struct.pack('<' + 'I' * len(words), *words)
    strings = b'\0'; symbols = bytes(16)
    for label in (name, *aliases):
        offset = len(strings); strings += label + b'\0'
        symbols += struct.pack('<IIIBBH', offset, 0x100, len(text), 0x12, 0, 1)
    off_text = 52; off_str = off_text + len(text); off_sym = off_str + len(strings); shoff = off_sym + len(symbols)
    header = struct.pack('<16sHHIIIIIHHHHHH', b'\x7fELF\x01\x01\x01' + bytes(9), 2, 243, 1, 0x100, 0, shoff, 0, 52, 0, 0, 40, 4, 0)
    section = lambda typ, flags, addr, off, size, link=0, entry=0: struct.pack('<IIIIIIIIII', 0, typ, flags, addr, off, size, link, 0, 4, entry)
    return header + text + strings + symbols + bytes(40) + section(1, 6, 0x100, off_text, len(text)) + section(3, 0, 0, off_str, len(strings)) + section(2, 0, 0, off_sym, len(symbols), 2, 16)


def fixture_outcomes():
    programs = {}; records = {}
    for name in a.NAMES:
        status = 'empty' if name == 'recursion' else 'complete'
        original = dict(status='failure-retained' if name in a.RECOVER else status, all_roi_count=0 if status == 'empty' else 1)
        programs[name] = dict(mode='recovered' if name in a.RECOVER else 'reused', family=a.FAMILIES[name], original_record=original)
        records[name] = dict(status=status, candidate_count=0 if status == 'empty' else 1, mode=programs[name]['mode'], family=a.FAMILIES[name], original_record=copy.deepcopy(original))
        if name in a.REUSE:
            for key, output in [('candidates', 'candidate_file'), ('trace_summary', 'trace_summary'), ('fusion', 'fusion')]:
                programs[name][key] = {'path': name + key, 'sha256': 'test'}; records[name][output] = copy.deepcopy(programs[name][key])
    return records, {'programs': programs}


class RawTests(unittest.TestCase):
    def test_exact_count_and_global_sequence(self):
        raw, rows = window(); result, counts, starts = a.replay_raw(raw, rows)
        self.assertEqual(result['trace_instructions'], 2); self.assertEqual(result['instret_delta'], 3)
        self.assertEqual(counts, {0x100: 1, 0x104: 1}); self.assertEqual(starts, {0x100, 0x108})

    def test_modulo32_marker_wrap(self):
        raw, rows = window(0xfffffffe); self.assertEqual(a.replay_raw(raw, rows)[0]['instret_stop'], 1)

    def test_count_missing_extra_markers_fail(self):
        for change in ('count', 'missing', 'extra', 'write'):
            with self.subTest(change=change):
                raw, rows = window()
                if change == 'count': raw[4] = commit(0x108, 0xc0202573, ' x10 0x99')
                if change == 'missing': raw.pop(4)
                if change == 'extra': raw.append(commit(0x110, 0xc0202573, ' x10 0x14'))
                if change == 'write': raw[4] = commit(0x108, 0xc0202573, ' x11 0xd')
                with self.assertRaises(ValueError): a.replay_raw(raw, rows)

    def test_malformed_after_stop_rejected(self):
        raw, rows = window(); raw.append('core garbage\n')
        with self.assertRaisesRegex(ValueError, 'Malformed'): a.replay_raw(raw, rows)

    def test_unmeasured_unknown_is_allowed_but_measured_is_not(self):
        raw, rows = window(); raw.append(commit(0x1000, 0xffffffff)); a.replay_raw(raw, rows)
        raw, rows = window(); raw[2] = commit(0x100, 0xffffffff)
        with self.assertRaisesRegex(ValueError, 'Unknown'): a.replay_raw(raw, rows)

    def test_decoded_poison_and_missing_extra_rows(self):
        for kind in ('seq', 'pc', 'op', 'raw', 'bool', 'missing', 'extra', 'duplicate-key'):
            with self.subTest(kind=kind):
                raw, rows = window(); row = json.loads(rows[0])
                if kind == 'missing': rows.pop()
                elif kind == 'extra': rows.append(rows[0])
                elif kind == 'duplicate-key': rows[0] = '{"pc":1,"pc":2}'
                else:
                    row[{'bool':'rd'}.get(kind, kind)] = {'seq':1, 'pc':'0x00000104', 'op':'sub', 'raw':'0x00000013', 'bool':True}[kind]
                    rows[0] = json.dumps(row)
                with self.assertRaises(ValueError): a.replay_raw(raw, rows)

    def test_raw_elf_instruction_identity(self):
        raw, rows = window(); a.replay_raw(raw, rows, {0x100:0x00108093, 0x104:0x00208093})
        with self.assertRaisesRegex(ValueError, 'ELF'): a.replay_raw(raw, rows, {0x100:0x00208093, 0x104:0x00208093})

    def test_gzip_crc_truncation_and_utf8(self):
        with tempfile.TemporaryDirectory() as d:
            raw, rows = window(); r = Path(d)/'raw.gz'; f = Path(d)/'decoded.gz'
            valid = gzip.compress(''.join(raw).encode()); f.write_bytes(gzip.compress(''.join(rows).encode()))
            r.write_bytes(valid); a.replay_gzip(r, f)
            corrupt = bytearray(valid); corrupt[-8] ^= 1
            for payload in (valid[:-4], corrupt, gzip.compress(b'\xff\n')):
                r.write_bytes(payload)
                with self.assertRaises((ValueError, EOFError, OSError, UnicodeError)): a.replay_gzip(r, f)


class StaticTests(unittest.TestCase):
    def test_static_elf_and_disassembly(self):
        data = toy_elf(); program = a.elf_program(data)
        self.assertEqual(set(program), {0x100,0x104}); self.assertEqual(program[0x100]['symbol'], 'toy')
        text = '00000100 <toy>:\n 100: 00108093 addi\n 104: 00208093 addi\n'
        self.assertEqual(a.parse_disassembly(text, data), program)
        for poison in (text.replace('00108093', '00208093'), text.replace('<toy>', '<wrong>'), text.split(' 104:')[0], text + ' 100: 00108093 addi\n'):
            with self.assertRaises(ValueError): a.parse_disassembly(poison, data)

    def test_same_address_function_alias_uses_saved_valid_heading(self):
        data = toy_elf(name=b'__gtsf2', aliases=(b'__gesf2',))
        text = '00000100 <__gesf2>:\n 100: 00108093 addi\n 104: 00208093 addi\n'
        actual = a.parse_disassembly(text, data)
        self.assertEqual(actual[0x100]['symbol'], '__gesf2')
        self.assertEqual(a.elf_program(data)[0x100]['symbol'], '__gtsf2')
        with self.assertRaises(ValueError): a.parse_disassembly(text.replace('00000100 <', '00000104 <'), data)

    def test_elf_header_bounds_and_symbol_rejection(self):
        for change in ('width','endian','machine','section','truncated','name'):
            with self.subTest(change=change):
                data = bytearray(toy_elf())
                if change == 'width': data[4] = 2
                elif change == 'endian': data[5] = 2
                elif change == 'machine': data[18] = 0
                elif change == 'section': struct.pack_into('<I', data, 32, len(data)+50)
                elif change == 'truncated': data = data[:-5]
                else: data[62:65] = b'\xff\xff\xff'
                with self.assertRaises((ValueError, UnicodeError)): a.elf_program(bytes(data))

    def test_extraction_and_fusion_all_occurrences(self):
        program = a.elf_program(toy_elf()); runs = a.Counter({0x100:1,0x104:1}); starts = {0x100,0x108}
        rows = a.extractCandidates(program,runs,starts,maxSize=4,limit=None)
        self.assertEqual(len(rows),1)
        checked = a.fusion(program,rows,'toy'); saved = dict(passed=True,seed=2026101507,benchmarks=[checked])
        a.extraction(program,runs,starts,rows,'toy',saved)
        bad = copy.deepcopy(rows); bad[0]['formula'] = 'sub(in0,3)'
        with self.assertRaises(ValueError): a.extraction(program,runs,starts,bad,'toy',saved)
        with self.assertRaisesRegex(ValueError,'fusion'): a.fusion(program,bad,'toy')
        bad = copy.deepcopy(saved); bad['benchmarks'][0]['individual_comparisons'] -= 1
        with self.assertRaises(ValueError): a.extraction(program,runs,starts,rows,'toy',bad)

    def test_zero_candidates_is_not_zero_error(self):
        program = a.elf_program(toy_elf((0x00000013,)))
        rows = a.extractCandidates(program, a.Counter({0x100:1}), {0x100,0x104}, maxSize=4, limit=None)
        self.assertEqual(rows,[]); self.assertEqual(a.fusion(program,rows,'recursion')['checked_occurrences'],0)


class ContractTests(unittest.TestCase):
    def test_six_outcomes_four_exact_reuse(self):
        records, plan = fixture_outcomes(); a.verify_outcomes(records,plan)
        for kind in ('omit','failure','empty','reuse','family','recursion'):
            with self.subTest(kind=kind):
                r = copy.deepcopy(records)
                if kind == 'omit': del r['recursion']
                elif kind == 'failure': r['pm']['status'] = 'failure-retained'
                elif kind == 'empty': r['pm']['status'] = 'empty'
                elif kind == 'reuse': r['fac']['candidate_file']['sha256'] = 'bad'
                elif kind == 'family': r['pm']['family'] = 'integer-recurrences'
                else: r['recursion'].update(status='complete',candidate_count=1)
                with self.assertRaises(ValueError): a.verify_outcomes(r,plan)

    def test_htif_exact_single_signed32_snapshot(self):
        good = dict(kind='external-output',upstream_status=0,values=[154,5])
        a.htif(json.dumps(good),[154,5])
        for kind in ('duplicate','failed','bool','wrong','unsigned','missing'):
            with self.subTest(kind=kind):
                value = copy.deepcopy(good)
                if kind == 'failed': value['upstream_status'] = 1
                elif kind == 'bool': value['upstream_status'] = False
                elif kind == 'wrong': value['values'][0] += 1
                elif kind == 'unsigned': value['values'][0] = 2**32-1
                text = '' if kind == 'missing' else json.dumps(value)
                if kind == 'duplicate': text += '\n' + text
                with self.assertRaises(ValueError): a.htif(text,[154,5])

    def test_archive_exact_members_and_reauthenticated_corruption(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'a.zip'; payload=b'fixed'
            row=dict(path='a',sha256=hashlib.sha256(payload).hexdigest(),bytes=len(payload))
            with zipfile.ZipFile(p,'w') as z:z.writestr('a',payload)
            self.assertEqual(a.verify_zip(p,[row]),1)
            with zipfile.ZipFile(p,'w') as z:z.writestr('a',b'changed')
            with self.assertRaises(ValueError): a.verify_zip(p,[row])
            with zipfile.ZipFile(p,'w') as z:z.writestr('a',payload);z.writestr('extra',b'')
            with self.assertRaises(ValueError): a.verify_zip(p,[row])
            row['path']='../escape'
            with zipfile.ZipFile(p,'w') as z:z.writestr('../escape',payload)
            with self.assertRaises(ValueError): a.verify_zip(p,[row])

    def test_duplicate_json_and_integer_bool_rejected(self):
        with self.assertRaises(ValueError):a.loads('{"x":1,"x":2}')
        for x in (False,True,-1,1.0):
            with self.assertRaises(ValueError):a.integer(x)

    def test_record_escape_rejected(self):
        with self.assertRaises(ValueError):a.local('../outside')
        with self.assertRaises(ValueError):a.local('/absolute')

    def test_output_oracle_pure_replay(self):
        self.assertEqual(a.validate_output('fac',[154,5],None)['expected'],[154,5])
        with self.assertRaises(ValueError):a.validate_output('recursion',[88,10],None)




class StageTests(unittest.TestCase):
    def test_capture_wrapper_source_claim_and_order(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'capture.json'; p.write_text('capture')
            row = dict(schema='isaforge-v11b-capture-worker-v1', program='pm', runner_sha256='source',claim_sha256='claim',capture_sha256=a.sha(p),primary_error=None,
                       started_at_utc='2026-10-16T00:00:00+00:00',completed_at_utc='2026-10-16T00:01:00+00:00')
            a.verify_capture_worker(row,'pm',p,'source','claim')
            for key,value in [('primary_error','failed'),('capture_sha256','changed'),('claim_sha256','wrong'),('completed_at_utc','2026-10-15T23:59:59+00:00'),('completed_at_utc','2026-10-16T00:06:00+00:00')]:
                poison={**row,key:value}
                with self.assertRaises(ValueError):a.verify_capture_worker(poison,'pm',p,'source','claim')

    def test_owned_worker_exact_archived_command_without_historical_filesystem(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d).resolve(); base = repo/'generated/pm'; base.mkdir(parents=True)
            (repo/'scripts').mkdir(); (repo/'scripts/recover_v11_transfer.py').write_text('source')
            (base/'decode-worker.log').write_text('log')
            root=repo/'results/study'; origin='/original/host/repository'
            row=dict(schema='isaforge-v11b-owned-worker-v1',program='pm',phase='decode',complete=True,returncode=0,primary_error=None,cleanup_errors=[],remaining_owned_children=[],timeout_seconds=1800,elapsed_seconds=3,
                     started_at_utc='2026-10-16T00:00:00+00:00',completed_at_utc='2026-10-16T00:00:03+00:00',
                     runner_sha256=a.sha(repo/'scripts/recover_v11_transfer.py'),claim_sha256='claim',log_sha256=a.sha(base/'decode-worker.log'),
                     command=['/original/venv/python',origin+'/scripts/recover_v11_transfer.py','worker','--root',origin+'/results/study','--program','pm','--phase','decode','--claim-sha256','claim'])
            with patch.object(a,'ROOT',repo):
                a.verify_worker(row,'pm','decode',base,root,'claim')
                for key,value in [('returncode',True),('complete',False),('cleanup_errors',['failed']),('remaining_owned_children',['pid']),('timeout_seconds',1801),('claim_sha256','wrong')]:
                    with self.assertRaises(ValueError):a.verify_worker({**row,key:value},'pm','decode',base,root,'claim')
                poison=copy.deepcopy(row);poison['command'][4]=origin+'/results/other'
                with self.assertRaises(ValueError):a.verify_worker(poison,'pm','decode',base,root,'claim')

    def test_capture_tools_and_original_elf_command(self):
        tools=dict(executables={'gzip':{'path':'/bin/gzip','sha256':'gzip'},'spike':{'path':'/bin/spike'}},environment={'LANG':'C'})
        capture=dict(schema='isaforge-v11-spooled-capture-v1',status='captured-not-validated',producer_returncode=0,compressor_returncode=0,primary_error=None,cleanup_errors=[],remaining_owned_children=[],compressor_sha256='gzip',compressor_command=['/bin/gzip','-1','-n','-c'],environment={'LANG':'C'},capture_and_drain_wall_seconds=1,
                     producer_command=['/bin/spike','--isa=rv32im_zicntr','-m16','--log-commits','--log=/dev/fd/4','/old/repo/results/study/inputs/elfs/pm.elf'])
        root=a.ROOT/'results/study';elf={'path':'inputs/elfs/pm.elf'}
        a.verify_capture(capture,tools,elf,root)
        for key,value in [('compressor_returncode',True),('cleanup_errors',['kill']),('status','failure-retained'),('capture_and_drain_wall_seconds',342)]:
            with self.assertRaises(ValueError):a.verify_capture({**capture,key:value},tools,elf,root)
        poison=copy.deepcopy(capture);poison['producer_command'][-1]='/wrong.elf'
        with self.assertRaises(ValueError):a.verify_capture(poison,tools,elf,root)

    def test_package_streaming_four_payloads_and_metadata_inventory(self):
        with tempfile.TemporaryDirectory() as d:
            repo=Path(d).resolve();root=repo/'results/study';stage=root/'run/attempt-0000';stage.mkdir(parents=True)
            attempt=repo/'generated/v11-spooled-recovery/attempt-0000'
            for n in ('preparation.json','plan.json','tools.json','recovery-approval.json','recovery-claim.json'):(root/n).write_text('{}')
            for n in ('programs.json','completed-rows.json','completion.json'):(stage/n).write_text('{}')
            for name in a.RECOVER:
                for phase,file in [('capture','raw-spike.log.gz'),('decode','decoded.jsonl.gz')]:
                    p=attempt/name/phase/file;p.parent.mkdir(parents=True);p.write_bytes(gzip.compress(b'synthetic\n'))
            def seal(extra=None,duplicate_payload=False):
                paths=sorted([*(p for p in root.rglob('*') if p.is_file() and p.name not in ('metadata.zip','evidence-manifest.json')),*(p for p in attempt.rglob('*') if p.is_file())])
                records=[];members=[]
                with zipfile.ZipFile(stage/'metadata.zip','w') as z:
                    for path in paths:
                        r=dict(path=path.relative_to(repo).as_posix(),sha256=a.sha(path),bytes=path.stat().st_size,packaged='.gz' not in path.name or duplicate_payload)
                        records.append(r)
                        if r['packaged']:z.write(path,r['path']);members.append({k:r[k] for k in ('path','sha256','bytes')})
                manifest=dict(schema='isaforge-v11b-recovery-evidence-v1',complete=True,completion_sha256=a.sha(stage/'completion.json'),compressed_payloads_duplicated=False,historical_archives_reused_by_reference=True,files=records,
                              archive=dict(path='metadata.zip',sha256=a.sha(stage/'metadata.zip'),bytes=(stage/'metadata.zip').stat().st_size,members=members))
                (stage/'evidence-manifest.json').write_text(json.dumps(manifest));return manifest
            seal()
            with patch.object(a,'ROOT',repo):
                a.verify_package(root,{})
                # Reauthenticate a forbidden fifth payload: semantic inventory must still reject it.
                extra=attempt/'pm/decode/extra.gz';extra.write_bytes(gzip.compress(b'poison'));seal()
                with self.assertRaisesRegex(ValueError,'four'):a.verify_package(root,{})
                extra.unlink();seal(duplicate_payload=True)
                with self.assertRaises(ValueError):a.verify_package(root,{})
                partial=attempt/'pm/decode/unfinished.partial';partial.write_text('partial');seal()
                with self.assertRaisesRegex(ValueError,'partial'):a.verify_package(root,{})




class FullSavedPackageTests(unittest.TestCase):
    def test_complete_tiny_package_replays_and_reauthenticated_poison_fails(self):
        # Preparation/history authentication has a separate real-input gate. This
        # fixture isolates the entire result replay from a supplied input review.
        with tempfile.TemporaryDirectory() as d:
            repo=Path(d).resolve();root=repo/'results/study';stage=root/'run/attempt-0000';stage.mkdir(parents=True)
            def put(p,obj):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(obj))
            def rec(p):return dict(path=str(p.relative_to(root)) if p.is_relative_to(root) else __import__('os').path.relpath(p,root),sha256=a.sha(p),bytes=p.stat().st_size)
            for name in ('tracing.py','run_holdout_benchmarks.py'):
                p=repo/'src'/name;p.parent.mkdir(exist_ok=True);p.write_text('synthetic frozen '+name)
            runner=repo/'scripts/recover_v11_transfer.py';runner.parent.mkdir();runner.write_text('synthetic runner')
            program=a.elf_program(toy_elf());_,counts,starts=a.replay_raw(*window())
            candidates=a.extractCandidates(program,counts,starts,maxSize=4,limit=None)
            programs={};outcomes={};oldreport={'records':{}};reuse_bytes={}
            values={'ammunition':[0,0,255,255,255,254,0,0,7,255,255,255,255,0,0],
                    'pm':[12,64,60,12,0,386641162,1119720706,1120321974,1119050649,1117695840,1117760337,1113256123,1114348353,1117757338]}
            for name in a.NAMES:
                elf=root/'inputs/elfs'/(name+'.elf');elf.parent.mkdir(parents=True,exist_ok=True);elf.write_bytes(toy_elf())
                old=dict(status='failure-retained' if name in a.RECOVER else 'empty' if name=='recursion' else 'complete',all_roi_count=0 if name=='recursion' else 1,trace_instructions=2,captured_outputs=values.get(name,[]))
                entry=dict(mode='recovered' if name in a.RECOVER else 'reused',family=a.FAMILIES[name],original_record=old,elf=rec(elf),upstream_directory='unused')
                programs[name]=entry;oldreport['records'][name]=copy.deepcopy(old)
                outcomes[name]=dict(mode=entry['mode'],family=entry['family'],original_record=copy.deepcopy(old),status='empty' if name=='recursion' else 'complete',candidate_count=0 if name=='recursion' else 1)
                if name in a.REUSE:
                    rows=[] if name=='recursion' else candidates
                    p=root/'inputs/reused'/name/'candidates.json';put(p,rows);entry['candidates']=rec(p);outcomes[name]['candidate_file']=rec(p);reuse_bytes[f'{name}/candidates-all-roi/{name}.json']=p.read_bytes()
                    p=p.with_name('trace-summary.json');put(p,dict(validated=True,unknown_instructions=0,trace_instructions=2,instret_start=10,instret_stop=13));entry['trace_summary']=rec(p);outcomes[name]['trace_summary']=rec(p)
                    p=p.with_name('fusion.json');put(p,dict(passed=True,seed=2026101507,benchmarks=[a.fusion(program,rows,name)]));entry['fusion']=rec(p);outcomes[name]['fusion']=rec(p)
            for name in ('preparation.json','plan.json','tools.json'):put(root/name,{})
            source_sha=a.sha(runner);claim=root/'recovery-claim.json'
            approval=dict(status='approved-v11b-input-only-recovery',preparation_sha256=a.sha(root/'preparation.json'),runner_sha256=source_sha,maximum_new_captures=2,maximum_labels=0,freeze_commit='a'*40,reviewed_at_utc='2026-10-16T00:00:00+00:00')
            put(root/'recovery-approval.json',approval)
            put(claim,dict(preparation_sha256=approval['preparation_sha256'],approval_sha256=a.sha(root/'recovery-approval.json'),runner_sha256=source_sha,maximum_new_captures=2,new_labels=0,claimed_at_utc='2026-10-16T00:00:01+00:00'))
            tools=dict(executables={'gzip':{'path':'/bin/gzip','sha256':'gzip'},'spike':{'path':'/bin/spike'}},environment={'LANG':'C'})
            for index,name in enumerate(a.RECOVER):
                base=repo/'generated/v11-spooled-recovery/attempt-0000'/name;minute=index*10
                stamp=lambda sec:f'2026-10-16T00:{minute:02d}:{sec:02d}+00:00'
                raw,decoded=window()
                for phase,file,lines in [('capture','raw-spike.log.gz',raw),('decode','decoded.jsonl.gz',decoded)]:
                    p=base/phase/file;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(gzip.compress(''.join(lines).encode()))
                rawpath=base/'capture/raw-spike.log.gz';decodedpath=base/'decode/decoded.jsonl.gz'
                capture=dict(schema='isaforge-v11-spooled-capture-v1',status='captured-not-validated',producer_returncode=0,compressor_returncode=0,primary_error=None,cleanup_errors=[],remaining_owned_children=[],compressor_sha256='gzip',compressor_command=['/bin/gzip','-1','-n','-c'],environment={'LANG':'C'},capture_and_drain_wall_seconds=1,raw_sha256=a.sha(rawpath),raw_bytes=rawpath.stat().st_size,
                             producer_command=['/bin/spike','--isa=rv32im_zicntr','-m16','--log-commits','--log=/dev/fd/4',str(root/'inputs/elfs'/(name+'.elf'))])
                put(base/'capture/capture.json',capture)
                put(base/'capture-worker.json',dict(schema='isaforge-v11b-capture-worker-v1',program=name,started_at_utc=stamp(2),completed_at_utc=stamp(3),runner_sha256=source_sha,claim_sha256=a.sha(claim),capture_sha256=a.sha(base/'capture/capture.json'),primary_error=None))
                (base/'capture/htif.stdout.log').write_text(json.dumps(dict(kind='external-output',upstream_status=0,values=values[name])))
                summary=a.replay_raw(raw,decoded)[0];summary.update(raw_sha256=a.sha(rawpath),decoded_sha256=a.sha(decodedpath),decoded_bytes=decodedpath.stat().st_size,parser_sha256=a.sha(repo/'src/tracing.py'),counter_source_sha256=a.sha(repo/'src/run_holdout_benchmarks.py'))
                put(base/'decode/decode.json',summary)
                folder=base/'extract';put(folder/'program.json',program);(folder/'disassembly.txt').write_text('00000100 <toy>:\n 100: 00108093 addi\n 104: 00208093 addi\n')
                put(folder/'candidates-all-roi'/f'{name}.json',candidates);put(folder/'fusion-all-roi.json',dict(passed=True,seed=2026101507,benchmarks=[a.fusion(program,candidates,name)]))
                oracle=a.validate_output(name,values[name],None);put(folder/'oracle.json',oracle)
                for opt in ('O0','O2'):put(root/'inputs/oracles'/name/(opt+'.json'),oracle)
                elf=folder/'programs'/(name+'.elf');elf.parent.mkdir();elf.write_bytes(toy_elf())
                extraction=dict(schema='isaforge-v11b-extraction-v1',program=name,candidate_count=1,candidate_sha256=a.sha(folder/'candidates-all-roi'/f'{name}.json'),fusion_sha256=a.sha(folder/'fusion-all-roi.json'),oracle_sha256=a.sha(folder/'oracle.json'),elf_sha256=a.sha(elf),decode_sha256=a.sha(base/'decode/decode.json'),program_sha256=a.sha(folder/'program.json'),disassembly_sha256=a.sha(folder/'disassembly.txt'),static_objdump_calls=3,maxSize=4,limit=None,fusion_vectors=16,fusion_seed=2026101507,complete=True)
                put(folder/'extraction.json',extraction)
                for phase,seconds in [('decode',(4,5)),('extract',(6,7))]:
                    (base/(phase+'-worker.log')).write_text('saved log')
                    row=dict(schema='isaforge-v11b-owned-worker-v1',program=name,phase=phase,complete=True,returncode=0,primary_error=None,cleanup_errors=[],remaining_owned_children=[],timeout_seconds=1800 if phase=='decode' else 300,elapsed_seconds=1,started_at_utc=stamp(seconds[0]),completed_at_utc=stamp(seconds[1]),runner_sha256=source_sha,claim_sha256=a.sha(claim),log_sha256=a.sha(base/(phase+'-worker.log')),command=['/venv/python',str(runner),'worker','--root',str(root),'--program',name,'--phase',phase,'--claim-sha256',a.sha(claim)])
                    put(base/(phase+'-worker.json'),row)
                outcomes[name].update(candidate_file=rec(folder/'candidates-all-roi'/f'{name}.json'),capture=rec(base/'capture/capture.json'),decode=rec(base/'decode/decode.json'),extraction=rec(folder/'extraction.json'),oracle=rec(folder/'oracle.json'),fusion=rec(folder/'fusion-all-roi.json'),trace_instructions=2)
            completed=[]
            for name,row in outcomes.items():
                for item in json.loads((root/row['candidate_file']['path']).read_text()):completed.append({**item,'benchmark':name,'family':a.FAMILIES[name]})
            put(stage/'programs.json',outcomes);put(stage/'completed-rows.json',completed)
            done=dict(schema='isaforge-v11b-recovery-completion-v1',complete=True,failures=[],preparation_sha256=a.sha(root/'preparation.json'),plan_sha256=a.sha(root/'plan.json'),tools_sha256=a.sha(root/'tools.json'),approval_sha256=a.sha(root/'recovery-approval.json'),claim_sha256=a.sha(claim),runner_sha256=source_sha,freeze_commit='a'*40,program_count=6,reused_program_count=4,recovery_program_count=2,capture_records=2,programs_sha256=a.sha(stage/'programs.json'),completed_rows_sha256=a.sha(stage/'completed-rows.json'),completed_program_formula_rows=len(completed),original_primary='undefined: empty recursion MAE; never zero',new_features=0,new_predictions=0,new_labels=0,new_fits=0,completed_at_utc='2026-10-16T00:11:00+00:00')
            def seal():
                put(stage/'completion.json',done);put(root/'completion.json',done)
                paths=sorted([p for p in repo.rglob('*') if p.is_file() and p.name not in ('metadata.zip','evidence-manifest.json')])
                records=[];members=[]
                with zipfile.ZipFile(stage/'metadata.zip','w') as z:
                    for p in paths:
                        r=dict(path=p.relative_to(repo).as_posix(),sha256=a.sha(p),bytes=p.stat().st_size,packaged='.gz' not in p.name);records.append(r)
                        if r['packaged']:z.write(p,r['path']);members.append({k:r[k] for k in ('path','sha256','bytes')})
                put(stage/'evidence-manifest.json',dict(schema='isaforge-v11b-recovery-evidence-v1',complete=True,completion_sha256=a.sha(stage/'completion.json'),compressed_payloads_duplicated=False,historical_archives_reused_by_reference=True,files=records,archive=dict(path='metadata.zip',sha256=a.sha(stage/'metadata.zip'),bytes=(stage/'metadata.zip').stat().st_size,members=members)))
            seal()
            data=dict(root=root,plan={'programs':programs},tools=tools,oldreport=oldreport,members={},old_member_count=229,preparation={'prepared_at_utc':'2026-10-15T23:59:00+00:00'})
            with patch.object(a,'ROOT',repo),patch.object(a,'inputs',return_value=data),patch.object(a,'archived',side_effect=lambda members,name:reuse_bytes[name]):
                result=a.run(root);self.assertEqual(result['program_formula_rows'],5);self.assertIsNone(result['original_primary'])
                # Reauthenticate every file after replacing decoded instructions.
                p=repo/'generated/v11-spooled-recovery/attempt-0000/pm/decode/decoded.jsonl.gz'
                lines=gzip.decompress(p.read_bytes()).decode().splitlines();poison=json.loads(lines[0]);poison['seq']-=1;lines[0]=json.dumps(poison);p.write_bytes(gzip.compress(('\n'.join(lines)+'\n').encode()));seal()
                with self.assertRaisesRegex(ValueError,'Decoded'):a.run(root)


if __name__ == '__main__': unittest.main()
