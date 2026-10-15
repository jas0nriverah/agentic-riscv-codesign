#!/usr/bin/env python3
"""One fixed mapping217 fit after a fully measured coverage augmentation.

Consumed development only. Retain the original model; freeze all application
and regression predictions before opening their targets. No model selection.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import statistics
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'scripts')]
import numpy as np
from sklearn.ensemble import ExtraTreesRegressor
from threadpoolctl import threadpool_limits
from isaforge import area_model_v6 as v6, area_model_v8 as v8
from evaluate_v8_applications import error_metrics

V8 = ROOT / 'results/2026-10-15-v8-application-transfer'
V6 = ROOT / 'results/2026-10-14-v6'


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def now():
    return datetime.now(timezone.utc).isoformat()


def matrix_for(rows, features, columns):
    if tuple(features['columns']) != tuple(columns):
        raise ValueError('Exact named feature columns required')
    records = {r['formula']: r['values'] for r in features['records']}
    if len(records) != len(features['records']) or set(records) != {r['formula'] for r in rows}:
        raise ValueError('Exact unique feature coverage required')
    x = np.asarray([records[r['formula']] for r in rows], dtype=float)
    if x.shape != (len(rows), len(columns)) or not np.isfinite(x).all() or np.any(x < 0):
        raise ValueError('Finite nonnegative complete feature matrix required')
    return x


def training_arrays(original, candidates, features, labels):
    if tuple(original['columns']) != v8.columns() or len(original['rows']) != 1665:
        raise ValueError('Original1665 full455 fitting data required')
    if len(candidates) != 48 or len({r['formula'] for r in candidates}) != 48:
        raise ValueError('Exact48 distinct coverage originals required')
    original_formulas = [r['formula'] for r in original['rows']]
    formulas = [r['formula'] for r in candidates]
    if len(set(original_formulas)) != 1665 or set(formulas).intersection(original_formulas):
        raise ValueError('Augmentation must not duplicate original fitting formulas')
    targets = {r['formula']: r['lut4_count'] for r in labels}
    if len(targets) != len(labels) or set(targets) != set(formulas):
        raise ValueError('Every coverage original needs exactly one measured label')
    if any(type(v) is not int or v < 0 for v in targets.values()):
        raise ValueError('Coverage targets must be nonnegative integer LUT counts')
    base_x = np.asarray(original['values'], dtype=float)
    base_y = np.asarray([r['lut4_count'] for r in original['rows']], dtype=float)
    if (base_x.shape != (1665, 455) or not np.isfinite(base_x).all() or np.any(base_x < 0)
            or not np.isfinite(base_y).all() or np.any(base_y < 0) or np.any(base_y != np.floor(base_y))):
        raise ValueError('Original fitting values or targets invalid')
    new_x = matrix_for(candidates, features, v6.columns())
    return (np.vstack((base_x[:, :336], new_x)),
            np.concatenate((base_y, [targets[f] for f in formulas])), base_x[:, :336])


def paired_metrics(rows, targets, predictions):
    formulas = [r['formula'] for r in rows]
    if not rows or any(f not in targets for f in formulas):
        raise ValueError('Nonempty complete scoring targets required')
    if any(type(targets[f]) not in (int, float) or not np.isfinite(targets[f]) or targets[f] < 0 or targets[f] != int(targets[f]) for f in formulas):
        raise ValueError('Scoring targets must be finite nonnegative integers')
    result = {}
    for name, points in predictions.items():
        if len(points) != len(rows) or any(any(p.get(k) != row[k] for k in ('formula','benchmark','candidate_id') if k in row) for row,p in zip(rows,points)):
            raise ValueError('Predictions must preserve complete row identity/order')
        result[name] = error_metrics([int(targets[f]) for f in formulas], [p['predicted_lut4'] for p in points])
    return result


def application_metrics(rows, programs, targets, predictions):
    if set(predictions) != {'frozen', 'augmented'} or any(len(ps) != len(rows) for ps in predictions.values()):
        raise ValueError('Exactly two complete prediction sets required')
    if len({(r['benchmark'], r['formula']) for r in rows}) != len(rows):
        raise ValueError('Duplicate program/formula would change formula weighting')
    identities = [(r['benchmark'], r['candidate_id']) for r in rows if 'candidate_id' in r]
    if len(identities) != len(set(identities)):
        raise ValueError('Duplicate program/candidate identity')
    declared = {p['benchmark']: p for p in programs}
    if len(declared) != len(programs) or set(declared) != {r['benchmark'] for r in rows}:
        raise ValueError('Every declared application program must be present')
    by_program = {}
    for program in declared:
        positions = [i for i, r in enumerate(rows) if r['benchmark'] == program]
        by_program[program] = paired_metrics([rows[i] for i in positions], targets,
            {name: [points[i] for i in positions] for name, points in predictions.items()})
    families = sorted({p['family'] for p in programs if p['primary_family']})
    by_family = {family: {name: statistics.fmean(by_program[p['benchmark']][name]['mae_lut4']
        for p in programs if p['primary_family'] and p['family'] == family) for name in predictions} for family in families}
    macro = {name: statistics.fmean(by_family[f][name] for f in families) for name in predictions}
    return {'by_program': by_program, 'primary_family_mae_lut4': by_family,
            'primary_family_macro_mae_lut4': macro,
            'augmented_minus_frozen_mae_lut4': macro['augmented'] - macro['frozen'],
            'paired_family_differences_lut4': {f: by_family[f]['augmented']-by_family[f]['frozen'] for f in families}}


def archive_features(cache, output):
    archive = output / 'feature-evidence.zip'
    files = []
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as stream:
        for path in sorted(cache.rglob('*')):
            if path.is_symlink():
                raise ValueError('No symlinks in feature evidence')
            if path.is_file():
                name = path.relative_to(cache).as_posix()
                stream.write(path, name)
                files.append({'path': name, 'sha256': sha(path), 'size': path.stat().st_size})
    write(output / 'feature-evidence.json', {'archive': archive.name, 'sha256': sha(archive), 'files': files})


def recheck(bindings):
    for path, digest in bindings.items():
        if sha(path) != digest:
            raise ValueError('Training evidence changed during run: ' + str(path))


def measurement_inputs(root, measurements, recipe, review):
    from measure_v9_coverage import verify_archive
    done_path = root / 'measurements/completion.json'
    done = read(done_path)
    if measurements != (root / 'measurements' / done['attempt']).resolve():
        raise ValueError('Exact completed measurement stage under this preparation required')
    if read(measurements / 'completion.json') != done:
        raise ValueError('Stage/root measurement completion differs')
    expected = {'schema': 'isaforge-v9-coverage-measurements-v1', 'complete': True,
        'failures': [], 'candidate_count': 48, 'unique_original_formulas': 48,
        'preparation_sha256': sha(root / 'preparation.json'), 'recipe_sha256': sha(root / 'recipe.json'),
        'candidates_sha256': sha(root / 'candidates.json'), 'frozen_tool': recipe['frozen_tool'],
        'verification_seed': 2026101519, 'vectors_per_formula': 2148, 'workers': 2,
        'original_rtl_only': True, 'legacy_measurements_reused': False,
        'new_estimator_fits': 0, 'new_physical_measurements': 48}
    if any(type(done.get(k)) is not type(v) or done.get(k) != v for k, v in expected.items()):
        raise ValueError('Coverage measurement preparation/recipe/proof/tool contract differs')
    labels_path = measurements / 'labels.json'
    if (done['labels_sha256'] != sha(labels_path)
            or review.get('measurement_completion_sha256') != sha(done_path)
            or review.get('labels_sha256') != sha(labels_path)):
        raise ValueError('Fit release must bind completed measurements and labels')
    verify_archive(root)
    paths = [done_path, measurements / 'completion.json', labels_path,
        root / 'measurements/raw-evidence.json', root / 'measurements/raw-evidence.zip']
    bindings = {path: sha(path) for path in paths}
    labels = read(labels_path)
    recheck(bindings)
    return labels, bindings


@threadpool_limits.wrap(limits=1)
def train(root, measurements, review_path, output):
    from prepare_v9_coverage import validate_preparation
    root, measurements, review_path, output = [Path(p).resolve() for p in (root, measurements, review_path, output)]
    manifest, recipe, candidates = validate_preparation(root)
    if output.exists() or not output.is_relative_to(root):
        raise ValueError('Fit attempt path must be new and owned by its preparation')
    review = read(review_path)
    if (review.get('status') != 'approved-one-coverage-fit'
            or review.get('preparation_sha256') != sha(root / 'preparation.json')
            or review.get('training_runner_sha256') != sha(__file__)):
        raise ValueError('Parent one-fit release must bind preparation and this runner')
    if (root / 'fit-claim.json').exists():
        raise ValueError('This preparation has already claimed its only fit')
    labels, measurement_bindings = measurement_inputs(root, measurements, recipe, review)
    training_path = V8 / 'training/training-data.json'
    original = read(training_path)
    point_freeze = read(V8 / 'point-freeze.json')
    entry = point_freeze['models']['mapping_v6']
    artifact = (V8 / entry['artifact']['path']).resolve()
    if sha(artifact) != entry['artifact']['sha256']:
        raise ValueError('Frozen baseline artifact changed')
    baseline = v6.load_model(artifact)
    if (baseline.training_formula_count != 1665 or baseline.kind != 'mapping_v6'
            or baseline.training_provenance != original['training_provenance']
            or baseline.frozen_tool != recipe['frozen_tool'] or baseline.frozen_tool != original['frozen_tool']):
        raise ValueError('Frozen baseline/training/tool lineage differs')
    output.mkdir(parents=True)
    cache = ROOT / 'generated/v9-coverage-features' / output.name
    if cache.exists():
        raise ValueError('New feature attempt must start without a cache')
    write(output / 'training-start.json', {'schema': 'isaforge-v9-coverage-training-start-v1',
        'started_at_utc': now(), 'preparation_sha256': sha(root / 'preparation.json'),
        'measurement_completion_sha256': sha(measurements / 'completion.json'),
        'review_sha256': sha(review_path), 'runner_sha256': sha(__file__),
        'runtime_source_sha256': v6.source_hashes(), 'configuration': v6.FIXED_PARAMETERS,
        'maximum_fits': 1, 'new_training_formulas': 48, 'original_training_formulas': 1665,
        'scope': 'consumed-development-only', 'original_training_data_sha256': sha(training_path)})
    new_x, records = v6.FeatureExtractor(cache, frozen_tool=baseline.frozen_tool).matrix(candidates, workers=2)
    features = {'columns': list(v6.columns()), 'records': records}
    write(output / 'coverage-features.json', features)
    archive_features(cache, output)
    x, y, original_x = training_arrays(original, candidates, features, labels)
    application_rows, programs = read(V8 / 'rows.json'), read(V8 / 'programs.json')
    application_x = matrix_for(application_rows, read(V8 / 'features.json'), v8.columns())[:, :336]
    regression_rows = read(V6 / 'corpus/test/candidates.json')
    regression_x = matrix_for(regression_rows, read(V6 / 'corpus/test/features.json'), v6.columns())
    if len(application_rows) != 152 or len(regression_rows) != 192:
        raise ValueError('Complete frozen application and regression pools required')
    # Every validation above precedes the one permitted fit. The attempt marker
    # is never overwritten even when the fit or subsequent serialization fails.
    write(output / 'fit-attempt.json', {'started_at_utc': now(), 'fit_index': 1,
        'rows': len(y), 'selected_columns': list(v6.mapping_columns()),
        'features_sha256': sha(output / 'coverage-features.json'), 'labels_sha256': sha(measurements / 'labels.json')})
    validate_preparation(root)
    recheck(measurement_bindings)
    write(root / 'fit-claim.json', {'output': str(output.relative_to(root)),
        'review_sha256': sha(review_path), 'claimed_at_utc': now(), 'maximum_fits': 1,
        'training_start_sha256': sha(output / 'training-start.json')})
    estimator = ExtraTreesRegressor(**v6.FIXED_PARAMETERS)
    estimator.fit(x[:, v6.mapping_indices()], y)
    model = v6.V6Predictor(estimator=estimator, kind='mapping_v6', feature_columns=v6.columns(),
        training_formula_count=len(y), calibration=v6.uncalibrated(), feature_minimum=x.min(axis=0).tolist(),
        feature_maximum=x.max(axis=0).tolist(), frozen_tool=baseline.frozen_tool,
        runtime_source_sha256=v6.source_hashes(), cache_root=str(cache),
        training_provenance={'scope': 'V9 consumed-development coverage augmentation',
            'original': original['training_provenance'], 'preparation_sha256': sha(root / 'preparation.json'),
            'coverage_features_sha256': sha(output / 'coverage-features.json'),
            'coverage_labels_sha256': sha(measurements / 'labels.json')})
    before = model.predict_features(application_rows, application_x)
    saved = v6.save_model(model, output / 'models/mapping-coverage.joblib')
    loaded = v6.load_model(saved['artifact'])
    if loaded.predict_features(application_rows, application_x) != before:
        raise ValueError('Serialized application inference differs in any field')
    cohorts = {'applications': (application_rows, application_x), 'v6_test_regression': (regression_rows, regression_x),
               'original_training_in_sample': (original['rows'], original_x), 'coverage_training_in_sample': (candidates, new_x)}
    predictions = {cohort: {name: m.predict_features(rows, values) for name, m in [('frozen', baseline), ('augmented', loaded)]}
                   for cohort, (rows, values) in cohorts.items()}
    frozen_points = read(V8 / point_freeze['models']['mapping_v6']['predictions']['path'])
    if any(p['formula'] != q['formula'] or p['predicted_lut4'] != q['predicted_lut4'] for p, q in zip(predictions['applications']['frozen'], frozen_points)) or len(frozen_points) != len(application_rows):
        raise ValueError('Frozen baseline application point replay changed')
    write(output / 'point-predictions.json', predictions)
    validate_preparation(root)
    recheck(measurement_bindings)
    write(output / 'point-freeze.json', {'frozen_at_utc': now(), 'scope': 'consumed-development-only',
        'new_fits': 1, 'training_rows': len(y), 'predictions_sha256': sha(output / 'point-predictions.json'),
        'artifact_sha256': sha(saved['artifact']), 'schema_sha256': sha(saved['schema']),
        'preparation_sha256': sha(root / 'preparation.json'), 'source_sha256': v6.source_hashes(),
        'all_application_fields_roundtrip_exact': True, 'evaluation_target_files_opened': False})
    print('Completed one fixed coverage fit and froze all points before evaluation target reads.', flush=True)
    return predictions


def score(root, measurements, output):
    from prepare_v9_coverage import validate_preparation
    root, measurements, output = map(lambda p: Path(p).resolve(), (root, measurements, output))
    _, recipe, _ = validate_preparation(root)
    freeze = read(output / 'point-freeze.json')
    if (freeze['predictions_sha256'] != sha(output / 'point-predictions.json')
            or freeze['preparation_sha256'] != sha(root / 'preparation.json')
            or freeze['source_sha256'] != v6.source_hashes()
            or freeze['artifact_sha256'] != sha(output / 'models/mapping-coverage.joblib')
            or freeze['schema_sha256'] != sha(output / 'models/mapping-coverage.json')):
        raise ValueError('Frozen predictions/preparation/runtime changed')
    predictions = read(output / 'point-predictions.json')
    rows, programs = read(V8 / 'rows.json'), read(V8 / 'programs.json')
    label_entry = recipe['evaluation']['v8']['labels']
    label_path = ROOT / label_entry['path']
    if sha(label_path) != label_entry['sha256']:
        raise ValueError('Consumed V8 target digest differs')
    labels = read(label_path)
    if len(labels) != 146 or len({r['formula'] for r in labels}) != 146:
        raise ValueError('Complete unique V8 target union required')
    targets = {r['formula']: r['lut4_count'] for r in labels}
    app = application_metrics(rows, programs, targets, predictions['applications'])
    primary_positions = [i for i, r in enumerate(rows) if r['primary_family']]
    app['pooled_primary'] = paired_metrics([rows[i] for i in primary_positions], targets,
        {n: [ps[i] for i in primary_positions] for n, ps in predictions['applications'].items()})
    # Fixed diagnosed examples; inclusion depends only on formula syntax.
    constant_positions = [i for i in primary_positions if 'mul(' in rows[i]['formula'] and any(k in rows[i]['formula'] for k in ('addi(0,54)', 'addi(0,2025)', 'addi(lui(4096),-640)'))]
    signed = 'sub(srai(add(in0,in1),5),srai(in1,31))'
    subsets = {'constant_multiply_six': constant_positions,
               'signed_shift_cap_case': [i for i in primary_positions if rows[i]['formula'] == signed]}
    if len(constant_positions) != 6 or len(subsets['signed_shift_cap_case']) != 1:
        raise ValueError('Declared diagnosed subset identity/count differs')
    app['diagnosed_subsets'] = {name: {'formulas': [rows[i]['formula'] for i in positions],
        'scores': paired_metrics([rows[i] for i in positions], targets,
            {n: [ps[i] for i in positions] for n, ps in predictions['applications'].items()})} for name, positions in subsets.items()}
    regression_rows = read(V6 / 'corpus/test/candidates.json')
    regression_entry = recipe['evaluation']['v6_test']['labels']
    regression_path = ROOT / regression_entry['path']
    if sha(regression_path) != regression_entry['sha256']:
        raise ValueError('Consumed V6 regression target digest differs')
    regression_labels = read(regression_path)
    if len(regression_labels) != 192 or len({r['formula'] for r in regression_labels}) != 192:
        raise ValueError('Complete unique regression target union required')
    regression_targets = {r['formula']: r['lut4_count'] for r in regression_labels}
    original = read(V8 / 'training/training-data.json')
    _, _, candidates = validate_preparation(root)
    if sha(measurements / 'labels.json') != read(output / 'fit-attempt.json')['labels_sha256']:
        raise ValueError('Coverage fitting targets changed before scoring')
    new_targets = {r['formula']: r['lut4_count'] for r in read(measurements / 'labels.json')}
    result = {'schema': 'isaforge-v9-coverage-development-evaluation-v1', 'scope': 'consumed-development-only',
        'primary': app, 'v6_test_regression': paired_metrics(regression_rows, regression_targets, predictions['v6_test_regression']),
        'original_training_in_sample': paired_metrics(original['rows'], {r['formula']: r['lut4_count'] for r in original['rows']}, predictions['original_training_in_sample']),
        'coverage_training_in_sample': paired_metrics(candidates, new_targets, predictions['coverage_training_in_sample']),
        'point_freeze_sha256': sha(output / 'point-freeze.json'), 'evaluated_at_utc': now(),
        'limitations': ['All evaluation cohorts are consumed development data; no independent transfer claim.',
            'One fixed seed and one fit; training errors are in-sample diagnostics.',
            'Measured iCE40 LUT4 count is not ASIC physical area, CPU speedup, timing, or energy.']}
    write(output / 'evaluation.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=('train', 'score'))
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--measurements', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--review', type=Path)
    args = parser.parse_args()
    if args.stage == 'train':
        if args.review is None:
            parser.error('train requires hash-bound --review')
        train(args.root, args.measurements, args.review, args.output)
    else:
        result = score(args.root, args.measurements, args.output)
        print(json.dumps(result['primary']['primary_family_macro_mae_lut4'], indent=2))
