"""Replay the frozen six-model score, independent audit, and research figures.

Uses committed predictions; never trains a model or runs hardware synthesis.
"""
import argparse
import json
import math
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
RESULTS = Path('results/2026-10-13-v3')
MODELS = ('resource_v2', 'v1_xgboost_log', 'v2_residual_xgb',
          'v3_original', 'v3_structural', 'masterrtl_sog')
TRAINING = ('results/2026-10-13/dataset.json',
            'results/2026-10-13-prospective/transfer/dataset.json',
            'results/2026-10-13-prospective/final/dataset.json')


def run(module, args):
    subprocess.run([sys.executable, '-m', module, *map(str, args)], cwd=ROOT, check=True)


def same_metrics(actual, expected):
    """Permit platform floating-point roundoff; require identical structure/counts."""
    if isinstance(expected, dict):
        return (isinstance(actual, dict) and actual.keys() == expected.keys()
                and all(same_metrics(actual[k], v) for k, v in expected.items()))
    if isinstance(expected, float):
        return (isinstance(actual, (int, float)) and not isinstance(actual, bool)
                and math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-10))
    return type(actual) is type(expected) and actual == expected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'generated/reproduction')
    parser.add_argument('--skip-figures', action='store_true', help='Score and audit without Matplotlib')
    args = parser.parse_args()
    output = args.output.resolve()
    if output.is_relative_to(ROOT/'results'):
        parser.error('choose an output outside the frozen results directory')
    output.mkdir(parents=True, exist_ok=True)
    score_args = []
    for path in TRAINING: score_args.extend(['--training', path])
    score_args.extend(['--probe', RESULTS/'probe'])
    for path in ['models/preregistration.json', 'masterrtl/preregistration.json']:
        score_args.extend(['--model-freeze', RESULTS/path])
    for name in MODELS:
        score_args.extend(['--predictions', f'{name}={RESULTS}/probe-inference/{name}.json'])
    score_args.extend(['--output', output/'probe-evaluation.json'])
    run('isaforge.probe_evaluation', score_args)
    expected = json.loads((ROOT/RESULTS/'probe-evaluation.json').read_text())
    replay = json.loads((output/'probe-evaluation.json').read_text())
    if not same_metrics(replay['models'], expected['models']):
        raise RuntimeError('replayed metrics differ from the frozen research result')
    run('isaforge.probe_audit', ['--output-prefix', output/'independent-audit'])
    if not args.skip_figures:
        plot_args = ['--development', RESULTS/'models/development-evaluation.json',
                     '--reference-development', RESULTS/'masterrtl/development-evaluation.json',
                     '--probe', RESULTS/'probe-evaluation.json',
                     '--probe-dataset', RESULTS/'probe/dataset.json']
        for name in MODELS:
            plot_args.extend(['--prediction', f'{name}={RESULTS}/probe-inference/{name}.json',
                              '--timing', f'{name}={RESULTS}/probe-inference/{name}.timing.json'])
        plot_args.extend(['--masterrtl-cold-timing', RESULTS/'masterrtl/cold-probe-timing.json',
                          '--independent-audit', RESULTS/'independent-audit.json',
                          '--output', output/'figures'])
        run('isaforge.challenger_plots', plot_args)
    print(f'Six-model score replay verified (floating-point tolerance 1e-10 absolute / 1e-12 relative). Artifacts: {output}')


if __name__ == '__main__':
    main()
