#!/usr/bin/env python3
"""Independent, no-fit V8 CLI replay against the frozen application points.

The audit runs two views against both the sealed inputs and reversed inputs
carrying poisoned unused outcome metadata. Native extraction and fitting are
forbidden in each worker. Existing evidence is never replaced.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys

VIEWS = ('legacy_original336', 'legacy_rewritten336')
IDENTITY = ('benchmark', 'candidate_id', 'formula')
FIELDS = (*IDENTITY, 'model', 'predicted_lut4', 'upper_lut4',
          'calibration_status', 'tree_disagreement_lut4',
          'outside_training_feature_ranges')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def write_new(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def proof_digest(features):
    # Preserve every original record field except the numerical feature array;
    # this explicitly includes proof outcomes, fallbacks, and tool identities.
    records = [{k: v for k, v in r.items() if k != 'values' and k != 'audit_unused_outcome'}
               for r in features['records']]
    records.sort(key=lambda row: row['formula'])
    return hashlib.sha256(json.dumps(records, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def worker(repo, cli_args):
    sys.path[:0] = [str(repo), str(repo / 'scripts')]
    from isaforge import area_model_v8 as v8
    from isaforge import area_model_v5 as v5, area_model_v6 as v6
    from isaforge import semantic_features_v7 as semantic
    from sklearn.ensemble import ExtraTreesRegressor
    from sklearn.tree import DecisionTreeRegressor, ExtraTreeRegressor

    attempted = []

    def forbidden(name):
        def fail(*args, **kwargs):
            attempted.append(name)
            raise AssertionError('Forbidden operation during stored-feature replay: ' + name)
        return fail

    # Loading compatibility records may inspect installed Z3, but cannot run a
    # timed normalization proof, native tool, process, or feature extraction.
    for cls in (ExtraTreesRegressor, DecisionTreeRegressor, ExtraTreeRegressor):
        cls.fit = forbidden(cls.__name__ + '.fit')
    for module in (v5, v6, v8):
        module.FeatureExtractor.matrix = forbidden(module.__name__ + '.FeatureExtractor.matrix')
    v8.V8Predictor.predict_with_evidence = forbidden('V8Predictor.predict_with_evidence')
    semantic.analyze_modes = forbidden('semantic.analyze_modes')
    semantic._prove = forbidden('semantic._prove')
    subprocess.Popen = forbidden('subprocess.Popen')
    subprocess.run = forbidden('subprocess.run')
    subprocess.call = forbidden('subprocess.call')
    subprocess.check_call = forbidden('subprocess.check_call')
    subprocess.check_output = forbidden('subprocess.check_output')
    os.system = forbidden('os.system')

    def audit_hook(event, args):
        if event in ('subprocess.Popen', 'os.system', 'os.posix_spawn', 'os.fork', 'os.forkpty'):
            forbidden(event)()
        if event == 'open' and isinstance(args[0], (str, bytes, os.PathLike)):
            name = os.fsdecode(args[0]).lower()
            if ('training-data.json' in name or '/measurements/' in name
                    or name.endswith('/label-release.json') or name.endswith('/targets.json')):
                forbidden('outcome/training-data read: ' + name)()

    sys.addaudithook(audit_hook)
    sys.argv = [str(repo / 'scripts/infer_v8_applications.py'), *cli_args]
    runpy.run_path(sys.argv[0], run_name='__main__')
    assert not attempted, attempted


def project(prediction, view):
    # Deliberately independent of train_v8_applications.point_projection.
    assert prediction['model'] == 'v8_' + view
    assert prediction['calibration_status'] == 'point_only'
    assert prediction['upper_lut4'] is None
    assert 'no calibrated application upper bound' in prediction['uncertainty_scope']
    return {**{key: prediction[key] for key in IDENTITY},
            'model': view, 'predicted_lut4': prediction['predicted_lut4'],
            'upper_lut4': None, 'calibration_status': 'point_only_application_pilot',
            'tree_disagreement_lut4': prediction['tree_disagreement_lut4'],
            'outside_training_feature_ranges': prediction['outside_training_feature_ranges']}


def keyed(rows):
    result = {tuple(row[key] for key in IDENTITY): row for row in rows}
    assert len(result) == len(rows), 'Duplicate membership identity'
    return result


def audit(repo, root, output):
    assert not output.exists(), 'Audit evidence directory is immutable'
    freeze_path = root / 'point-freeze.json'
    freeze = read(freeze_path)  # Fails before creating evidence if models are absent.
    assert freeze['new_estimator_fits'] == 2 and freeze['point_only'] is True
    assert freeze['fresh_application_labels_read'] is False
    rows_path, features_path = root / 'rows.json', root / 'features.json'
    rows, features = read(rows_path), read(features_path)
    assert len(features['columns']) == 455
    assert len({r['formula'] for r in features['records']}) == len(features['records'])
    assert {r['formula'] for r in features['records']} == {r['formula'] for r in rows}
    bound = [freeze_path, rows_path, features_path, repo / 'scripts/infer_v8_applications.py', Path(__file__).resolve()]
    for view in VIEWS:
        for key in ('artifact', 'schema', 'predictions'):
            entry = freeze['models'][view][key]
            path = (root / entry['path']).resolve()
            assert digest(path) == entry['sha256']
            bound.append(path)
    hashes = {str(p): digest(p) for p in bound}
    output.mkdir(parents=True)
    altered_rows = []
    for row in reversed(rows):
        altered = {key: deepcopy(row[key]) for key in IDENTITY}
        altered.update({key: {'poisoned_unused_metadata': -123456789} for key in row if key not in IDENTITY})
        altered.update(lut4_count=-123456789, measured_lut4=987654321,
                       predicted_lut4=987654321, target={'forbidden_if_consumed': True})
        altered_rows.append(altered)
    altered_features = deepcopy(features)
    altered_features['records'].reverse()
    for record in altered_features['records']:
        record['audit_unused_outcome'] = {'lut4_count': -123456789, 'target': 987654321}
    assert proof_digest(features) == proof_digest(altered_features)
    altered_rows_path = output / 'reversed-poisoned-rows.json'
    altered_features_path = output / 'reversed-poisoned-features.json'
    write_new(altered_rows_path, altered_rows)
    write_new(altered_features_path, altered_features)
    runs, baseline = [], {}
    for view in VIEWS:
        expected_path = (root / freeze['models'][view]['predictions']['path']).resolve()
        expected = read(expected_path)
        assert all(set(row) == set(FIELDS) for row in expected)
        for variant, rp, fp, input_rows in (
                ('sealed', rows_path, features_path, rows),
                ('reversed-poisoned', altered_rows_path, altered_features_path, altered_rows)):
            prediction_path = output / (view + '-' + variant + '.json')
            model_path = (root / freeze['models'][view]['artifact']['path']).resolve()
            cli_args = ['--model', str(model_path), '--candidates', str(rp),
                        '--output', str(prediction_path), '--cache-root', str(output / 'forbidden-native-cache'),
                        '--features', str(fp)]
            command = [sys.executable, str(Path(__file__).resolve()), '--worker', '--repo', str(repo), '--', *cli_args]
            completed = subprocess.run(command, cwd=repo, text=True, capture_output=True)
            log_path = output / (view + '-' + variant + '.log')
            with log_path.open('x') as stream:
                stream.write(completed.stdout + completed.stderr)
            assert completed.returncode == 0, f'CLI failed; see {log_path}'
            evidence = read(prediction_path)
            actual = evidence['predictions']
            assert evidence['mode'] == 'stored-full455-feature-replay-no-native-extraction'
            assert evidence['upper_bounds_available'] is False
            assert evidence['feature_file_sha256'] == digest(fp)
            assert evidence['application_rows'] == len(rows)
            assert [tuple(p[k] for k in IDENTITY) for p in actual] == [tuple(r[k] for k in IDENTITY) for r in input_rows]
            projected = [project(row, view) for row in actual]
            assert keyed(projected) == keyed(expected), f'Frozen point mismatch: {view}/{variant}'
            if variant == 'sealed':
                assert projected == expected, 'Sealed row order differs'
                baseline[view] = keyed(actual)
            else:
                assert keyed(actual) == baseline[view], 'Unused metadata/order influenced raw point output'
            runs.append({'view': view, 'variant': variant, 'rows': len(actual),
                         'all_projected_fields_exactly_equal_frozen_points': True,
                         'cli_output': str(prediction_path), 'cli_output_sha256': digest(prediction_path),
                         'guarded_worker_returncode': completed.returncode})
    assert {str(p): digest(p) for p in bound} == hashes, 'Bound source/input/model evidence changed'
    assert not (output / 'forbidden-native-cache').exists(), 'Stored replay created native cache'
    report = {'schema': 'independent-v8-stored-point-audit-v1', 'status': 'passed',
              'python': sys.executable, 'bound_sha256': hashes, 'runs': runs,
              'exact_compared_fields': list(FIELDS), 'comparison_tolerance': 0,
              'proof_metadata_sha256': proof_digest(features),
              'proof_metadata_preserved_in_reversed_copy': True,
              'guards': ['estimator.fit', 'tree.fit', 'FeatureExtractor.matrix',
                         'predict_with_evidence', 'semantic.analyze_modes', 'semantic._prove',
                         'subprocess launch', 'os.system', 'fork/spawn', 'training-data and target reads'],
              'new_fits': 0, 'native_extractions': 0, 'target_labels_read': False,
              'timed_normalization_retries': 0}
    write_new(output / 'audit.json', report)
    print(json.dumps({'status': 'passed', 'runs': len(runs), 'rows_per_run': len(rows),
                      'report': str(output / 'audit.json')}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--root', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--worker', action='store_true')
    args, remaining = parser.parse_known_args()
    if args.worker:
        worker(args.repo.resolve(), remaining[1:] if remaining[:1] == ['--'] else remaining)
    else:
        assert args.root and args.output
        audit(args.repo.resolve(), args.root.resolve(), args.output.resolve())
