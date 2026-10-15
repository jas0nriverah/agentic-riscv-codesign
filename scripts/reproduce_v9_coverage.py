#!/usr/bin/env python3
"""Replay fixed V9 coverage evidence using saved features, without fits/native tools.

Use the pinned numerical libraries and proofs extra; add reports for figures.
Output must be fresh and outside results. Independent audits run by default.
"""
from __future__ import annotations
import argparse
from contextlib import ExitStack, contextmanager
import hashlib
import importlib.util
import json
import math
from pathlib import Path, PurePosixPath
import sys
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'scripts')]
import numpy as np
from isaforge import area_model_v5 as v5, area_model_v6 as v6, area_model_v8 as v8
import prepare_v9_coverage as preparation
import train_v9_coverage as trainer

DEFAULT_ROOT = ROOT / 'results/2026-10-15-v9-coverage-development'
DEFAULT_OUTPUT = ROOT / 'generated/reproduction/v9-coverage'
COUNTS = {'applications': 152, 'v6_test_regression': 192,
          'original_training_in_sample': 1665, 'coverage_training_in_sample': 48}


def read(p): return json.loads(Path(p).read_text())
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def need(value, message):
    if not value: raise ValueError(message)
def write(p, value):
    with Path(p).open('x') as stream:
        stream.write(json.dumps(value, indent=2, allow_nan=False) + '\n')
def exact(a, b):
    return json.dumps(a, sort_keys=True, separators=(',', ':'), allow_nan=False) == json.dumps(b, sort_keys=True, separators=(',', ':'), allow_nan=False)


@contextmanager
def no_fit_or_native():
    from sklearn.ensemble import ExtraTreesRegressor
    from sklearn.tree import DecisionTreeRegressor, ExtraTreeRegressor
    from isaforge import semantic_features_v7 as semantic
    with ExitStack() as stack:
        for cls in (ExtraTreesRegressor, DecisionTreeRegressor, ExtraTreeRegressor):
            stack.enter_context(patch.object(cls, 'fit', side_effect=RuntimeError('Reproduction forbids fitting')))
        for module in (v5, v6, v8):
            stack.enter_context(patch.object(module.FeatureExtractor, 'matrix', side_effect=RuntimeError('Reproduction forbids native feature extraction')))
        stack.enter_context(patch.object(semantic, 'analyze_modes', side_effect=RuntimeError('Reproduction forbids normalization retries')))
        stack.enter_context(patch('subprocess.Popen', side_effect=RuntimeError('Reproduction forbids native processes')))
        yield


def verify_feature_archive(fit):
    manifest = read(fit / 'feature-evidence.json')
    need(manifest['archive'] == 'feature-evidence.zip', 'Feature archive name differs')
    archive = fit / manifest['archive']
    need(sha(archive) == manifest['sha256'], 'Feature archive digest differs')
    records = {r['path']: r for r in manifest['files']}
    need(records and len(records) == len(manifest['files']), 'Unique nonempty feature archive records required')
    with zipfile.ZipFile(archive) as z:
        names = z.namelist()
        need(len(names) == len(set(names)) and set(names) == set(records), 'Feature archive inventory differs')
        for info in z.infolist():
            name = PurePosixPath(info.filename)
            need(not name.is_absolute() and '..' not in name.parts and '\\' not in info.filename
                 and str(name) == info.filename and not info.is_dir()
                 and ((info.external_attr >> 16) & 0o170000) in (0, 0o100000), 'Unsafe feature archive member')
            data = z.read(info); record = records[info.filename]
            need(type(record['size']) is int and len(data) == record['size']
                 and hashlib.sha256(data).hexdigest() == record['sha256'], 'Feature archive member differs')
    return len(records)


