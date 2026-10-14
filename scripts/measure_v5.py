#!/usr/bin/env python3
"""Measure a sealed V5 cohort; test measurement requires frozen predictions."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from isaforge.rtl import generate_rtl
from isaforge.v4_corpus import _ice40
from isaforge.v4_validation import verify_wrapping


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def collect(root, cohort, generated, workers=4):
    directory = root / 'corpus' / cohort
    candidates = directory / 'candidates.json'
    rows = json.loads(candidates.read_text())
    if not rows or len({r['formula'] for r in rows}) != len(rows):
        raise ValueError('Expected unique, nonempty cohort')
    release = None
    if cohort == 'test':
        # The scorer validates every source, artifact and prediction before labels exist.
        from evaluate_v5 import validate_freeze
        validate_freeze(root)
        release = {'authorized_after_freeze': True, 'freeze_sha256': sha(root/'freeze.json'),
                   'candidate_sha256': sha(candidates),
                   'released_at_utc': datetime.now(timezone.utc).isoformat()}
        if (root/'label-release.json').exists():
            release = json.loads((root/'label-release.json').read_text())
            if release['freeze_sha256'] != sha(root/'freeze.json'):
                raise ValueError('Existing release is for a different freeze')
        else:
            write(root/'label-release.json', release)
    executable = shutil.which('yosys')
    if executable is None:
        raise RuntimeError('Yosys required')
    version = subprocess.check_output([executable, '-V'], text=True).strip()
    generated = generated / cohort
    started = time.perf_counter()
    verification = []
    # Independent batches keep compiler resource use bounded and retain every circuit.
    for start in range(0, len(rows), 128):
        chunk = rows[start:start+128]
        result = verify_wrapping([r['formula'] for r in chunk],
                                generated/'verification'/f'batch-{start:04d}',
                                seed=2026101419+start, random_vectors=2048, timeout=300)
        if result.get('verified') is not True:
            raise ValueError('Verification did not pass')
        verification.append(result)
        print(f'{cohort}: verified {start+len(chunk)}/{len(rows)}', flush=True)
    write(directory/'verification.json', verification)
    measured, failures = {}, []

    def measure(row):
        folder = generated/'circuits'/hashlib.sha256(row['formula'].encode()).hexdigest()[:20]
        path = folder/'metrics.json'
        if path.exists():
            old = json.loads(path.read_text())
            if (old['formula'] == row['formula'] and old['tool'] == version
                    and old['rtl_sha256'] == hashlib.sha256(generate_rtl(row['formula']).encode()).hexdigest()
                    and all(sha(folder/name) == old[field] for name, field in
                            [('ice40-netlist.json', 'netlist_sha256'), ('ice40.ys', 'script_sha256'),
                             ('ice40.log', 'log_sha256')])):
                return old
        return _ice40(row['formula'], folder, executable, version)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        tasks = {pool.submit(measure, row): row for row in rows}
        for future in as_completed(tasks):
            row = tasks[future]
            try:
                measured[row['formula']] = future.result()
            except Exception as error:
                failures.append({'formula': row['formula'], 'error': str(error)})
            write(directory/'progress.json', {'completed': len(measured), 'total': len(rows),
                  'failures': failures, 'elapsed_seconds': time.perf_counter()-started})
            if (len(measured)+len(failures)) % 32 == 0:
                print(f'{cohort}: measured {len(measured)}/{len(rows)}, failed {len(failures)}', flush=True)
    labeled = [{**r, 'lut4_count': measured[r['formula']]['ice40_lut4_count'],
                'carry_count': measured[r['formula']]['ice40_carry_count'],
                'measurement_source': 'rtl_synthesis', 'correctness_verified': True,
                'rtl_sha256': measured[r['formula']]['rtl_sha256'], 'synthesis_tool': version}
               for r in rows if r['formula'] in measured]
    write(directory/'dataset.json', labeled)
    write(directory/'completion.json', {'complete': not failures and len(labeled) == len(rows),
          'candidate_sha256': sha(candidates), 'dataset_sha256': sha(directory/'dataset.json'),
          'verification_sha256': sha(directory/'verification.json'), 'failures': failures,
          'formula_count': len(rows), 'measured_count': len(labeled), 'release': release,
          'tool': version, 'tool_sha256': sha(executable),
          'collector_sha256': sha(__file__), 'elapsed_seconds': time.perf_counter()-started})
    if failures:
        raise RuntimeError('Incomplete collection; all failures retained')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT/'results/2026-10-14-v5')
    parser.add_argument('--cohort', choices=('development', 'test'), required=True)
    parser.add_argument('--generated', type=Path, default=ROOT/'generated/v5-corpus')
    args = parser.parse_args()
    collect(args.root, args.cohort, args.generated)
