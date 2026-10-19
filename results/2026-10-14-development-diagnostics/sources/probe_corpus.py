"""Freeze and measure novel synthetic RV32 formula stress tests.

This module has no model imports: candidate acquisition cannot use model scores
or synthesis labels. These are synthetic circuits, not independent workloads.
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
import subprocess
import time

from .features import candidate_id, parse_formula
from .rtl import generate_rtl, verify_rtl_batch
from .synthesis import run_synthesis


DEFAULT_SEED = 2026101303
STRATA = ('arithmetic_chain', 'shared_diamond', 'parallel_branches', 'mask_logic',
          'constant_shifts', 'variable_shifts', 'comparators', 'multiplication')
MASKS = (1, 3, 15, 255, 65535, 16777215, 1431655765, 2863311530,
         252645135, 4042322160, 2147483647, 2147483648, 4294967295)
CONSTANTS = (-2047, -257, -33, -1, 3, 5, 7, 17, 63, 129, 1023, 2047)
SHIFTS = (0, 1, 2, 4, 7, 8, 13, 16, 24, 30, 31)


def _json_bytes(value):
    return (json.dumps(value, indent=2, allow_nan=False) + '\n').encode()


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_json_bytes(value))


def formula_shape(formula):
    """Count distinct DAG operations and input leaves, retaining sharing."""
    operations, inputs = set(), set()
    def visit(node):
        if node.children:
            operations.add(node.canonical())
            for child in node.children:
                visit(child)
        elif node.value in ('in0', 'in1'):
            inputs.add(node.value)
    visit(parse_formula(formula))
    return len(operations), len(inputs)


def excluded_formulas(paths):
    """Read formula fields only; never use measured label values."""
    formulas = set()
    for path in paths:
        rows = json.loads(Path(path).read_text())
        if not isinstance(rows, list):
            raise ValueError('exclusion corpora must be row arrays')
        formulas.update(parse_formula(row['formula']).canonical() for row in rows)
    return formulas


def _draw(stratum, rng):
    a, b = rng.sample(('in0', 'in1'), 2)
    op = rng.choice(('add', 'sub', 'and', 'or', 'xor'))
    imm, mask, shift = rng.choice(CONSTANTS), rng.choice(MASKS), rng.choice(SHIFTS)
    if stratum == 'arithmetic_chain':
        inner = f'{op}({a},{b})'
        mid = f'{rng.choice(("addi", "xori", "andi"))}({inner},{imm if rng.randrange(2) else mask})'
        return f'{rng.choice(("add", "sub", "xor"))}({mid},{a})'
    if stratum == 'shared_diamond':
        shared = f'{op}({a},{b})'
        left = f'andi({shared},{mask})'
        right = f'{rng.choice(("slli", "srli", "srai"))}({shared},{shift})'
        return f'{rng.choice(("add", "sub", "or", "xor"))}({left},{right})'
    if stratum == 'parallel_branches':
        left = f'{rng.choice(("addi", "xori", "andi"))}({a},{imm})'
        right = f'{rng.choice(("slli", "srli", "srai"))}({b},{shift})'
        merged = f'{op}({left},{right})'
        return f'{rng.choice(("andi", "xori", "ori"))}({merged},{mask})'
    if stratum == 'mask_logic':
        left = f'andi({a},{mask})'
        right = f'andi({b},{rng.choice(MASKS)})'
        return f'{rng.choice(("and", "or", "xor", "add"))}({left},{right})'
    if stratum == 'constant_shifts':
        left = f'{rng.choice(("slli", "srli", "srai"))}({a},{shift})'
        combined = f'{op}({left},{b})'
        return f'{rng.choice(("slli", "srli", "srai"))}({combined},{rng.choice(SHIFTS)})'
    if stratum == 'variable_shifts':
        value = f'{rng.choice(("addi", "xori", "andi"))}({a},{imm})'
        amount = f'andi({b},{rng.choice((1, 3, 7, 15, 31, 63, 255))})'
        return f'{rng.choice(("sll", "srl", "sra"))}({value},{amount})'
    if stratum == 'comparators':
        left = f'{rng.choice(("addi", "andi", "xori"))}({a},{imm})'
        compare = f'{rng.choice(("slt", "sltu"))}({left},{b})'
        return f'{rng.choice(("slli", "addi", "xori"))}({compare},{shift})'
    if stratum == 'multiplication':
        # Equal probability constant and variable multiplies; the latter use
        # a declared input mask, spanning narrow and full-width multipliers.
        left = f'{rng.choice(("addi", "andi", "xori"))}({a},{imm})'
        right = str(rng.choice(CONSTANTS)) if rng.randrange(2) else f'andi({b},{mask})'
        product = f'{rng.choice(("mul", "mulh", "mulhu", "mulhsu"))}({left},{right})'
        return f'{rng.choice(("addi", "xori", "srli"))}({product},{shift})'
    raise ValueError('unknown stratum')


def generate_candidates(excluded, *, count=192, seed=DEFAULT_SEED):
    if isinstance(count, bool) or not isinstance(count, int) or count < len(STRATA) or count % len(STRATA):
        raise ValueError('count must be a positive multiple of eight')
    excluded = {parse_formula(f).canonical() for f in excluded}
    rng, seen, rows = random.Random(seed), set(excluded), []
    for stratum in STRATA:
        accepted, attempts = 0, 0
        while accepted < count // len(STRATA):
            attempts += 1
            if attempts > 100000:
                raise ValueError('cannot populate novel stratum')
            formula = parse_formula(_draw(stratum, rng)).canonical()
            operations, inputs = formula_shape(formula)
            if formula in seen or not 2 <= operations <= 4 or not 1 <= inputs <= 2:
                continue
            seen.add(formula)
            benchmark = 'synthetic_probe_' + stratum
            rows.append({'benchmark': benchmark, 'candidate_id': candidate_id(benchmark, formula),
                         'formula': formula, 'stratum': stratum,
                         'distinct_operation_count': operations, 'input_count': inputs,
                         'provenance': 'synthetic formula stress test; no executed workload'})
            accepted += 1
    return rows


def freeze_candidates(exclusions, output, *, count=192, seed=DEFAULT_SEED,
                      expected_excluded_count=None):
    output = Path(output)
    excluded = excluded_formulas(exclusions)
    if expected_excluded_count is not None and len(excluded) != expected_excluded_count:
        raise ValueError('unexpected existing formula union; refusing to freeze')
    candidates = generate_candidates(excluded, count=count, seed=seed)
    core = {'protocol_version': 1, 'seed': seed, 'candidate_count': count,
            'stratum_counts': dict(sorted(Counter(r['stratum'] for r in candidates).items())),
            'generator_sha256': _sha(__file__),
            'rtl_source_sha256': _sha(Path(__file__).with_name('rtl.py')),
            'synthesis_source_sha256': _sha(Path(__file__).with_name('synthesis.py')),
            'exclusion_source_sha256': {str(Path(p)): _sha(p) for p in exclusions},
            'excluded_formula_count': len(excluded),
            'excluded_formulas_sha256': hashlib.sha256(_json_bytes(sorted(excluded))).hexdigest(),
            'candidate_sha256': hashlib.sha256(_json_bytes(candidates)).hexdigest(),
            'acquisition': 'equal predeclared strata; seeded graph-pattern generation; exact canonical exclusion',
            'measurement_target': 'isolated RV32 combinational datapath, Yosys default iCE40 LUT4/carry mapping',
            'label_access': 'collect only after candidate freeze; do not disclose or score before model v3 freeze',
            'limitations': ['Synthetic formulas are not independent real workloads.',
                            'Not a published-system comparison or architecture speedup measurement.',
                            'Canonical identity exclusion does not imply semantic or graph-family independence.',
                            'Random/boundary RTL oracle comparisons are not formal equivalence.']}
    frozen_path = output / 'freeze.json'
    if frozen_path.exists():
        frozen = json.loads(frozen_path.read_text())
        if ({k: frozen[k] for k in core} != core
                or _sha(output / 'candidates.json') != core['candidate_sha256']
                or _sha(output / 'excluded-formulas.json') != core['excluded_formulas_sha256']):
            raise ValueError('frozen acquisition or source changed; refusing replacement')
        return candidates, frozen
    if output.exists() and any(output.iterdir()):
        raise ValueError('nonempty destination without freeze; refusing replacement')
    output.mkdir(parents=True, exist_ok=True)
    # Freeze files precede every correctness or synthesis tool invocation.
    _write(output / 'candidates.json', candidates)
    _write(output / 'excluded-formulas.json', sorted(excluded))
    core['frozen_at_utc'] = datetime.now(timezone.utc).isoformat()
    _write(frozen_path, core)
    return candidates, core


def collect_probe(candidates, frozen, output, *, workers=2, random_vectors=2048):
    output = Path(output)
    if workers < 1:
        raise ValueError('workers must be positive')
    if (_sha(output / 'candidates.json') != frozen['candidate_sha256']
            or hashlib.sha256(_json_bytes(candidates)).hexdigest() != frozen['candidate_sha256']
            or _sha(__file__) != frozen['generator_sha256']
            or _sha(Path(__file__).with_name('rtl.py')) != frozen['rtl_source_sha256']
            or _sha(Path(__file__).with_name('synthesis.py')) != frozen['synthesis_source_sha256']):
        raise ValueError('candidate freeze integrity failure')
    formulas = [r['formula'] for r in candidates]
    verification = verify_rtl_batch(formulas, output / 'verification', seed=frozen['seed'],
                                    random_vectors=random_vectors, timeout=300)
    _write(output / 'verification.json', verification)
    print(f"Verified actual RTL for {len(formulas)} frozen formulas", flush=True)
    version = subprocess.run(['yosys', '-V'], check=True, capture_output=True, text=True).stdout.strip()
    started, measured, failures = time.monotonic(), {}, []
    def measure(formula):
        folder = output / 'circuits' / hashlib.sha256(formula.encode()).hexdigest()[:20]
        metrics_path = folder / 'metrics.json'
        if metrics_path.exists():
            metrics = json.loads(metrics_path.read_text())
            if (metrics.get('formula') == formula and metrics.get('tool') == version
                    and metrics.get('rtl_sha256') == hashlib.sha256(generate_rtl(formula).encode()).hexdigest()
                    and 'ice40_lut4_count' in metrics):
                return metrics
        return run_synthesis(formula, folder, timeout=300)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(measure, f): f for f in formulas}
        for future in as_completed(futures):
            formula = futures[future]
            try:
                measured[formula] = future.result()
            except Exception as error:
                failures.append({'formula': formula, 'error': str(error)})
            _write(output / 'progress.json', {'completed': len(measured), 'total': len(formulas),
                                            'failures': failures, 'elapsed_seconds': time.monotonic() - started})
            print(f"Completed {len(measured)}/{len(formulas)} circuits; {len(failures)} failures", flush=True)
    rows = []
    for row in candidates:
        if row['formula'] not in measured:
            continue
        metrics = measured[row['formula']]
        rows.append(dict(row, lut4_count=metrics['ice40_lut4_count'],
                         carry_count=metrics['ice40_carry_count'],
                         generic_cell_count=metrics['generic_cell_count'],
                         generic_logic_depth=metrics['generic_logic_depth'],
                         measurement_source='rtl_synthesis', correctness_verified=True,
                         rtl_sha256=metrics['rtl_sha256'], synthesis_tool=metrics['tool']))
    _write(output / 'dataset.json', rows)
    complete = not failures and len(rows) == len(candidates)
    _write(output / 'completion.json', {'complete': complete, 'candidate_count': len(candidates),
                                      'verified_circuit_count': verification['formula_count'],
                                      'measured_circuit_count': len(rows), 'failures': failures,
                                      'freeze_sha256': _sha(output / 'freeze.json'),
                                      'dataset_sha256': _sha(output / 'dataset.json'),
                                      'elapsed_seconds': time.monotonic() - started,
                                      'limitations': frozen['limitations']})
    if not complete:
        raise RuntimeError('probe collection incomplete; see progress.json')
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exclude', type=Path, action='append', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--count', type=int, default=192)
    parser.add_argument('--seed', type=int, default=DEFAULT_SEED)
    parser.add_argument('--expected-excluded-count', type=int, default=713)
    parser.add_argument('--workers', type=int, default=2)
    parser.add_argument('--random-vectors', type=int, default=2048)
    parser.add_argument('--freeze-only', action='store_true')
    args = parser.parse_args(argv)
    candidates, frozen = freeze_candidates(args.exclude, args.output, count=args.count, seed=args.seed,
                                           expected_excluded_count=args.expected_excluded_count)
    print(f"Frozen {len(candidates)} novel synthetic formulas; excluded {frozen['excluded_formula_count']}", flush=True)
    if not args.freeze_only:
        collect_probe(candidates, frozen, args.output, workers=args.workers, random_vectors=args.random_vectors)


if __name__ == '__main__':
    main()
