#!/usr/bin/env python3
"""V11c dtc-pinned profile audit; no native execution, features or labels.

The original independent streaming/ELF/occurrence replay helpers are reused from
frozen audit_v11_recovery. Profile/control-file checks below are a static
adaptation, with retained V11b failure and exact fac startup preflight required.
"""
import argparse
import ast
import copy
from datetime import datetime, timezone
import json
import hashlib
import os
from pathlib import Path, PurePosixPath
import re
import audit_v11_recovery as shared
import audit_v11b_failure as failure_audit
from audit_v11_recovery import (need, read, sha, same, integer, verify_record, verify_zip, relative_record,
    historical, archived, expected_policy, timestamp, verify_capture, verify_outcomes, elf_program,
    replay_gzip, htif, validate_output, parse_disassembly, extraction)
ROOT = Path(__file__).resolve().parents[1]
OLD = shared.OLD
NAMES, RECOVER, REUSE, FAMILIES = shared.NAMES, shared.RECOVER, shared.REUSE, shared.FAMILIES
ENDPOINT_SHA, PROTOCOL_SHA = shared.ENDPOINT_SHA, shared.PROTOCOL_SHA
FAILED = 'results/2026-10-16-v11b-transfer-recovery'
FAILED_SHA = '1f851d12e7c5d5a6b185137ad50ed08c5b0c15e762824e9a77a5311c102a752b'
FAILED_REPORT_SHA = '662ccc6305f1f11d6ffc4486e934f5e16d94ecaf1a15905732b0155ce4e2b7bd'
PREFIX = 'generated/v11-spooled-recovery/dtc-attempt-0000'
EXECUTED_RUNNER_SHA = '602517137439678e4cee2c0d5b196383e0dc20dc5243e010c7e0d79a1e430f77'
REVIEWED_RUNNER_SHA = '4639b4b1b3001011e8d1b020993f9a82ac565305887d31480447e7f555dd1efa'

def inputs(root):
    root = Path(root).resolve(); need(root.is_relative_to(ROOT / 'results'), 'Repository result root required')
    prep = read(root / 'preparation.json'); plan = read(root / 'plan.json'); tools = read(root / 'tools.json')
    need(prep['schema'] == 'isaforge-v11c-recovery-preparation-v1' and prep['status'] == 'prepared-inputs-only' and not (root / 'preparation-failure.json').exists(), 'Successful input preparation required')
    need(plan['schema'] == 'isaforge-v11c-recovery-plan-v1' and same(prep['policy'], expected_policy()) and same(plan['policy'], expected_policy()), 'Exact fixed recovery policy required')
    for key in ('native_trace_jobs', 'feature_jobs', 'predictions', 'labels', 'fits'): need(type(prep[key]) is int and prep[key] == 0, 'Preparation must be input-only')
    need(plan['features_predictions_labels_fits_released'] is False and plan['original_primary'] == 'undefined: empty recursion MAE; never zero', 'Original primary/release scope changed')
    bindings = {}
    for record in prep['files']:
        path = relative_record(record, root); need(path not in bindings, 'Duplicate preparation binding')
        bindings[path] = record['sha256']
    oldplan, oldreport, members, old_member_count = historical()
    mandatory = {ROOT / p for p in oldplan['runtime_source_sha256']}
    mandatory.update(ROOT / x['path'] for x in read(OLD / 'input-provenance-amendment.json')['added_runtime_sources'])
    mandatory.update(ROOT / p for p in ('scripts/recover_v11c_transfer.py', 'tests/test_recover_v11c_transfer.py',
                     'scripts/capture_v11_spooled.py', 'tests/test_capture_v11_spooled.py',
                     'scripts/audit_v11c_recovery.py', 'tests/test_audit_v11c_recovery.py', 'docs/v11-transfer-recovery-plan.md'))
    mandatory.update(ROOT / p for p in ('scripts/audit_v11_recovery.py', 'tests/test_audit_v11_recovery.py', 'scripts/audit_v11b_failure.py', 'scripts/recover_v11_transfer.py', 'tests/test_recover_v11_transfer.py'))
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
    partials.update(ROOT / 'generated/v11-spooled-recovery/attempt-0000' / n / 'capture/raw-spike.log.gz.partial' for n in RECOVER)
    need(partials <= set(bindings), 'Retained V11b empty partial bindings required')
    for record in prep['files']:
        path = (root / record['path']).resolve()
        need(type(record['git_required']) is bool and record['git_required'] is (path not in partials), 'Only four declared historical partials may be local-only')
    need(tuple(plan['programs']) == NAMES and plan['upstream_commit'] == oldplan['upstream_commit'] and plan['reservation_commit'] == oldplan['reservation_commit'], 'Fixed reserved source panel changed')
    need(tools['schema'] == 'isaforge-v11c-recovery-tools-v1', 'Tool inventory schema')
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
    verify_failure_binding(plan['previous_failure'], bindings)
    validate_dtc_tools(tools)
    preflight = verify_preflight(root, tools, plan)
    need(timestamp(preflight['completed_at_utc']) <= timestamp(prep['prepared_at_utc']), 'Preparation predates completed startup check')
    need({root/'preflight'/n for n in ('receipt.json','tools.json','runner-source.py','helper-source.py','stdout.log','stderr.log')} <= set(bindings), 'Startup evidence missing from preparation')
    return dict(root=root, preparation=prep, plan=plan, tools=tools, oldplan=oldplan, oldreport=oldreport, members=members,
                old_member_count=old_member_count, bindings=bindings)



