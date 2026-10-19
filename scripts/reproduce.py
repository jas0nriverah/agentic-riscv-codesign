#!/usr/bin/env python3
"""Verify curated evidence and recompute all reported metrics without model fitting."""
import argparse
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BENCHMARKS = ('research-baselines', 'application-transfer', 'arithmetic-stress')


def metrics(actual, predicted):
    if not actual or len(actual) != len(predicted):
        raise ValueError('Nonempty aligned observations required')
    if any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in actual + predicted):
        raise ValueError('Finite nonnegative labels and predictions required')
    error = [abs(p-y) for y, p in zip(actual, predicted)]
    positive = [100*abs(p-y)/y for y, p in zip(actual, predicted) if y > 0]
    zeros = [abs(p-y) for y, p in zip(actual, predicted) if y == 0]
    return {'n': len(actual), 'positive_n': len(positive), 'zero_n': len(zeros),
            'mae_lut4': math.fsum(error)/len(error),
            'mape_percent': math.fsum(positive)/len(positive) if positive else None,
            'zero_mae_lut4': math.fsum(zeros)/len(zeros) if zeros else None,
            'max_underprediction_lut4': max(0, max(y-p for y, p in zip(actual, predicted))),
            'caps': {str(c): {'false_accept': sum(p <= c < y for y, p in zip(actual, predicted)),
                             'false_reject': sum(y <= c < p for y, p in zip(actual, predicted))}
                     for c in (32, 64, 128)}}


def summarize(data):
    rows = data['rows']
    if len({r['id'] for r in rows}) != len(rows):
        raise ValueError('Duplicate physical circuit ID')
    names = set(rows[0]['predictions'])
    if any(set(r['predictions']) != names for r in rows):
        raise ValueError('Every model must predict the complete matched panel')
    result = {'scope': data['scope'], 'models': {}}
    for name in sorted(names):
        m = metrics([r['measured_lut4'] for r in rows], [r['predictions'][name] for r in rows])
        if 'outcomes' in data:
            families = {}
            for outcome in data['outcomes']:
                if outcome['status'] == 'empty':
                    continue
                subset = [r for r in rows if outcome['program'] in r['programs']]
                value = metrics([r['measured_lut4'] for r in subset], [r['predictions'][name] for r in subset])['mae_lut4']
                families.setdefault(outcome['family'], []).append(value)
            m['family_mae_lut4'] = {f: math.fsum(v)/len(v) for f, v in sorted(families.items())}
            m['primary_family_macro_mae_lut4'] = math.fsum(m['family_mae_lut4'].values())/len(families)
        else:
            groups = sorted({r['group'] for r in rows})
            m['group_mae_lut4'] = {g: metrics([r['measured_lut4'] for r in rows if r['group'] == g],
                                                 [r['predictions'][name] for r in rows if r['group'] == g])['mae_lut4'] for g in groups}
            m['primary_group_macro_mae_lut4'] = math.fsum(m['group_mae_lut4'].values())/len(groups)
        result['models'][name] = m
    return result


def run():
    manifest = json.loads((ROOT/'results/provenance.json').read_text())
    for name, expected in manifest['export_files_sha256'].items():
        actual = hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError('Curated artifact changed: '+name)
    return {'unit': 'one unique original circuit; repeated program memberships are used only in the application family-macro endpoint',
            'mape': '100 * mean(abs(prediction - measured) / measured) over strictly positive measured LUT4 counts',
            'benchmarks': {name: summarize(json.loads((ROOT/'results'/name/'observations.json').read_text())) for name in BENCHMARKS}}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'generated/reproduction/summary.json')
    parser.add_argument('--check', action='store_true', help='Also require exact agreement with results/summary.json')
    args = parser.parse_args()
    result = run()
    if args.check and result != json.loads((ROOT/'results/summary.json').read_text()):
        raise ValueError('Saved summary differs from complete metric replay')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    print('Verified all curated input hashes and recomputed three matched result sets:', args.output)
