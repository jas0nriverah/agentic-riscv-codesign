#!/usr/bin/env python3
"""Separately approved complete-pool original-RTL targets after frozen V6/V9 points.

No fitting, candidate selection, historical-label reuse, retry or timing claim.
Preparation/validation start no native jobs; collect alone needs target approval.
"""
from __future__ import annotations
import argparse
from collections import Counter
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import datetime, timezone
import hashlib
import itertools
import json
import math
import os
from pathlib import Path, PurePosixPath
import random
import re
import shutil
import stat
import subprocess
import sys
import threading
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'scripts')]
import measure_v13b_coverage as native
import capture_v11_spooled as cleanup
from measure_v6 import WORKER
from evaluate_v6 import verification_source
from isaforge.rtl import BOUNDARIES, evaluate_formula, generate_rtl

SEED = 2026101611
ATTEMPT = 'attempt-0000'
PREFIX = 'generated/v11e-transfer-targets'
GIB = 1024**3
POLICY = {'seed': SEED, 'random_vectors': 2048, 'boundary_vectors': 100, 'vectors_per_original': 2148,
          'verification_batch_maximum': 128, 'mapping_workers': 2, 'worker_seconds': 360,
          'poll_seconds': .25, 'archive_seconds': 300, 'attempt_seconds': 3600, 'initial_free_bytes': 16*GIB,
          'minimum_free_bytes': 8*GIB, 'maximum_attempt_bytes': 8*GIB,
          'maximum_archive_bytes': 6*GIB, 'maximum_log_bytes': 64*1024**2,
          'maximum_raw_file_bytes': GIB, 'retries': 0, 'replacement_candidates': 0,
          'historical_labels_reused': False, 'original_rtl_only': True, 'new_fits': 0}
FF_TYPES = {'SB_DFF', 'SB_DFFE', 'SB_DFFSR', 'SB_DFFR', 'SB_DFFSS', 'SB_DFFS',
            'SB_DFFESR', 'SB_DFFER', 'SB_DFFESS', 'SB_DFFES', 'SB_DFFN', 'SB_DFFNE',
            'SB_DFFNSR', 'SB_DFFNR', 'SB_DFFNSS', 'SB_DFFNS', 'SB_DFFNESR', 'SB_DFFNER',
            'SB_DFFNESS', 'SB_DFFNES'}
BRAM_TYPES = {'SB_RAM40_4K', 'SB_RAM40_4KNR', 'SB_RAM40_4KNW', 'SB_RAM40_4KNRNW'}
need, read, write = native.need, native.read, native.write

class AbortStage(ValueError):
    """Provenance, resources or unconfirmed cleanup stop every remaining case."""


def now(): return datetime.now(timezone.utc).isoformat()
def utc(value):
    d = datetime.fromisoformat(value)
    need(d.tzinfo is not None and d.utcoffset().total_seconds() == 0, 'UTC timestamp required')
    return d

def sha(path, check=None):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for body in iter(lambda:stream.read(1024**2),b''):
            h.update(body)
            if check is not None: check()
    if check is not None: check()
    return h.hexdigest()

def digest(data): return hashlib.sha256(data).hexdigest()
def equal(a, b): return json.dumps(a, sort_keys=True, allow_nan=False) == json.dumps(b, sort_keys=True, allow_nan=False)
def record(path, root): return {'path': os.path.relpath(Path(path).resolve(), root), 'sha256': sha(path)}
def integer(value):
    need(type(value) is int and value >= 0, 'Nonnegative integer required')
    return value

def sources():
    import predict_v11e_transfer as prediction
    return sorted({*prediction.sources(), *native.required_sources(), ROOT/'scripts/measure_v11e_transfer.py',
                   ROOT/'tests/test_measure_v11e_transfer.py', ROOT/'scripts/audit_v11e_targets.py',
                   ROOT/'tests/test_audit_v11e_targets.py', ROOT/'scripts/capture_v11_spooled.py',
                   ROOT/'tests/test_capture_v11_spooled.py', ROOT/'docs/v11-comparison-reporting-plan.md'})

def provenance(bindings, check=None):
    try: need(all(p.is_file() and not p.is_symlink() and sha(p,check) == h for p,h in bindings.items()), 'Bound bytes changed')
    except Exception as error: raise AbortStage('Sealed source/input changed: '+repr(error)) from error

def hot_bindings(bindings):
    # Full scientific payloads are authenticated at entry/exit. Polling hashes
    # executed sources/installed tools and named compact control seals only;
    # thousands of completed feature-cache JSON files must never enter this loop.
    controls = {'point-freeze.json','inference-plan.json','measurement-plan.json',
                'measurement-tools.json','measurement-approval.json','label-release.json'}
    return {p:h for p,h in bindings.items() if
            (not p.is_relative_to(ROOT/'generated') and not p.is_relative_to(ROOT/'results')
             and p.suffix not in ('.joblib','.zip','.gz'))
            or p.is_relative_to(ROOT/'results') and p.name in controls}