def audit_inputs(root):
    data = inputs(root)
    return dict(schema='isaforge-v11c-independent-input-audit-v1', status='pass', preparation_sha256=sha(data['root'] / 'preparation.json'),
                audited_at_utc=datetime.now(timezone.utc).isoformat(), source_sha256=sha(__file__), programs=6, exact_reused_outcomes=4,
                recovered_programs_pending=2, historical_archive_members=data['old_member_count'], bound_files=len(data['bindings']),
                original_primary=None, original_primary_reason='Empty recursion formula MAE is undefined; original primary cannot be repaired by recovery.',
                audit_native_jobs=0, retained_fac_startup_preflights=1, preflight_sha256=sha(data['root']/'preflight/receipt.json'), prior_failure_completion_sha256=FAILED_SHA, executed_preflight_runner_sha256=EXECUTED_RUNNER_SHA, reviewed_preparation_runner_sha256=REVIEWED_RUNNER_SHA, new_labels=0, new_fits=0)



def verify_worker(row, name, phase, base, root, claim_sha):
    timeout = 1800 if phase == 'decode' else 300
    need(row['schema'] == 'isaforge-v11c-owned-worker-v1' and row['program'] == name and row['phase'] == phase, 'Wrong owned worker')
    need(row['complete'] is True and type(row['returncode']) is int and row['returncode'] == 0 and row['primary_error'] is None and row['cleanup_errors'] == [] and row['remaining_owned_children'] == [], 'Failed/incomplete owned worker')
    need(row['timeout_seconds'] == timeout and type(row['timeout_seconds']) is int and 0 <= row['elapsed_seconds'] <= timeout + 11, 'Worker budget mismatch')
    start, end = timestamp(row['started_at_utc']), timestamp(row['completed_at_utc']); need(start <= end, 'Worker chronology reversed')
    need(row['runner_sha256'] == sha(ROOT / 'scripts/recover_v11c_transfer.py') and row['claim_sha256'] == claim_sha and row['log_sha256'] == sha(base / (phase + '-worker.log')), 'Worker source/claim/log mismatch')
    command = row['command']; need(isinstance(command, list) and len(command) == 11 and Path(command[1]).is_absolute() and Path(command[1]).parts[-2:] == ('scripts', 'recover_v11c_transfer.py'), 'Owned worker command changed')
    origin = Path(command[1]).parents[1]
    need(command[2:] == ['worker', '--root', str(origin / root.relative_to(ROOT)), '--program', name, '--phase', phase, '--claim-sha256', claim_sha], 'Owned worker command identity changed')
    return start, end



def verify_capture_worker(row, name, capture_path, runner_sha, claim_sha):
    need(row['schema'] == 'isaforge-v11c-capture-worker-v1' and row['program'] == name and row['runner_sha256'] == runner_sha and row['claim_sha256'] == claim_sha and row['capture_sha256'] == sha(capture_path) and row['primary_error'] is None, 'Capture wrapper identity/failure mismatch')
    start, end = timestamp(row['started_at_utc']), timestamp(row['completed_at_utc'])
    need(start <= end and (end - start).total_seconds() <= 341, 'Capture wrapper chronology/budget mismatch')
    return start, end



