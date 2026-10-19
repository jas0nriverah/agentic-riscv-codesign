#!/usr/bin/env python3
"""Read-only, streaming V11b input recovery audit. No native execution or labels.

Raw commit parsing/counters, archive integrity and ELF bytes are replayed here.
RV32 instruction decoding, candidate extraction, software fusion execution and
program-specific output oracles are shared frozen helpers, explicitly disclosed.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
import gzip
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import random
import re
import struct
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'scripts'), str(ROOT)]
from tracing import decode
from candidates import extractCandidates, findBlocks
from verify_candidate_fusions import execute
from collect_v11_reserved import validate_output

NAMES = ('ammunition', 'audiobeam', 'pm', 'fmref', 'fac', 'recursion')
RECOVER = ('ammunition', 'pm')
REUSE = ('audiobeam', 'fmref', 'fac', 'recursion')
FAMILIES = dict(zip(NAMES, ('arbitrary-precision-bit-strings', 'audio-beamforming',
                          'numeric-template-matching', 'fm-reception', 'integer-recurrences', 'integer-recurrences')))
OLD = ROOT / 'results/2026-10-15-v11-reserved-transfer'
OLD_PLAN_SHA = '533fb31680e29cf3173c2bc93821a3a8d27063e96100ffd670a804be9a71d74c'
ENDPOINT_SHA = 'aef3c6952b399d98804f873d3d8514bf21c49715de074993c4914b57237976ad'
PROTOCOL_SHA = '72f5aa9053ebd6505243a67744cd36944c88114098e45aad4ee4c090c18c4c59'
OLD_REPORT_SHA = '1aa550c818ab07f65b5fc46c85a2ee658b03be8ad040af6714b8e8c9070c1dca'
OLD_RAW_SHA = '2639044e9019e49740da2746db8b8e19f69e83e137aa5a11310a453f0e5b400d'
COMMIT = re.compile(r'^core\s+\d+:\s+\d+\s+(0x[0-9a-f]+)\s+\((0x[0-9a-f]+)\)(.*)$', re.I)
WRITES = re.compile(r'\bx\s*(\d+)\s+(0x[0-9a-f]+)', re.I)


def need(ok, message):
    if not ok: raise ValueError(message)


def loads(data):
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, 'Duplicate JSON key')
            result[key] = value
        return result
    return json.loads(data, object_pairs_hook=pairs, parse_constant=lambda s: (_ for _ in ()).throw(ValueError(s)))


def read(path): return loads(Path(path).read_bytes())
def same(a, b): return json.dumps(a, sort_keys=True, allow_nan=False) == json.dumps(b, sort_keys=True, allow_nan=False)
def integer(x):
    need(type(x) is int and x >= 0, 'Nonnegative integer required')
    return x


def stream_hash(stream):
    h = hashlib.sha256(); size = 0
    for chunk in iter(lambda: stream.read(1024 * 1024), b''):
        h.update(chunk); size += len(chunk)
    return h.hexdigest(), size


def sha(path):
    with Path(path).open('rb') as stream: return stream_hash(stream)[0]


def local(path, base=None):
    if base is None: base = ROOT
    p = PurePosixPath(path)
    need(not p.is_absolute() and '..' not in p.parts and str(p) == path, 'Unsafe relative evidence path')
    result = base / path
    need(result.resolve().is_relative_to(base.resolve()) and not result.is_symlink(), 'Evidence escapes root')
    return result


def verify_record(record, base=None):
    path = local(record['path'], base)
    need(path.is_file() and sha(path) == record['sha256'], 'File hash mismatch: ' + str(path))
    if 'bytes' in record: need(path.stat().st_size == integer(record['bytes']), 'File size mismatch')
    return path


def verify_zip(path, members):
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        need(len(names) == len(set(names)) == len(members), 'ZIP duplicate/member count mismatch')
        expected = {m['path']: m for m in members}
        need(set(names) == set(expected), 'ZIP membership mismatch')
        for name in names:
            p = PurePosixPath(name)
            need(not p.is_absolute() and '..' not in p.parts, 'Unsafe ZIP member')
            with archive.open(name) as stream: digest, size = stream_hash(stream)
            need(digest == expected[name]['sha256'] and size == integer(expected[name]['bytes']), 'ZIP member mismatch: ' + name)
    return len(names)


def replay_raw(raw, decoded, instruction_words=None):
    """Both streams are strict text iterables; compare one decoded row at a time.

    Consume raw data after the stop marker too: bad trailing records, extra markers,
    truncation and gzip CRC failures cannot hide behind an apparently valid ROI.
    """
    readings = []; runs = Counter(); starts = set(); previous = None; count = 0
    decoded = iter(decoded)
    for seq, line in enumerate(raw):
        match = COMMIT.match(line)
        if not match:
            need(not line.startswith('core'), 'Malformed core record')
            continue
        pc, word = int(match[1], 16), int(match[2], 16)
        need(0 <= word < 2 ** 32, 'Non-RV32 word')
        if word & 0xFFFFF07F == 0xC0202073:
            rd = (word >> 7) & 31
            writes = {int(r): int(v, 16) for r, v in WRITES.findall(match[3])}
            need(rd in writes and 0 <= writes[rd] < 2 ** 32, 'Missing/invalid instret reading')
            readings.append(writes[rd]); need(len(readings) <= 2, 'Extra instret marker')
        elif len(readings) == 1:
            op, rd, rs1, rs2, imm = decode(word)
            need(op != 'unknown', 'Unknown measured instruction')
            if instruction_words is not None: need(instruction_words.get(pc) == word, 'Raw commit differs from original ELF')
            expected = dict(pc=match[1], raw=f'0x{word:08x}', op=op, rd=rd, rs1=rs1, rs2=rs2, imm=imm, seq=seq)
            line = next(decoded, None); need(line is not None, 'Missing decoded record')
            actual = loads(line); need(actual == expected and all(type(actual[k]) is type(v) for k, v in expected.items()), 'Decoded row differs from raw commit')
            runs[pc] += 1
            if previous is None or pc != previous + 4: starts.add(pc)
            previous = pc; count += 1
    need(next(decoded, None) is None, 'Extra decoded record')
    need(len(readings) == 2, 'Incomplete instret window')
    delta = (readings[1] - readings[0]) & 0xffffffff
    need(delta == count + 1, 'Instret/commit count mismatch')
    if previous is not None: starts.add(previous + 4)
    return dict(instret_start=readings[0], instret_stop=readings[1], instret_delta=delta,
                trace_instructions=count, unknown_instructions=0, validated=True,
                pc_counts=[[pc, n] for pc, n in sorted(runs.items())], block_starts=sorted(starts)), runs, starts


def replay_gzip(raw, decoded, instruction_words=None):
    with gzip.open(raw, 'rt', encoding='utf-8', errors='strict') as a, gzip.open(decoded, 'rt', encoding='utf-8', errors='strict') as b:
        return replay_raw(a, b, instruction_words)


def htif(text, expected):
    rows = [loads(line) for line in text.splitlines() if line.startswith('{')]
    need(len(rows) == 1 and rows[0].get('kind') == 'external-output', 'Exactly one HTIF output required')
    need(type(rows[0].get('upstream_status')) is int and rows[0]['upstream_status'] == 0, 'Upstream failure')
    values = rows[0].get('values')
    need(isinstance(values, list) and all(type(x) is int and -(2**31) <= x < 2**31 for x in values), 'Signed RV32 snapshot required')
    need(same(values, expected), 'O0/O2/trace snapshot mismatch')
    return values


def elf_program(data, include_words=False, include_aliases=False):
    """Independent ELF32/little-endian executable word and symbol reader.

    No disassembler subprocess. Reject compressed/unaligned executable sections.
    The supported files are fixed RV32IM ELF bytes, not a generic ELF loader.
    """
    need(data[:7] == b'\x7fELF\x01\x01\x01' and len(data) >= 52, 'ELF32 little-endian required')
    header = struct.unpack_from('<16sHHIIIIIHHHHHH', data)
    need(header[2] == 243 and header[11] == 40 and header[12] > 0, 'RV32 section table required')
    shoff, count, strindex = header[6], header[12], header[13]
    need(shoff + count * 40 <= len(data) and strindex < count, 'ELF section table bounds')
    sections = [struct.unpack_from('<IIIIIIIIII', data, shoff + i * 40) for i in range(count)]
    def chunk(section):
        off, size = section[4:6]; need(off + size <= len(data), 'ELF section bounds')
        return data[off:off + size]
    symbols = {}
    for section in sections:
        if section[1] != 2: continue
        need(section[9] == 16 and section[6] < count, 'ELF symbol table shape')
        strings = chunk(sections[section[6]]); table = chunk(section)
        need(len(table) % 16 == 0, 'Truncated symbol table')
        for off in range(0, len(table), 16):
            name, value, size, info, other, index = struct.unpack_from('<IIIBBH', table, off)
            if index == 0 or index >= count or not (sections[index][2] & 4) or not name: continue
            need(name < len(strings), 'ELF symbol name bound')
            stop = strings.find(b'\0', name); need(stop >= 0, 'ELF symbol terminator')
            text = strings[name:stop].decode('utf-8', errors='strict')
            # File/section/debug labels are not objdump instruction headings.
            if info & 15 in (3, 4) or text.startswith('$'): continue
            symbols.setdefault(value, []).append((info & 15 == 2, info >> 4 != 0, text))
    program = {}; words = {}; aliases = {}
    for section in sections:
        if not section[2] & 4 or section[1] == 8: continue
        payload = chunk(section); need(section[3] % 4 == 0 and len(payload) % 4 == 0, 'Non-RV32 executable alignment')
        symbol = None; allowed = {None}
        for off in range(0, len(payload), 4):
            pc = section[3] + off
            if pc in symbols:
                symbol = sorted(symbols[pc], reverse=True)[0][2]; allowed = {x[2] for x in symbols[pc]}
            aliases[pc] = set(allowed)
            word = struct.unpack_from('<I', payload, off)[0]; words[pc] = word
            op, rd, rs1, rs2, imm = decode(word)
            need(pc not in program, 'Overlapping executable sections')
            program[pc] = dict(op=op, rd=rd, rs1=rs1, rs2=rs2, imm=imm, symbol=symbol)
    need(program, 'No executable RV32 instructions')
    if include_aliases: return program, words, aliases, {pc: {x[2] for x in values} for pc, values in symbols.items()}
    return (program, words) if include_words else program


def parse_disassembly(text, elf):
    words, instruction_words, aliases, headings = elf_program(elf, include_aliases=True); result = {}; symbol = None
    for line in text.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1].startswith('<') and parts[1].endswith('>:'):
            symbol = parts[1][1:-2]
            need(symbol in headings.get(int(parts[0], 16), set()), 'Disassembly heading is not an ELF symbol at this address')
        if len(parts) >= 2 and parts[0].endswith(':') and len(parts[1]) == 8:
            pc, word = int(parts[0][:-1], 16), int(parts[1], 16)
            need(pc in words and pc not in result and instruction_words[pc] == word, 'Static disassembly PC/word invalid/duplicated')
            op, rd, rs1, rs2, imm = decode(word)
            row = dict(op=op, rd=rd, rs1=rs1, rs2=rs2, imm=imm, symbol=symbol)
            need(all(row[k] == words[pc][k] for k in ('op', 'rd', 'rs1', 'rs2', 'imm')), 'Disassembly differs from ELF instructions')
            need(symbol in aliases[pc], 'Disassembly symbol differs from ELF aliases')
            result[pc] = row
    need(set(result) == set(words), 'Disassembly omits executable instructions')
    return result


def fusion(program, rows, name):
    """Independent occurrence/schedule reconstruction, shared frozen execute()."""
    rng = random.Random(2026101507)
    starts = {int(o['blockStart'], 16) for row in rows for o in row['occurrences']}
    blocks = {b[0]: b for b in findBlocks(program, starts)}; groups = {}
    for row in rows:
        for occurrence in row['occurrences']:
            start = int(occurrence['blockStart'], 16); block = blocks[start]
            members = {block.index(int(pc, 16)) for pc in occurrence['pcs']}
            groups.setdefault(start, []).append(dict(formula=row['formula'], members=members, selected=occurrence['selectedForSavings']))
    checked = comparisons = joint = 0
    for start, occurrences in groups.items():
        block = blocks[start]
        need(all(program[pc]['op'] != 'unknown' for pc in block), 'Opaque fusion occurrence')
        states = [{reg: rng.getrandbits(32) if reg else 0 for reg in range(32)} for _ in range(16)]
        expected = [execute(block, program, state.copy(), []) for state in states]
        for occurrence in occurrences:
            for state, baseline in zip(states, expected):
                need(execute(block, program, state.copy(), [occurrence]) == baseline, 'Individual fusion mismatch')
                comparisons += 1
            checked += 1
        by_formula = {}
        for occurrence in occurrences:
            if occurrence['selected']: by_formula.setdefault(occurrence['formula'], []).append(occurrence)
        for replacements in by_formula.values():
            for state, baseline in zip(states, expected):
                need(execute(block, program, state.copy(), replacements) == baseline, 'Joint fusion mismatch')
                joint += 1
    return dict(benchmark=name, checked_occurrences=checked, skipped_opaque_block_occurrences=0,
                vectors_per_occurrence=16, individual_comparisons=comparisons, joint_formula_block_comparisons=joint)


def extraction(program, runs, starts, rows, name, saved_fusion):
    starts = set(starts); previous = None
    for pc in sorted(program):
        symbol = program[pc]['symbol']
        if symbol != previous: starts.add(pc)
        previous = symbol
    expected = extractCandidates(program, runs, starts, maxSize=4, limit=None)
    need(same(rows, expected), 'Complete static candidate/occurrence extraction differs')
    result = fusion(program, rows, name)
    need(saved_fusion.get('passed') is True and saved_fusion.get('seed') == 2026101507 and
         same(saved_fusion.get('benchmarks'), [result]), 'Saved fusion result differs')
    return result


def historical():
    need(sha(OLD / 'input-plan.json') == OLD_PLAN_SHA and sha(OLD / 'input-report.json') == OLD_REPORT_SHA and sha(OLD / 'raw-evidence-manifest.json') == OLD_RAW_SHA, 'Historical V11 anchor changed')
    plan, report, manifest = read(OLD / 'input-plan.json'), read(OLD / 'input-report.json'), read(OLD / 'raw-evidence-manifest.json')
    need(tuple(plan['programs']) == tuple(report['records']) == NAMES and len(manifest['archives']) == 7, 'Original six/seven inventory required')
    members = {}; count = 0
    for archive in manifest['archives']:
        path = verify_record(archive, OLD); count += verify_zip(path, archive['members'])
        for m in archive['members']:
            need(m['path'] not in members, 'Historical member repeated')
            members[m['path']] = (path, m)
    need(count == 229, 'Historical complete archive inventory required')
    for name in NAMES:
        r = report['records'][name]
        need(r['family'] == FAMILIES[name] and r['status'] == ('failure-retained' if name in RECOVER else 'empty' if name == 'recursion' else 'complete'), 'Original outcome changed')
        need(r['O0_O2_snapshot_bitexact'] is True and members[f'{name}/O2/{name}.elf'][1]['sha256'] == r['O2_build']['elf_sha256'], 'Historical ELF/selfcheck identity changed')
    need(report['records']['recursion']['all_roi_count'] == 0 and report['records']['recursion']['trace_instructions'] == 1181, 'Empty recursion must remain visible')
    return plan, report, members, count


def archived(members, name):
    path, _ = members[name]
    with zipfile.ZipFile(path) as archive: return archive.read(name)


def relative_record(record, base):
    """Preparation records deliberately refer to other repository directories."""
    need(type(record['path']) is str and not Path(record['path']).is_absolute(), 'Relative repository record required')
    path = (base / record['path']).resolve()
    need(path.is_relative_to(ROOT) and path.is_file() and not (base / record['path']).is_symlink(), 'Record escapes repository')
    need(sha(path) == record['sha256'] and path.stat().st_size == integer(record['bytes']), 'Bound record changed: ' + record['path'])
    return path


def expected_policy():
    gib = 1024 ** 3
    return dict(workers=1, capture_seconds=300, compressor_drain_seconds=30, offline_seconds=1800,
                cleanup_seconds_per_child=5, poll_seconds=.25, startup_free_bytes=26*gib,
                later_program_startup_free_bytes=18*gib, minimum_free_bytes=8*gib,
                raw_gzip_bytes_per_program=4*gib, decoded_gzip_bytes_per_program=4*gib,
                attempt_bytes=18*gib, metadata_log_bytes_per_file=16*1024**2, retries=0,
                extraction_seconds=300, maxSize=4, limit=None, fusion_vectors=16, fusion_seed=2026101507,
                metadata_archive_bytes=2*gib, static_objdump_calls_per_recovered_program=3,
                recover=list(RECOVER), reuse=list(REUSE), programs=list(NAMES),
                new_features=0, new_predictions=0, new_labels=0, new_fits=0)


def inputs(root):
    root = Path(root).resolve(); need(root.is_relative_to(ROOT / 'results'), 'Repository result root required')
    prep = read(root / 'preparation.json'); plan = read(root / 'plan.json'); tools = read(root / 'tools.json')
    need(prep['schema'] == 'isaforge-v11b-recovery-preparation-v1' and prep['status'] == 'prepared-inputs-only' and not (root / 'preparation-failure.json').exists(), 'Successful input preparation required')
    need(plan['schema'] == 'isaforge-v11b-recovery-plan-v1' and same(prep['policy'], expected_policy()) and same(plan['policy'], expected_policy()), 'Exact fixed recovery policy required')
    for key in ('native_trace_jobs', 'feature_jobs', 'predictions', 'labels', 'fits'): need(type(prep[key]) is int and prep[key] == 0, 'Preparation must be input-only')
    need(plan['features_predictions_labels_fits_released'] is False and plan['original_primary'] == 'undefined: empty recursion MAE; never zero', 'Original primary/release scope changed')
    bindings = {}
    for record in prep['files']:
        path = relative_record(record, root); need(path not in bindings, 'Duplicate preparation binding')
        bindings[path] = record['sha256']
    oldplan, oldreport, members, old_member_count = historical()
    mandatory = {ROOT / p for p in oldplan['runtime_source_sha256']}
    mandatory.update(ROOT / x['path'] for x in read(OLD / 'input-provenance-amendment.json')['added_runtime_sources'])
    mandatory.update(ROOT / p for p in ('scripts/recover_v11_transfer.py', 'tests/test_recover_v11_transfer.py',
                     'scripts/capture_v11_spooled.py', 'tests/test_capture_v11_spooled.py',
                     'scripts/audit_v11_recovery.py', 'tests/test_audit_v11_recovery.py', 'docs/v11-transfer-recovery-plan.md'))
    mandatory.update({root / 'endpoint-adoption.json', ROOT / 'docs/v11b-transfer-protocol.md'})
    need(sha(root / 'endpoint-adoption.json') == ENDPOINT_SHA and sha(ROOT / 'docs/v11b-transfer-protocol.md') == PROTOCOL_SHA, 'Endpoint adoption/protocol changed')
    need(same(plan['endpoint_adoption'], dict(path='endpoint-adoption.json', sha256=ENDPOINT_SHA, bytes=(root / 'endpoint-adoption.json').stat().st_size)), 'Plan adoption binding changed')
    mandatory.update({root / 'plan.json', root / 'tools.json', OLD / 'input-plan.json', OLD / 'input-report.json', OLD / 'raw-evidence-manifest.json'})
    mandatory.update(path for path, row in members.values())
    partials = set()
    for record in read(OLD / 'raw-evidence-manifest.json')['omitted_local_failed_partials']:
        path = ROOT / 'generated/v11-reserved-inputs/attempt-0000' / record['path']; partials.add(path); mandatory.add(path)
        need(path in bindings and bindings[path] == record['sha256'] and path.stat().st_size == record['bytes'], 'Original failed partial binding changed')
    need(len(partials) == 2 and mandatory <= set(bindings), 'Missing required source/historical input binding')
    for record in prep['files']:
        path = (root / record['path']).resolve()
        need(type(record['git_required']) is bool and record['git_required'] is (path not in partials), 'Only two declared failed partials may be local-only')
    need(tuple(plan['programs']) == NAMES and plan['upstream_commit'] == oldplan['upstream_commit'] and plan['reservation_commit'] == oldplan['reservation_commit'], 'Fixed reserved source panel changed')
    need(tools['schema'] == 'isaforge-v11b-recovery-tools-v1', 'Tool inventory schema')
    for name in ('cc', 'objdump', 'spike'):
        need(tools['executables'][name]['sha256'] == oldplan['tools'][name]['sha256'] and tools['executables'][name]['path'] == oldplan['tools'][name]['path'], 'Original native tool identity changed')
    prepared_inputs = set()
    for name in NAMES:
        entry = plan['programs'][name]; original = oldreport['records'][name]
        need(same(entry['original_record'], original) and entry['family'] == FAMILIES[name] and entry['mode'] == ('recovered' if name in RECOVER else 'reused') and entry['upstream_directory'] == oldplan['programs'][name]['directory'], 'Prepared original program changed')
        elf = relative_record(entry['elf'], root); prepared_inputs.add(elf)
        need(elf == root / 'inputs/elfs' / (name + '.elf') and sha(elf) == original['O2_build']['elf_sha256'], 'Exact original O2 ELF required')
        for opt in ('O0', 'O2'):
            p = root / 'inputs/oracles' / name / (opt + '.json'); prepared_inputs.add(p)
            need(sha(p) == members[f'{name}/{opt}-oracle.json'][1]['sha256'], 'Original oracle changed')
        if name in REUSE:
            for file, source in [('candidates', f'{name}/candidates-all-roi/{name}.json'), ('trace_summary', f'{name}/{name}.jsonl.summary.json'), ('fusion', f'{name}/fusion-all-roi.json')]:
                p = relative_record(entry[file], root); prepared_inputs.add(p)
                need(sha(p) == members[source][1]['sha256'], 'Reused outcome bytes changed')
        for p, h in oldplan['programs'][name]['files'].items():
            q = root / 'inputs/upstream' / p; prepared_inputs.add(q)
            need(sha(q) == h and h == members['upstream/' + p][1]['sha256'], 'Reserved source snapshot changed')
    need(prepared_inputs == {p for p in (root / 'inputs').rglob('*') if p.is_file()} and prepared_inputs <= set(bindings), 'Prepared input inventory mismatch')
    return dict(root=root, preparation=prep, plan=plan, tools=tools, oldplan=oldplan, oldreport=oldreport, members=members,
                old_member_count=old_member_count, bindings=bindings)


def audit_inputs(root):
    data = inputs(root)
    return dict(schema='isaforge-v11b-independent-input-audit-v1', status='pass', preparation_sha256=sha(data['root'] / 'preparation.json'),
                audited_at_utc=datetime.now(timezone.utc).isoformat(), source_sha256=sha(__file__), programs=6, exact_reused_outcomes=4,
                recovered_programs_pending=2, historical_archive_members=data['old_member_count'], bound_files=len(data['bindings']),
                original_primary=None, original_primary_reason='Empty recursion formula MAE is undefined; original primary cannot be repaired by recovery.',
                new_native_jobs=0, new_labels=0, new_fits=0)


def timestamp(value):
    result = datetime.fromisoformat(value)
    need(result.tzinfo is not None and result.utcoffset().total_seconds() == 0, 'UTC timestamp required')
    return result


def verify_worker(row, name, phase, base, root, claim_sha):
    timeout = 1800 if phase == 'decode' else 300
    need(row['schema'] == 'isaforge-v11b-owned-worker-v1' and row['program'] == name and row['phase'] == phase, 'Wrong owned worker')
    need(row['complete'] is True and type(row['returncode']) is int and row['returncode'] == 0 and row['primary_error'] is None and row['cleanup_errors'] == [] and row['remaining_owned_children'] == [], 'Failed/incomplete owned worker')
    need(row['timeout_seconds'] == timeout and type(row['timeout_seconds']) is int and 0 <= row['elapsed_seconds'] <= timeout + 11, 'Worker budget mismatch')
    start, end = timestamp(row['started_at_utc']), timestamp(row['completed_at_utc']); need(start <= end, 'Worker chronology reversed')
    need(row['runner_sha256'] == sha(ROOT / 'scripts/recover_v11_transfer.py') and row['claim_sha256'] == claim_sha and row['log_sha256'] == sha(base / (phase + '-worker.log')), 'Worker source/claim/log mismatch')
    command = row['command']; need(isinstance(command, list) and len(command) == 11 and Path(command[1]).is_absolute() and Path(command[1]).parts[-2:] == ('scripts', 'recover_v11_transfer.py'), 'Owned worker command changed')
    origin = Path(command[1]).parents[1]
    need(command[2:] == ['worker', '--root', str(origin / root.relative_to(ROOT)), '--program', name, '--phase', phase, '--claim-sha256', claim_sha], 'Owned worker command identity changed')
    return start, end


def verify_capture(capture, tools, elf_record, root):
    need(capture['schema'] == 'isaforge-v11-spooled-capture-v1' and capture['status'] == 'captured-not-validated', 'Capture is not complete')
    need(all(type(capture[k]) is int and capture[k] == 0 for k in ('producer_returncode', 'compressor_returncode')) and capture['primary_error'] is None and capture['cleanup_errors'] == [] and capture['remaining_owned_children'] == [], 'Capture/cleanup failed')
    need(capture['compressor_sha256'] == tools['executables']['gzip']['sha256'] and capture['compressor_command'] == [tools['executables']['gzip']['path'], '-1', '-n', '-c'] and same(capture['environment'], tools['environment']), 'Compressor/environment contract changed')
    command = capture['producer_command']
    need(len(command) == 6 and command[:4] == [tools['executables']['spike']['path'], '--isa=rv32im_zicntr', '-m16', '--log-commits'] and re.fullmatch(r'--log=/dev/fd/[0-9]+', command[4]) is not None, 'Spike capture command changed')
    elf_tail = root.relative_to(ROOT) / elf_record['path']
    need(Path(command[5]).is_absolute() and str(command[5]).endswith('/' + elf_tail.as_posix()), 'Captured ELF identity changed')
    need(0 <= capture['capture_and_drain_wall_seconds'] <= 341, 'Capture/drain/cleanup envelope exceeded')


def verify_capture_worker(row, name, capture_path, runner_sha, claim_sha):
    need(row['schema'] == 'isaforge-v11b-capture-worker-v1' and row['program'] == name and row['runner_sha256'] == runner_sha and row['claim_sha256'] == claim_sha and row['capture_sha256'] == sha(capture_path) and row['primary_error'] is None, 'Capture wrapper identity/failure mismatch')
    start, end = timestamp(row['started_at_utc']), timestamp(row['completed_at_utc'])
    need(start <= end and (end - start).total_seconds() <= 341, 'Capture wrapper chronology/budget mismatch')
    return start, end


def verify_outcomes(records, plan):
    need(tuple(records) == NAMES, 'All six outcomes must be retained in original order')
    for name in NAMES:
        row, entry = records[name], plan['programs'][name]
        need(row['mode'] == entry['mode'] and row['family'] == FAMILIES[name] and same(row['original_record'], entry['original_record']), 'Program outcome provenance differs')
        need(row['status'] in ('complete', 'empty'), 'Partial/failed program cannot supply a pool')
        n = integer(row['candidate_count']); need((row['status'] == 'empty') == (n == 0), 'Empty is distinct from failed or nonempty')
        if name in REUSE:
            need(row['status'] == entry['original_record']['status'] and n == entry['original_record']['all_roi_count'], 'Reused outcome changed')
            need(same(row['candidate_file'], entry['candidates']) and same(row['trace_summary'], entry['trace_summary']) and same(row['fusion'], entry['fusion']), 'Reused evidence reference changed')
    need(records['recursion']['status'] == 'empty' and records['recursion']['candidate_count'] == 0, 'Recursion cannot be filled or dropped')


def verify_package(root, done):
    stage = root / 'run/attempt-0000'; manifest = read(stage / 'evidence-manifest.json')
    need(manifest['schema'] == 'isaforge-v11b-recovery-evidence-v1' and manifest['complete'] is True and manifest['completion_sha256'] == sha(stage / 'completion.json'), 'Complete evidence manifest required')
    need(manifest['compressed_payloads_duplicated'] is False and manifest['historical_archives_reused_by_reference'] is True, 'Payload preservation policy changed')
    files = {}
    for record in manifest['files']:
        path = verify_record(record); need(path not in files, 'Duplicate evidence record')
        need(record['packaged'] is ('.gz' not in path.name), 'Payload packaging flag wrong')
        files[path] = record
    archive = manifest['archive']; archive_path = verify_record(archive, stage)
    verify_zip(archive_path, archive['members'])
    expected_members = [{k: r[k] for k in ('path', 'sha256', 'bytes')} for r in files.values() if r['packaged']]
    need(same(sorted(archive['members'], key=lambda x: x['path']), sorted(expected_members, key=lambda x: x['path'])), 'Metadata ZIP/ledger disagreement')
    need(not any('.gz' in PurePosixPath(r['path']).name for r in archive['members']), 'Large gzip duplicated inside metadata ZIP')
    attempt = ROOT / 'generated/v11-spooled-recovery/attempt-0000'
    payload = {attempt / n / phase / file for n in RECOVER for phase, file in (('capture', 'raw-spike.log.gz'), ('decode', 'decoded.jsonl.gz'))}
    need({p for p, r in files.items() if not r['packaged']} == payload, 'Exact four authoritative gzip payloads required')
    actual = {p for p in attempt.rglob('*') if p.is_file()}
    need(actual <= set(files) and not any(p.name.endswith('.partial') for p in actual), 'Missing or partial owned evidence')
    owned = actual | {p for p in root.rglob('*') if p.is_file()}
    need(sum(p.stat().st_size for p in owned) <= 18 * 1024**3, 'Whole-attempt byte cap exceeded including root metadata')
    for p in owned:
        need(not p.is_symlink(), 'Owned evidence symlink')
        if p in payload: need(p.stat().st_size <= 4 * 1024**3, 'Gzip payload cap exceeded')
        elif p.name == 'metadata.zip': need(p.stat().st_size <= 2 * 1024**3, 'Metadata archive cap exceeded')
        else: need(p.stat().st_size <= 16 * 1024**2, 'Metadata file cap exceeded')
    mandatory = {root / n for n in ('preparation.json', 'plan.json', 'tools.json', 'recovery-approval.json', 'recovery-claim.json')}
    mandatory |= {stage / n for n in ('programs.json', 'completed-rows.json', 'completion.json')}
    need(mandatory <= set(files), 'Missing package control evidence')
    return manifest, files


def run(root):
    data = inputs(root); root = data['root']; plan = data['plan']; tools = data['tools']; oldreport = data['oldreport']
    stage = root / 'run/attempt-0000'; done = read(root / 'completion.json')
    need(done['schema'] == 'isaforge-v11b-recovery-completion-v1' and done['complete'] is True and done['failures'] == [], 'Incomplete attempt cannot pass full input audit')
    need(same(done, read(stage / 'completion.json')), 'Root/stage completion mismatch')
    expected = dict(preparation_sha256=sha(root / 'preparation.json'), plan_sha256=sha(root / 'plan.json'), tools_sha256=sha(root / 'tools.json'),
                    approval_sha256=sha(root / 'recovery-approval.json'), claim_sha256=sha(root / 'recovery-claim.json'), runner_sha256=sha(ROOT / 'scripts/recover_v11_transfer.py'),
                    program_count=6, reused_program_count=4, recovery_program_count=2, capture_records=2,
                    programs_sha256=sha(stage / 'programs.json'), completed_rows_sha256=sha(stage / 'completed-rows.json'),
                    original_primary='undefined: empty recursion MAE; never zero', new_features=0, new_predictions=0, new_labels=0, new_fits=0)
    need(all(k in done and same(done[k], v) for k, v in expected.items()), 'Completion identity/count/scope mismatch')
    approval = read(root / 'recovery-approval.json'); claim = read(root / 'recovery-claim.json')
    need(approval['status'] == 'approved-v11b-input-only-recovery' and approval['preparation_sha256'] == expected['preparation_sha256'] and approval['runner_sha256'] == expected['runner_sha256'] and approval['maximum_new_captures'] == 2 and approval['maximum_labels'] == 0 and done['freeze_commit'] == approval['freeze_commit'], 'Approval release identity changed')
    need(claim['preparation_sha256'] == expected['preparation_sha256'] and claim['approval_sha256'] == expected['approval_sha256'] and claim['runner_sha256'] == expected['runner_sha256'] and claim['maximum_new_captures'] == 2 and claim['new_labels'] == 0, 'Single capture claim identity changed')
    need(timestamp(data['preparation']['prepared_at_utc']) <= timestamp(approval['reviewed_at_utc']) <= timestamp(claim['claimed_at_utc']) <= timestamp(done['completed_at_utc']), 'Preparation/release/claim chronology changed')
    manifest, files = verify_package(root, done)
    records = read(stage / 'programs.json'); verify_outcomes(records, plan)
    completed = []; reviews = {}; previous_end = timestamp(claim['claimed_at_utc'])
    for name in NAMES:
        row = records[name]; entry = plan['programs'][name]
        candidates = relative_record(row['candidate_file'], root); rows = read(candidates)
        need(isinstance(rows, list) and len(rows) == row['candidate_count'] and len({r['formula'] for r in rows}) == len(rows), 'Canonical candidate membership/count mismatch')
        if name in REUSE:
            # Original full traces are authenticated by all original ZIP member hashes.
            # They are not presented as newly captured or independently raw-replayed.
            need(candidates.read_bytes() == archived(data['members'], f'{name}/candidates-all-roi/{name}.json'), 'Reused candidates differ')
            summary = read(relative_record(row['trace_summary'], root)); saved_fusion = read(relative_record(row['fusion'], root))
            need(summary['validated'] is True and summary['unknown_instructions'] == 0 and summary['trace_instructions'] == oldreport['records'][name]['trace_instructions'] and (summary['instret_stop'] - summary['instret_start']) & 0xffffffff == summary['trace_instructions'] + 1, 'Reused full-window identity invalid')
            need(saved_fusion['passed'] is True and saved_fusion['seed'] == 2026101507 and len(saved_fusion['benchmarks']) == 1 and saved_fusion['benchmarks'][0]['skipped_opaque_block_occurrences'] == 0, 'Original fusion validation absent')
            reviews[name] = dict(mode='exact-historical-reuse', status=row['status'], candidate_count=len(rows), trace_instructions=summary['trace_instructions'])
        else:
            base = ROOT / 'generated/v11-spooled-recovery/attempt-0000' / name
            capture_path = relative_record(row['capture'], root); capture = read(capture_path)
            need(capture_path == base / 'capture/capture.json', 'Capture reference changed')
            verify_capture(capture, tools, entry['elf'], root)
            raw, decoded_path = base / 'capture/raw-spike.log.gz', base / 'decode/decoded.jsonl.gz'
            need(sha(raw) == capture['raw_sha256'] and integer(capture['raw_bytes']) == raw.stat().st_size, 'Captured raw identity mismatch')
            saved_decode = read(relative_record(row['decode'], root))
            elf_path = relative_record(entry['elf'], root); program, words = elf_program(elf_path.read_bytes(), include_words=True)
            actual_decode, runs, starts = replay_gzip(raw, decoded_path, words)
            need(all(k in saved_decode and same(v, saved_decode[k]) for k, v in actual_decode.items()), 'Decoded summary/counters differ')
            need(saved_decode['raw_sha256'] == sha(raw) and saved_decode['decoded_sha256'] == sha(decoded_path) and saved_decode['decoded_bytes'] == decoded_path.stat().st_size and saved_decode['parser_sha256'] == sha(ROOT / 'src/tracing.py') and saved_decode['counter_source_sha256'] == sha(ROOT / 'src/run_holdout_benchmarks.py'), 'Decoder provenance differs')
            values = htif((base / 'capture/htif.stdout.log').read_text(), oldreport['records'][name]['captured_outputs'])
            oracle = validate_output(name, values, root / 'inputs/upstream' / entry['upstream_directory'])
            need(same(oracle, read(relative_record(row['oracle'], root))), 'Output oracle differs')
            for opt in ('O0', 'O2'): need(same(oracle, read(root / 'inputs/oracles' / name / (opt + '.json'))), 'Original snapshot/oracle differs')
            static = parse_disassembly((base / 'extract/disassembly.txt').read_text(), elf_path.read_bytes())
            program = static
            need(same({str(k): v for k, v in program.items()}, read(base / 'extract/program.json')), 'Native parsed program differs from ELF/disassembly')
            f = extraction(program, runs, starts, rows, name, read(relative_record(row['fusion'], root)))
            x = read(relative_record(row['extraction'], root))
            fields = dict(schema='isaforge-v11b-extraction-v1', program=name, candidate_count=len(rows), candidate_sha256=sha(candidates),
                          fusion_sha256=sha(base / 'extract/fusion-all-roi.json'), oracle_sha256=sha(base / 'extract/oracle.json'), elf_sha256=sha(elf_path),
                          decode_sha256=sha(base / 'decode/decode.json'), program_sha256=sha(base / 'extract/program.json'),
                          disassembly_sha256=sha(base / 'extract/disassembly.txt'), static_objdump_calls=3, maxSize=4, limit=None, fusion_vectors=16, fusion_seed=2026101507, complete=True)
            need(all(k in x and same(x[k], v) for k, v in fields.items()), 'Extraction manifest differs')
            need(sha(base / 'extract/programs' / (name + '.elf')) == entry['elf']['sha256'], 'Fusion ELF differs')
            first, end = verify_worker(read(base / 'decode-worker.json'), name, 'decode', base, root, expected['claim_sha256'])
            second, finish = verify_worker(read(base / 'extract-worker.json'), name, 'extract', base, root, expected['claim_sha256'])
            capture_start, capture_end = verify_capture_worker(read(base / 'capture-worker.json'), name, capture_path, expected['runner_sha256'], expected['claim_sha256'])
            need(previous_end <= capture_start <= capture_end <= first <= end <= second <= finish <= timestamp(done['completed_at_utc']), 'Sequential recovery stage order changed')
            previous_end = finish
            need(row['trace_instructions'] == actual_decode['trace_instructions'], 'Program window count differs')
            reviews[name] = dict(mode='recovered-raw-stream-replayed', status=row['status'], candidate_count=len(rows), trace_instructions=actual_decode['trace_instructions'], fusion=f)
        completed.extend({**r, 'benchmark': name, 'family': FAMILIES[name]} for r in rows)
    need(same(completed, read(stage / 'completed-rows.json')) and len(completed) == integer(done['completed_program_formula_rows']), 'Complete pool membership differs')
    return dict(schema='isaforge-v11b-independent-recovery-audit-v1', status='pass', complete=True,
                audited_at_utc=datetime.now(timezone.utc).isoformat(), source_sha256=sha(__file__), preparation_sha256=expected['preparation_sha256'], completion_sha256=sha(root / 'completion.json'),
                evidence_manifest_sha256=sha(stage / 'evidence-manifest.json'), programs=reviews, program_count=6, reused_program_count=4, recovered_program_count=2,
                program_formula_rows=len(completed), unique_canonical_formulas=len({r['formula'] for r in completed}), historical_archive_members=data['old_member_count'], evidence_files=len(files),
                original_primary=None, original_primary_reason='Empty recursion formula MAE remains undefined; recovery does not redefine the original endpoint.',
                labels_predictions_features_fits=0,
                independence='Independent streaming raw parser, counters, ELF instruction/symbol reader, inventories and hash checks. Shared frozen RV32 decode, pure candidate extractor, fusion execute and output oracle; no native jobs. Reused four outcomes authenticated unchanged, not newly raw-replayed. Git approval commit bytes and OS hermeticity are not reverified by this portable audit.')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, required=True); p.add_argument('--output', type=Path, required=True)
    p.add_argument('--action', choices=('inputs', 'results'), default='results')
    args = p.parse_args(); need(not args.output.exists(), 'Fresh audit output required')
    report = audit_inputs(args.root) if args.action == 'inputs' else run(args.root)
    with args.output.open('x') as f: json.dump(report, f, indent=2, allow_nan=False); f.write('\n')
    print(json.dumps(report, indent=2, allow_nan=False))


if __name__ == '__main__': main()
