#!/usr/bin/env python3
"""Collect the approved fixed V9 coverage batch; never fit or replace candidates."""
from __future__ import annotations
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'scripts')]
from measure_v6 import OwnedWorkers, run_owned
from evaluate_v6 import verification_source
from isaforge.features import parse_formula
from isaforge.rtl import generate_rtl

PREFIX = 'generated/v9-coverage-measurements/'
VERIFY_SEED = 2026101519
COUNT = 48


def read(path): return json.loads(Path(path).read_text())
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def now(): return datetime.now(timezone.utc).isoformat()
def write(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
def utc(value):
    value = datetime.fromisoformat(value)
    if value.tzinfo is None: raise ValueError('Timezone-aware stage timestamp required')
    return value

def integer(value):
    if type(value) is not int or value < 0: raise ValueError('Nonnegative integer resource count required')
    return value


def required_sources():
    return [Path(__file__).resolve(), ROOT / 'scripts/prepare_v9_coverage.py',
            ROOT / 'scripts/measure_v6.py', ROOT / 'scripts/evaluate_v6.py',
            *(ROOT / 'isaforge' / name for name in ('features.py', 'rtl.py', 'synthesis.py', 'v4_corpus.py', 'v4_validation.py'))]


def prepared_inputs(root):
    from prepare_v9_coverage import validate_preparation
    root = Path(root).resolve()
    manifest, recipe, candidates = validate_preparation(root)
    if manifest.get('schema') != 'isaforge-v9-coverage-preparation-v1':
        raise ValueError('Fixed V9 coverage preparation required')
    formulas = [r['formula'] for r in candidates]
    if (len(formulas) != COUNT or len(set(formulas)) != COUNT
            or any(parse_formula(f).canonical() != f for f in formulas)):
        raise ValueError('Exactly48 distinct canonical original circuits required')
    bindings = {root / 'preparation.json': sha(root / 'preparation.json')}
    for entry in [*manifest['files'], manifest['recipe'], manifest['candidates']]:
        path = (root / entry['path']).resolve()
        if not path.is_relative_to(ROOT) or sha(path) != entry['sha256']:
            raise ValueError('Changed or nonportable prepared evidence')
        if path in bindings and bindings[path] != entry['sha256']:
            raise ValueError('Conflicting prepared bindings')
        bindings[path] = entry['sha256']
    if any(path.resolve() not in bindings for path in required_sources()):
        raise ValueError('Required collector/runtime sources missing from preparation')
    return manifest, recipe, candidates, bindings


def validate_approval(root, approval):
    root, approval = Path(root).resolve(), Path(approval).resolve()
    if approval != root / 'measurement-approval.json':
        raise ValueError('Exact root/measurement-approval.json required')
    manifest, recipe, candidates, bindings = prepared_inputs(root)
    review = read(approval)
    expected = {'status': 'approved-v9-coverage-measurements',
                'preparation_sha256': sha(root / 'preparation.json'),
                'recipe_sha256': manifest['recipe']['sha256'],
                'candidates_sha256': manifest['candidates']['sha256'],
                'collector_sha256': sha(__file__)}
    if (any(review.get(k) != v for k, v in expected.items())
            or not isinstance(review.get('freeze_commit'), str)
            or not re.fullmatch('[0-9a-f]{40}', review['freeze_commit'])
            or utc(review['reviewed_at_utc']) < utc(manifest['prepared_at_utc'])):
        raise ValueError('Exact committed parent coverage approval required')
    for path, digest in bindings.items():
        result = subprocess.run(['git', 'show', review['freeze_commit'] + ':' + path.relative_to(ROOT).as_posix()],
                                cwd=ROOT, capture_output=True)
        if result.returncode or hashlib.sha256(result.stdout).hexdigest() != digest:
            raise ValueError('Approved preparation differs from committed bytes')
    return manifest, recipe, candidates, review, bindings


def destination(name, repository, attempt):
    repository = Path(repository).resolve(); path = PurePosixPath(name)
    prefix = PREFIX + attempt + '/'
    if (not re.fullmatch('attempt-[0-9]{4}', attempt) or not name.startswith(prefix)
            or path.is_absolute() or '..' in path.parts or '\\' in name or str(path) != name):
        raise ValueError('Unexpected owned coverage evidence path')
    allowed = repository / PREFIX / attempt; target = repository / name
    if not allowed.resolve().is_relative_to(repository) or not target.resolve().is_relative_to(allowed.resolve()):
        raise ValueError('Coverage evidence escapes owned attempt')
    return target


def collect(root, approval, *, workers=2, attempt='attempt-0000'):
    root = Path(root).resolve()
    if type(workers) is not int or workers != 2 or not isinstance(attempt, str) or not re.fullmatch('attempt-[0-9]{4}', attempt):
        raise ValueError('Fixed2 workers and explicit owned attempt required')
    directory = root / 'measurements'
    if (directory / 'completion.json').exists() and read(directory / 'completion.json').get('complete') is True:
        raise ValueError('Completed coverage measurements are immutable')
    manifest, recipe, candidates, review, bindings = validate_approval(root, approval)
    output = directory / attempt; scratch = ROOT / PREFIX / attempt
    destination(PREFIX + attempt + '/member', ROOT, attempt)
    if output.exists() or scratch.exists(): raise ValueError('Fresh coverage attempt required')
    tool = recipe['frozen_tool']; executable = shutil.which('yosys')
    if executable is None: raise RuntimeError('Frozen Yosys required')
    version = subprocess.check_output([executable, '-V'], text=True).strip()
    if version != tool['version'] or sha(executable) != tool['executable_sha256']:
        raise ValueError('Frozen Yosys binary/version differs')
    identity = {'schema': 'isaforge-v9-coverage-label-release-v1',
                'preparation_sha256': sha(root / 'preparation.json'), 'recipe_sha256': manifest['recipe']['sha256'],
                'candidates_sha256': manifest['candidates']['sha256'], 'approval_sha256': sha(approval),
                'freeze_commit': review['freeze_commit'], 'collector_sha256': sha(__file__),
                'verification_seed': VERIFY_SEED, 'vectors_per_formula': 2148, 'workers': 2,
                'candidate_count': COUNT, 'frozen_tool': tool}
    release_path = root / 'label-release.json'
    if release_path.exists():
        release = read(release_path)
        if any(release.get(k) != v for k, v in identity.items()): raise ValueError('Existing coverage release differs')
    else:
        release = {**identity, 'released_at_utc': now()}; write(release_path, release)
    bindings[Path(approval).resolve()] = sha(approval)
    output.mkdir(parents=True); scratch.mkdir(parents=True)
    formulas = sorted(r['formula'] for r in candidates)
    owner = OwnedWorkers(); failures = []; proofs = []; measured = {}; interruption = None
    try:
        folder = scratch / 'verification/batch-0000'
        proof = run_owned({'kind': 'verify', 'formulas': formulas, 'folder': str(folder), 'seed': VERIFY_SEED},
                          scratch / 'verification-0000-worker.log', owner)
        if (proof.get('verified') is not True or proof.get('formula_count') != COUNT
                or proof.get('vectors_per_formula') != 2148 or proof.get('total_comparisons') != COUNT * 2148
                or proof.get('random_seed') != VERIFY_SEED
                or proof.get('v4_validation_override_sha256') != sha(ROOT / 'isaforge/v4_validation.py')
                or sha(folder / 'verification.v') != proof['rtl_sha256']
                or (folder / 'verification.v').read_text() != verification_source(formulas)
                or sha(folder / 'vectors.txt') != proof['vectors_sha256']):
            raise ValueError('Incomplete or changed original RTL verification')
        proofs.append(proof)
    except BaseException as error:
        failures.append({'stage': 'verification', 'error': repr(error)})
        if not isinstance(error, Exception): owner.cancel(); interruption = error
    write(output / 'verification.json', proofs)

    def measure(formula):
        folder = scratch / 'circuits' / hashlib.sha256(formula.encode()).hexdigest()[:20]
        if folder.exists(): raise ValueError('Fresh original circuit directory required')
        metric = run_owned({'kind': 'map', 'formula': formula, 'folder': str(folder),
                            'executable': executable, 'version': version}, folder / 'worker.log', owner)
        metric['tool_sha256'] = tool['executable_sha256']
        original = generate_rtl(formula).encode()
        if (metric.get('formula') != formula or metric.get('tool') != version
                or metric.get('measurement_source') != 'rtl_synthesis'
                or metric['rtl_sha256'] != hashlib.sha256(original).hexdigest()
                or (folder / 'candidate.v').read_bytes() != original):
            raise ValueError('Mapped target is not approved original RTL')
        for name, key in [('ice40.ys', 'script_sha256'), ('ice40.log', 'log_sha256'), ('ice40-netlist.json', 'netlist_sha256')]:
            if sha(folder / name) != metric[key]: raise ValueError('Mapped raw evidence hash differs')
        netlist = read(folder / 'ice40-netlist.json')
        cells = Counter(cell['type'] for cell in netlist['modules']['candidate'].get('cells', {}).values())
        if dict(cells) != metric['ice40_cell_types']: raise ValueError('Raw mapped cell recount differs')
        for key, cell in [('ice40_lut4_count', 'SB_LUT4'), ('ice40_carry_count', 'SB_CARRY')]:
            if integer(metric[key]) != cells[cell]: raise ValueError('Raw resource count differs')
        write(folder / 'metrics.json', metric)
        return metric

    if not failures:
        pool = ThreadPoolExecutor(max_workers=2)
        try:
            futures = {pool.submit(measure, f): f for f in formulas}
            for future in as_completed(futures):
                formula = futures[future]
                try: measured[formula] = future.result()
                except Exception as error: failures.append({'stage': 'synthesis', 'formula': formula, 'error': repr(error)})
                write(output / 'progress.json', {'unique_completed': len(measured), 'unique_total': COUNT, 'failures': failures})
        except BaseException as error:
            owner.cancel(); interruption = error; failures.append({'stage': 'cancellation', 'error': repr(error)})
        finally: pool.shutdown(wait=True, cancel_futures=True)
    if any(not p.is_file() or sha(p) != h for p, h in bindings.items()):
        failures.append({'stage': 'provenance', 'error': 'Bound source/preparation/approval changed during collection'})
    if sha(executable) != tool['executable_sha256']:
        failures.append({'stage': 'provenance', 'error': 'Frozen Yosys binary changed during collection'})
    unique = [measured[f] for f in formulas if f in measured]
    labels = [{**row, 'lut4_count': measured[row['formula']]['ice40_lut4_count'],
               'carry_count': measured[row['formula']]['ice40_carry_count'],
               'rtl_sha256': measured[row['formula']]['rtl_sha256'],
               'measurement_source': 'rtl_synthesis', 'correctness_verified': True}
              for row in candidates if row['formula'] in measured]
    write(output / 'unique-measurements.json', unique); write(output / 'labels.json', labels)
    done = {'schema': 'isaforge-v9-coverage-measurements-v1', 'complete': not failures and len(labels) == COUNT,
            'failures': failures, 'attempt': attempt, 'candidate_count': COUNT, 'unique_original_formulas': len(labels),
            'preparation_sha256': identity['preparation_sha256'], 'recipe_sha256': identity['recipe_sha256'],
            'candidates_sha256': identity['candidates_sha256'], 'approval_sha256': identity['approval_sha256'],
            'freeze_commit': review['freeze_commit'],
            'verification_seed': VERIFY_SEED, 'vectors_per_formula': 2148, 'verification_batch_sizes': [COUNT],
            'labels_sha256': sha(output / 'labels.json'), 'unique_measurements_sha256': sha(output / 'unique-measurements.json'),
            'verification_sha256': sha(output / 'verification.json'), 'collector_sha256': sha(__file__),
            'release_sha256': sha(release_path), 'frozen_tool': tool, 'workers': 2,
            'original_rtl_only': True, 'legacy_measurements_reused': False, 'new_estimator_fits': 0,
            'new_physical_measurements': len(unique), 'scratch_directory': scratch.relative_to(ROOT).as_posix(),
            'completed_at_utc': now()}
    write(output / 'completion.json', done); write(directory / 'completion.json', done)
    pack(root)  # Failed attempts are archived inside their own retained stage.
    if interruption is not None: raise interruption
    if not done['complete']: raise RuntimeError('Incomplete coverage measurements retained; fitting blocked')
    return done


def pack(root):
    root = Path(root).resolve(); directory = root / 'measurements'; done = read(directory / 'completion.json')
    attempt = done['attempt']
    if not isinstance(attempt, str) or not re.fullmatch('attempt-[0-9]{4}', attempt): raise ValueError('Owned attempt required')
    scratch = ROOT / PREFIX / attempt
    if done['scratch_directory'] != scratch.relative_to(ROOT).as_posix(): raise ValueError('Owned scratch identity differs')
    destination(PREFIX + attempt + '/member', ROOT, attempt)
    stage = directory / attempt
    if read(stage / 'completion.json') != done: raise ValueError('Stage and root completion differ')
    validate_completed_files(stage, done)
    archive_dir = directory if done['complete'] is True else stage
    archive = archive_dir / 'raw-evidence.zip'; manifest_path = archive_dir / 'raw-evidence.json'
    if archive.exists() or manifest_path.exists(): raise ValueError('Raw evidence archive is immutable')
    records = []
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as stream:
        for path in sorted(scratch.rglob('*')):
            if path.is_symlink(): raise ValueError('Symlink raw evidence forbidden')
            if not path.is_file() or {'obj_dir', 'obj_dir_wrapv'}.intersection(path.parts): continue
            name = path.relative_to(ROOT).as_posix(); destination(name, ROOT, attempt); data = path.read_bytes()
            info = zipfile.ZipInfo(name, date_time=(2026, 10, 15, 0, 0, 0)); info.compress_type = zipfile.ZIP_DEFLATED; info.external_attr = 0o100644 << 16
            stream.writestr(info, data, compresslevel=9)
            records.append({'path': name, 'size': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
    manifest = {'schema': 'isaforge-v9-coverage-raw-evidence-v1', 'archive': archive.name,
                'archive_sha256': sha(archive), 'attempt': attempt, 'complete': done['complete'], 'files': records,
                'completion_sha256': sha(archive_dir / 'completion.json'), 'compiler_objects_included': False}
    write(manifest_path, manifest)
    return manifest


def validate_completed_files(stage, done):
    if type(done.get('complete')) is not bool or (done['complete'] and done.get('failures') != []):
        raise ValueError('Consistent complete/failure status required')
    for name, key in [('labels.json', 'labels_sha256'), ('unique-measurements.json', 'unique_measurements_sha256'),
                      ('verification.json', 'verification_sha256')]:
        if sha(stage / name) != done[key]: raise ValueError('Completed coverage output changed: ' + name)


def verify_archive(root, *, attempt=None):
    directory = Path(root).resolve() / 'measurements'
    if attempt is not None:
        if not re.fullmatch('attempt-[0-9]{4}', attempt): raise ValueError('Owned attempt required')
        directory /= attempt
    manifest = read(directory / 'raw-evidence.json')
    if manifest.get('schema') != 'isaforge-v9-coverage-raw-evidence-v1' or manifest.get('archive') != 'raw-evidence.zip':
        raise ValueError('Coverage raw archive identity differs')
    archive = directory / 'raw-evidence.zip'
    if sha(archive) != manifest['archive_sha256'] or sha(directory / 'completion.json') != manifest['completion_sha256']:
        raise ValueError('Coverage raw archive/completion digest differs')
    done = read(directory / 'completion.json')
    if manifest['attempt'] != done['attempt'] or manifest['complete'] is not done['complete']:
        raise ValueError('Raw archive attempt/status differs')
    stage = Path(root).resolve() / 'measurements' / done['attempt']
    validate_completed_files(stage, done)
    records = {r['path']: r for r in manifest['files']}
    if len(records) != len(manifest['files']): raise ValueError('Duplicate raw manifest records')
    with zipfile.ZipFile(archive) as stream:
        names = stream.namelist()
        if len(names) != len(set(names)) or set(names) != set(records): raise ValueError('Raw archive inventory differs')
        for info in stream.infolist():
            destination(info.filename, ROOT, manifest['attempt'])
            data = stream.read(info); record = records[info.filename]
            if (info.is_dir() or ((info.external_attr >> 16) & 0o170000) not in (0, 0o100000)
                    or type(record['size']) is not int or len(data) != record['size']
                    or hashlib.sha256(data).hexdigest() != record['sha256']):
                raise ValueError('Coverage raw archived member differs')
    return archive


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('collect', 'pack', 'verify'))
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--approval', type=Path)
    parser.add_argument('--workers', type=int, default=2)
    parser.add_argument('--attempt', default='attempt-0000')
    args = parser.parse_args()
    if args.action == 'collect':
        if args.approval is None: parser.error('collect requires --approval root/measurement-approval.json')
        result = collect(args.root, args.approval, workers=args.workers, attempt=args.attempt)
    else: result = pack(args.root) if args.action == 'pack' else {'archive': str(verify_archive(args.root))}
    print(json.dumps(result, indent=2))