def verify_package(root, done):
    stage = root / 'run/attempt-0000'; manifest = read(stage / 'evidence-manifest.json')
    need(manifest['schema'] == 'isaforge-v11c-recovery-evidence-v1' and manifest['complete'] is True and manifest['completion_sha256'] == sha(stage / 'completion.json'), 'Complete evidence manifest required')
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
    attempt = ROOT / 'generated/v11-spooled-recovery/dtc-attempt-0000'
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
    need(done['schema'] == 'isaforge-v11c-recovery-completion-v1' and done['complete'] is True and done['failures'] == [], 'Incomplete attempt cannot pass full input audit')
    need(same(done, read(stage / 'completion.json')), 'Root/stage completion mismatch')
    expected = dict(preparation_sha256=sha(root / 'preparation.json'), plan_sha256=sha(root / 'plan.json'), tools_sha256=sha(root / 'tools.json'),
                    approval_sha256=sha(root / 'recovery-approval.json'), claim_sha256=sha(root / 'recovery-claim.json'), runner_sha256=sha(ROOT / 'scripts/recover_v11c_transfer.py'),
                    program_count=6, reused_program_count=4, recovery_program_count=2, capture_records=2,
                    programs_sha256=sha(stage / 'programs.json'), completed_rows_sha256=sha(stage / 'completed-rows.json'),
                    original_primary='undefined: empty recursion MAE; never zero', new_features=0, new_predictions=0, new_labels=0, new_fits=0)
    need(all(k in done and same(done[k], v) for k, v in expected.items()), 'Completion identity/count/scope mismatch')
    approval = read(root / 'recovery-approval.json'); claim = read(root / 'recovery-claim.json')
    need(approval['preflight_sha256'] == sha(root/'preflight/receipt.json'), 'Approval startup evidence mismatch')
    need(approval['status'] == 'approved-v11c-input-only-recovery' and approval['preparation_sha256'] == expected['preparation_sha256'] and approval['runner_sha256'] == expected['runner_sha256'] and approval['maximum_new_captures'] == 2 and approval['maximum_labels'] == 0 and done['freeze_commit'] == approval['freeze_commit'], 'Approval release identity changed')
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
            base = ROOT / 'generated/v11-spooled-recovery/dtc-attempt-0000' / name
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
            fields = dict(schema='isaforge-v11c-extraction-v1', program=name, candidate_count=len(rows), candidate_sha256=sha(candidates),
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
    return dict(schema='isaforge-v11c-independent-recovery-audit-v1', status='pass', complete=True,
                audited_at_utc=datetime.now(timezone.utc).isoformat(), source_sha256=sha(__file__), preparation_sha256=expected['preparation_sha256'], completion_sha256=sha(root / 'completion.json'),
                evidence_manifest_sha256=sha(stage / 'evidence-manifest.json'), programs=reviews, program_count=6, reused_program_count=4, recovered_program_count=2,
                program_formula_rows=len(completed), unique_canonical_formulas=len({r['formula'] for r in completed}), historical_archive_members=data['old_member_count'], evidence_files=len(files),
                original_primary=None, original_primary_reason='Empty recursion formula MAE remains undefined; recovery does not redefine the original endpoint.',
                labels_predictions_features_fits=0,
                independence='V11c profile/failure/startup/provenance checks with shared frozen V11b streaming raw parser, counters, ELF reader and occurrence replay. That replay shares frozen RV32 decode, candidate extraction, fusion execute and output oracles. Four original outcomes authenticated unchanged, not newly raw-replayed. No native jobs; Git commit bytes, historical native paths and OS hermeticity are not reverified.')



def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, required=True); p.add_argument('--output', type=Path, required=True)
    p.add_argument('--action', choices=('inputs', 'results'), default='results')
    args = p.parse_args(); need(not args.output.exists(), 'Fresh audit output required')
    report = audit_inputs(args.root) if args.action == 'inputs' else run(args.root)
    with args.output.open('x') as f: json.dump(report, f, indent=2, allow_nan=False); f.write('\n')
    print(json.dumps(report, indent=2, allow_nan=False))



