#!/usr/bin/env python3
"""Authenticate and replay the published V8 application evaluation without fits.

Use Python 3.13 with requirements-research.txt and the proofs extra (also the
reports extra for figures). The frozen
scorer reads retained raw evidence directly; no synthesis, simulator, historical
local tool path, or raw-evidence restoration is needed. Output must be fresh.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'scripts')]
import score_v8_applications as scorer

DEFAULT_ROOT = ROOT / 'results/2026-10-15-v8-application-transfer'
DEFAULT_OUTPUT = ROOT / 'generated/reproduction/v8'
RMSLE_ABSOLUTE_TOLERANCE = 1e-14


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def comparable(value):
    """Ignore only the top-level evaluation timestamp, preserving JSON types."""
    if not isinstance(value, dict) or 'evaluated_at_utc' not in value:
        raise ValueError('Timestamped evaluation object required')
    scorer.utc(value['evaluated_at_utc'])
    result = dict(value)
    del result['evaluated_at_utc']
    return json.dumps(result, sort_keys=True, separators=(',', ':'), allow_nan=False)


def rmsle_metric_path(path):
    """Only the frozen evaluator's declared log/sqrt summaries permit roundoff."""
    parts = path.split('/')[1:]
    if len(parts) == 5 and parts[0] == 'scores' and parts[1] in scorer.MODELS:
        return parts[2] == 'by_program' and parts[4] == 'rmsle'
    if len(parts) == 4 and parts[0] == 'scores' and parts[1] in scorer.MODELS:
        return parts[2] in ('pooled_all_application_rows', 'pooled_primary_application_rows') and parts[3] == 'rmsle'
    if len(parts) == 8 and parts[:2] == ['secondary_diagnostics', 'novelty']:
        return (parts[2] in ('canonical_seen', 'no_declared_identity_match', 'strict_no_declared_match', 'familiar_under_any_declared_test')
                and parts[3] == 'scores' and parts[4] in scorer.MODELS and parts[5] == 'by_program' and parts[7] == 'rmsle')
    if len(parts) == 6 and parts[:2] == ['secondary_diagnostics', 'ood']:
        return (parts[2] in scorer.MODELS and parts[3] in ('outside_any_selected_feature_range', 'inside_selected_feature_ranges')
                and parts[4:] == ['metrics', 'rmsle'])
    return False


def difference_report(reference, reproduced, limit=100, *, rmsle_roundoff=False):
    """Count all differences and report a bounded list, with optional RMSLE rule.

    Linux/Python 3.13 and macOS/Python 3.14 differed only in 23 RMSLE fields
    (largest absolute difference 2.43e-16). The log1p subtraction can magnify
    relative/ULP differences near zero. Permit 1e-14 absolute, zero relative,
    only for finite nonnegative floats at these declared metric paths.
    """
    if type(limit) is not int or not 1 <= limit <= 1000:
        raise ValueError('Diagnostic limit must be an integer from 1 to 1000')
    differences = []
    count = 0
    accepted = 0
    maxima = {'absolute': 0.0, 'relative': 0.0, 'ulps': 0.0}

    def preview(value):
        if isinstance(value, (dict, list)) or (isinstance(value, str) and len(value) > 512):
            encoded = json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
            return {'type': type(value).__name__, 'length': len(value),
                    'sha256': hashlib.sha256(encoded).hexdigest()}
        return value

    def record(path, reason, expected, actual):
        nonlocal count, accepted
        count += 1
        item = {'path': path, 'reason': reason,
                'expected': preview(expected), 'actual': preview(actual)}
        if type(expected) is float and type(actual) is float and math.isfinite(expected) and math.isfinite(actual):
            absolute = abs(actual - expected)
            scale = max(abs(expected), abs(actual))
            numeric = {'absolute': absolute, 'relative': absolute / scale if scale else 0.0,
                       'ulps': absolute / max(math.ulp(expected), math.ulp(actual))}
            item['numeric_difference'] = numeric
            for key, value in numeric.items():
                maxima[key] = max(maxima[key], value)
            if (rmsle_roundoff and reason == 'value' and expected >= 0 and actual >= 0
                    and rmsle_metric_path(path) and absolute <= RMSLE_ABSOLUTE_TOLERANCE):
                accepted += 1
                item['accepted_rmsle_roundoff'] = True
        if len(differences) < limit:
            differences.append(item)

    def walk(expected, actual, path=''):
        if type(expected) is not type(actual):
            record(path, 'type', expected, actual)
        elif isinstance(expected, dict):
            for key in sorted(set(expected) | set(actual)):
                if path == '' and key == 'evaluated_at_utc':
                    continue
                child = path + '/' + key.replace('~', '~0').replace('/', '~1')
                if key not in expected:
                    record(child, 'unexpected_key', None, actual[key])
                elif key not in actual:
                    record(child, 'missing_key', expected[key], None)
                else:
                    walk(expected[key], actual[key], child)
        elif isinstance(expected, list):
            if len(expected) != len(actual):
                record(path, 'list_length', len(expected), len(actual))
            for index, (a, b) in enumerate(zip(expected, actual)):
                walk(a, b, path + '/' + str(index))
        elif json.dumps(expected, allow_nan=False) != json.dumps(actual, allow_nan=False):
            record(path, 'value', expected, actual)

    walk(reference, reproduced)
    return {'schema': 'isaforge-v8-reproduction-mismatch-v1', 'status': 'pass' if count == accepted else 'fail',
            'comparison': 'Exact JSON fields and types except top-level evaluated_at_utc' +
                (' and finite nonnegative RMSLE floats at declared metric paths within 1e-14 absolute (zero relative) tolerance.' if rmsle_roundoff else '; no numerical tolerance.'),
            'path_format': 'JSON Pointer (RFC 6901)', 'difference_count': count,
            'accepted_rmsle_roundoff_count': accepted, 'incompatible_difference_count': count - accepted,
            'reported_difference_count': len(differences), 'truncated': count > len(differences),
            'maximum_float_difference': maxima, 'differences': differences}