def authenticate(root, fit):
    manifest, recipe, candidates = preparation.validate_preparation(root)
    freeze = read(fit / 'point-freeze.json')
    need(freeze['new_fits'] == 1 and freeze['training_rows'] == 1713
         and freeze['evaluation_target_files_opened'] is False
         and freeze['preparation_sha256'] == sha(root / 'preparation.json')
         and freeze['source_sha256'] == v6.source_hashes(), 'Fixed completed one-fit freeze differs')
    for path, key in [(fit / 'point-predictions.json', 'predictions_sha256'),
                      (fit / 'models/mapping-coverage.joblib', 'artifact_sha256'),
                      (fit / 'models/mapping-coverage.json', 'schema_sha256')]:
        need(sha(path) == freeze[key], 'Frozen point/artifact/schema digest differs')
    review = read(root / 'fit-approval.json'); claim = read(root / 'fit-claim.json')
    start = read(fit / 'training-start.json'); attempt = read(fit / 'fit-attempt.json')
    need(review['status'] == 'approved-one-coverage-fit'
         and review['preparation_sha256'] == sha(root / 'preparation.json')
         and review['training_runner_sha256'] == sha(ROOT / recipe['training_script']), 'Fit approval differs')
    need(fit.is_relative_to(root) and claim['output'] == fit.relative_to(root).as_posix()
         and claim['maximum_fits'] == start['maximum_fits'] == 1
         and claim['training_start_sha256'] == sha(fit / 'training-start.json')
         and claim['review_sha256'] == start['review_sha256'] == sha(root / 'fit-approval.json')
         and start['runner_sha256'] == sha(ROOT / recipe['training_script'])
         and start['configuration'] == recipe['fixed_parameters'] == v6.FIXED_PARAMETERS
         and attempt['fit_index'] == 1 and attempt['rows'] == 1713
         and attempt['selected_columns'] == list(v6.mapping_columns()), 'One-fit claim/start/attempt differs')
    completion = read(root / 'measurements/completion.json')
    need(isinstance(completion['attempt'], str) and len(completion['attempt']) == 12
         and completion['attempt'].startswith('attempt-') and completion['attempt'][8:].isdigit(), 'Owned measurement attempt required')
    measurements = root / 'measurements' / completion['attempt']
    _, measured_bindings = trainer.measurement_inputs(root, measurements, recipe, review)
    need(start['measurement_completion_sha256'] == sha(root / 'measurements/completion.json')
         and attempt['labels_sha256'] == completion['labels_sha256']
         and attempt['features_sha256'] == sha(fit / 'coverage-features.json'), 'Fitted labels/features/completion changed')
    feature_members = verify_feature_archive(fit)
    for key, entry in recipe['baseline_model'].items():
        need(sha((root / entry['path']).resolve()) == entry['sha256'], 'Original baseline ' + key + ' changed')
    reference = read(fit / 'evaluation.json')
    need(reference['point_freeze_sha256'] == sha(fit / 'point-freeze.json'), 'Published evaluation freeze differs')
    paths = [(root / e['path']).resolve() for e in manifest['files']]
    paths += [root / n for n in ('preparation.json', 'measurement-approval.json', 'label-release.json', 'fit-approval.json', 'fit-claim.json')]
    paths += list(measured_bindings)
    paths += [fit / n for n in ('point-freeze.json', 'point-predictions.json', 'training-start.json', 'fit-attempt.json',
        'models/mapping-coverage.joblib', 'models/mapping-coverage.json', 'coverage-features.json', 'feature-evidence.json', 'feature-evidence.zip', 'evaluation.json')]
    return {'recipe': recipe, 'candidates': candidates, 'measurements': measurements,
            'reference': reference, 'feature_archive_members': feature_members,
            'bindings': {p: sha(p) for p in paths}}