def verify_failure_binding(record, bindings):
    oldroot = ROOT / FAILED
    need(sha(oldroot/'completion.json') == FAILED_SHA and sha(oldroot/'run/input-review/independent-failure-audit.json') == FAILED_REPORT_SHA, 'Exact retained V11b failure/report required')
    replay = failure_audit.inspect(oldroot); saved = read(oldroot/'run/input-review/independent-failure-audit.json')
    need(all(same(value, saved.get(key)) for key,value in replay.items() if key != 'audited_at_utc'), 'Retained independent failure audit no longer reproduces')
    expected = dict(root=FAILED, freeze_commit='92bd7c52f5363c02dd19733941950d914db8f062',
                    preparation_sha256=sha(oldroot/'preparation.json'), completion_sha256=FAILED_SHA,
                    evidence_manifest_sha256=sha(oldroot/'run/attempt-0000/evidence-manifest.json'),
                    metadata_archive_sha256=sha(oldroot/'run/attempt-0000/metadata.zip'), independent_failure_audit_sha256=FAILED_REPORT_SHA, captures=2, retired_commits=0, new_labels=0,
                    amendment='Environment-only: add pinned dtc to controlled PATH; unchanged programs, ELFs, budgets, ROI, extraction, endpoint and ordering.')
    need(same(record, expected), 'V11c environment-only recovery lineage changed')
    need({p for p in oldroot.rglob('*') if p.is_file()} <= set(bindings), 'Prior V11b failure evidence missing from preparation')


def validate_dtc_tools(tools):
    need(set(tools['executables']) == {'cc','objdump','spike','gzip','python','dtc'}, 'Explicit pinned dtc executable required')
    for name,record in tools['executables'].items():
        need(Path(record['path']).is_absolute() and re.fullmatch('[0-9a-f]{64}',record['sha256']) is not None, 'Executable identity malformed')
    for name in ('dtc','gzip'):
        row = tools['executables'][name]
        need(row['version'] == (row['version_stdout'] + row['version_stderr']).strip() and bool(row['version']), 'Captured executable version identity missing')
    parents = sorted({str(Path(r['path']).parent) for r in tools['executables'].values()})
    need(same(tools['environment'], dict(PATH=':'.join([*parents,'/usr/bin','/bin']), LANG='C', LC_ALL='C', TZ='UTC')), 'Exact dtc-inclusive controlled PATH required')
    need(set(tools['dependencies']) == {'gzip','spike','objdump','dtc'}, 'dtc dynamic dependency inventory missing')
    for dependency in tools['dependencies'].values():
        need(isinstance(dependency['command'],list) and bool(dependency['listing']) and isinstance(dependency['boundary'],str), 'Dependency capture identity missing')
        for row in dependency['files']:
            need(Path(row['path']).is_absolute() and re.fullmatch('[0-9a-f]{64}',row['sha256']) is not None, 'Dependency identity malformed')


def verify_startup_source(executed, current, tools):
    """Preserve executed bytes; allow only the declared non-acquisition changes.

    sources()/failure_evidence() are outside the statically named startup call
    closure. validate_tools may add exactly the satisfied dependency-set guard.
    All other module statements/functions, including preflight, are identical.
    """
    need(hashlib.sha256(executed.encode()).hexdigest() == EXECUTED_RUNNER_SHA and hashlib.sha256(current.encode()).hexdigest() == REVIEWED_RUNNER_SHA, 'Only the exact parent-reviewed startup/current source pair is accepted')
    old,new=ast.parse(executed),ast.parse(current)
    named=lambda tree:{n.name:n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
    oldfn,newfn=named(old),named(new)
    need(set(oldfn)==set(newfn),'Startup runner function inventory changed')
    other=lambda tree:ast.dump(ast.Module(body=[n for n in tree.body if not isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))],type_ignores=[]),include_attributes=False)
    need(other(old)==other(new),'Startup runner module globals/imports changed')
    closure=set();pending=['preflight']
    while pending:
        name=pending.pop()
        if name in closure:continue
        closure.add(name)
        for node in ast.walk(oldfn[name]):
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id in oldfn:pending.append(node.func.id)
    need(not {'sources','failure_evidence'} & closure,'Provenance changes enter startup execution')
    guard=ast.parse("need(set(tools['dependencies'])=={'gzip','spike','objdump','dtc'},'Exact native dependency inventory required')").body[0]
    oldcheck,newcheck=copy.deepcopy(oldfn['validate_tools']),copy.deepcopy(newfn['validate_tools'])
    if ast.dump(oldcheck)!=ast.dump(newcheck):
        need(set(tools['dependencies'])=={'gzip','spike','objdump','dtc'},'Additional startup dependency guard is not satisfied')
        matches=[n for n in newcheck.body if ast.dump(n)==ast.dump(guard)]
        need(len(matches)==1,'Unexpected startup validation change')
        newcheck.body=[n for n in newcheck.body if ast.dump(n)!=ast.dump(guard)]
        need(ast.dump(oldcheck)==ast.dump(newcheck),'Startup validation changed beyond one satisfied guard')
    for name in oldfn:
        if name in ('sources','failure_evidence','validate_tools'):continue
        need(ast.dump(oldfn[name])==ast.dump(newfn[name]),'Executed startup source changed: '+name)
    return dict(executed_startup_function_unchanged=True,changed_nonstartup_functions=sorted(name for name in ('sources','failure_evidence') if ast.dump(oldfn[name])!=ast.dump(newfn[name])),satisfied_extra_dependency_guard=ast.dump(oldfn['validate_tools'])!=ast.dump(newfn['validate_tools']))


