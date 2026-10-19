"""Label-independent v4 development/test acquisition and iCE40 measurement.

The inspected v3 probe is excluded and is development evidence only. Test
measurement requires an explicit release manifest linking frozen model artifacts
and complete label-free predictions. No model module is imported here.
"""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import random
import shutil
import subprocess
import time

from .features import candidate_id, parse_formula
from .probe_corpus import STRATA, _draw, excluded_formulas, formula_shape
from .rtl import generate_rtl, verify_rtl_batch
from .synthesis import _yosys_quote, netlist_metrics

DEVELOPMENT_SEED = 2026101401
TEST_SEED = 2026101402
MUL_OPS = ('mul', 'mulh', 'mulhu', 'mulhsu')
MUL_REGIMES = ('negative_constant', 'unit_constant', 'power_constant',
               'near_power_constant', 'sparse_variable', 'narrow_variable',
               'dense_variable', 'sign_extended_variable')


def _bytes(value):
    return (json.dumps(value, indent=2, allow_nan=False) + '\n').encode()


def _write(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_bytes(value))


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _sources():
    here = Path(__file__).parent
    return {name: _sha(here / name) for name in
            ('v4_corpus.py', 'probe_corpus.py', 'features.py', 'rtl.py', 'synthesis.py')}


def _multiply(slot, rng):
    op, regime = MUL_OPS[slot % 4], MUL_REGIMES[(slot // 4) % 8]
    a, b = rng.sample(('in0', 'in1'), 2)
    left_op = rng.choice(('addi', 'andi', 'xori'))
    left_c = rng.choice((-2047, -1023, -257, -33, -1, 3, 7, 17, 63, 129, 511, 2047, 65535))
    left = f'{left_op}({a},{left_c})'
    if regime == 'negative_constant':
        right = str(rng.choice((-3, -5, -7, -17, -129, -257, -1023, -2047, -65535)))
    elif regime == 'unit_constant':
        right = str(rng.choice((-1, 0, 1)))
    elif regime == 'power_constant':
        right = str(1 << rng.choice((1, 4, 8, 15, 16, 24, 30, 31)))
    elif regime == 'near_power_constant':
        right = str((1 << rng.choice((3, 5, 8, 11, 16, 24, 30))) + rng.choice((-1, 1)))
    elif regime == 'sparse_variable':
        right = f'andi({b},{rng.choice((1, 256, 65536, 2147483648, 257, 65537, 2147483649, 16777217))})'
    elif regime == 'narrow_variable':
        right = f'andi({b},{(1 << rng.choice((2, 3, 5, 8, 11, 16))) - 1})'
    elif regime == 'dense_variable':
        right = f'xori({b},{rng.choice((-1, 3, 255, 1431655765, 2863311530))})'
    else:
        right = f'srai({b},{rng.choice((1, 8, 16, 24, 31))})'
    wrapper = rng.choice(('addi', 'xori', 'andi', 'srli', 'srai'))
    operand = (rng.choice((0, 1, 3, 7, 13, 16, 24, 30, 31)) if wrapper in ('srli', 'srai') else
               rng.choice((-1, 0, 1, 3, 7, 31, 255, 65535, 2147483647)))
    formula = f'{wrapper}({op}({left},{right}),{operand})'
    return formula, {'template': f'{wrapper}({op}(transform(input),{regime}),immediate)',
                     'operand_regime': regime, 'multiply_variant': op,
                     'left_transform': left_op, 'output_transform': wrapper}


def generate(excluded, count, seed, cohort):
    if cohort not in ('development', 'test'):
        raise ValueError('unknown cohort')
    if isinstance(count, bool) or count <= 0 or count % 32:
        raise ValueError('count must be a positive multiple of 32')
    rng = random.Random(seed)
    seen = {parse_formula(f).canonical() for f in excluded}; rows = []
    for stratum in STRATA:
        for slot in range(count // 8):
            for attempt in range(100000):
                if stratum == 'multiplication':
                    formula, metadata = _multiply(slot, rng)
                else:
                    formula = _draw(stratum, rng)
                    metadata = {'template': stratum, 'operand_regime': stratum}
                formula = parse_formula(formula).canonical()
                operations, inputs = formula_shape(formula)
                if formula not in seen and 2 <= operations <= 4 and 1 <= inputs <= 2:
                    break
            else:
                raise ValueError('could not populate predeclared stratum/regime')
            seen.add(formula)
            benchmark = f'v4_{cohort}_{stratum}'
            rows.append({'benchmark': benchmark, 'candidate_id': candidate_id(benchmark, formula),
                         'formula': formula, 'stratum': stratum, 'cohort': cohort,
                         'distinct_operation_count': operations, 'input_count': inputs,
                         'generation_slot': slot, **metadata,
                         'provenance': 'synthetic formula; no executed workload; no model or label acquisition'})
    return rows


def freeze(exclusions, root):
    root = Path(root)
    old = excluded_formulas(exclusions)
    if len(old) != 905:
        raise ValueError('expected 713 old training plus 192 inspected probe formulas')
    development = generate(old, 384, DEVELOPMENT_SEED, 'development')
    test_excluded = old | {r['formula'] for r in development}
    test = generate(test_excluded, 256, TEST_SEED, 'test')
    for cohort, rows, excluded, seed in (
            ('development', development, old, DEVELOPMENT_SEED),
            ('test', test, test_excluded, TEST_SEED)):
        directory = root / cohort
        core = {'protocol_version': 4, 'cohort': cohort, 'seed': seed,
                'candidate_count': len(rows), 'excluded_formula_count': len(excluded),
                'candidate_sha256': hashlib.sha256(_bytes(rows)).hexdigest(),
                'excluded_sha256': hashlib.sha256(_bytes(sorted(excluded))).hexdigest(),
                'stratum_counts': dict(Counter(r['stratum'] for r in rows)),
                'multiplication_regime_counts': dict(Counter(r['operand_regime'] for r in rows if r['stratum'] == 'multiplication')),
                'runtime_source_sha256': _sources(),
                'exclusion_source_sha256': {str(Path(p)): _sha(p) for p in exclusions},
                'target': 'isolated default Yosys synth_ice40 SB_LUT4; no DSP or place-and-route',
                'label_access': 'development immediate; test requires explicit parent release after model and predictions freeze',
                'limitations': ['Synthetic formulas are not real workload transfer.',
                                'Exact exclusion does not prove graph-family or semantic independence.',
                                'Sampled RTL oracle validation is not formal equivalence.',
                                'This v4 design uses inspected v3 findings; v3 is development evidence.']}
        existing = directory / 'freeze.json'
        if existing.exists():
            saved = json.loads(existing.read_text())
            if any(saved.get(k) != v for k, v in core.items()) or _sha(directory / 'candidates.json') != core['candidate_sha256']:
                raise ValueError('frozen acquisition changed')
        else:
            if directory.exists() and any(directory.iterdir()):
                raise ValueError('nonempty acquisition directory without freeze')
            core['frozen_at_utc'] = datetime.now(timezone.utc).isoformat()
            _write(directory / 'candidates.json', rows)
            _write(directory / 'excluded-formulas.json', sorted(excluded))
            _write(existing, core)
    return development, test


def _validate_release(path, rows, frozen):
    release = json.loads(Path(path).read_text())
    if release.get('test_candidate_sha256') != frozen['candidate_sha256'] or release.get('authorized_by_parent') is not True:
        raise ValueError('test release must explicitly authorize the frozen candidate pool')
    if not release.get('model_artifacts') or not release.get('prediction_artifacts'):
        raise ValueError('test release requires frozen models and complete predictions')
    for category in ('model_artifacts', 'prediction_artifacts'):
        for item in release[category]:
            if _sha(item['path']) != item['sha256']:
                raise ValueError('released artifact hash changed')
            if category == 'prediction_artifacts':
                predictions = json.loads(Path(item['path']).read_text())
                if len(predictions) != len(rows) or {r['formula'] for r in predictions} != {r['formula'] for r in rows}:
                    raise ValueError('released predictions must cover the entire test pool')
    return {'path': str(Path(path).resolve()), 'sha256': _sha(path), 'manifest': release}


def _ice40(formula, directory, executable, version):
    directory = Path(directory); directory.mkdir(parents=True, exist_ok=True)
    rtl = directory / 'candidate.v'; rtl.write_text(generate_rtl(formula))
    script = directory / 'ice40.ys'; netlist = directory / 'ice40-netlist.json'
    script.write_text(f'read_verilog {_yosys_quote(rtl.resolve())}\nsynth_ice40 -top candidate\ncheck -assert\nwrite_json {_yosys_quote(netlist.resolve())}\nstat\n')
    try:
        run = subprocess.run([executable, '-s', str(script)], capture_output=True, text=True, timeout=300)
    except subprocess.TimeoutExpired as error:
        out = error.stdout or b''; err = error.stderr or b''
        (directory / 'ice40.log').write_bytes((out.encode() if isinstance(out, str) else out) + (err.encode() if isinstance(err, str) else err))
        raise
    (directory / 'ice40.log').write_text(run.stdout + run.stderr)
    if run.returncode:
        raise RuntimeError(f'Yosys exit {run.returncode}; see {directory / "ice40.log"}')
    mapped = netlist_metrics(json.loads(netlist.read_text()))
    result = {'formula': formula, 'tool': version, 'measurement_source': 'rtl_synthesis',
              'ice40_lut4_count': mapped['cell_types'].get('SB_LUT4', 0),
              'ice40_carry_count': mapped['cell_types'].get('SB_CARRY', 0),
              'ice40_cell_types': mapped['cell_types'], 'rtl_sha256': _sha(rtl),
              'netlist_sha256': _sha(netlist), 'script_sha256': _sha(script), 'log_sha256': _sha(directory / 'ice40.log'),
              'command': [executable, '-s', str(script)], 'generic_measurement': 'omitted; irrelevant to LUT4 label',
              'measured_at_utc': datetime.now(timezone.utc).isoformat()}
    _write(directory / 'metrics.json', result)
    return result


def collect(root, generated_root, cohort, workers=4, release=None):
    if not 1 <= workers <= 4:
        raise ValueError('workers must be between one and four')
    directory = Path(root) / cohort; generated = Path(generated_root) / cohort
    frozen = json.loads((directory / 'freeze.json').read_text())
    rows = json.loads((directory / 'candidates.json').read_text())
    if _sha(directory / 'candidates.json') != frozen['candidate_sha256'] or frozen['runtime_source_sha256'] != _sources():
        raise ValueError('acquisition/source integrity failure')
    release_record = None
    if cohort == 'test':
        if release is None:
            raise ValueError('test labels sealed until explicit model/prediction freeze release')
        release_record = _validate_release(release, rows, frozen)
        _write(directory / 'release.json', release_record)
    executable = shutil.which('yosys')
    if executable is None:
        raise RuntimeError('Yosys required')
    version = subprocess.run([executable, '-V'], check=True, capture_output=True, text=True).stdout.strip()
    verification = verify_rtl_batch([r['formula'] for r in rows], generated / 'verification', seed=frozen['seed'], random_vectors=2048, timeout=300)
    _write(directory / 'verification.json', verification)
    print(f'Correctness verified: {cohort} {len(rows)} circuits', flush=True)
    started = time.monotonic(); measured = {}; failures = []
    def measure(row):
        folder = generated / 'circuits' / hashlib.sha256(row['formula'].encode()).hexdigest()[:20]
        metrics = folder / 'metrics.json'
        if metrics.exists():
            cached = json.loads(metrics.read_text())
            if cached['formula'] == row['formula'] and cached['tool'] == version and cached['rtl_sha256'] == hashlib.sha256(generate_rtl(row['formula']).encode()).hexdigest() and _sha(folder / 'ice40-netlist.json') == cached['netlist_sha256']:
                return cached
        return _ice40(row['formula'], folder, executable, version)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(measure, row): row for row in rows}
        for future in as_completed(futures):
            row = futures[future]
            try:
                measured[row['formula']] = future.result()
            except Exception as error:
                failures.append({'formula': row['formula'], 'error': str(error)})
            _write(directory / 'progress.json', {'cohort': cohort, 'completed': len(measured), 'total': len(rows), 'failures': failures, 'elapsed_seconds': time.monotonic() - started})
            if (len(measured) + len(failures)) % 16 == 0:
                print(f'{cohort}: {len(measured)}/{len(rows)} measured; {len(failures)} failures', flush=True)
    labeled = []
    for row in rows:
        if row['formula'] in measured:
            m = measured[row['formula']]
            labeled.append({**row, 'lut4_count': m['ice40_lut4_count'], 'carry_count': m['ice40_carry_count'],
                            'measurement_source': 'rtl_synthesis', 'correctness_verified': True,
                            'rtl_sha256': m['rtl_sha256'], 'synthesis_tool': version})
    _write(directory / 'dataset.json', labeled)
    complete = len(labeled) == len(rows) and not failures
    _write(directory / 'completion.json', {'complete': complete, 'cohort': cohort, 'candidate_count': len(rows),
                                          'measured_count': len(labeled), 'failures': failures,
                                          'freeze_sha256': _sha(directory / 'freeze.json'),
                                          'dataset_sha256': _sha(directory / 'dataset.json'),
                                          'verification_sha256': _sha(directory / 'verification.json'),
                                          'release': release_record, 'tool': version,
                                          'elapsed_seconds': time.monotonic() - started})
    if not complete:
        raise RuntimeError('collection incomplete; failures retained')
    return labeled


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exclude', action='append', type=Path)
    parser.add_argument('--root', type=Path, default=Path('results/2026-10-13-v4/corpus'))
    parser.add_argument('--generated-root', type=Path, default=Path('generated/v4-corpus'))
    parser.add_argument('--freeze', action='store_true')
    parser.add_argument('--collect', choices=('development', 'test'))
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--release', type=Path)
    args = parser.parse_args(argv)
    if args.freeze:
        if not args.exclude:
            parser.error('--freeze requires --exclude corpora')
        dev, test = freeze(args.exclude, args.root)
        print(f'Frozen development={len(dev)} test={len(test)} with separate seeds', flush=True)
    if args.collect:
        collect(args.root, args.generated_root, args.collect, args.workers, args.release)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