def replay_inference(root, fit, authenticated):
    recipe = authenticated['recipe']
    baseline = v6.load_model((root / recipe['baseline_model']['artifact']['path']).resolve())
    augmented = v6.load_model(fit / 'models/mapping-coverage.joblib')
    need(baseline.training_formula_count == 1665 and augmented.training_formula_count == 1713
         and baseline.kind == augmented.kind == 'mapping_v6'
         and baseline.estimator.get_params() == augmented.estimator.get_params() == trainer.ExtraTreesRegressor(**v6.FIXED_PARAMETERS).get_params()
         and len(augmented.estimator.estimators_) == 300
         and all(t.tree_.n_node_samples[0] == 1713 for t in augmented.estimator.estimators_), 'Loaded fixed forests differ')
    original = read(root / 'original-training.json')
    app_rows = read(trainer.V8 / 'rows.json'); regression_rows = read(trainer.V6 / 'corpus/test/candidates.json')
    cohorts = {
        'applications': (app_rows, trainer.matrix_for(app_rows, read(trainer.V8 / 'features.json'), v8.columns())[:, :336]),
        'v6_test_regression': (regression_rows, trainer.matrix_for(regression_rows, read(trainer.V6 / 'corpus/test/features.json'), v6.columns())),
        'original_training_in_sample': (original['rows'], np.asarray(original['values'], dtype=float)),
        'coverage_training_in_sample': (authenticated['candidates'], trainer.matrix_for(authenticated['candidates'], read(fit / 'coverage-features.json'), v6.columns())),
    }
    frozen = read(fit / 'point-predictions.json')
    need(set(frozen) == set(COUNTS), 'Complete four-cohort frozen points required')
    for cohort, (rows, matrix) in cohorts.items():
        need(len(rows) == COUNTS[cohort] and matrix.shape == (len(rows), 336)
             and np.isfinite(matrix).all() and (matrix >= 0).all(), 'Complete saved-feature cohort required')
        need(set(frozen[cohort]) == {'frozen', 'augmented'}, 'Exactly frozen/augmented points required')
        for name, model in [('frozen', baseline), ('augmented', augmented)]:
            need(exact(model.predict_features(rows, matrix), frozen[cohort][name]), 'Saved-feature inference differs: ' + cohort + '/' + name)
    return {'cohort_rows': COUNTS, 'models_per_cohort': 2, 'all_prediction_fields_and_json_types_exact': True}


def score_to_fresh(root, fit, measurements, output):
    """Redirect only the frozen scorer's final write; never copy/mutate fit files."""
    def writer(path, value):
        need(Path(path).resolve() == fit / 'evaluation.json', 'Unexpected frozen scorer write')
        write(output / 'evaluation.json', value)
    with patch.object(trainer, 'write', side_effect=writer):
        return trainer.score(root, measurements, fit)


def rmsle_path(path):
    p = path.split('/')[1:]; models = ('frozen', 'augmented')
    return ((len(p) == 5 and p[:2] == ['primary', 'by_program'] and p[3] in models and p[4] == 'rmsle')
        or (len(p) == 4 and p[:2] == ['primary', 'pooled_primary'] and p[2] in models and p[3] == 'rmsle')
        or (len(p) == 6 and p[:2] == ['primary', 'diagnosed_subsets'] and p[3] == 'scores' and p[4] in models and p[5] == 'rmsle')
        or (len(p) == 3 and p[0] in ('v6_test_regression', 'original_training_in_sample', 'coverage_training_in_sample') and p[1] in models and p[2] == 'rmsle'))


