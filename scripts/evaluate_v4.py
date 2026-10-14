#!/usr/bin/env python3
"""Independent frozen V4 holdout score; no model imports, fitting, or synthesis."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import numpy as np

MODELS = {'v4', 'masterrtl_retrained', 'masterrtl_frozen', 'v2_frozen', 'v3_frozen'}
CAPS = (16, 32, 64, 128, 256)
SEED = 2026101305
REPLICATES = 10000
PROTOCOL = Path(__file__).resolve().parents[1] / 'docs/v4-protocol.md'


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check_record(record, base):
    path = (base / record['path']).resolve()
    if sha(path) != record['sha256']:
        raise ValueError(f'Frozen file hash mismatch: {path}')
    return path


def utc(value):
    stamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if stamp.tzinfo is None or stamp.utcoffset().total_seconds() != 0:
        raise ValueError('Freeze/release timestamps must explicitly use UTC')
    return stamp


def key(row):
    result = row['benchmark'], row['candidate_id']
    if any(not isinstance(v, str) or not v for v in result):
        raise ValueError('Candidate keys must be nonempty strings')
    return result


def index(rows):
    if not isinstance(rows, list) or not rows:
        raise ValueError('Rows must be a nonempty JSON list')
    result = {}
    for row in rows:
        k = key(row)
        if k in result:
            raise ValueError(f'Duplicate candidate identity: {k}')
        result[k] = row
    return result


def aligned(declared, rows, field, *, measured=False):
    indexed = index(rows)
    if set(indexed) != set(index(declared)):
        raise ValueError('Missing or extra candidate identities')
    values = []
    for candidate in declared:
        row = indexed[key(candidate)]
        if row.get('formula') != candidate['formula']:
            raise ValueError('Candidate formula differs')
        if measured and row.get('stratum') != candidate['stratum']:
            raise ValueError('Measured stratum differs')
        value = row[field]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f'{field} must be numeric')
        if not np.isfinite(value) or value < 0:
            raise ValueError(f'{field} must be finite and nonnegative')
        if measured and (int(value) != value
                         or row.get('correctness_verified') is not True
                         or row.get('measurement_source') != 'rtl_synthesis'):
            raise ValueError('Labels require verified integer RTL synthesis counts')
        values.append(value)
    return np.asarray(values, dtype=float)


def ratio(numerator, denominator):
    return float(numerator / denominator) if denominator else None


def metrics(y, p):
    error = np.abs(p - y)
    positive, zero = y > 0, y == 0
    ape = 100 * error[positive] / y[positive]
    confusion = {}
    for cap in CAPS:
        truth, predicted = y <= cap, p <= cap
        fa = int(np.sum(predicted & ~truth))
        fr = int(np.sum(~predicted & truth))
        confusion[str(cap)] = {
            'true_accept_count': int(np.sum(predicted & truth)),
            'true_reject_count': int(np.sum(~predicted & ~truth)),
            'false_accept_count': fa, 'false_reject_count': fr,
            'true_feasible_count': int(truth.sum()),
            'true_infeasible_count': int((~truth).sum()),
            'predicted_feasible_count': int(predicted.sum()),
            'false_accept_rate_among_true_infeasible': ratio(fa, (~truth).sum()),
            'false_reject_rate_among_true_feasible': ratio(fr, truth.sum()),
            'infeasible_fraction_among_predicted_feasible': ratio(fa, predicted.sum()),
        }
    return {
        'sample_count': len(y), 'mae_lut4': float(error.mean()),
        'rmsle': float(np.sqrt(np.mean((np.log1p(p) - np.log1p(y)) ** 2))),
        'positive_mape_percent': float(ape.mean()) if len(ape) else None,
        'positive_median_ape_percent': float(np.median(ape)) if len(ape) else None,
        'positive_count': int(positive.sum()), 'zero_count': int(zero.sum()),
        'zero_target_mae_lut4': float(error[zero].mean()) if zero.any() else None,
        'cap_feasibility': confusion,
    }


def validate_freeze(manifest_path):
    manifest_path = Path(manifest_path).resolve()
    base, m = manifest_path.parent, read(manifest_path)
    if m.get('schema') != 'isaforge-v4-freeze-v1':
        raise ValueError('Unsupported freeze manifest schema')
    candidate_time = utc(m['candidate_frozen_at_utc'])
    if set(m['models']) != MODELS:
        raise ValueError('All five preregistered comparators are required')
    paths = {name: check_record(m[name], base)
             for name in ('candidates', 'development_data', 'protocol', 'evaluator')}
    if paths['evaluator'] != Path(__file__).resolve() or paths['protocol'] != PROTOCOL:
        raise ValueError('Manifest must freeze this evaluator and V4 protocol')
    declared, development = read(paths['candidates']), read(paths['development_data'])
    index(declared)
    if len(declared) != 256 or len({r['formula'] for r in declared}) != 256:
        raise ValueError('Planned holdout requires 256 unique formulas')
    strata = sorted({r['stratum'] for r in declared})
    indices = {s: np.asarray([i for i, r in enumerate(declared) if r['stratum'] == s])
               for s in strata}
    if len(indices) != 8 or any(len(ix) != 32 for ix in indices.values()):
        raise ValueError('Planned holdout requires eight strata of 32')
    if len(development) != 1289 or len({r['formula'] for r in development}) != 1289:
        raise ValueError('Development cohort must contain 1289 unique formulas')
    if {r['formula'] for r in declared} & {r['formula'] for r in development}:
        raise ValueError('Holdout formula occurs in development data')
    predictions = {}
    for name, entry in m['models'].items():
        if utc(entry['frozen_at_utc']) < candidate_time:
            raise ValueError('Model freeze predates candidate freeze')
        if not entry['sources']:
            raise ValueError('Each model requires frozen runtime source files')
        check_record(entry['artifact'], base)
        for record in entry['sources']:
            check_record(record, base)
        prediction_path = check_record(entry['predictions'], base)
        predictions[name] = aligned(declared, read(prediction_path), 'predicted_lut4')
    return m, declared, indices, predictions


def evaluate(manifest_path, release_path):
    m, declared, indices, predictions = validate_freeze(manifest_path)
    release_path = Path(release_path).resolve()
    release = read(release_path)
    released = utc(release['released_at_utc'])
    if any(utc(entry['frozen_at_utc']) >= released for entry in m['models'].values()):
        raise ValueError('All model/prediction freezes must precede label release')
    dataset_path = check_record(release['dataset'], release_path.parent)
    y = aligned(declared, read(dataset_path), 'lut4_count', measured=True)
    models = {}
    for name, p in sorted(predictions.items()):
        grouped = {s: metrics(y[ix], p[ix]) for s, ix in indices.items()}
        models[name] = {'primary_macro_stratum_mae_lut4': float(np.mean(
            [x['mae_lut4'] for x in grouped.values()])),
            'pooled': metrics(y, p), 'by_stratum': grouped,
            'candidate_errors': [{'benchmark': r['benchmark'], 'candidate_id': r['candidate_id'],
                'formula': r['formula'], 'stratum': r['stratum'], 'lut4_count': float(y[i]),
                'predicted_lut4': float(p[i]), 'signed_error_lut4': float(p[i] - y[i]),
                'absolute_error_lut4': float(abs(p[i] - y[i]))}
                for i, r in enumerate(declared)]}
    rng = np.random.default_rng(SEED)
    draws = {s: ix[rng.integers(0, len(ix), (REPLICATES, len(ix)))]
             for s, ix in indices.items()}
    comparisons = {}
    for name in sorted(MODELS - {'v4'}):
        d = abs(predictions['v4'] - y) - abs(predictions[name] - y)
        samples = np.mean([d[draw].mean(axis=1) for draw in draws.values()], axis=0)
        comparisons[name] = {
            'difference_definition': 'V4 absolute error minus comparator absolute error; negative favors V4',
            'macro_stratum_mae_difference_lut4': float(np.mean([d[ix].mean() for ix in indices.values()])),
            'descriptive_paired_bootstrap_95_percentile_interval_lut4': np.quantile(samples, [.025, .975]).tolist(),
            'v4_smaller_absolute_error_count': int(np.sum(d < -1e-9)),
            'comparator_smaller_absolute_error_count': int(np.sum(d > 1e-9)),
            'tie_count': int(np.sum(abs(d) <= 1e-9)),
            'by_stratum_mae_difference_lut4': {s: float(d[ix].mean()) for s, ix in indices.items()},
        }
    return {'schema': 'isaforge-v4-evaluation-v1', 'evaluation_status': 'complete frozen holdout',
        'holdout_formula_count': len(declared), 'development_formula_count': 1289,
        'stratum_counts': {s: len(ix) for s, ix in indices.items()}, 'models': models,
        'paired_comparisons': comparisons,
        'bootstrap': {'seed': SEED, 'replicates': REPLICATES, 'unit': 'paired formulas within fixed strata'},
        'provenance': {'freeze_manifest_sha256': sha(manifest_path),
            'label_release_sha256': sha(release_path), 'dataset_sha256': sha(dataset_path),
            'freeze_manifest': m, 'release': release,
            'evaluated_at_utc': datetime.now(timezone.utc).isoformat(), 'numpy_version': np.__version__},
        'limitations': ['Synthetic isolated LUT4 prediction; no workload acquisition or processor performance claim.',
            'Exact canonical disjointness does not establish semantic independence.',
            'Bootstrap intervals are descriptive within fixed strata, not population confidence or adjusted significance.',
            'Recorded hashes and chronology do not independently prove absence of prior label access.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', required=True, type=Path)
    parser.add_argument('--release', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--validate-freeze', action='store_true')
    args = parser.parse_args()
    if args.validate_freeze:
        validate_freeze(args.manifest)
        print('Freeze validated: 256 held-out inputs and all five complete prediction files; no labels read.')
        return
    if args.release is None or args.output is None:
        parser.error('--release and --output are required for scoring')
    report = evaluate(args.manifest, args.release)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    print(json.dumps({name: value['primary_macro_stratum_mae_lut4']
                      for name, value in report['models'].items()}, indent=2))


if __name__ == '__main__':
    main()