def reproduce(root=DEFAULT_ROOT, output=DEFAULT_OUTPUT, *, skip_figures=False):
    root, output = Path(root).resolve(), Path(output).resolve()
    reference_path = root / 'evaluation.json'
    if output.exists():
        raise ValueError('Reproduction output must be a fresh directory')
    if not reference_path.is_file():
        raise ValueError('Published V8 evaluation.json required')
    output.mkdir(parents=True)
    evaluation_path = output / 'evaluation.json'
    # The frozen scorer gates all fresh target reads on committed approval and
    # authenticates every frozen file, archive member, proof and raw cell count.
    scorer.score(root, evaluation_path)
    reproduced = json.loads(evaluation_path.read_text())
    reference = json.loads(reference_path.read_text())
    roundoff_count = 0
    if comparable(reproduced) != comparable(reference):
        mismatch = difference_report(reference, reproduced, rmsle_roundoff=True)
        mismatch.update(published_evaluation_sha256=sha(reference_path),
                        reproduced_evaluation_sha256=sha(evaluation_path))
        roundoff_count = mismatch['accepted_rmsle_roundoff_count']
        mismatch_path = output / ('roundoff.json' if mismatch['status'] == 'pass' else 'mismatch.json')
        mismatch_path.write_text(json.dumps(mismatch, indent=2, allow_nan=False) + '\n')
        if mismatch['status'] != 'pass':
            print(json.dumps(mismatch, indent=2, allow_nan=False), file=sys.stderr)
            raise ValueError('Reproduced V8 evaluation differs from published reference; output retained for inspection')
    report = {
        'schema': 'isaforge-v8-application-reproduction-v1',
        'status': 'pass',
        'published_evaluation_sha256': sha(reference_path),
        'reproduced_evaluation_sha256': sha(evaluation_path),
        'point_freeze_sha256': reproduced['provenance']['point_freeze_sha256'],
        'scorer_sha256': sha(scorer.__file__),
        'reproduction_source_sha256': sha(__file__),
        'comparison': 'All JSON fields and types match except top-level evaluated_at_utc and declared RMSLE floats within 1e-14 absolute (zero relative) tolerance.',
        'accepted_rmsle_roundoff_count': roundoff_count,
        'new_estimator_fits': 0,
        'fresh_target_generation': False,
        'raw_evidence_restored': False,
        'figures_generated': not skip_figures,
    }
    if not skip_figures:
        from plot_v8_applications import run as plot
        plot(evaluation_path, output / 'figures', root=root)
    (output / 'reproduction.json').write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=DEFAULT_ROOT)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--skip-figures', action='store_true')
    args = parser.parse_args()
    report = reproduce(args.root, args.output, skip_figures=args.skip_figures)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