def budget(n):
    integer(n); need(n > 0, 'Nonempty complete pool required')
    batches = (n+127)//128
    return {'candidate_count': n, 'verification_batches': batches, 'expected_rtl_comparisons': 2148*n,
            'maximum_mapping_attempts': n,
            'maximum_attempt_seconds': 3600,
            'uncapped_serial_batch_worker_bound_seconds': 360*(batches+(n+1)//2)+600+10*(n+batches),
            'engineering_amendment': 'One 3600-second attempt including packaging; unfinished full pool remains failed.'}

def prediction_inputs(root):
    """No inference: authenticate the prediction owner's full frozen-point API."""
    import predict_v11e_transfer as prediction
    root = Path(root).resolve()
    freeze, candidates, memberships, bindings = prediction.validate_point_freeze(root)
    need(freeze['schema'] == 'isaforge-v11e-recovered-feature-point-freeze-v1' and freeze['complete'] is True, 'Full-pool paired point freeze required')
    need(root/'point-freeze.json' in bindings, 'Point-freeze bytes must be bound')
    formulas = [r['formula'] for r in candidates]
    ids = [r['candidate_id'] for r in candidates]
    need(formulas == sorted(set(formulas)) and len(set(ids)) == len(ids) and bool(ids), 'Complete sorted unique original pool required')
    from isaforge.features import parse_formula
    need(all(parse_formula(f).canonical() == f for f in formulas), 'Original formulas must be canonical')
    need(len(memberships) == 6 and {r['program'] for r in memberships} == set(prediction.inputs.FAMILIES), 'All six program outcomes required')
    seen = set(); program_ids = set()
    for row in memberships:
        name = row['program']; count = integer(row['canonical_count']); members = row['canonical_ids']
        need(name not in seen and row['family'] == prediction.inputs.FAMILIES[name] and row['status'] == ('complete' if count else 'empty'), 'Complete original outcomes required')
        need(type(members) is list and len(members) == len(set(members)) == count and set(members) <= set(ids), 'Full program membership differs')
        seen.add(name); program_ids.update(members)
        need(name != 'recursion' or count == 0, 'Empty recursion must remain empty')
    need(program_ids == set(ids) and all(any(r['canonical_count'] for r in memberships if r['family'] == f)
         for f in set(prediction.inputs.FAMILIES.values())), 'Full five-family pool required')
    points = read(root/'predictions/attempt-0000/result.json')
    need(set(points['models']) == {'V6', 'V9'}, 'Exact frozen predictor pair required')
    for rows in points['models'].values():
        need([r['candidate_id'] for r in rows] == ids and [r['formula'] for r in rows] == formulas, 'Exactly two full ordered point sets required')
        need(all(type(r['predicted_lut4']) in (int, float) and math.isfinite(r['predicted_lut4']) and r['predicted_lut4'] >= 0
             and r['upper_lut4'] is None and r['calibration_status'] == 'uncalibrated' for r in rows), 'Finite uncalibrated frozen points required')
    done = read(root/'predictions/completion.json')
    need(done['complete'] is True and done['failures'] == [] and type(done['prediction_count']) is int and done['prediction_count'] == 2*len(ids), 'Complete paired predictions required')
    need(all(type(done[k]) is int and done[k] == 0 for k in ('new_labels', 'new_fits', 'calibration_jobs')), 'Prediction stage must precede labels without fitting')
    provenance(bindings)
    return freeze, candidates, memberships, bindings


def prepare_measurement(root):
    root = Path(root).resolve(); need(root.is_relative_to(ROOT/'results'), 'Repository result root required')
    freeze, candidates, memberships, bindings = prediction_inputs(root)
    need(not any((root/n).exists() for n in ('measurement-plan.json', 'measurement-tools.json', 'measurements', 'label-release.json')), 'Fresh separate target stage required')
    tools = read(root/'tools.json'); native.validate_tools(tools)
    bindings.update({p.resolve():sha(p) for p in sources()})
    write(root/'measurement-tools.json', tools); provenance(bindings)
    plan = {'schema': 'isaforge-v11-transfer-target-plan-v1', 'status': 'prepared-no-target-jobs', 'created_at_utc': now(),
            'point_freeze_sha256': sha(root/'point-freeze.json'), 'prediction_completion_sha256': sha(root/'predictions/completion.json'),
            'prediction_frozen_at_utc': freeze['frozen_at_utc'],
            'policy': dict(POLICY), 'budget': budget(len(candidates)), 'tools': record(root/'measurement-tools.json', root),
            'program_formula_memberships': sum(r['canonical_count'] for r in memberships),
            'files': [record(p, root) for p in sorted(bindings)],
            'verification': 'All original RTL in <=128-case batches before any mapping; frozen signed-overflow validation workaround retained with unchanged RTL.',
            'scope': 'Fresh complete-pool isolated iCE40 resources. No refit, selection, calibration, timing, power or CPU claim.',
            'native_jobs': 0, 'new_labels': 0, 'new_fits': 0}
    need(utc(plan['created_at_utc']) >= utc(freeze['frozen_at_utc']), 'Target plan precedes frozen points')
    write(root/'measurement-plan.json', plan); return plan


def validate_plan(root):
    root = Path(root).resolve(); freeze, candidates, memberships, bindings = prediction_inputs(root)
    plan = read(root/'measurement-plan.json')
    need(plan['schema'] == 'isaforge-v11-transfer-target-plan-v1' and plan['status'] == 'prepared-no-target-jobs'
         and equal(plan['policy'], POLICY) and equal(plan['budget'], budget(len(candidates))), 'Exact complete-pool target plan required')
    need(plan['point_freeze_sha256'] == sha(root/'point-freeze.json') and plan['prediction_completion_sha256'] == sha(root/'predictions/completion.json'), 'Prelabel prediction identity changed')
    need(plan['prediction_frozen_at_utc'] == freeze['frozen_at_utc'] and utc(plan['created_at_utc']) >= utc(freeze['frozen_at_utc']), 'Target plan precedes or changes point-freeze chronology')
    need(plan['program_formula_memberships'] == sum(r['canonical_count'] for r in memberships), 'Whole membership denominator changed')
    expected = {**bindings, **{p.resolve():sha(p) for p in sources()}}
    sealed = {}
    for entry in plan['files']:
        path = (root/entry['path']).resolve(); need(path not in sealed, 'Duplicate target-plan binding'); sealed[path] = entry['sha256']
    need(sealed == expected, 'Exact full input/prediction/source closure required'); provenance(sealed)
    need(plan['tools'] == record(root/'measurement-tools.json', root), 'Target tool seal differs')
    tools = read(root/'measurement-tools.json'); need(equal(tools, read(root/'tools.json')), 'Feature and target tool inventory differ'); native.validate_tools(tools)
    sealed.update({root/n:sha(root/n) for n in ('measurement-plan.json', 'measurement-tools.json')})
    return candidates, memberships, plan, tools, sealed


def validate_approval(root, path):
    import predict_v11e_transfer as prediction
    root = Path(root).resolve(); path = Path(path).resolve(); need(path == root/'measurement-approval.json', 'Separate exact target approval required')
    candidates, memberships, plan, tools, bindings = validate_plan(root); approval = read(path)
    expected = {'status': 'approved-v11-full-pool-original-targets', 'candidate_count': len(candidates),
                'maximum_new_labels': len(candidates), 'expected_rtl_comparisons': 2148*len(candidates),
                'point_freeze_sha256': sha(root/'point-freeze.json'), 'prediction_completion_sha256': sha(root/'predictions/completion.json'),
                'measurement_plan_sha256': sha(root/'measurement-plan.json'), 'tools_sha256': sha(root/'measurement-tools.json'),
                'collector_sha256': sha(__file__), 'collector_tests_sha256': sha(ROOT/'tests/test_measure_v11e_transfer.py')}
    need(all(k in approval and equal(approval[k], v) for k,v in expected.items()), 'Exact separately reviewed target release required')
    need(utc(approval['reviewed_at_utc']) >= max(utc(plan['created_at_utc']), utc(read(root/'predictions/completion.json')['completed_at_utc'])), 'Target review precedes frozen predictions/plan')
    prediction.git_freeze(root, bindings, approval['freeze_commit'])
    bindings[path] = sha(path); return candidates, memberships, plan, tools, approval, bindings


def vectors():
    pairs = list(itertools.product(BOUNDARIES, repeat=2)); rng = random.Random(SEED)
    pairs.extend((rng.getrandbits(32), rng.getrandbits(32)) for _ in range(2048))
    need(len(pairs) == 2148, 'Fixed vector count differs'); return pairs


def validate_verification(proof, folder, formulas):
    wanted = {'verified': True, 'formula_count': len(formulas), 'vectors_per_formula': 2148,
              'total_comparisons': len(formulas)*2148, 'random_seed': SEED}
    need(all(type(proof.get(k)) is type(v) and proof[k] == v for k,v in wanted.items()), 'Incomplete original RTL verification')
    need(proof['v4_validation_override_sha256'] == sha(ROOT/'isaforge/v4_validation.py'), 'Frozen verifier changed')
    need((folder/'verification.v').read_text() == verification_source(formulas) and sha(folder/'verification.v') == proof['rtl_sha256'], 'Original batch RTL differs')
    with (folder/'vectors.txt').open() as stream:
        for a,b in vectors():
            expected = ' '.join(f'{v:08x}' for v in (a,b,*[evaluate_formula(f,a,b) for f in formulas]))+'\n'
            need(stream.readline() == expected, 'Original vector/oracle bytes differ')
        need(stream.read(1) == '', 'Extra verification vectors')
    need(sha(folder/'vectors.txt') == proof['vectors_sha256'] and type(proof['signed_overflow_workaround_applied']) is bool, 'Vector or workaround evidence differs')


def validate_metric(metric, folder, formula, tools):
    original = generate_rtl(formula).encode(); executable = tools['executables']['yosys']
    need(metric.get('formula') == formula and metric.get('tool') == executable['version'] and metric.get('measurement_source') == 'rtl_synthesis'
         and metric['rtl_sha256'] == digest(original) and (folder/'candidate.v').read_bytes() == original, 'Target is not exact original RTL')
    for name,key in [('ice40.ys','script_sha256'), ('ice40.log','log_sha256'), ('ice40-netlist.json','netlist_sha256')]:
        need(sha(folder/name) == metric[key], 'Raw target evidence differs')
    expected = f'read_verilog "{folder/"candidate.v"}"\nsynth_ice40 -top candidate\ncheck -assert\nwrite_json "{folder/"ice40-netlist.json"}"\nstat\n'
    need((folder/'ice40.ys').read_text() == expected and metric.get('command') == [executable['path'],'-s',str(folder/'ice40.ys')], 'Fixed mapping command/recipe differs')
    counts = Counter(c['type'] for c in read(folder/'ice40-netlist.json')['modules']['candidate'].get('cells',{}).values())
    need(type(metric['ice40_cell_types']) is dict and all(type(v) is int and v >= 0 for v in metric['ice40_cell_types'].values()), 'Exact integer primitive counts required')
    need(dict(counts) == metric['ice40_cell_types'] and set(counts) <= {'SB_LUT4','SB_CARRY'}|FF_TYPES|BRAM_TYPES, 'Unaccounted mapped primitive inventory')
    need(integer(metric['ice40_lut4_count']) == counts['SB_LUT4'] and integer(metric['ice40_carry_count']) == counts['SB_CARRY'], 'LUT/carry recount differs')
    log = (folder/'ice40.log').read_text()
    return {**metric, 'ice40_ff_count': sum(counts[k] for k in FF_TYPES), 'ice40_bram_count': sum(counts[k] for k in BRAM_TYPES),
            'tool_sha256': executable['sha256'], 'abc_invocations': native.abc_invocations(log,tools),
            'data_invocations': native.data_invocations(log,tools,folder/'candidate.v')}


class AttemptGuard:
    """Account stable evidence once; poll only the <=2 owned active workspaces.

    No whole-directory inventory is performed while streaming an archive chunk.
    Stage boundaries reconcile the complete tree and reject unexpected paths,
    symlinks and nonregular files. This is resource supervision, not a claim of
    atomic filesystem isolation; polling overshoot remains possible.
    """
    def __init__(self, scratch, output, *, began=None, maximum_seconds=None):
        self.scratch, self.output = Path(scratch), Path(output)
        self.began, self.maximum_seconds = began, maximum_seconds
        self.files = {}; self.active = set(); self.lock = threading.RLock()
        self.archiving = False; self.archive_maximum = None
        self.total = self.payload_bytes = self.member_count = self.stage_count = 0
        self.inventory()

    def limits(self):
        need(shutil.disk_usage(ROOT).free >= POLICY['minimum_free_bytes'], 'Below8GiB free-space floor')
        if self.began is not None:
            need(time.monotonic()-self.began <= self.maximum_seconds, 'Whole target attempt deadline')

    def scan(self, directory):
        found = {}
        if not directory.exists(): return found
        for base, directories, names in os.walk(directory, followlinks=False):
            self.limits()
            for name in [*directories, *names]:
                path = Path(base)/name; info = path.lstat()
                need(not stat.S_ISLNK(info.st_mode), 'Symlink in owned target attempt')
                if stat.S_ISDIR(info.st_mode): continue
                need(stat.S_ISREG(info.st_mode), 'Nonregular owned evidence')
                size = info.st_size
                cap = POLICY['maximum_archive_bytes'] if path.name == 'raw-evidence.zip' else POLICY['maximum_log_bytes'] if path.suffix == '.log' else POLICY['maximum_raw_file_bytes']
                need(size <= cap, 'Owned file/log byte cap reached')
                found[path] = size
        return found

    def inventory(self):
        with self.lock:
            self.files = {**self.scan(self.scratch), **self.scan(self.output)}
            self.total = sum(self.files.values())
            selected = self.payloads(self.files)
            self.payload_bytes = sum(selected.values()); self.member_count = len(selected)
            self.stage_count = sum(p.parent == self.output for p in selected)
            self.enforce(self.files)
        return dict(self.files)

    def payloads(self, files):
        return {p:n for p,n in files.items() if p.is_relative_to(self.scratch) and not {'obj_dir','obj_dir_wrapv'}.intersection(p.relative_to(self.scratch).parts)
                or p.parent == self.output and p.name in ('verification.json','unique-measurements.json','labels.json','completion.json')}

    def reservation(self, files):
        selected = self.payloads(files); payload = sum(selected.values())
        # Include four pending stage records even before they exist.
        count = len(selected)+sum(self.output/n not in selected for n in ('verification.json','unique-measurements.json','labels.json','completion.json'))
        return payload+(payload+999)//1000+65536*count+1024**2

    def enforce_totals(self, current, maximum, archive_size=0):
        self.limits()
        need(current <= POLICY['maximum_attempt_bytes'], 'Whole8GiB attempt cap reached')
        need(maximum <= POLICY['maximum_archive_bytes'], 'Insufficient archive reservation')
        need(current+max(0,maximum-archive_size) <= POLICY['maximum_attempt_bytes'], 'Insufficient whole-attempt/archive reservation')
        need(shutil.disk_usage(ROOT).free >= POLICY['minimum_free_bytes']+max(0,maximum-archive_size), 'Insufficient free space for archive plus floor')

    def enforce(self, files):
        maximum = self.archive_maximum if self.archiving else self.reservation(files)
        self.enforce_totals(sum(files.values()), maximum, files.get(self.output/'raw-evidence.zip',0))

    def begin(self, folder):
        with self.lock:
            folder = Path(folder); need(folder.is_relative_to(self.scratch), 'Owned worker directory required')
            need(not any(folder.is_relative_to(p) or p.is_relative_to(folder) for p in self.active), 'Overlapping active workspace')
            self.active.add(folder)

    def end(self, folder):
        try:
            with self.lock:
                folder = Path(folder); found = self.scan(folder)
                for path,size in found.items():
                    old = self.files.get(path); self.total += size-(old or 0)
                    if self.payloads({path:size}):
                        self.payload_bytes += size-(old or 0)
                        if old is None:
                            self.member_count += 1
                            self.stage_count += path.parent == self.output
                    self.files[path] = size
                self.active.discard(folder); self()
        except (ValueError, OSError) as error: raise AbortStage(str(error)) from error

    def __call__(self):
        try:
            with self.lock:
                if self.archiving:
                    # O(1) per chunk: stable bytes were fixed at the boundary.
                    path = self.output/'raw-evidence.zip'; size = 0
                    if path.exists():
                        need(not path.is_symlink() and path.is_file(), 'Symlink archive evidence')
                        size = path.stat().st_size
                        need(size <= POLICY['maximum_archive_bytes'], 'Owned archive byte cap reached')
                    total = self.total-self.files.get(path,0)+size
                    self.enforce_totals(total,self.archive_maximum,size)
                else:
                    # Closed workspaces remain cached. Only <=2 current native
                    # workspaces can change, including their compiler objects.
                    total = self.total; payload = self.payload_bytes
                    members = self.member_count; stages = self.stage_count
                    for folder in self.active:
                        found = self.scan(folder)
                        total += sum(found.values())
                        selected = self.payloads(found)
                        payload += sum(selected.values()); members += len(selected)
                        stages += sum(p.parent == self.output for p in selected)
                    maximum = payload+(payload+999)//1000+65536*(members+4-stages)+1024**2
                    self.enforce_totals(total,maximum)
        except (ValueError, OSError) as error: raise AbortStage(str(error)) from error


def guard(scratch, output, *, began=None, maximum_seconds=None):
    # Public one-shot boundary check; collect retains one incremental guard.
    try: AttemptGuard(scratch, output, began=began, maximum_seconds=maximum_seconds)()
    except (ValueError, OSError) as error: raise AbortStage(str(error)) from error


class HardwareWorkers(native.HardwareWorkers):
    """Keep the SDK-aware environment, with bounded process-object cleanup."""
    def __init__(self, tools):
        super().__init__(tools); self.processes = {}; self.tools = tools
    def python_identity(self):
        invoked = Path(sys.executable); resolved = invoked.resolve(); expected = self.tools['executables']['python']
        actual = sha(resolved)
        if str(resolved) != expected['path'] or actual != expected['sha256']: raise AbortStage('Invoked Python alias differs from pinned executable')
        return {'invoked':str(invoked),'resolved':str(resolved),'sha256':actual}
    def launch(self, command, stream):
        with self.lock:
            need(not self.cancelled, 'Owned hardware attempt canceled')
            process = subprocess.Popen(command, cwd=ROOT, env=self.environment, stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
            self.processes[process.pid] = process; return process
    def remove(self, process):
        with self.lock: self.processes.pop(process.pid, None)
    def cancel(self):
        with self.lock: self.cancelled = True; processes = list(self.processes.values())
        return cleanup.cleanup([('target-worker',p) for p in processes])


def cancel(owner, failures):
    try:
        errors, remaining = owner.cancel()
        if errors or remaining: failures.append({'stage':'cleanup','errors':errors,'remaining_owned_children':remaining})
    except BaseException as error: failures.append({'stage':'cleanup','error':repr(error),'remaining_owned_children':'unconfirmed'})


def run_worker(payload, folder, owner, hot, check):
    folder.mkdir(parents=True, exist_ok=True); log = folder/'worker.log'; result = folder/'worker.result.json'; receipt = folder/'worker.json'
    need(not any(p.exists() for p in (log,result,receipt)), 'Single fresh target worker required')
    command = [sys.executable,'-c',WORKER,json.dumps({**payload,'result':str(result)})]
    started = now(); began = time.monotonic(); process = None; error = None; errors = []; remaining = []; python_identity = None
    try:
        if hasattr(owner,'python_identity'): python_identity = owner.python_identity()
        provenance(hot); check()
        with log.open('xb') as stream:
            process = owner.launch(command,stream)
            while process.poll() is None:
                check(); need(time.monotonic()-began <= POLICY['worker_seconds'], 'Owned360s worker deadline')
                time.sleep(POLICY['poll_seconds'])
            check(); need(time.monotonic()-began <= POLICY['worker_seconds'], 'Worker terminal deadline')
            need(process.returncode == 0, 'Owned hardware worker failed; evidence retained')
        provenance(hot)
        if hasattr(owner,'python_identity'): need(owner.python_identity() == python_identity, 'Python invocation identity changed during worker')
    except BaseException as caught: error = caught
    finally:
        if process is not None:
            try: errors, remaining = cleanup.cleanup([(payload['kind'],process)])
            except BaseException as caught: errors = [{'operation':'cleanup','error':repr(caught)}]; remaining = [{'pid':process.pid,'scope':'cleanup-unconfirmed'}]
            if not errors and not remaining: owner.remove(process)
    saved = {'schema':'isaforge-v11-target-worker-v1','kind':payload['kind'],'command':command,'started_at_utc':started,'completed_at_utc':now(),
             'python_invocation':python_identity,'returncode':process.returncode if process else None,'timeout_seconds':POLICY['worker_seconds'],'elapsed_seconds':time.monotonic()-began,
             'primary_error':repr(error) if error else None,'cleanup_errors':errors,'remaining_owned_children':remaining,
             'log_sha256':sha(log) if log.exists() else None,'complete':error is None and not errors and not remaining}
    write(receipt,saved)
    if errors or remaining: raise AbortStage('Owned cleanup unconfirmed; primary='+repr(error))
    if error is not None: raise error
    return read(result)


def archive_files(scratch, output):
    result = {p.relative_to(scratch).as_posix():p for p in scratch.rglob('*') if p.is_file() and not {'obj_dir','obj_dir_wrapv'}.intersection(p.parts)}
    for name in ('verification.json','unique-measurements.json','labels.json','completion.json'): result['stage/'+name] = output/name
    return result


def archive(scratch, output, done, check):
    # One boundary inventory/reservation; chunk checks stat only the live ZIP.
    check.inventory(); maximum = check.reservation(check.files)
    files = archive_files(scratch, output); records = []; began = time.monotonic()
    check.archiving = True; check.archive_maximum = maximum
    def archive_check():
        check(); need(time.monotonic()-began <= POLICY['archive_seconds'], 'Archive deadline')
    with zipfile.ZipFile(output/'raw-evidence.zip','x',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for name,path in sorted(files.items()):
            need(not path.is_symlink(), 'Symlink archive evidence'); h = hashlib.sha256(); size = 0
            need(path in check.files, 'Archive member absent from boundary inventory')
            before = path.stat()
            with path.open('rb') as stream, z.open(name,'w',force_zip64=True) as target:
                for body in iter(lambda:stream.read(1024**2),b''):
                    target.write(body); h.update(body); size += len(body); check()
                    need(time.monotonic()-began <= POLICY['archive_seconds'], 'Archive deadline')
            after = path.stat()
            need((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)==(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns)
                 and size == check.files[path], 'Evidence changed during archive')
            records.append({'path':name,'sha256':h.hexdigest(),'bytes':size})
    check(); need(time.monotonic()-began <= POLICY['archive_seconds'], 'Archive terminal deadline')
    need((output/'raw-evidence.zip').stat().st_size <= maximum, 'Archive exceeded reserved bound')
    write(output/'raw-evidence.json',{'schema':'isaforge-v11-target-archive-v1','complete':done['complete'],'attempt':ATTEMPT,
        'archive_sha256':sha(output/'raw-evidence.zip',archive_check),'completion_sha256':sha(output/'completion.json'),'files':records,
        'compiler_objects_included':False,'scope':'Vectors, original RTL, raw netlists/scripts/logs and source/worker records. Saved full point/membership/feature inputs remain external exact hash-bound dependencies referenced by point-freeze.json; no prior label cache.'})
    check.inventory(); archive_check()


def verify_archive(root, check=None):
    output = Path(root)/'measurements'/ATTEMPT; raw = read(output/'raw-evidence.json'); done = read(output/'completion.json')
    need(raw['schema'] == 'isaforge-v11-target-archive-v1' and raw['complete'] is done['complete'] and raw['attempt'] == ATTEMPT, 'Raw archive identity differs')
    if check is not None: check()
    need(sha(output/'raw-evidence.zip',check) == raw['archive_sha256'] and sha(output/'completion.json') == raw['completion_sha256'], 'Archive/completion hash differs')
    entries = {r['path']:r for r in raw['files']}; need(len(entries) == len(raw['files']), 'Duplicate archive member')
    with zipfile.ZipFile(output/'raw-evidence.zip') as z:
        need(len(z.namelist()) == len(set(z.namelist())) and set(z.namelist()) == set(entries), 'Complete archive inventory differs')
        for name,row in entries.items():
            p = PurePosixPath(name); need(not p.is_absolute() and '..' not in p.parts and '\\' not in name and str(p) == name, 'Unsafe archive path')
            h = hashlib.sha256(); size = 0
            with z.open(name) as stream:
                for body in iter(lambda:stream.read(1024**2),b''):
                    h.update(body); size += len(body)
                    if check is not None: check()
            need(size == integer(row['bytes']) and h.hexdigest() == row['sha256'], 'Archived member hash differs')
        for name,key in [('verification.json','verification_sha256'),('unique-measurements.json','unique_measurements_sha256'),('labels.json','labels_sha256')]:
            need(sha(output/name) == done[key] and z.read('stage/'+name) == (output/name).read_bytes(), 'Archived stage bytes differ')
        need(z.read('stage/completion.json') == (output/'completion.json').read_bytes(), 'Archived completion differs')
    return raw


def collect(root, approval):
    root = Path(root).resolve(); candidates,memberships,plan,tools,review,bindings = validate_approval(root,approval)
    scratch = ROOT/PREFIX/ATTEMPT; output = root/'measurements'/ATTEMPT
    need(not scratch.exists() and not (root/'measurements').exists() and not (root/'label-release.json').exists(), 'One fresh target attempt; no retry')
    need(shutil.disk_usage(ROOT).free >= POLICY['initial_free_bytes'], 'Target start needs16GiB free, reserving8GiB attempt plus8GiB floor')
    scratch.mkdir(parents=True); output.mkdir(parents=True); began = time.monotonic(); failures = []; proofs = []; measured = {}; interruption = None
    maximum_seconds = plan['budget']['maximum_attempt_seconds']; hot = hot_bindings(bindings)
    check = AttemptGuard(scratch,output,began=began,maximum_seconds=maximum_seconds)
    release = {'schema':'isaforge-v11-target-release-v1','released_at_utc':now(),'freeze_commit':review['freeze_commit'],
               'approval_sha256':sha(approval),'point_freeze_sha256':sha(root/'point-freeze.json'),'prediction_completion_sha256':sha(root/'predictions/completion.json'),
               'measurement_plan_sha256':sha(root/'measurement-plan.json'),'tools_sha256':sha(root/'measurement-tools.json'),
               'candidate_count':len(candidates),'collector_sha256':sha(__file__),'policy':dict(POLICY)}
    need(utc(release['released_at_utc']) >= utc(review['reviewed_at_utc']), 'Release precedes review'); write(root/'label-release.json',release)
    bindings[root/'label-release.json'] = sha(root/'label-release.json'); hot[root/'label-release.json'] = bindings[root/'label-release.json']
    owner = HardwareWorkers(tools); formulas = [r['formula'] for r in candidates]
    try:
        provenance(bindings,check); native.validate_tools(tools); check()
        for name in ('measurement-plan.json','measurement-tools.json','measurement-approval.json','label-release.json','point-freeze.json'):
            shutil.copyfile(root/name,scratch/name)
        for path in sources():
            target = scratch/'sources'/path.relative_to(ROOT); target.parent.mkdir(parents=True,exist_ok=True); shutil.copyfile(path,target)
        check.inventory(); check()
        for offset in range(0,len(formulas),128):
            batch = formulas[offset:offset+128]; folder = scratch/'verification'/f'batch-{offset:04d}'
            check.begin(folder)
            try:
                proof = run_worker({'kind':'verify','formulas':batch,'folder':str(folder),'seed':SEED},folder,owner,hot,check)
                validate_verification(proof,folder,batch); proofs.append(proof)
            finally: check.end(folder)
            check()
        gate = {'verified_at_utc':now(),'formula_count':len(formulas),'comparison_count':2148*len(formulas),'verification_sha256':digest(json.dumps(proofs,sort_keys=True).encode())}
        write(scratch/'verification-gate.json',gate); check.inventory()
        def measure(formula):
            folder = scratch/'circuits'/digest(formula.encode()); need(not folder.exists(),'Fresh circuit directory required')
            check.begin(folder)
            try:
                folder.mkdir(parents=True)
                write(folder/'measurement-start.json',{'formula':formula,'started_at_utc':now(),'verification_gate_sha256':sha(scratch/'verification-gate.json')})
                metric = run_worker({'kind':'map','formula':formula,'folder':str(folder),'executable':tools['executables']['yosys']['path'],
                                     'version':tools['executables']['yosys']['version']},folder,owner,hot,check)
                metric = validate_metric(metric,folder,formula,tools); write(folder/'measurement.json',metric); return metric
            finally: check.end(folder)
        pool = ThreadPoolExecutor(max_workers=2)
        try:
            pending = {}; iterator = iter(formulas)
            while True:
                check()
                while len(pending) < 2:
                    formula = next(iterator,None)
                    if formula is None: break
                    pending[pool.submit(measure,formula)] = formula
                if not pending: break
                ready,_ = wait(pending,timeout=POLICY['poll_seconds'],return_when=FIRST_COMPLETED)
                for future in ready:
                    formula = pending.pop(future)
                    try: measured[formula] = future.result()
                    except AbortStage: raise
                    except Exception as error: failures.append({'stage':'mapping','formula':formula,'error':repr(error)})
        except BaseException:
            cancel(owner,failures); raise
        finally:
            try: pool.shutdown(wait=True,cancel_futures=True)
            except BaseException as error: failures.append({'stage':'worker-shutdown','error':repr(error)}); cancel(owner,failures)
    except BaseException as error:
        failures.append({'stage':'verification-or-guard','error':repr(error)}); cancel(owner,failures)
        if not isinstance(error,Exception): interruption = error
    try: provenance(bindings,check); native.validate_tools(tools); check()
    except BaseException as error: failures.append({'stage':'final-provenance-resource','error':repr(error)})
    unique = [measured[f] for f in formulas if f in measured]
    labels = [{**r,'lut4_count':measured[r['formula']]['ice40_lut4_count'],'carry_count':measured[r['formula']]['ice40_carry_count'],
               'ff_count':measured[r['formula']]['ice40_ff_count'],'bram_count':measured[r['formula']]['ice40_bram_count'],
               'rtl_sha256':measured[r['formula']]['rtl_sha256'],'correctness_verified':True,'measurement_source':'rtl_synthesis'} for r in candidates if r['formula'] in measured]
    for name,value in [('verification',proofs),('unique-measurements',unique),('labels',labels)]: write(output/(name+'.json'),value)
    try: check.inventory(); check()
    except BaseException as error: failures.append({'stage':'archive-reservation','error':repr(error)})
    done = {'schema':'isaforge-v11-transfer-target-completion-v1','attempt':ATTEMPT,'complete':not failures and len(labels) == len(candidates) and sum(p['total_comparisons'] for p in proofs) == 2148*len(candidates),
            'failures':failures,'candidate_count':len(candidates),'new_physical_measurements':len(unique),'mapping_attempts':len(list((scratch/'circuits').glob('*/measurement-start.json'))),
            'verified_comparisons':sum(p['total_comparisons'] for p in proofs),'verification_batch_sizes':[p['formula_count'] for p in proofs],
            'verification_seed':SEED,'vectors_per_original':2148,'mapping_workers':2,'original_rtl_only':True,'historical_labels_reused':False,'new_fits':0,
            'primary_available':not failures and len(labels) == len(candidates),
            'primary_availability_scope':'Complete target pool for amended V11b-E1 only; independent measurement admission remains required before scoring.',
            'original_endpoint_available':False,'original_endpoint':'Undefined equal-all-program MAE: complete empty recursion error is not zero.',
            'point_freeze_sha256':release['point_freeze_sha256'],
            'prediction_completion_sha256':release['prediction_completion_sha256'],'release_sha256':sha(root/'label-release.json'),
            'measurement_plan_sha256':release['measurement_plan_sha256'],'tools_sha256':release['tools_sha256'],'approval_sha256':release['approval_sha256'],
            'freeze_commit':review['freeze_commit'],'collector_sha256':sha(__file__),'completed_at_utc':now(),
            **{key:sha(output/name) for name,key in [('verification.json','verification_sha256'),('unique-measurements.json','unique_measurements_sha256'),('labels.json','labels_sha256')]}}
    write(output/'completion.json',done)
    try: archive(scratch,output,done,check); verify_archive(root,check); check(); provenance(bindings,check); check()
    except BaseException as error:
        done = {**done,'complete':False,'primary_available':False,'failures':[*done['failures'],{'stage':'archive-final','error':repr(error)}]}
    write(root/'measurements/completion.json',done)
    if interruption is not None: raise interruption
    need(done['complete'], 'Incomplete target attempt retained; full-pool primary unavailable'); return done


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('action',choices=('prepare','validate','collect','verify'))
    parser.add_argument('--root',type=Path,required=True); parser.add_argument('--approval',type=Path); args = parser.parse_args()
    if args.action == 'collect': need(args.approval is not None,'Separate target approval required'); result = collect(args.root,args.approval)
    elif args.action == 'prepare': result = prepare_measurement(args.root)
    elif args.action == 'verify': result = verify_archive(args.root)
    else: result = {'status':'valid','candidate_count':len(validate_plan(args.root)[0]),'native_jobs':0}
    print(json.dumps(result,indent=2,allow_nan=False))
