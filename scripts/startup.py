#!/usr/bin/env python3
"""Local startup checks and real, reproducible cached-model inference."""
from __future__ import annotations
import argparse
from importlib.metadata import PackageNotFoundError, version
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def dependencies():
    problems = []
    if sys.version_info < (3, 11):
        problems.append('Python 3.11+ required')
    for line in (ROOT / 'requirements-research.txt').read_text().splitlines():
        if not line or line.startswith('#'):
            continue
        name, expected = line.split('==')
        try:
            actual = version(name)
        except PackageNotFoundError:
            actual = 'missing'
        if actual != expected:
            problems.append(f'{name}: need {expected}, found {actual}')
    for name in ('pytest', 'matplotlib'):
        try:
            version(name)
        except PackageNotFoundError:
            problems.append(f'{name}: missing')
    if problems:
        raise ValueError('\n'.join(problems))


def check():
    dependencies()
    # Import after checking the exact serialized-model environment.
    from predict import load
    from reproduce import run
    load('base')  # authenticates weights, metadata, runtime source and versions
    if run() != json.loads((ROOT / 'results/summary.json').read_text()):
        raise ValueError('Saved benchmark summary differs from replay')
    print('Ready: pinned dependencies, base model and three benchmark datasets verified.')


def demo():
    from predict import run
    from reproduce import run as replay
    base = ROOT / 'generated/start'
    base.mkdir(parents=True, exist_ok=True)
    output = Path(tempfile.mkdtemp(prefix='run-', dir=base))
    result = run(ROOT / 'results/arithmetic-stress/candidates.json',
                 ROOT / 'results/arithmetic-stress/features.json', 'base',
                 output / 'predictions.json', output / 'features')
    observations = json.loads((ROOT / 'results/arithmetic-stress/observations.json').read_text())['rows']
    if len(result['predictions']) != len(observations):
        raise ValueError('Incomplete demo predictions')
    for predicted, measured in zip(result['predictions'], observations):
        if predicted['formula'] != measured['formula'] or predicted['predicted_lut4'] != measured['predictions']['base']:
            raise ValueError('Demo inference differs from the frozen benchmark')
    (output / 'summary.json').write_text(json.dumps(replay(), indent=2) + '\n')
    print('\nISAForge | RV32 formula → circuit features → predicted FPGA area\n')
    print(f'{"Formula":48} {"Predicted LUT4":>15} {"Measured LUT4":>15}')
    for predicted, measured in zip(result['predictions'][:3], observations[:3]):
        print(f'{predicted["formula"]:48} {predicted["predicted_lut4"]:15.2f} {measured["measured_lut4"]:15d}')
    print(f'\nVerified {len(observations)} real model predictions against saved results; zero fits or synthesis jobs.')
    print('Measured values are retained Yosys labels, not new measurements.')
    print('Area estimates are uncalibrated; synthesize before committing a hardware budget.')
    print(f'Outputs: {output}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--dependencies', action='store_true')
    mode.add_argument('--check', action='store_true')
    mode.add_argument('--demo', action='store_true')
    args = parser.parse_args()
    try:
        if args.dependencies:
            dependencies()
        elif args.check:
            check()
        else:
            dependencies()
            demo()
    except (ValueError, OSError, ImportError) as exc:
        print(f'ISAForge: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