def verify_preflight(root, tools, plan):
    folder = root/'preflight'; row = read(folder/'receipt.json')
    need(row['schema'] == 'isaforge-v11c-dtc-preflight-v1' and row['complete'] is True and row['program'] == 'fac' and type(row['returncode']) is int and row['returncode'] == 0 and row['primary_error'] is None and row['cleanup_errors'] == [] and row['remaining_owned_children'] == [], 'Complete clean fac startup check required')
    need(type(row['timeout_seconds']) is int and row['timeout_seconds'] == 60 and type(row['elapsed_seconds']) in (int,float) and 0 <= row['elapsed_seconds'] <= 60, 'Fixed startup budget changed')
    start,end = timestamp(row['started_at_utc']),timestamp(row['completed_at_utc'])
    need(start <= end and (end-start).total_seconds() <= 61, 'Invalid startup chronology')
    for key in ('new_trace_captures','new_features','new_predictions','new_labels','new_fits'):
        need(type(row[key]) is int and row[key] == 0, 'Startup scope exceeded')
    expected = plan['programs']['fac']['original_record']['captured_outputs']
    need(same(expected,[154,5]) and same(row['expected_outputs'],expected) and same(row['captured_outputs'],expected), 'Exact original fac snapshot required')
    need(row['elf_sha256'] == plan['programs']['fac']['elf']['sha256'] and row['elf_path'] == FAILED+'/inputs/elfs/fac.elf', 'Exact original startup ELF required')
    command = row['command']
    need(isinstance(command,list) and len(command) == 4 and command[:3] == [tools['executables']['spike']['path'],'--isa=rv32im_zicntr','-m16'] and Path(command[3]).is_absolute() and command[3].endswith('/'+row['elf_path']), 'Startup command is not the exact non-tracing fac invocation')
    need(same(row['environment'],tools['environment']) and same(read(folder/'tools.json'),tools) and row['tools_sha256'] == sha(folder/'tools.json'), 'Startup tool/environment changed')
    for name in ('stdout','stderr'): need(row[name+'_sha256'] == sha(folder/(name+'.log')), 'Startup log identity changed')
    values = htif((folder/'stdout.log').read_text(),expected)
    need(same(row['oracle'],validate_output('fac',values,None)), 'Startup oracle changed')
    need(row['runner_sha256'] == sha(folder/'runner-source.py'), 'Executed startup runner snapshot hash differs')
    verify_startup_source((folder/'runner-source.py').read_text(),(ROOT/'scripts/recover_v11c_transfer.py').read_text(),tools)
    need(row['helper_sha256'] == sha(folder/'helper-source.py') == sha(ROOT/'scripts/capture_v11_spooled.py'), 'Startup executed helper differs from frozen bytes')
    for p in folder.iterdir(): need(p.is_file() and not p.is_symlink() and p.stat().st_size <= 16*1024**2,'Startup metadata invalid')
    required = {'receipt.json','tools.json','runner-source.py','helper-source.py','stdout.log','stderr.log'}
    need({p.name for p in folder.iterdir()} == required, 'Exact startup evidence inventory required')
    receipt_record = dict(path='preflight/receipt.json',sha256=sha(folder/'receipt.json'),bytes=(folder/'receipt.json').stat().st_size)
    need(same(plan['preflight'],receipt_record), 'Preparation startup receipt binding changed')
    return row


if __name__ == '__main__': main()
