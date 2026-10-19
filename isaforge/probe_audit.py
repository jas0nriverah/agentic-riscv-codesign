"""Reproduce the released six-model synthetic-probe audit without model fitting.

Run ``python -m isaforge.probe_audit --output-prefix generated/audit-replay/audit``
from the repository root to use the tracked result files. Bootstrap intervals
describe paired formula errors within eight fixed synthetic strata, not real
workload or published ASIC benchmark superiority.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import scipy
from scipy.stats import spearmanr

from .rtl import evaluate_formula

MODELS = ('resource_v2', 'v1_xgboost_log', 'v2_residual_xgb',
          'v3_original', 'v3_structural', 'masterrtl_sog')
COMPARATORS = ('v3_structural', 'v2_residual_xgb')
BOOTSTRAP_SEED = 2026101304
BOOTSTRAP_REPLICATES = 10000
COLLAPSE_FORMULA = 'srli(mul(andi(in1,1023),andi(in0,2147483648)),30)'
ROOT = Path(__file__).resolve().parents[1]
TRACKED = ROOT / 'results/2026-10-13-v3'


def _read(path):
    return json.loads(Path(path).read_text())


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _key(row):
    return row['benchmark'], row['candidate_id']


def _metrics(y, predicted):
    positive, zero = y > 0, y == 0
    nonzero = None
    if positive.any():
        yp, pp = y[positive], predicted[positive]
        nonzero = {'mae_lut4': float(np.mean(abs(yp - pp))),
                   'rmsle': float(np.sqrt(np.mean((np.log1p(yp) - np.log1p(pp)) ** 2))),
                   'spearman': float(spearmanr(yp, pp).statistic) if np.ptp(yp) > 0 and np.ptp(pp) > 0 else None,
                   'sample_count': len(yp)}
    return {'mae_lut4': float(np.mean(abs(y - predicted))),
            'rmsle': float(np.sqrt(np.mean((np.log1p(y) - np.log1p(predicted)) ** 2))),
            'spearman': float(spearmanr(y, predicted).statistic) if np.ptp(y) > 0 and np.ptp(predicted) > 0 else None,
            'pearson': float(np.corrcoef(y, predicted)[0, 1]) if np.ptp(y) > 0 and np.ptp(predicted) > 0 else None,
            'positive_mape_percent': float(np.mean(100 * abs(y[positive] - predicted[positive]) / y[positive])) if positive.any() else None,
            'positive_mape_count': int(positive.sum()), 'sample_count': len(y),
            'zero_lut4_count': int(zero.sum()),
            'zero_target_mae_lut4': float(np.mean(predicted[zero])) if zero.any() else None,
            'nonzero_lut4_metrics': nonzero}


def _verify_metrics(actual, expected):
    for name, value in actual.items():
        if isinstance(value, dict):
            _verify_metrics(value, expected[name])
        elif value is None or expected[name] is None:
            if value != expected[name]:
                raise ValueError(f'recomputed metric differs: {name}')
        elif not math.isclose(value, expected[name], rel_tol=1e-10, abs_tol=1e-10):
            raise ValueError(f'recomputed metric differs: {name}')


def _paired_comparisons(y, predictions, indices, seed, replicates):
    rng = np.random.default_rng(seed)
    # One shared set of paired draws, in sorted stratum order, matches the
    # original audit. All eight strata remain fixed rather than resampled.
    draws = {s: ix[rng.integers(0, len(ix), (replicates, len(ix)))]
             for s, ix in indices.items()}
    comparisons = {}
    for comparator in COMPARATORS:
        d = abs(predictions[comparator] - y) - abs(predictions['masterrtl_sog'] - y)
        samples = np.stack([d[draw].mean(axis=1) for draw in draws.values()], axis=1).mean(axis=1)
        by_stratum = {s: {
            'paired_mean_error_difference_lut4': float(d[ix].mean()),
            'masterrtl_mae_lut4': float(abs(predictions['masterrtl_sog'][ix] - y[ix]).mean()),
            'comparator_mae_lut4': float(abs(predictions[comparator][ix] - y[ix]).mean()),
            'masterrtl_smaller_absolute_error_count': int(np.sum(d[ix] > 1e-9)),
            'comparator_smaller_absolute_error_count': int(np.sum(d[ix] < -1e-9)),
            'ties': int(np.sum(abs(d[ix]) <= 1e-9))} for s, ix in indices.items()}
        comparisons[comparator] = {
            'difference_definition': 'comparator absolute error minus MasterRTL absolute error; positive favors MasterRTL',
            'primary_macro_stratum_mae_difference_lut4': float(np.mean([d[ix].mean() for ix in indices.values()])),
            'stratified_paired_bootstrap_95_percentile_interval_lut4': [float(v) for v in np.quantile(samples, [.025, .975])],
            'masterrtl_relative_mae_reduction_percent': float(100 * (abs(predictions[comparator] - y).mean() - abs(predictions['masterrtl_sog'] - y).mean()) / abs(predictions[comparator] - y).mean()),
            'masterrtl_smaller_absolute_error_count': int(np.sum(d > 1e-9)),
            'comparator_smaller_absolute_error_count': int(np.sum(d < -1e-9)),
            'ties': int(np.sum(abs(d) <= 1e-9)),
            'bootstrap_fraction_difference_positive': float(np.mean(samples > 0)),
            'masterrtl_better_strata_count': sum(x['paired_mean_error_difference_lut4'] > 0 for x in by_stratum.values()),
            'by_stratum': by_stratum}
    return comparisons


def compute_audit(evaluation, candidates, measured, prediction_paths, *,
                  seed=BOOTSTRAP_SEED, replicates=BOOTSTRAP_REPLICATES,
                  prediction_freeze_commit='f62a167'):
    report, declared, measured_rows = _read(evaluation), _read(candidates), _read(measured)
    keys = [_key(r) for r in declared]
    measurements = {_key(r): r for r in measured_rows}
    if (len(keys) != len(set(keys)) or len(keys) != len(measured_rows)
            or len(keys) != 192 or set(keys) != set(measurements)):
        raise ValueError('audit requires complete 192-candidate identity coverage')
    if _sha(measured) != report['provenance']['dataset_sha256']:
        raise ValueError('measured dataset differs from scored dataset')
    if set(prediction_paths) != set(MODELS) or set(report['models']) != set(MODELS):
        raise ValueError('audit requires all six frozen comparators')
    strata = sorted({r['stratum'] for r in declared})
    indices = {s: np.asarray([i for i, r in enumerate(declared) if r['stratum'] == s]) for s in strata}
    if len(strata) != 8 or any(len(ix) != 24 for ix in indices.values()):
        raise ValueError('audit requires eight frozen strata of 24 candidates')
    if any(measurements[k]['formula'] != r['formula'] or measurements[k]['stratum'] != r['stratum']
           for k, r in zip(keys, declared)):
        raise ValueError('candidate formula or stratum differs from measured identity')
    y = np.asarray([measurements[k]['lut4_count'] for k in keys], dtype=float)
    if (not np.isfinite(y).all() or np.any(y < 0)
            or any(measurements[k].get('correctness_verified') is not True
                   or measurements[k].get('measurement_source') != 'rtl_synthesis' for k in keys)):
        raise ValueError('audit requires finite, nonnegative, verified synthesis labels')
    positive, zero = y > 0, y == 0
    predictions, recomputed, checks = {}, {}, []
    for name in MODELS:
        path = prediction_paths[name]
        if _sha(path) != report['provenance']['prediction_sha256'][name]:
            raise ValueError('prediction differs from scored frozen predictions')
        pred = _read(path)
        mapped = {_key(r): r for r in pred}
        if len(mapped) != len(pred) or set(mapped) != set(keys):
            raise ValueError('prediction identity coverage differs')
        if any(mapped[k]['formula'] != measurements[k]['formula'] for k in keys):
            raise ValueError('prediction formula differs')
        p = np.asarray([mapped[k]['predicted_lut4'] for k in keys])
        if not np.isfinite(p).all() or np.any(p < 0):
            raise ValueError('predictions must be finite and nonnegative')
        predictions[name] = p
        pooled = _metrics(y, p)
        by_stratum = {s: _metrics(y[ix], p[ix]) for s, ix in indices.items()}
        _verify_metrics(pooled, report['models'][name]['pooled'])
        for s in strata:
            _verify_metrics(by_stratum[s], report['models'][name]['by_stratum'][s])
        macro = float(np.mean([m['mae_lut4'] for m in by_stratum.values()]))
        if not math.isclose(macro, report['models'][name]['macro_stratum_mae_lut4'], rel_tol=1e-12):
            raise ValueError('macro-stratum MAE differs')
        recomputed[name] = {'pooled': pooled, 'by_stratum': by_stratum, 'macro_stratum_mae_lut4': macro}
        checks.append({'model': name, 'all_pooled_and_stratum_metrics_match': True,
                       'prediction_sha256': _sha(path), 'all_nested_nonzero_metrics_match': True})
    records = []
    for i, k in enumerate(keys):
        row = measurements[k]
        records.append({'benchmark': k[0], 'candidate_id': k[1], 'formula': row['formula'],
                        'stratum': row['stratum'], 'actual_lut4': float(y[i]),
                        'models': {n: {'predicted_lut4': float(p[i]),
                                      'signed_error_lut4': float(p[i] - y[i]),
                                      'absolute_error_lut4': float(abs(p[i] - y[i])),
                                      'absolute_percentage_error': float(100 * abs(p[i] - y[i]) / y[i]) if y[i] > 0 else None}
                                   for n, p in predictions.items()}})
    comparisons = _paired_comparisons(y, predictions, indices, seed, replicates)
    bins = [('1-2 LUT4', 1, 2), ('3-8 LUT4', 3, 8), ('9-32 LUT4', 9, 32),
            ('33-128 LUT4', 33, 128), ('129+ LUT4', 129, float('inf'))]
    mape = {}
    for name, p in predictions.items():
        ape = np.full(len(y), np.nan)
        ape[positive] = 100 * abs(p[positive] - y[positive]) / y[positive]
        denominator_bins = []
        for label, lo, hi in bins:
            mask = positive & (y >= lo) & (y <= hi)
            denominator_bins.append({'label_bin': label, 'count': int(mask.sum()),
                'mean_absolute_percentage_error': float(ape[mask].mean()) if mask.any() else None,
                'contribution_to_reported_positive_mape_percentage_points': float(np.sum(ape[mask]) / positive.sum()),
                'fraction_of_total_positive_mape_sum': float(np.sum(ape[mask]) / np.sum(ape[positive])) if np.sum(ape[positive]) else 0})
        top = sorted((r for r in records if r['actual_lut4'] > 0),
                     key=lambda r: (-r['models'][name]['absolute_percentage_error'], r['candidate_id']))[:10]
        mape[name] = {'positive_mape_percent': float(ape[positive].mean()),
            'positive_mape_count': int(positive.sum()),
            'positive_median_absolute_percentage_error': float(np.median(ape[positive])),
            'positive_p90_absolute_percentage_error': float(np.quantile(ape[positive], .9)),
            'zero_target_count': int(zero.sum()), 'zero_target_mae_lut4': float(p[zero].mean()),
            'zero_target_predicted_positive_count': int(np.sum(zero & (p > 1e-9))),
            'positive_target_predicted_zero_count': int(np.sum(positive & (p <= 1e-9))),
            'true_label_bins': denominator_bins,
            'top_10_percentage_errors': [{'candidate_id': r['candidate_id'], 'formula': r['formula'],
                'stratum': r['stratum'], 'actual_lut4': r['actual_lut4'], **r['models'][name]} for r in top]}
    collapse = next(r for r in records if r['formula'] == COLLAPSE_FORMULA)
    notes = []
    for name in COMPARATORS:
        value = collapse['models'][name]['absolute_percentage_error']
        notes.append({'model': name, 'candidate_id': collapse['candidate_id'], 'formula': COLLAPSE_FORMULA,
            'actual_lut4': collapse['actual_lut4'], 'predicted_lut4': collapse['models'][name]['predicted_lut4'],
            'absolute_error_lut4': collapse['models'][name]['absolute_error_lut4'], 'ape_percent': value,
            'contribution_to_positive_mape_percentage_points': value / int(positive.sum()),
            'fraction_of_total_positive_mape_sum': value / (mape[name]['positive_mape_percent'] * int(positive.sum())),
            'rv32_semantics_explanation': 'Mask selects only bit 31 of in0. Low 32-bit multiplication keeps only bit 0 of masked in1; right shift by 30 puts their AND in output bit 1. Thus result = ((in0 >> 31) & (in1 & 1)) << 1. The model failed to capture a genuine collapsed one-LUT circuit; MAPE additionally magnifies the large absolute error through denominator one.'})
    boundaries = [0, 1, 2, 3, 1023, 1024, 2**31 - 1, 2**31, 2**32 - 1]
    pairs = [(a, b) for a in boundaries for b in boundaries]
    rng = np.random.default_rng(2026101305)
    pairs.extend((int(a), int(b)) for a, b in rng.integers(0, 2**32, (4096, 2), dtype=np.uint64))
    if not all(evaluate_formula(COLLAPSE_FORMULA, a, b) == (((a >> 31) & (b & 1)) << 1) for a, b in pairs):
        raise ValueError('collapse explanation differs from RV32 oracle')
    return {'method': 'Independent recomputation from frozen label/prediction files; no model selection, fitting, or source edits',
        'created_at_utc': datetime.now(timezone.utc).isoformat(), 'prediction_freeze_commit': prediction_freeze_commit,
        'candidate_count': len(keys), 'stratum_counts': {s: len(ix) for s, ix in indices.items()},
        'positive_target_count': int(positive.sum()), 'zero_target_count': int(zero.sum()),
        'bootstrap': {'seed': seed, 'replicates': replicates,
            'estimator': 'equal-weight mean of eight within-stratum paired mean absolute-error differences',
            'resampling': '24 candidate pairs with replacement within each fixed declared stratum; same draws for both models and both comparisons',
            'interval': 'two-sided percentile interval, quantiles 0.025 and 0.975',
            'interpretation': 'Descriptive conditional formula-level uncertainty for this curated synthetic stress probe. Strata are fixed, not independently sampled real workloads.',
            'rng': 'numpy.default_rng / PCG64', 'stratum_order': strata},
        'input_sha256': {'probe_evaluation': _sha(evaluation), 'candidates': _sha(candidates),
                         'measured_dataset': _sha(measured), **{'prediction:' + n: _sha(p) for n, p in prediction_paths.items()}},
        'metric_recomputation_checks': checks, 'recomputed_metrics': recomputed,
        'paired_masterrtl_comparisons': comparisons, 'percentage_error_audit': mape, 'candidate_errors': records,
        'limitations': ['Matched retrained MasterRTL recipe adaptation on isolated iCE40 LUT4 labels, not reproduction of published ASIC scores.',
            'Synthetic formulas are not independent executed workloads; these intervals do not establish superiority on real programs or full processor PPA.',
            'MAPE includes every positive label, including labels of one or two LUT4; zeros are excluded only from MAPE and remain in MAE/RMSLE.',
            'Bootstrap resampling is descriptive and does not correct selection of this convenience stress-test pool or dependence between related graph patterns.'],
        'dominant_percentage_error_candidate_analysis': notes,
        'dominant_percentage_error_semantics_check': {'formula': COLLAPSE_FORMULA,
            'simplification': '((in0 >> 31) & (in1 & 1)) << 1', 'oracle_comparisons': len(pairs),
            'random_seed': 2026101305, 'status': 'passed',
            'interpretation': 'Additional check of algebraic explanation against retained Python RV32 oracle; existing actual-RTL correctness verification already covered this circuit.'},
        'runtime_versions': {'numpy': np.__version__, 'scipy': scipy.__version__}}


def text_report(audit):
    metrics, comparisons, mape = (audit[k] for k in ('recomputed_metrics', 'paired_masterrtl_comparisons', 'percentage_error_audit'))
    lines = ['Independent audit of six frozen matched-target predictors', '',
        'All six pooled and eight-stratum metrics independently recomputed and matched the saved evaluation.',
        '192 formulas: eight fixed strata of 24; 181 positive targets and 11 zero targets.',
        'Difference = comparator absolute error minus MasterRTL absolute error; positive favors MasterRTL.',
        f"Stratified paired bootstrap: seed {audit['bootstrap']['seed']}, {audit['bootstrap']['replicates']:,} replicates, within-stratum resampling, percentile 95% intervals.", '']
    for comparator, detail in comparisons.items():
        ci = detail['stratified_paired_bootstrap_95_percentile_interval_lut4']
        lines.append(f"MasterRTL vs {comparator}: MAE {metrics['masterrtl_sog']['pooled']['mae_lut4']:.6f} vs {metrics[comparator]['pooled']['mae_lut4']:.6f} LUT4; paired difference {detail['primary_macro_stratum_mae_difference_lut4']:.6f}, 95% interval [{ci[0]:.6f}, {ci[1]:.6f}]; relative reduction {detail['masterrtl_relative_mae_reduction_percent']:.2f}%; smaller per-circuit error on {detail['masterrtl_smaller_absolute_error_count']}/192; smaller stratum MAE on {detail['masterrtl_better_strata_count']}/8.")
        for s, row in detail['by_stratum'].items():
            lines.append(f"  {s}: paired difference {row['paired_mean_error_difference_lut4']:.6f} LUT4")
    lines += ['', 'Percentage errors retain every positive-label candidate. APE = 100*abs(predicted-actual)/actual; tiny positive denominators can dominate MAPE. Zero targets remain in MAE/RMSLE and are audited separately.']
    for name in MODELS:
        row = mape[name]
        small, top = row['true_label_bins'][0], row['top_10_percentage_errors'][0]
        lines += [f"{name}: positive MAPE {row['positive_mape_percent']:.3f}%, median APE {row['positive_median_absolute_percentage_error']:.3f}%; 1-2 LUT4 labels ({small['count']}) contribute {small['contribution_to_reported_positive_mape_percentage_points']:.3f} percentage points ({100 * small['fraction_of_total_positive_mape_sum']:.1f}% of total MAPE sum).",
            f"  Largest APE: actual {top['actual_lut4']:.0f}, predicted {top['predicted_lut4']:.6f}, absolute error {top['absolute_error_lut4']:.6f}, APE {top['absolute_percentage_error']:.3f}%; {top['formula']}"]
    lines += ['', 'This is a matched published-recipe adaptation on a synthetic probe, not replication of the paper benchmark. Bootstrap intervals describe formula-level variability conditional on eight curated strata, not real-workload or architecture-level superiority. No model, source, feature, or selection changes were made. Full per-candidate errors and denominator-bin contributions are in independent-audit.json.',
        '', 'Dominant collapse case: ' + COLLAPSE_FORMULA,
        'RV32 low-32-bit multiplication means result = ((in0 >> 31) & (in1 & 1)) << 1, consistent with one mapped LUT4. The prediction error is a real missed simplification, not merely an unstable denominator.']
    for row in audit['dominant_percentage_error_candidate_analysis']:
        lines.append(f"{row['model']}: this single retained candidate contributes {row['contribution_to_positive_mape_percentage_points']:.3f} percentage points ({100 * row['fraction_of_total_positive_mape_sum']:.1f}%) of positive MAPE.")
    return '\n'.join(lines) + '\n'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evaluation', type=Path, default=TRACKED / 'probe-evaluation.json')
    parser.add_argument('--candidates', type=Path, default=TRACKED / 'probe/candidates.json')
    parser.add_argument('--measured', type=Path, default=TRACKED / 'probe/dataset.json')
    parser.add_argument('--predictions-dir', type=Path, default=TRACKED / 'probe-inference')
    parser.add_argument('--prediction', action='append', help='Override prediction paths with all six name=path entries')
    parser.add_argument('--output-prefix', type=Path, required=True)
    parser.add_argument('--seed', type=int, default=BOOTSTRAP_SEED)
    parser.add_argument('--replicates', type=int, default=BOOTSTRAP_REPLICATES)
    parser.add_argument('--prediction-freeze-commit', default='f62a167')
    args = parser.parse_args(argv)
    if args.replicates < 1:
        parser.error('--replicates must be positive')
    predictions = {name: args.predictions_dir / (name + '.json') for name in MODELS}
    if args.prediction:
        predictions = {}
        for spec in args.prediction:
            name, path = spec.split('=', 1)
            if name in predictions:
                parser.error('duplicate prediction name')
            predictions[name] = Path(path)
    audit = compute_audit(args.evaluation, args.candidates, args.measured, predictions,
                          seed=args.seed, replicates=args.replicates,
                          prediction_freeze_commit=args.prediction_freeze_commit)
    args.output_prefix.parent.mkdir(parents=True, exist_ok=True)
    args.output_prefix.with_suffix('.json').write_text(json.dumps(audit, indent=2, allow_nan=False) + '\n')
    args.output_prefix.with_suffix('.txt').write_text(text_report(audit))
    print(json.dumps({'candidate_count': audit['candidate_count'], 'all_six_metrics_match': True,
                      'bootstrap_seed': args.seed, 'bootstrap_replicates': args.replicates}))


if __name__ == '__main__':
    main()
