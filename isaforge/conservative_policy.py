"""Calibrate cautious resource rejection without modifying the frozen model.

An empirical one-sided log-error margin discounts a point prediction before
rejecting a high-merit candidate. This is not a calibrated feasibility guarantee
for correlated program families. Final choices still require actual synthesis.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path

from .area_model import _validated_rows
from .features import parse_formula


def calibrate(training_rows, calibration_rows, predictions, quantile=.9):
    if not 0 < quantile < 1:
        raise ValueError('quantile must be between zero and one')
    train = _validated_rows(training_rows)
    calibration = _validated_rows(calibration_rows)
    if {r['benchmark'] for r in train} & {r['benchmark'] for r in calibration}:
        raise ValueError('calibration programs must be absent from model training')
    seen = {r['formula'] for r in train}
    by_key = {(r['benchmark'], r['candidate_id']): r for r in calibration}
    estimates = {}
    for p in predictions:
        key = (p['benchmark'], p['candidate_id'])
        if key in estimates or key not in by_key:
            raise ValueError('duplicate or unexpected calibration prediction')
        if parse_formula(p['formula']).canonical() != by_key[key]['formula']:
            raise ValueError('calibration formula mismatch')
        value = p['predicted_lut4']
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise ValueError('invalid calibration prediction')
        estimates[key] = value
    if set(estimates) != set(by_key):
        raise ValueError('calibration predictions must cover the pool exactly')
    residuals, program_maxima = {}, {}
    for key, r in by_key.items():
        if r['formula'] not in seen:
            value = math.log1p(estimates[key]) - math.log1p(r['lut4_count'])
            if r['formula'] in residuals and not math.isclose(residuals[r['formula']], value, abs_tol=1e-9):
                raise ValueError('formula-only residuals must agree across programs')
            residuals[r['formula']] = value
            program_maxima[r['benchmark']] = max(program_maxima.get(r['benchmark'], -math.inf), value)
    if not residuals:
        raise ValueError('calibration requires formulas absent from model training')
    # The decision unit is a program, not a formula. Protect rare high-merit
    # cases using each program's worst overprediction, then weight programs
    # equally. A large family must not dominate the rejection margin.
    ordered = sorted(program_maxima.values())
    # Conservative finite-sample order statistic; no exchangeability claim.
    rank = min(len(ordered), math.ceil((len(ordered) + 1) * quantile))
    margin = max(0.0, ordered[rank - 1])
    return {'policy': 'empirical one-sided log-error margin before resource rejection',
            'frozen_at_utc': datetime.now(timezone.utc).isoformat(), 'quantile': quantile,
            'order_statistic_rank': rank, 'log_overprediction_margin': margin,
            'calibration_novel_formula_count': len(residuals),
            'calibration_program_count': len(ordered),
            'program_maximum_log_overpredictions': program_maxima,
            'training_benchmarks': sorted({r['benchmark'] for r in train}),
            'calibration_benchmarks': sorted({r['benchmark'] for r in calibration}),
            'limitations': ['An empirical margin; correlated formulas/programs prevent a distribution-free coverage claim.',
                            'Calibration labels are additional historical measurements outside the target budget.',
                            'Discounted scores only order measurements; actual measured feasibility is mandatory.']}


def apply_margin(predictions, calibration):
    margin = calibration['log_overprediction_margin']
    if not math.isfinite(margin) or margin < 0:
        raise ValueError('invalid calibration margin')
    result = []
    for row in predictions:
        value = row['predicted_lut4']
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise ValueError('invalid point prediction')
        result.append({**row, 'point_predicted_lut4': value,
                       'predicted_lut4': max(0.0, math.expm1(math.log1p(value) - margin)),
                       'target': 'discounted resource score for acquisition; not a point area prediction'})
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    fit = sub.add_parser('calibrate')
    for name in ('training-rows', 'calibration-rows', 'predictions', 'output'):
        fit.add_argument('--' + name, type=Path, required=True)
    apply = sub.add_parser('apply')
    for name in ('calibration', 'predictions', 'output'):
        apply.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == 'calibrate':
        paths = [args.training_rows, args.calibration_rows, args.predictions]
        report = calibrate(*(json.loads(p.read_text()) for p in paths))
        report['input_sha256'] = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    else:
        report = apply_margin(json.loads(args.predictions.read_text()), json.loads(args.calibration.read_text()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')


if __name__ == '__main__':
    main()