def compare_evaluation(reference, actual):
    need(isinstance(reference, dict) and isinstance(actual, dict) and 'evaluated_at_utc' in reference and 'evaluated_at_utc' in actual, 'Timestamped evaluations required')
    changes = []; failures = []
    def walk(a, b, path=''):
        if type(a) is not type(b): failures.append({'path': path, 'reason': 'type'})
        elif isinstance(a, dict):
            if set(a) != set(b): failures.append({'path': path, 'reason': 'keys'})
            else:
                for key in a:
                    if path == '' and key == 'evaluated_at_utc': continue
                    walk(a[key], b[key], path + '/' + key.replace('~', '~0').replace('/', '~1'))
        elif isinstance(a, list):
            if len(a) != len(b): failures.append({'path': path, 'reason': 'length'})
            else:
                for i, (x, y) in enumerate(zip(a, b)): walk(x, y, path + '/' + str(i))
        elif not exact(a, b):
            item = {'path': path, 'expected': a, 'actual': b}
            if type(a) is float and type(b) is float and a >= 0 and b >= 0 and math.isfinite(a) and math.isfinite(b) and rmsle_path(path) and abs(a - b) <= 1e-14:
                changes.append(item)
            else: failures.append(item)
    walk(reference, actual)
    return {'status': 'pass' if not failures else 'fail', 'accepted_rmsle_roundoff_count': len(changes),
            'incompatible_difference_count': len(failures), 'accepted_rmsle_roundoff': changes[:100], 'differences': failures[:100],
            'rule': 'Every field/type exact except top-level evaluation time and declared finite nonnegative RMSLE floats within1e-14 absolute/zero relative tolerance.'}


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path); module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_audits(root, fit, output):
    folder = root / 'independent-audit'
    manifest = read(folder / 'manifest.json')
    for entry in manifest['files']:
        need(sha(folder / entry['path']) == entry['sha256'], 'Independent raw audit package changed')
    original_raw = read(folder / 'raw-audit.json')
    need(sha(folder / 'raw-audit.json') == read(root / 'fit-approval.json')['raw_audit_sha256']
         and sha(folder / 'audit_v9_raw.py') == original_raw['audit_source_sha256']
         and sha(folder / 'unsigned_oracle.py') == original_raw['oracle_source_sha256'], 'Reviewed independent raw audit source differs')
    oracle = load_module(folder / 'unsigned_oracle.py', 'v9_reproduction_unsigned_oracle')
    with patch.dict(sys.modules, {'unsigned_oracle': oracle}):
        raw_module = load_module(folder / 'audit_v9_raw.py', 'v9_reproduction_raw_audit')
        raw = raw_module.run(root, folder / 'audit-readiness.json')
    need(raw['passed'] is True and raw['netlists_recounted'] == 48 and raw['independent_expected_outputs_recomputed'] == 103104, 'Independent raw replay incomplete')
    write(output / 'raw-audit.json', raw)
    metric_path = root / 'fit-review/replay_fit_metrics.py'
    need(sha(metric_path) == read(root / 'fit-review/metric-replay.json')['audit_source_sha256'], 'Reviewed independent metric source changed')
    metric_module = load_module(metric_path, 'v9_reproduction_metric_audit')
    metric_module.run(ROOT, root, fit, output / 'metric-replay.json')
    need(read(output / 'metric-replay.json')['status'] == 'pass', 'Independent metric replay failed')
    return {'raw_expected_outputs_recomputed': 103104, 'netlists_recounted': 48, 'independent_metrics_passed': True}


def reproduce(root=DEFAULT_ROOT, output=DEFAULT_OUTPUT, *, fit=None, skip_figures=False):
    root, output = Path(root).resolve(), Path(output).resolve()
    fit = (root / 'fit-attempt-0000') if fit is None else Path(fit).resolve()
    need(not output.exists(), 'Reproduction output must be fresh')
    need(not output.is_relative_to(root) and not output.is_relative_to(ROOT / 'results'), 'Reproduction output must be outside results')
    with no_fit_or_native():
        authenticated = authenticate(root, fit)
        inferred = replay_inference(root, fit, authenticated)
        output.mkdir(parents=True)
        actual = score_to_fresh(root, fit, authenticated['measurements'], output)
        comparison = compare_evaluation(authenticated['reference'], actual)
        write(output / 'comparison.json', comparison)
        need(comparison['status'] == 'pass', 'Frozen arithmetic differs from published evaluation; see comparison.json')
        audited = run_audits(root, fit, output)
        need(all(sha(p) == digest for p, digest in authenticated['bindings'].items()), 'Frozen source/evidence changed during reproduction')
    if not skip_figures:
        from plot_v9_coverage import run as plot
        plot(root, fit, output / 'figures')
    report = {'schema': 'isaforge-v9-coverage-reproduction-v1', 'status': 'pass',
        'preparation_sha256': sha(root / 'preparation.json'), 'point_freeze_sha256': sha(fit / 'point-freeze.json'),
        'published_evaluation_sha256': sha(fit / 'evaluation.json'), 'reproduced_evaluation_sha256': sha(output / 'evaluation.json'),
        'source_sha256': sha(__file__), 'feature_archive_members_verified': authenticated['feature_archive_members'],
        'saved_feature_inference': inferred, 'comparison': comparison, 'independent_audits': audited,
        'new_fits': 0, 'new_feature_extractions': 0, 'new_target_measurements': 0, 'archives_restored': False,
        'figures_generated': not skip_figures, 'scope': 'Replay of consumed-development evidence; no independent transfer confirmation.'}
    write(output / 'reproduction.json', report)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=DEFAULT_ROOT)
    parser.add_argument('--fit', type=Path)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--skip-figures', action='store_true')
    args = parser.parse_args()
    print(json.dumps(reproduce(args.root, args.output, fit=args.fit, skip_figures=args.skip_figures), indent=2))
