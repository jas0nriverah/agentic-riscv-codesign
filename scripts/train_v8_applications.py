#!/usr/bin/env python3
"""Fit exactly two fixed legacy representations and freeze application points.

No application target file is read. The existing mapping217 control is reused.
All predictions precede a separate, committed original-RTL label release.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'scripts')]
import numpy as np
from sklearn.ensemble import ExtraTreesRegressor
from threadpoolctl import threadpool_limits
from isaforge import area_model_v5 as v5, area_model_v6 as v6, area_model_v8 as v8
from isaforge import masterrtl_baseline as master
from train_v6 import read, sha, write, now, record, checked

MODELS = ('mapping_v6', 'legacy_original336', 'legacy_rewritten336', 'dual_graph', 'sog_tuned', 'masterrtl_fixed')


def verify_files(manifest, base):
    return [checked(entry, base) for entry in manifest['files']]


def point_projection(rows, predictions, name):
    """Strip historical calibration fields explicitly; keep points and diagnostics."""
    if len(rows) != len(predictions):
        raise ValueError('Complete application prediction coverage required')
    result = []
    by_formula = {}
    for row, prediction in zip(rows, predictions):
        if any(row[k] != prediction.get(k) for k in ('benchmark', 'candidate_id', 'formula')):
            raise ValueError('Prediction identity/order mismatch')
        value = prediction['predicted_lut4']
        if isinstance(value, bool) or not np.isfinite(value) or value < 0:
            raise ValueError('Finite nonnegative point prediction required')
        if row['formula'] in by_formula and by_formula[row['formula']] != value:
            raise ValueError('Same formula must have the same model point across programs')
        by_formula[row['formula']] = value
        spread, outside = prediction.get('tree_disagreement_lut4'), prediction.get('outside_training_feature_ranges')
        if spread is not None and (isinstance(spread, bool) or not np.isfinite(spread) or spread < 0):
            raise ValueError('Invalid tree disagreement diagnostic')
        if outside is not None and (type(outside) is not int or outside < 0):
            raise ValueError('Invalid outside-training-range diagnostic')
        result.append({**{k: row[k] for k in ('benchmark', 'candidate_id', 'formula')},
                       'model': name, 'predicted_lut4': float(value), 'upper_lut4': None,
                       'calibration_status': 'point_only_application_pilot',
                       'tree_disagreement_lut4': prediction.get('tree_disagreement_lut4'),
                       'outside_training_feature_ranges': prediction.get('outside_training_feature_ranges')})
    return result


@threadpool_limits.wrap(limits=1)
def run(root, training, review_path, cache_root):
    root, training, review_path, cache_root = map(lambda p: Path(p).resolve(), (root, training, review_path, cache_root))
    if any((root / name).exists() for name in ('training-start.json', 'point-freeze.json', 'label-release.json', 'measurements')):
        raise ValueError('Existing training or label attempt is immutable')
    input_path = root / 'input-seal.json'
    inputs = read(input_path)
    if inputs['status'] != 'sealed-inputs-only' or inputs['runtime_source_sha256'] != v8.source_hashes():
        raise ValueError('Complete source-bound input seal required')
    paths = verify_files(inputs, root)
    preparation_path = training / 'preparation.json'
    preparation = read(preparation_path)
    paths += verify_files(preparation, training)
    if preparation['runtime_source_sha256'] != v8.source_hashes():
        raise ValueError('Training preparation runtime changed')
    train_path = checked(preparation['training_data'], training)
    review = read(review_path)
    if (review.get('status') != 'approved-fixed-two-fits'
            or review.get('input_seal_sha256') != sha(input_path)
            or review.get('training_preparation_sha256') != sha(preparation_path)
            or review.get('training_runner_sha256') != sha(__file__)):
        raise ValueError('Independent review and explicit parent two-fit release required')
    data = read(train_path)
    if tuple(data['columns']) != v8.columns() or len(data['rows']) != 1665:
        raise ValueError('Original1665 full455 training contract required')
    x = np.asarray(data['values'], dtype=float)
    y = np.asarray([r['lut4_count'] for r in data['rows']], dtype=float)
    if x.shape != (1665, 455) or not np.isfinite(x).all() or np.any(x < 0) or not np.isfinite(y).all() or np.any(y < 0):
        raise ValueError('Invalid training matrix or targets')
    rows_path = checked(inputs['rows'], root)
    feature_path = checked(inputs['features'], root)
    rows = read(rows_path)
    features = read(feature_path)
    if tuple(features['columns']) != v8.columns():
        raise ValueError('Application full455 feature columns differ')
    by_formula = {r['formula']: r['values'] for r in features['records']}
    if len(by_formula) != len(features['records']) or set(by_formula) != {r['formula'] for r in rows}:
        raise ValueError('Complete canonical feature coverage required')
    application_x = np.asarray([by_formula[r['formula']] for r in rows], dtype=float)
    if application_x.shape != (len(rows), 455) or not np.isfinite(application_x).all() or np.any(application_x < 0):
        raise ValueError('Invalid application feature matrix')
    prior_root = ROOT / 'results/2026-10-14-v6'
    old_root = ROOT / 'results/2026-10-14-v5'
    prior = read(prior_root / 'point-freeze.json')
    old = read(old_root / 'freeze.json')
    control_entries = {'mapping_v6': (prior_root, prior['models']['mapping_v6'])}
    control_entries.update({name: (old_root, old['models'][name]) for name in ('dual_graph', 'sog_tuned', 'masterrtl_fixed')})
    controls, entries = {}, {}
    for name, (base, entry) in control_entries.items():
        artifact = checked(entry['artifact'], base)
        schema = checked(entry['schema'], base)
        paths += [artifact, schema]
        entries[name] = {k: record(p, root) for k, p in [('artifact', artifact), ('schema', schema)]}
        if name == 'mapping_v6':
            controls[name] = v6.load_model(artifact, cache_root)
        elif name == 'masterrtl_fixed':
            controls[name] = master.load_model(artifact, cache_root / 'sog')
        else:
            controls[name] = v5.load_model(artifact, cache_root)
    baseline = controls['mapping_v6']
    if (baseline.training_provenance != data['training_provenance'] or baseline.frozen_tool != data['frozen_tool']
            or baseline.estimator.get_params() != ExtraTreesRegressor(**v8.FIXED_PARAMETERS).get_params()):
        raise ValueError('Frozen mapping training lineage/recipe differs')
    paths += [input_path, preparation_path, train_path, review_path, rows_path, feature_path, Path(__file__),
              prior_root / 'point-freeze.json', old_root / 'freeze.json']
    bindings = [record(p, root) for p in dict.fromkeys(paths)]
    observed, logical = v8.environment(), v8.compatibility()
    start = {'schema': 'isaforge-v8-training-start-v1', 'started_at_utc': now(), 'files': bindings,
             'environment': observed, 'compatibility': logical, 'runtime_source_sha256': v8.source_hashes(),
             'training_provenance': data['training_provenance'], 'configuration': v8.FIXED_PARAMETERS,
             'planned_fits': list(v8.TRAINED_VIEWS), 'maximum_fits': 2,
             'fresh_application_labels_read': False, 'mapping_control_refitted': False}
    write(root / 'training-start.json', start)
    for index, view in enumerate(v8.TRAINED_VIEWS, 1):
        write(root / 'fit-attempts' / (view + '.json'), {'fit_index': index, 'view': view, 'started_at_utc': now(),
              'training_start_sha256': sha(root / 'training-start.json')})
        estimator = ExtraTreesRegressor(**v8.FIXED_PARAMETERS)
        estimator.fit(x[:, v8.view_indices(view)], y)
        model = v8.V8Predictor(estimator=estimator, view=view, feature_columns=v8.columns(), training_formula_count=1665,
            feature_minimum=x.min(axis=0).tolist(), feature_maximum=x.max(axis=0).tolist(), frozen_tool=data['frozen_tool'],
            runtime_source_sha256=v8.source_hashes(), training_provenance=data['training_provenance'],
            training_environment=observed, audited_compatibility=logical, cache_root=str(cache_root))
        before = model.predict_features(rows, application_x, feature_columns=v8.columns())
        saved = v8.save_model(model, root / 'models' / (view + '.joblib'))
        controls[view] = v8.load_model(saved['artifact'], cache_root)
        if controls[view].predict_features(rows, application_x, feature_columns=v8.columns()) != before:
            raise ValueError('All-field application inference changed after serialization')
        entries[view] = {key: record(saved[key], root) for key in ('artifact', 'schema')}
        print('Completed fixed fit:', view, flush=True)
    for name in MODELS:
        model = controls[name]
        if name in v8.TRAINED_VIEWS:
            predictions = model.predict_features(rows, application_x, feature_columns=v8.columns())
        elif name == 'mapping_v6':
            predictions = model.predict_features(rows, application_x[:, :336])
        elif name == 'masterrtl_fixed':
            predictions = model.predict(rows)
        else:
            predictions = model.predict_features(rows, application_x[:, :313])
        path = root / 'point-predictions' / (name + '.json')
        write(path, point_projection(rows, predictions, name))
        entries[name]['predictions'] = record(path, root)
    verify_files(start, root)
    if v8.environment() != observed or v8.source_hashes() != start['runtime_source_sha256']:
        raise ValueError('Training source/environment changed during fits')
    write(root / 'point-freeze.json', {'schema': 'isaforge-v8-application-points-v1', 'frozen_at_utc': now(),
          'files': [*bindings, record(root / 'training-start.json', root),
                    *(record(p, root) for p in sorted((root / 'fit-attempts').glob('*.json')))],
          'models': entries, 'new_estimator_fits': 2, 'application_rows': len(rows),
          'unique_original_formulas': len(by_formula), 'fresh_application_labels_read': False,
          'primary_comparison': 'legacy_rewritten336 minus mapping_v6', 'point_only': True})
    print('Frozen all six application point prediction sets; no labels released.', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('root', 'training', 'review', 'cache-root'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    run(args.root, args.training, args.review, args.cache_root)
