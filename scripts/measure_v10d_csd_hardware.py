#!/usr/bin/env python3
"""V10d: sealed actual-RTL word-algebra gate, then64 fresh paired area jobs.

prepare/validate are input-only. collect requires the exact committed parent
release. No old SAT verdict is modified; V10c16proved/16timeout/0area is retained.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import statistics
import subprocess
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'scripts')]
import measure_v10_csd_hardware as frozen
import prove_v10_rtl_algebra as algebra
from prepare_v10_csd_hardware import validate_tools

SCHEMA = 'isaforge-v10d-csd-hardware-preparation-v1'
PREFIX = 'generated/v10d-csd-hardware/'
OLD_ROOT = 'results/2026-10-15-v10c-csd-hardware'
OLD_FREEZE = 'f7e04033a4bf52d5095dc7027d1d8a21a4f6e884'
OLD_NATIVE_COMMIT = '888dc3ea6cdc4403d8cbfab38a51771c0fbf07d8'
CHECKER_REVIEW_COMMIT = '73b8a2be55e0a8fae440fa09d8b38d5193eaaf92'
OLD_PREPARATION_SHA = '366deab82a91f674ddf0bbdd53f583740a9bea4af42eae760caac6643a7cf121'
PRIOR_V9 = 'results/2026-10-15-v9-coverage-development/measurements/attempt-0000/unique-measurements.json'
ARMS = ('original', 'csd')
MIN_FREE_BYTES = 2 * 1024**3
MAX_ATTEMPT_BYTES = 2 * 1024**3
FRONTEND_MIDDLE = ['hierarchy -check -top candidate', 'proc', 'opt_clean', 'check -assert']
run_owned = frozen.run_owned
measure_arm = frozen.measure_arm
HardwareWorkers = frozen.HardwareWorkers


def need(condition, message):
    if not condition: raise ValueError(message)


def read(path): return json.loads(Path(path).read_bytes())
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def digest(data): return hashlib.sha256(data).hexdigest()
def now(): return datetime.now(timezone.utc).isoformat()
def normalized(value): return json.loads(json.dumps(value, allow_nan=False))
def utc(value):
    parsed = datetime.fromisoformat(value)
    need(parsed.tzinfo is not None, 'Timezone-aware stage timestamp required')
    return parsed


def write(path, value):
    path = Path(path);path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False);stream.write('\n')


def copy(source, destination):
    destination = Path(destination);destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open('xb') as stream: stream.write(Path(source).read_bytes())


def record(path, root):
    path = Path(path).resolve()
    return {'path': os.path.relpath(path, Path(root).resolve()), 'sha256': sha(path)}


def checked(entry, root):
    need(set(entry) == {'path', 'sha256'} and isinstance(entry['path'], str)
        and not Path(entry['path']).is_absolute(), 'Relative file binding required')
    path = (Path(root) / entry['path']).resolve()
    need(path.is_relative_to(ROOT) and path.is_file() and sha(path) == entry['sha256'], 'Bound input differs: ' + entry['path'])
    return path


def committed(path, commit):
    path = Path(path).resolve()
    data = subprocess.check_output(['git', 'show', commit + ':' + path.relative_to(ROOT).as_posix()], cwd=ROOT)
    need(digest(data) == sha(path), 'Historical committed bytes differ: ' + str(path))


def required_sources():
    return [ROOT / 'scripts/measure_v10d_csd_hardware.py', ROOT / 'tests/test_measure_v10d_csd_hardware.py',
        ROOT / 'docs/v10d-csd-hardware-protocol.md', ROOT / 'scripts/prove_v10_rtl_algebra.py',
        ROOT / 'tests/test_prove_v10_rtl_algebra.py', ROOT / 'scripts/measure_v10_csd_hardware.py',
        ROOT / 'tests/test_measure_v10_csd_hardware.py', ROOT / 'scripts/prepare_v10_csd_hardware.py',
        ROOT / 'scripts/audit_v10d_hardware.py', ROOT / 'tests/test_audit_v10d_hardware.py',
        ROOT / 'scripts/audit_v10_hardware.py', ROOT / 'tests/test_audit_v10_hardware.py',
        *sorted((ROOT / 'isaforge').glob('*.py'))]


def baseline_inputs():
    old = ROOT / OLD_ROOT
    need(sha(old / 'preparation.json') == OLD_PREPARATION_SHA, 'Exact V10c input preparation required')
    preparation = read(old / 'preparation.json')
    files = [old / 'preparation.json']
    for entry in preparation['files']:
        path = checked(entry, old);committed(path, OLD_FREEZE);files.append(path)
    committed(old / 'preparation.json', OLD_FREEZE)
    pairs = read(checked(preparation['pairs'], old))
    need(len(pairs) == len({p['pair_id'] for p in pairs}) == 32, 'Exact32 inherited pairs required')
    native = [old / 'measurements/completion.json', old / 'measurements/attempt-0000/completion.json',
        old / 'measurements/attempt-0000/rtl-equivalence.json', old / 'measurements/attempt-0000/arm-measurements.json',
        old / 'measurements/attempt-0000/raw-evidence.json', old / 'measurements/attempt-0000/raw-evidence.zip',
        old / 'measurement-approval.json', old / 'label-release.json']
    for path in native: committed(path, OLD_NATIVE_COMMIT)
    done, proofs = read(native[0]), read(native[2])
    need(done['complete'] is False and done['pair_count'] == 32 and done['fresh_synthesis_jobs_completed'] == 0
        and done['universal_actual_rtl_pairs_proved'] == 16 and read(native[3]) == [], 'Preserved V10c16/16/0 outcome required')
    need(len(proofs) == 32 and {p['pair_id'] for p in proofs} == {p['pair_id'] for p in pairs}
        and sum(p['proved'] is True for p in proofs) == 16
        and sum(p['status'] == 'timeout' for p in proofs) == 16, 'All32 native SAT outcomes required')
    review_root = ROOT / 'results/2026-10-15-v10-hardware-preparation'
    review_files = [review_root / name for name in ('independent-algebra-review.json', 'evidence-manifest.json',
        'synthetic-algebra-evidence.zip', 'synthetic-timing-evidence.zip')]
    for path in review_files: committed(path, CHECKER_REVIEW_COMMIT)
    review = read(review_files[0])
    need(review['status'] == 'go-within-accepted-unsigned-json-scope'
        and review['checker_sha256'] == sha(ROOT / 'scripts/prove_v10_rtl_algebra.py')
        and review['tests_sha256'] == sha(ROOT / 'tests/test_prove_v10_rtl_algebra.py'), 'Exact independently reviewed checker required')
    prior = ROOT / PRIOR_V9;committed(prior, CHECKER_REVIEW_COMMIT)
    return preparation, pairs, list(dict.fromkeys([*files, *native, *review_files, prior]))


def recipe():
    return {'schema': 'isaforge-v10d-csd-hardware-recipe-v1', 'scope': 'Consumed32-case hardware development, distinct actual-RTL proof method',
        'pairs': 32, 'arms': list(ARMS), 'frontend_jobs': 64, 'frontend_timeout_seconds': 60,
        'frontend_middle_commands': FRONTEND_MIDDLE, 'proof_method': 'reviewed unsigned32 actual-word-JSON modular polynomial equality',
        'required_proof_pairs': 32, 'all_proofs_before_any_area': True, 'fresh_synthesis_jobs': 64,
        'measurement_timeout_seconds_per_arm': 360, 'workers': 2,
        'verification_seed': frozen.SEED, 'vectors_per_arm': frozen.VECTORS,
        'mapped_verification': '2148 samples; not universal mapped equivalence',
        'hardware_measurement_implementation': 'immutable measure_v10_csd_hardware.measure_arm; exact original target flow',
        'alternatives': 1, 'filtering': False, 'replacements': False, 'automatic_retries': False, 'model_fits': 0,
        'min_free_bytes': MIN_FREE_BYTES, 'workspace_guard_bytes': MAX_ATTEMPT_BYTES, 'workspace_poll_seconds': 1,
        'workspace_guard_scope': 'scratch plus result attempt, checked every1s/job boundary; possible one-interval overshoot; cancel and retain',
        'primary': 'all32 paired csd-minus-original LUT4; mean,median,range,wins/ties/losses; constant/context matrix',
        'carry': 'separate descriptive counts/deltas', 'prior_v9_originals': 'bound consumed context; disagreement reporting only',
        'incomplete': 'complete primary pending; retain all failure evidence',
        'limits': 'isolated combinational iCE40 LUT4/carry; no CPU integration, timing, power, ASIC area or transfer claim'}


def prepare(root):
    root = Path(root).resolve()
    need(root.is_relative_to(ROOT) and not root.exists(), 'Fresh repository-owned preparation root required')
    sources = required_sources();need(all(p.is_file() for p in sources), 'Finish required source/test/protocol files before preparation')
    before = {p: sha(p) for p in sources}
    baseline, pairs, inherited = baseline_inputs()
    old = ROOT / OLD_ROOT
    tools = read(checked(baseline['tools'], old));validate_tools(tools)
    root.mkdir(parents=True)
    try:
        for name, source in [('pairs.json', checked(baseline['pairs'], old)), ('tools.json', checked(baseline['tools'], old)),
            ('prior-v9-originals.json', ROOT / PRIOR_V9), ('source-candidates.json', old / 'source-candidates.json')]:
            copy(source, root / name)
        for pair in pairs:
            for entry in [pair['proof'], pair['miter_rtl'], *(pair['arms'][arm]['rtl'] for arm in ARMS)]:
                copy(checked(entry, old), root / entry['path'])
        write(root / 'recipe.json', recipe())
        amendment = {'schema': 'isaforge-v10d-proof-method-amendment-v1', 'previous_root': OLD_ROOT,
            'previous_input_commit': OLD_FREEZE, 'previous_native_commit': OLD_NATIVE_COMMIT,
            'previous_native_outcome': {'pairs': 32, 'sat_proved': 16, 'sat_timeout': 16, 'area_measurements': 0},
            'new_method': '64 exact-arm native word frontends +32 reviewed universal modular-algebra proofs',
            'same_inputs_rtl_csd_source_proofs_tools': True, 'new_area_outcomes_read': False,
            'proof_review_commit': CHECKER_REVIEW_COMMIT, 'old_run_marked_complete': False, 'model_fits': 0}
        write(root / 'premeasurement-amendment.json', amendment)
        need(all(sha(p) == value for p, value in before.items()), 'Sources changed during input preparation')
        files = [*sorted(p for p in root.rglob('*') if p.is_file()), *inherited, *sources]
        files = list(dict.fromkeys(p.resolve() for p in files))
        manifest = {'schema': SCHEMA, 'status': 'prepared-inputs-only', 'created_at_utc': now(), 'new_native_jobs': 0,
            'new_area_outcomes_read': False, 'model_fits': 0, 'recipe': record(root / 'recipe.json', root),
            'pairs': record(root / 'pairs.json', root), 'tools': record(root / 'tools.json', root),
            'prior_v9_originals': record(root / 'prior-v9-originals.json', root),
            'source_preparation': record(old / 'preparation.json', root),
            'previous_native_completion': record(old / 'measurements/completion.json', root),
            'amendment': record(root / 'premeasurement-amendment.json', root),
            'required_source_paths': [os.path.relpath(p.resolve(), root) for p in sources],
            'files': [record(p, root) for p in files]}
        write(root / 'preparation.json', manifest)
        validate_preparation(root)
        return manifest
    except Exception as error:
        write(root / 'preparation-failure.json', {'status': 'failed-closed', 'error': repr(error), 'new_native_jobs': 0, 'created_at_utc': now()})
        raise


def validate_preparation(root):
    root = Path(root).resolve()
    need(root.is_relative_to(ROOT) and not (root / 'preparation-failure.json').exists(), 'Valid repository-owned input preparation required')
    manifest = read(root / 'preparation.json')
    need(manifest.get('schema') == SCHEMA and manifest.get('status') == 'prepared-inputs-only'
        and manifest.get('new_native_jobs') == manifest.get('model_fits') == 0
        and manifest.get('new_area_outcomes_read') is False, 'Input-only preparation required')
    bindings = {}
    for entry in manifest['files']:
        path = checked(entry, root);need(path not in bindings, 'Duplicate flat binding');bindings[path] = entry['sha256']
    def bound(entry):
        path = checked(entry, root);need(bindings.get(path) == entry['sha256'], 'Reference absent from flat bindings');return path
    fixed_recipe = read(bound(manifest['recipe']));need(fixed_recipe == recipe(), 'Fixed V10d recipe differs')
    source = bound(manifest['source_preparation']);need(sha(source) == OLD_PREPARATION_SHA and source == ROOT / OLD_ROOT / 'preparation.json', 'Exact V10c lineage required')
    baseline = read(source);old = source.parent
    pairs_path = bound(manifest['pairs']);need(sha(pairs_path) == baseline['pairs']['sha256'], 'Exact inherited32pair bytes required')
    pairs = read(pairs_path);need(len(pairs) == len({p['pair_id'] for p in pairs}) == 32, 'Complete32 distinct pairs required')
    need(sha(bound(manifest['tools'])) == baseline['tools']['sha256'], 'Exact inherited tools required')
    need(sha(bound(manifest['prior_v9_originals'])) == sha(ROOT / PRIOR_V9), 'Consumed V9 context bytes differ')
    for entry in baseline['files']:
        path = checked(entry, old);need(bindings.get(path) == entry['sha256'], 'Every old input/source binding must be retained')
    _, inherited_pairs, inherited_files = baseline_inputs()
    need(pairs == inherited_pairs and all(bindings.get(path.resolve()) == sha(path) for path in inherited_files),
        'Complete historical input/native-failure/review closure must remain bound')
    for pair in pairs:
        for entry in [pair['proof'], pair['miter_rtl'], *(pair['arms'][arm]['rtl'] for arm in ARMS)]:
            path = bound(entry);need(path.is_relative_to(root), 'Copied arm/proof must be inside new preparation')
    for path in required_sources(): need(bindings.get(path.resolve()) == sha(path), 'Required production source missing')
    need(set(manifest['required_source_paths']) == {os.path.relpath(p.resolve(), root) for p in required_sources()}, 'Production closure list differs')
    previous = read(bound(manifest['previous_native_completion']))
    need(previous['complete'] is False and previous['universal_actual_rtl_pairs_proved'] == 16
        and previous['fresh_synthesis_jobs_completed'] == 0, 'Previous incomplete SAT attempt must remain incomplete')
    amendment = read(bound(manifest['amendment']))
    need(amendment.get('same_inputs_rtl_csd_source_proofs_tools') is True and amendment.get('new_area_outcomes_read') is False
        and amendment.get('previous_input_commit') == OLD_FREEZE and amendment.get('previous_native_commit') == OLD_NATIVE_COMMIT,
        'Explicit premeasurement proof-method amendment required')
    tools = read(root / 'tools.json')
    bindings[root / 'preparation.json'] = sha(root / 'preparation.json')
    return manifest, fixed_recipe, pairs, tools, bindings


def validate_approval(root, approval):
    root, approval = Path(root).resolve(), Path(approval).resolve()
    need(approval == root / 'measurement-approval.json', 'Exact root/measurement-approval.json required')
    manifest, fixed_recipe, pairs, tools, bindings = validate_preparation(root)
    validate_tools(tools)
    review = read(approval)
    expected = {'status': 'approved-v10d-csd-hardware-measurements', 'preparation_sha256': sha(root / 'preparation.json'),
        'recipe_sha256': manifest['recipe']['sha256'], 'pairs_sha256': manifest['pairs']['sha256'],
        'collector_sha256': sha(__file__), 'checker_sha256': sha(algebra.__file__)}
    need(all(review.get(k) == value for k, value in expected.items()) and re.fullmatch('[0-9a-f]{40}', review.get('freeze_commit', '')), 'Parent release differs from exact V10d freeze')
    need(utc(review['reviewed_at_utc']) >= utc(manifest['created_at_utc']), 'Parent review must follow input preparation')
    for path in bindings: committed(path, review['freeze_commit'])
    bindings[approval] = sha(approval)
    return manifest, fixed_recipe, pairs, tools, review, bindings


def frontend_commands(rtl, word):
    return [f'read_verilog {frozen._yosys_quote(Path(rtl).resolve())}', *FRONTEND_MIDDLE,
        f'write_json {frozen._yosys_quote(Path(word).resolve())}']


def frontend(root, pair, arm, folder, tools, owner):
    folder.mkdir(parents=True)
    started = now();entry = pair['arms'][arm]['rtl'];source = checked(entry, root)
    rtl, script, log, word = [folder / name for name in ('candidate.v', 'frontend.ys', 'frontend.log', 'word.json')]
    copy(source, rtl);script.write_text('\n'.join(frontend_commands(rtl, word)) + '\n')
    execution = run_owned([tools['executables']['yosys']['path'], '-s', str(script)], log, owner, 60)
    success = execution['returncode'] == 0 and execution['timed_out'] is False and word.is_file()
    error = ('Successful frontend exit produced no word.json'
        if execution['returncode'] == 0 and execution['timed_out'] is False and not word.is_file() else None)
    if success:
        try:
            algebra.load(word)
            observed = re.findall(r"Parsing Verilog input from [`']([^']+)'", log.read_text(errors='replace'))
            need(observed and all(Path(p).resolve() == rtl.resolve() for p in observed), 'Frontend read an unbound RTL file')
        except Exception as exc: success = False;error = repr(exc)
    result = {'schema': 'isaforge-v10d-frontend-v1', 'pair_id': pair['pair_id'], 'arm': arm,
        'success': success, 'status': 'complete' if success else 'timeout' if execution['timed_out'] else 'failed',
        'execution': execution, 'started_at_utc': started, 'completed_at_utc': now(),
        'candidate_rtl_sha256': sha(rtl), 'script_sha256': sha(script), 'log_sha256': sha(log),
        'word_json_sha256': sha(word) if word.is_file() else None, 'yosys': tools['executables']['yosys'],
        'command': [tools['executables']['yosys']['path'], '-s', str(script)], 'error': error}
    write(folder / 'frontend.json', result)
    return result


def prove_pair(pair, frontends, scratch):
    folder = scratch / 'algebra-proofs' / pair['pair_id'].split(':')[1];folder.mkdir(parents=True)
    started = now();clock = time.monotonic()
    evidence = {arm: frontends.get(pair['pair_id'] + '/' + arm) for arm in ARMS}
    result = None;error = None
    try:
        need(all(evidence[arm] and evidence[arm]['success'] is True for arm in ARMS), 'Both actual frontends must succeed')
        need(all(utc(evidence[arm]['completed_at_utc']) <= utc(started) for arm in ARMS), 'Frontend must complete before proof starts')
        graphs = []
        for arm in ARMS:
            location = scratch / 'frontend' / pair['pair_id'].split(':')[1] / arm
            need(sha(location / 'word.json') == evidence[arm]['word_json_sha256']
                and sha(location / 'candidate.v') == evidence[arm]['candidate_rtl_sha256'] == pair['arms'][arm]['rtl']['sha256'],
                'Actual frontend RTL/JSON changed before universal proof')
            graphs.append(algebra.load(location / 'word.json'))
        result = normalized(algebra.prove_pair(*graphs, width=32))
    except Exception as exc: error = repr(exc)
    record = {'schema': 'isaforge-v10d-actual-rtl-proof-v1', 'pair_id': pair['pair_id'],
        'proved': bool(result is not None and result.get('proved') is True and result.get('status') == 'proved'),
        'checker_sha256': sha(algebra.__file__), 'checker_result': result, 'frontend_records': evidence,
        'started_at_utc': started, 'completed_at_utc': now(), 'elapsed_seconds': time.monotonic() - clock,
        'error': error, 'scope': 'Universal equality of exact parsed original/CSD RTL JSON; shared reviewed checker, no mapped proof'}
    write(folder / 'proof.json', record)
    return record


def measured_arm(root, pair, arm, folder, tools, owner, gate, scratch):
    started = {'pair_id': pair['pair_id'], 'arm': arm, 'started_at_utc': now(),
        'measurement_gate_sha256': sha(scratch / 'measurement-gate.json')}
    need(utc(started['started_at_utc']) >= utc(gate['measurement_started_at_utc']), 'Measurement started before all-proof gate')
    source = scratch / 'measurement-start' / pair['pair_id'].split(':')[1] / (arm + '.json')
    write(source, started)
    try:
        result = measure_arm(root, pair, arm, folder, tools, owner)
        need(utc(result['measured_at_utc']) >= utc(started['started_at_utc']), 'Measurement completion predates start')
        return result
    finally:
        folder.mkdir(parents=True, exist_ok=True)
        copy(source, folder / 'measurement-start.json')


def workspace_bytes(*directories):
    size = 0
    for directory in directories:
        if not directory.exists(): continue
        for path in directory.rglob('*'):
            need(not path.is_symlink(), 'Attempt symlinks forbidden')
            if path.is_file(): size += path.stat().st_size
    return size


def guard(scratch, stage):
    need(workspace_bytes(scratch, stage) <= MAX_ATTEMPT_BYTES, 'Attempt workspace exceeded monitored2GiB guard; retain all partial evidence')


def recheck(bindings, tools):
    need(all(path.is_file() and sha(path) == expected for path, expected in bindings.items()), 'Bound source/input/release changed')
    validate_tools(tools)


def cancel(owner, failures):
    try: owner.cancel()
    except BaseException as error: failures.append({'phase': 'owned-process-cleanup', 'error': repr(error)})


def phase(jobs, operation, output, name, stage, scratch, owner, failures):
    pool = ThreadPoolExecutor(max_workers=2)
    try:
        pending = {pool.submit(operation, *arguments): key for key, arguments in jobs}
        completed = 0
        while pending:
            ready, _ = wait(pending, timeout=1, return_when=FIRST_COMPLETED)
            guard(scratch, stage)
            for future in ready:
                key = pending.pop(future);completed += 1
                try:
                    value = future.result();output[key] = value
                    if name == 'frontend' and value['success'] is not True:
                        failures.append({'phase': name, 'job': key, 'status': value['status']})
                    if name == 'algebra-proof' and value['proved'] is not True:
                        failures.append({'phase': name, 'job': key, 'status': 'not-proved', 'error': value['error']})
                except Exception as error: failures.append({'phase': name, 'job': key, 'error': repr(error)})
                write(stage / f'{name}-progress-{completed:04d}.json', {'phase': name, 'completed_records': len(output), 'failures': failures, 'at_utc': now()})
    except BaseException:
        cancel(owner, failures)
        raise
    finally:
        try: pool.shutdown(wait=True, cancel_futures=True)
        except BaseException as error:
            failures.append({'phase': 'worker-pool-cleanup', 'error': repr(error)})
            cancel(owner, failures)


def distribution(values):
    return {'count': len(values), 'mean': statistics.fmean(values), 'median': statistics.median(values),
        'minimum': min(values), 'maximum': max(values), 'lower': sum(x < 0 for x in values),
        'equal': sum(x == 0 for x in values), 'higher': sum(x > 0 for x in values)}


def summary(pairs, records, prior):
    index = {(r['pair_id'], r['arm']): r for r in records}
    expected = {(p['pair_id'], arm) for p in pairs for arm in ARMS}
    need(len(pairs) == 32 and len(index) == len(records) == 64 and set(index) == expected, 'Complete32 pairs/64 unique fresh arms required')
    prior_index = {r['formula']: r for r in prior}
    need(len(prior_index) == len(prior), 'Unique prior original measurements required')
    rows = []
    for pair in pairs:
        a, b = (index[pair['pair_id'], arm] for arm in ARMS)
        old = prior_index[pair['formula']]
        for metric in (a, b):
            need(type(metric['lut4_count']) is int and metric['lut4_count'] >= 0
                and type(metric['carry_count']) is int and metric['carry_count'] >= 0, 'Integer physical resource counts required')
        rows.append({'pair_id': pair['pair_id'], 'formula': pair['formula'], 'constant_u32': pair['constant_u32'], 'context': pair['context'],
            'original_lut4': a['lut4_count'], 'csd_lut4': b['lut4_count'], 'csd_minus_original_lut4': b['lut4_count'] - a['lut4_count'],
            'original_carry': a['carry_count'], 'csd_carry': b['carry_count'], 'csd_minus_original_carry': b['carry_count'] - a['carry_count'],
            'prior_v9_original_lut4': old['ice40_lut4_count'], 'prior_v9_original_carry': old['ice40_carry_count'],
            'fresh_minus_prior_original_lut4': a['lut4_count'] - old['ice40_lut4_count'],
            'fresh_minus_prior_original_carry': a['carry_count'] - old['ice40_carry_count'],
            'prior_original_rtl_equal': old['rtl_sha256'] == pair['arms']['original']['rtl']['sha256'],
            'prior_original_tool_equal': old['tool_sha256'] == a['yosys']['sha256']})
    def grouped(key, field):
        return {str(value): distribution([r[field] for r in rows if r[key] == value]) for value in sorted({r[key] for r in rows})}
    return {'schema': 'isaforge-v10d-paired-summary-v1', 'complete': True, 'pairs': rows,
        'lut4': distribution([r['csd_minus_original_lut4'] for r in rows]),
        'carry_descriptive': distribution([r['csd_minus_original_carry'] for r in rows]),
        'by_constant_lut4': grouped('constant_u32', 'csd_minus_original_lut4'), 'by_context_lut4': grouped('context', 'csd_minus_original_lut4'),
        'fresh_original_v9_lut4_disagreements': sum(r['fresh_minus_prior_original_lut4'] != 0 for r in rows),
        'fresh_original_v9_carry_disagreements': sum(r['fresh_minus_prior_original_carry'] != 0 for r in rows),
        'scope': recipe()['limits']}


def destination(name, attempt):
    path = PurePosixPath(name)
    need(attempt == 'attempt-0000' and not path.is_absolute() and '..' not in path.parts and '\\' not in name
        and str(path) == name and name.startswith(PREFIX + attempt + '/'), 'Owned single-attempt archive path required')
    target = ROOT / name
    need(target.resolve().is_relative_to((ROOT / PREFIX / attempt).resolve()), 'Raw evidence path escapes owned attempt')
    return target


def pack(root, scratch, stage, done):
    write(scratch / 'completion.json', done)
    files = []
    with zipfile.ZipFile(stage / 'raw-evidence.zip', 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(scratch.rglob('*')):
            need(not path.is_symlink(), 'Raw evidence symlinks forbidden')
            if not path.is_file(): continue
            name = path.relative_to(ROOT).as_posix();destination(name, done['attempt'])
            data = path.read_bytes();archive.writestr(name, data)
            files.append({'path': name, 'size': len(data), 'sha256': digest(data)})
    write(stage / 'raw-evidence.json', {'schema': 'isaforge-v10d-raw-evidence-v1', 'archive': 'raw-evidence.zip',
        'archive_sha256': sha(stage / 'raw-evidence.zip'), 'completion_sha256': sha(stage / 'completion.json'),
        'attempt': done['attempt'], 'files': files})


def collect(root, approval, *, attempt='attempt-0000', workers=2):
    root = Path(root).resolve()
    need(attempt == 'attempt-0000' and type(workers) is int and workers == 2, 'One fixed attempt and2workers required')
    need(not (root / 'label-release.json').exists() and not (root / 'measurements').exists(), 'Single-attempt collection; preserve every earlier outcome')
    manifest, fixed_recipe, pairs, tools, review, bindings = validate_approval(root, approval)
    need(shutil.disk_usage(root).free >= MIN_FREE_BYTES, 'At least2GiB free required before collection')
    stage = root / 'measurements' / attempt;scratch = ROOT / PREFIX / attempt
    need(not stage.exists() and not scratch.exists(), 'Fresh owned attempt directories required')
    stage.mkdir(parents=True);scratch.mkdir(parents=True)
    release = {'schema': 'isaforge-v10d-csd-hardware-release-v1', 'attempt': attempt, 'released_at_utc': now(),
        'preparation_sha256': sha(root / 'preparation.json'), 'approval_sha256': sha(approval), 'freeze_commit': review['freeze_commit'],
        'collector_sha256': sha(__file__), 'checker_sha256': sha(algebra.__file__), 'pairs': 32, 'frontend_jobs': 64,
        'fresh_synthesis_jobs': 64, 'workers': 2, 'verification_seed': frozen.SEED, 'vectors_per_arm': frozen.VECTORS,
        'collection_repository': str(ROOT), 'native_environment': frozen.native_environment(tools),
        'tools_sha256': sha(root / 'tools.json'), 'prior_v9_originals_sha256': sha(root / 'prior-v9-originals.json')}
    write(root / 'label-release.json', release);bindings[root / 'label-release.json'] = sha(root / 'label-release.json')
    for name in ('pairs.json', 'recipe.json', 'tools.json', 'preparation.json', 'prior-v9-originals.json', 'premeasurement-amendment.json'):
        copy(root / name, scratch / name)
    copy(approval, scratch / 'approval.json');copy(root / 'label-release.json', scratch / 'release.json')
    copy(__file__, scratch / 'collector-source.py');copy(algebra.__file__, scratch / 'checker-source.py')
    copy(frozen.__file__, scratch / 'frozen-measurement-source.py')
    for pair in pairs: copy(root / pair['proof']['path'], scratch / 'source-proofs' / pair['pair_id'].split(':')[1] / 'proof.json')
    owner = HardwareWorkers(tools);frontends, proofs, arms, failures = {}, {}, {}, []
    gate = None;interruption = None
    try:
        jobs = [(p['pair_id'] + '/' + arm, (root, p, arm, scratch / 'frontend' / p['pair_id'].split(':')[1] / arm, tools, owner))
            for p in pairs for arm in ARMS]
        phase(jobs, frontend, frontends, 'frontend', stage, scratch, owner, failures)
        jobs = [(p['pair_id'], (p, frontends, scratch)) for p in pairs]
        phase(jobs, prove_pair, proofs, 'algebra-proof', stage, scratch, owner, failures)
        frontend_rows = [frontends[p['pair_id'] + '/' + arm] for p in pairs for arm in ARMS if p['pair_id'] + '/' + arm in frontends]
        proof_rows = [proofs[p['pair_id']] for p in pairs if p['pair_id'] in proofs]
        write(stage / 'frontends.json', frontend_rows);write(stage / 'algebra-proofs.json', proof_rows)
        if not failures and len(frontends) == 64 and len(proofs) == 32 and all(p['proved'] is True for p in proof_rows):
            recheck(bindings, tools)
            gate = {'schema': 'isaforge-v10d-area-gate-v1', 'measurement_started_at_utc': now(),
                'all32_proof_sha256': sha(stage / 'algebra-proofs.json'), 'all64_frontend_sha256': sha(stage / 'frontends.json')}
            need(all(utc(p['completed_at_utc']) <= utc(gate['measurement_started_at_utc']) for p in proof_rows), 'Proof chronology violation')
            write(stage / 'measurement-gate.json', gate);copy(stage / 'measurement-gate.json', scratch / 'measurement-gate.json')
            jobs = [(p['pair_id'] + '/' + arm, (root, p, arm, scratch / 'circuits' / p['pair_id'].split(':')[1] / arm, tools, owner, gate, scratch))
                for p in pairs for arm in ARMS]
            phase(jobs, measured_arm, arms, 'fresh-synthesis', stage, scratch, owner, failures)
    except BaseException as error:
        interruption = error;failures.append({'phase': 'interruption-or-resource', 'error': repr(error)})
        cancel(owner, failures)
    try: recheck(bindings, tools)
    except Exception as error: failures.append({'phase': 'provenance', 'error': repr(error)})
    frontend_rows = [frontends[p['pair_id'] + '/' + arm] for p in pairs for arm in ARMS if p['pair_id'] + '/' + arm in frontends]
    proof_rows = [proofs[p['pair_id']] for p in pairs if p['pair_id'] in proofs]
    arm_rows = [arms[p['pair_id'] + '/' + arm] for p in pairs for arm in ARMS if p['pair_id'] + '/' + arm in arms]
    for name, rows in [('frontends.json', frontend_rows), ('algebra-proofs.json', proof_rows), ('arm-measurements.json', arm_rows)]:
        if not (stage / name).exists(): write(stage / name, rows)
        copy(stage / name, scratch / name)
    try:
        # Reserve an uncompressed archive plus metadata before the immutable
        # completion verdict. ZIP compression cannot exceed this conservative
        # bound for this finite evidence inventory (4MiB directory allowance).
        need(workspace_bytes(scratch, stage) + workspace_bytes(scratch) + 4 * 1024**2 <= MAX_ATTEMPT_BYTES,
            'Insufficient monitored workspace allowance for complete archive')
    except Exception as error:
        failures.append({'phase': 'archive-resource-reservation', 'error': repr(error)})
    complete = not failures and gate is not None and len(frontend_rows) == 64 and len(proof_rows) == 32 and len(arm_rows) == 64
    if complete:
        try:
            need(all(utc(row['measured_at_utc']) >= utc(gate['measurement_started_at_utc']) for row in arm_rows), 'Area chronology violation')
            report = summary(pairs, arm_rows, read(root / 'prior-v9-originals.json'))
            write(stage / 'summary.json', report);copy(stage / 'summary.json', scratch / 'summary.json')
        except Exception as error: complete = False;failures.append({'phase': 'complete-primary-summary', 'error': repr(error)})
    done = {'schema': 'isaforge-v10d-csd-hardware-measurements-v1', 'complete': complete, 'attempt': attempt,
        'pair_count': 32, 'frontend_jobs_completed': len(frontend_rows), 'successful_frontend_jobs': sum(r['success'] is True for r in frontend_rows),
        'universal_actual_rtl_pairs_proved': sum(r['proved'] is True for r in proof_rows), 'proof_records': len(proof_rows),
        'fresh_synthesis_jobs_completed': len(arm_rows), 'planned_fresh_synthesis_jobs': 64, 'failures': failures,
        'measurement_started_at_utc': gate['measurement_started_at_utc'] if gate else None,
        'preparation_sha256': sha(root / 'preparation.json'), 'approval_sha256': sha(approval),
        'release_sha256': sha(root / 'label-release.json'), 'collector_sha256': sha(__file__), 'checker_sha256': sha(algebra.__file__),
        'frontends_sha256': sha(stage / 'frontends.json'), 'algebra_proofs_sha256': sha(stage / 'algebra-proofs.json'),
        'arm_measurements_sha256': sha(stage / 'arm-measurements.json'), 'summary_sha256': sha(stage / 'summary.json') if complete else None,
        'measurement_gate_sha256': sha(stage / 'measurement-gate.json') if gate else None,
        'tools_sha256': sha(root / 'tools.json'), 'prior_v9_originals_sha256': sha(root / 'prior-v9-originals.json'),
        'scratch_directory': scratch.relative_to(ROOT).as_posix(), 'workers': 2, 'vectors_per_arm': frozen.VECTORS,
        'verification_seed': frozen.SEED, 'legacy_measurements_reused': False, 'new_estimator_fits': 0,
        'previous_v10c_result': 'incomplete16SATproved/16timeout/0area, preserved unchanged', 'completed_at_utc': now()}
    write(stage / 'completion.json', done);write(root / 'measurements/completion.json', done)
    for path in sorted(stage.glob('*progress*.json')): copy(path, scratch / 'progress' / path.name)
    pack(root, scratch, stage, done)
    if interruption is not None: raise interruption
    need(complete, 'Incomplete V10d attempt retained; complete primary unavailable')
    return done


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'validate', 'collect'))
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--approval', type=Path)
    args = parser.parse_args()
    if args.action == 'prepare': result = prepare(args.root)
    elif args.action == 'validate':
        m, r, p, t, b = validate_preparation(args.root);validate_tools(t)
        result = {'status': 'valid', 'pairs': len(p), 'bindings': len(b), 'new_native_jobs': 0}
    else:
        if args.approval is None: parser.error('collect requires --approval')
        result = collect(args.root, args.approval)
    print(json.dumps(result, indent=2))
