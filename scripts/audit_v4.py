#!/usr/bin/env python3
"""Read-only independent V4 score/provenance replay; write an audit report.

No evaluator import, model fitting, model loading, or new measurement. Mapped
counts are independently recounted from retained raw netlists. Scalar metrics
use Python arithmetic; NumPy is used only for fixed paired bootstrap draws.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import statistics
import subprocess
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
MODELS = {'v4', 'masterrtl_retrained', 'masterrtl_frozen', 'v2_frozen', 'v3_frozen'}
CAPS = (16, 32, 64, 128, 256)
SEED, REPLICATES = 2026101305, 10000


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def close(actual, expected, context):
    if isinstance(actual, dict):
        require(set(actual) == set(expected), f'{context}: metric fields differ')
        for key, value in actual.items():
            close(value, expected[key], f'{context}.{key}')
    elif isinstance(actual, list):
        require(len(actual) == len(expected), f'{context}: lengths differ')
        for i, value in enumerate(actual):
            close(value, expected[i], f'{context}[{i}]')
    elif actual is None:
        require(expected is None, f'{context}: null differs')
    elif isinstance(actual, (int, float)):
        require(expected is not None and math.isclose(actual, expected, rel_tol=1e-10, abs_tol=1e-10),
                f'{context}: {actual} differs from {expected}')
    else:
        require(actual == expected, f'{context}: value differs')


def record_path(record, base):
    p = (base / record['path']).resolve()
    require(sha(p) == record['sha256'], f'Hash mismatch: {p}')
    return p


def keyed(rows):
    result = {(r['benchmark'], r['candidate_id']): r for r in rows}
    require(len(result) == len(rows), 'Duplicate row identities')
    return result


def division(a, b):
    return a / b if b else None


def scalar_metrics(y, p):
    require(len(y) == len(p) and len(y) > 0, 'Metric rows missing')
    require(all(math.isfinite(v) and v >= 0 for v in y + p), 'Invalid nonnegative metric input')
    error = [abs(a - b) for a, b in zip(y, p)]
    positive_ape = [100 * e / a for a, e in zip(y, error) if a > 0]
    zero_error = [e for a, e in zip(y, error) if a == 0]
    confusion = {}
    for cap in CAPS:
        truth = [a <= cap for a in y]
        guess = [a <= cap for a in p]
        fa = sum(g and not t for g, t in zip(guess, truth))
        fr = sum(not g and t for g, t in zip(guess, truth))
        feasible, infeasible, predicted = sum(truth), len(truth) - sum(truth), sum(guess)
        confusion[str(cap)] = {
            'true_accept_count': sum(g and t for g, t in zip(guess, truth)),
            'true_reject_count': sum(not g and not t for g, t in zip(guess, truth)),
            'false_accept_count': fa, 'false_reject_count': fr,
            'true_feasible_count': feasible, 'true_infeasible_count': infeasible,
            'predicted_feasible_count': predicted,
            'false_accept_rate_among_true_infeasible': division(fa, infeasible),
            'false_reject_rate_among_true_feasible': division(fr, feasible),
            'infeasible_fraction_among_predicted_feasible': division(fa, predicted),
        }
    return {'sample_count': len(y), 'mae_lut4': statistics.mean(error),
        'rmsle': math.sqrt(statistics.mean([(math.log1p(a) - math.log1p(b)) ** 2
                                          for a, b in zip(y, p)])),
        'positive_mape_percent': statistics.mean(positive_ape) if positive_ape else None,
        'positive_median_ape_percent': statistics.median(positive_ape) if positive_ape else None,
        'positive_count': len(positive_ape), 'zero_count': len(zero_error),
        'zero_target_mae_lut4': statistics.mean(zero_error) if zero_error else None,
        'cap_feasibility': confusion}


def corpus_audit(corpus, generated, cohort, count):
    # This renderer's bytes are verified against the frozen commit before this
    # function runs; regeneration checks provenance, not semantic equivalence.
    from isaforge.rtl import generate_rtl
    directory, raw = corpus / cohort, generated / cohort
    declared = read(directory / 'candidates.json')
    measured = read(directory / 'dataset.json')
    completion, verification, frozen = [read(directory / name) for name in
                                       ('completion.json', 'verification.json', 'freeze.json')]
    require(len(declared) == len(measured) == count, f'{cohort}: incomplete corpus')
    require(set(keyed(declared)) == set(keyed(measured)), f'{cohort}: identity coverage differs')
    require(completion['complete'] is True and not completion['failures'], f'{cohort}: failed collection')
    for field, filename in [('dataset_sha256', 'dataset.json'),
                            ('verification_sha256', 'verification.json'), ('freeze_sha256', 'freeze.json')]:
        require(completion[field] == sha(directory / filename), f'{cohort}: completion digest mismatch')
    require(frozen['candidate_sha256'] == sha(directory / 'candidates.json'), f'{cohort}: candidate digest mismatch')
    require(verification['verified'] is True and verification['formula_count'] == count
            and verification['total_comparisons'] == count * verification['vectors_per_formula'],
            f'{cohort}: verification contract mismatch')
    require(verification['rtl_sha256'] == sha(raw / 'verification/verification.v')
            and verification['vectors_sha256'] == sha(raw / 'verification/vectors.txt'),
            f'{cohort}: retained verification files differ')
    require(verification['v4_validation_override_sha256'] == sha(ROOT / 'isaforge/v4_validation.py'),
            f'{cohort}: validation override source differs')
    if verification.get('signed_overflow_workaround_applied'):
        require(verification['independent_yosys_log_sha256'] == sha(
            raw / 'verification/yosys-boundary-cross-check/eval.log'),
            f'{cohort}: independent simulator log differs')
    records = keyed(measured)
    lut4_sum, carry_sum, zero_count = 0, 0, 0
    per_candidate = []
    for declared_row in declared:
        row = records[(declared_row['benchmark'], declared_row['candidate_id'])]
        require(all(row[k] == v for k, v in declared_row.items()), f'{cohort}: input changed')
        formula = row['formula']
        folder = raw / 'circuits' / hashlib.sha256(formula.encode()).hexdigest()[:20]
        metrics = read(folder / 'metrics.json')
        netlist = read(folder / 'ice40-netlist.json')
        counts = Counter(cell['type'] for module in netlist['modules'].values()
                         for cell in module.get('cells', {}).values())
        require(row['lut4_count'] == metrics['ice40_lut4_count'] == counts['SB_LUT4'],
                f'{cohort}: LUT4 label differs from raw mapped cells: {formula}')
        require(row['carry_count'] == metrics['ice40_carry_count'] == counts['SB_CARRY'],
                f'{cohort}: carry label differs from raw mapped cells: {formula}')
        require(metrics['formula'] == formula
                and row['rtl_sha256'] == metrics['rtl_sha256'] == sha(folder / 'candidate.v'),
                f'{cohort}: retained RTL/formula mismatch')
        require(row['rtl_sha256'] == hashlib.sha256(generate_rtl(formula).encode()).hexdigest(),
                f'{cohort}: original-formula RTL regeneration differs')
        for field, filename in [('netlist_sha256', 'ice40-netlist.json'),
                                ('script_sha256', 'ice40.ys'), ('log_sha256', 'ice40.log')]:
            require(metrics[field] == sha(folder / filename), f'{cohort}: synthesis digest mismatch')
        require(row['synthesis_tool'] == metrics['tool'] == completion['tool']
                and row['measurement_source'] == 'rtl_synthesis'
                and row['correctness_verified'] is True, f'{cohort}: provenance fields mismatch')
        lut4_sum += counts['SB_LUT4']; carry_sum += counts['SB_CARRY']
        zero_count += counts['SB_LUT4'] == 0
        per_candidate.append({'candidate_id': row['candidate_id'], 'rtl_sha256': row['rtl_sha256'],
                              'netlist_sha256': metrics['netlist_sha256'], 'lut4': counts['SB_LUT4'],
                              'carry': counts['SB_CARRY']})
    for name, digest in frozen['runtime_source_sha256'].items():
        require(sha(ROOT / 'isaforge' / name) == digest, f'{cohort}: frozen collector source differs')
    return {'candidate_count': count, 'stratum_counts': dict(Counter(r['stratum'] for r in declared)),
        'dataset_sha256': sha(directory / 'dataset.json'), 'freeze_sha256': sha(directory / 'freeze.json'),
        'verification_sha256': sha(directory / 'verification.json'),
        'raw_netlist_lut4_sum': lut4_sum, 'raw_netlist_carry_sum': carry_sum,
        'zero_lut4_count': zero_count, 'verification_comparisons': verification['total_comparisons'],
        'signed_overflow_workaround_applied': verification.get('signed_overflow_workaround_applied', False),
        'raw_counts_and_hashes_verified': True, 'retained_candidate_records': per_candidate}


def audit(base, generated, commit):
    base, generated = base.resolve(), generated.resolve()
    manifest = read(base / 'freeze.json'); scored = read(base / 'evaluation.json')
    require(set(manifest['models']) == set(scored['models']) == MODELS, 'Missing preregistered comparator')
    require(scored['provenance']['freeze_manifest'] == manifest, 'Scorer manifest differs')
    require(scored['provenance']['freeze_manifest_sha256'] == sha(base / 'freeze.json'), 'Scorer freeze hash differs')
    require(scored['provenance']['label_release_sha256'] == sha(base / 'label-release.json'), 'Scorer release hash differs')
    release = read(base / 'label-release.json')
    candidates = read(record_path(manifest['candidates'], base))
    truth_rows = read(record_path(release['dataset'], base))
    require(len(candidates) == len(truth_rows) == 256, 'Incomplete holdout')
    require(sha(record_path(release['dataset'], base)) == scored['provenance']['dataset_sha256'], 'Scored labels differ')
    stamp = lambda value: datetime.fromisoformat(value.replace('Z', '+00:00'))
    require(all(stamp(manifest['candidate_frozen_at_utc']) <= stamp(m['frozen_at_utc'])
                < stamp(release['released_at_utc']) for m in manifest['models'].values()), 'Freeze chronology differs')
    all_records = [manifest[x] for x in ('candidates', 'development_data', 'protocol', 'evaluator')]
    for entry in manifest['models'].values():
        all_records.extend([entry['predictions'], entry['artifact'], *entry['sources']])
    frozen_files = {}
    for record in all_records:
        path = record_path(record, base)
        relative = path.relative_to(ROOT).as_posix()
        committed = subprocess.run(['git', 'show', f'{commit}:{relative}'], cwd=ROOT,
                                   check=True, capture_output=True).stdout
        require(hashlib.sha256(committed).hexdigest() == record['sha256'], f'File differs from freeze commit: {relative}')
        frozen_files[relative] = record['sha256']
    corpora = {cohort: corpus_audit(base / 'corpus', generated, cohort, count)
               for cohort, count in [('development', 384), ('test', 256)]}
    development = read(record_path(manifest['development_data'], base))
    require(len(development) == len({r['formula'] for r in development}) == 1289, 'Incorrect development cohort')
    require(not ({r['formula'] for r in development} & {r['formula'] for r in candidates}), 'Canonical train/test overlap')
    truth = keyed(truth_rows)
    require(set(truth) == set(keyed(candidates)), 'Holdout identities differ')
    y = [truth[(r['benchmark'], r['candidate_id'])]['lut4_count'] for r in candidates]
    strata = sorted({r['stratum'] for r in candidates})
    indices = {s: [i for i, r in enumerate(candidates) if r['stratum'] == s] for s in strata}
    require(len(indices) == 8 and all(len(ix) == 32 for ix in indices.values()), 'Holdout strata differ')
    predictions, metrics = {}, {}
    for name, entry in sorted(manifest['models'].items()):
        rows = keyed(read(record_path(entry['predictions'], base)))
        require(set(rows) == set(truth), f'{name}: prediction identities differ')
        for row in candidates:
            require(rows[(row['benchmark'], row['candidate_id'])]['formula'] == row['formula'], 'Prediction formula differs')
        p = [rows[(r['benchmark'], r['candidate_id'])]['predicted_lut4'] for r in candidates]
        predictions[name] = p
        pooled = scalar_metrics(y, p)
        grouped = {s: scalar_metrics([y[i] for i in ix], [p[i] for i in ix]) for s, ix in indices.items()}
        primary = statistics.mean(v['mae_lut4'] for v in grouped.values())
        close(pooled, scored['models'][name]['pooled'], name + '.pooled')
        close(grouped, scored['models'][name]['by_stratum'], name + '.by_stratum')
        close(primary, scored['models'][name]['primary_macro_stratum_mae_lut4'], name + '.primary')
        errors = keyed(scored['models'][name]['candidate_errors'])
        require(set(errors) == set(truth), f'{name}: missing reported candidate errors')
        for i, row in enumerate(candidates):
            result = errors[(row['benchmark'], row['candidate_id'])]
            require(result['formula'] == row['formula'] and result['stratum'] == row['stratum'], 'Reported error identity differs')
            for field, value in [('lut4_count', y[i]), ('predicted_lut4', p[i]),
                                 ('absolute_error_lut4', abs(p[i] - y[i])), ('signed_error_lut4', p[i] - y[i])]:
                close(value, result[field], f'{name}.candidate.{field}')
        metrics[name] = {'primary_macro_stratum_mae_lut4': primary, 'pooled': pooled, 'by_stratum': grouped}
    rng = np.random.default_rng(SEED)
    draws = {s: np.asarray(ix)[rng.integers(0, len(ix), (REPLICATES, len(ix)))] for s, ix in indices.items()}
    comparisons = {}
    for name in sorted(MODELS - {'v4'}):
        d = np.asarray([abs(a - t) - abs(b - t) for a, b, t in zip(predictions['v4'], predictions[name], y)])
        sampled = np.stack([d[draw].mean(axis=1) for draw in draws.values()], axis=1).mean(axis=1)
        actual = {'difference_definition': 'V4 absolute error minus comparator absolute error; negative favors V4',
            'macro_stratum_mae_difference_lut4': statistics.mean(float(d[ix].mean()) for ix in indices.values()),
            'descriptive_paired_bootstrap_95_percentile_interval_lut4': np.quantile(sampled, [.025, .975]).tolist(),
            'v4_smaller_absolute_error_count': int(np.sum(d < -1e-9)),
            'comparator_smaller_absolute_error_count': int(np.sum(d > 1e-9)),
            'tie_count': int(np.sum(abs(d) <= 1e-9)),
            'by_stratum_mae_difference_lut4': {s: float(d[ix].mean()) for s, ix in indices.items()}}
        close(actual, scored['paired_comparisons'][name], 'paired.' + name)
        baseline_mae = metrics[name]['primary_macro_stratum_mae_lut4']
        comparisons[name] = {**actual, 'v4_relative_mae_reduction_percent':
                            100 * (baseline_mae - metrics['v4']['primary_macro_stratum_mae_lut4']) / baseline_mae}
    return {'audit_status': 'passed', 'audit_source_sha256': sha(__file__),
        'audited_at_utc': datetime.now(timezone.utc).isoformat(), 'source_freeze_commit': commit,
        'inputs': {'evaluation_sha256': sha(base / 'evaluation.json'), 'freeze_sha256': sha(base / 'freeze.json'),
                   'label_release_sha256': sha(base / 'label-release.json')},
        'frozen_files_verified_against_manifest_and_commit': frozen_files,
        'corpus_audits': corpora, 'models': metrics, 'paired_comparisons': comparisons,
        'bootstrap': {'seed': SEED, 'replicates': REPLICATES, 'unit': 'paired formulas within eight fixed strata'},
        'checks': {'all_640_raw_resource_counts_verified': True, 'all_five_scalar_and_stratum_metrics_verified': True,
                   'all_1280_candidate_errors_verified': True, 'all_four_paired_bootstrap_results_verified': True,
                   'canonical_development_holdout_disjointness_verified': True, 'freeze_sources_unchanged': True},
        'limits': ['Synthetic isolated LUT4 target; no real workload, acquisition, CPU speedup or energy result.',
                   'Exact canonical exclusion does not imply semantic independence.',
                   'Paired intervals are descriptive conditional on fixed strata, not population coverage or adjusted significance.',
                   'Recorded hashes, chronology and Git commit do not independently prove absence of prior label access.',
                   'Verification is sampled; the simulator overflow incident remains retained.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results', type=Path, default=ROOT / 'results/2026-10-13-v4')
    parser.add_argument('--generated', type=Path, default=ROOT / 'generated/v4-corpus')
    parser.add_argument('--freeze-commit', default='2383818')
    parser.add_argument('--output-prefix', type=Path)
    args = parser.parse_args()
    report = audit(args.results, args.generated, args.freeze_commit)
    prefix = args.output_prefix or args.results / 'independent-validation'
    prefix.parent.mkdir(parents=True, exist_ok=True)
    prefix.with_suffix('.json').write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    lines = ['Independent V4 validation: PASSED',
             f"Frozen sources/artifacts/predictions match manifest and commit {args.freeze_commit}.",
             '640 retained raw netlists, all five metric sets, 1280 errors, and four 10000-draw paired comparisons verified.', '']
    for name, values in report['models'].items():
        lines.append(f"{name}: MAE {values['primary_macro_stratum_mae_lut4']:.6f}; RMSLE {values['pooled']['rmsle']:.6f}; positive MAPE {values['pooled']['positive_mape_percent']:.6f}%")
    lines.append('')
    for name, values in report['paired_comparisons'].items():
        interval = values['descriptive_paired_bootstrap_95_percentile_interval_lut4']
        lines.append(f"V4 minus {name}: {values['macro_stratum_mae_difference_lut4']:.6f} LUT4; descriptive interval [{interval[0]:.6f}, {interval[1]:.6f}]; relative MAE reduction {values['v4_relative_mae_reduction_percent']:.4f}%")
    lines.extend(['', *report['limits']])
    prefix.with_suffix('.txt').write_text('\n'.join(lines) + '\n')
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
