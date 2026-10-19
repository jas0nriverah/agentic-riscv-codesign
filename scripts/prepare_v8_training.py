#!/usr/bin/env python3
"""Reconstruct the fixed V8 training matrix from published V5–V7 evidence.

Preparation only: no estimator fit, new application label, or model selection.
The full455 storage schema is distinct from either selected336 view.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'scripts')]
import numpy as np
from isaforge import area_model_v6 as v6
from isaforge import area_model_v8 as v8
from train_v6 import select_fitting, read, sha, write, now, record, checked


def reconcile(rows, fit, prefix, targets, fitting, matrices):
    """Require exact formula/target/order and all three archived feature views."""
    if len(rows) != 1665 or len(fitting['rows']) != 1665:
        raise ValueError('Exact original1665 rows required')
    for row, index, target, archived in zip(rows, fit, targets, fitting['rows']):
        if (row['formula'] != archived['formula'] or index != archived['development_index']
                or target != archived['lut4_count']):
            raise ValueError('V7 fitting formula/target/order differs from V5')
    expected = {
        'base': list(v6.mapping_columns()),
        'legacy_original': list(v8.view_columns('legacy_original336')),
        # Archived V7 called the normalized block by its original names.
        'legacy_rewritten': list(v8.view_columns('legacy_original336')),
    }
    arrays = {}
    for name, names in expected.items():
        entry = matrices[name]
        values = np.asarray(entry['values'], dtype=float)
        if (entry['columns'] != names or values.shape != (1665, len(names))
                or not np.isfinite(values).all() or np.any(values < 0)):
            raise ValueError('Archived V7 feature schema/values differ: ' + name)
        arrays[name] = values
    full = np.column_stack((prefix, arrays['legacy_rewritten'][:, 217:]))
    for name, view in [('base', 'mapping217'), ('legacy_original', 'legacy_original336'),
                       ('legacy_rewritten', 'legacy_rewritten336')]:
        if not np.array_equal(full[:, v8.view_indices(view)], arrays[name]):
            raise ValueError('V8 selected view fails exact V7 replay: ' + name)
    return full


def run(output, restored):
    output, restored = Path(output).resolve(), Path(restored).resolve()
    if output.exists():
        raise ValueError('Training preparation path must be new; retain prior attempts')
    published = ROOT / 'results/2026-10-14-development-semantics-v7/evidence/evidence-manifest.json'
    manifest = read(published)
    if read(restored / 'RESTORE-MANIFEST.json') != manifest:
        raise ValueError('Restored V7 manifest differs from published archive')
    # Validate every archive member, including the pre-score freeze and proofs.
    archived = []
    for entry in manifest['files']:
        path = restored / entry['path']
        if sha(path) != entry['sha256'] or path.stat().st_size != entry['bytes']:
            raise ValueError('Restored V7 member changed: ' + entry['path'])
        archived.append(path)
    old_root = ROOT / 'results/2026-10-14-v5'
    prior_root = ROOT / 'results/2026-10-14-v6'
    freeze_path = prior_root / 'point-freeze.json'
    freeze = read(freeze_path)
    consumed_path = prior_root / 'corpus/consumed-features.json'
    frozen = {(prior_root / r['path']).resolve(): r['sha256'] for r in freeze['files']}
    helper = ROOT / 'scripts/train_v6.py'
    if frozen.get(helper) != sha(helper):
        raise ValueError('Imported frozen V6 fitting helpers changed')
    if frozen.get(consumed_path) != sha(consumed_path):
        raise ValueError('V6 consumed features not bound by point freeze')
    consumed = read(consumed_path)
    if tuple(consumed['columns']) != v6.columns():
        raise ValueError('V6 full336 column order differs')
    rows, fit, prefix, targets, old_inputs = select_fitting(old_root, consumed['records'])
    prepared = restored / 'prepared'
    pre_score = read(prepared / 'pre-score-freeze.json')
    for name, digest in v8.source_hashes().items():
        if name == 'area_model_v8.py':
            continue
        key = 'sources/isaforge/' + name
        if pre_score['files_sha256'].get(key) != digest or sha(prepared / key) != digest:
            raise ValueError('Current runtime differs from archived V7 feature producer: ' + name)
    matrices = {name: read(prepared / 'matrices' / (name + '.json'))
                for name in ('base', 'legacy_original', 'legacy_rewritten')}
    full = reconcile(rows, fit, prefix, targets, read(prepared / 'fitting.json'), matrices)
    baseline_entry = freeze['models']['mapping_v6']
    artifact = checked(baseline_entry['artifact'], prior_root)
    schema = checked(baseline_entry['schema'], prior_root)
    baseline = v6.load_model(artifact)
    if baseline.kind != 'mapping_v6' or baseline.training_formula_count != 1665:
        raise ValueError('Frozen mapping point control differs')
    from sklearn.ensemble import ExtraTreesRegressor
    if baseline.estimator.get_params() != ExtraTreesRegressor(**v8.FIXED_PARAMETERS).get_params():
        raise ValueError('V8 fixed recipe differs from mapping control')
    provenance = {
        'fit_indices': fit,
        'fit_indices_sha256': hashlib.sha256(json.dumps(fit, separators=(',', ':')).encode()).hexdigest(),
        'training_dataset_sha256': sha(old_root / 'development-data.json'),
        'development_dataset_sha256': sha(old_root / 'development-data.json'),
        'development_features_sha256': sha(old_root / 'development-features.json'),
        'split_sha256': sha(old_root / 'split.json'),
    }
    if baseline.training_provenance != provenance:
        raise ValueError('Mapping control exact fitting provenance differs')
    paths = [published, *archived, freeze_path, consumed_path, artifact, schema,
             old_root / 'freeze.json', *old_inputs, Path(__file__), helper,
             *(ROOT / 'isaforge' / name for name in v8.source_hashes())]
    bindings = [record(path, output) for path in dict.fromkeys(paths)]
    write(output / 'training-data.json', {
        'schema': 'isaforge-v8-fixed-training-data-v1', 'columns': list(v8.columns()),
        'rows': [{'formula': row['formula'], 'development_index': index, 'lut4_count': float(y)}
                 for row, index, y in zip(rows, fit, targets)], 'values': full.tolist(),
        'training_provenance': provenance, 'frozen_tool': baseline.frozen_tool,
    })
    write(output / 'preparation.json', {
        'schema': 'isaforge-v8-training-preparation-v1', 'prepared_at_utc': now(),
        'files': bindings, 'training_data': record(output / 'training-data.json', output),
        'runtime_source_sha256': v8.source_hashes(), 'preparation_environment': v8.environment(),
        'fixed_parameters': v8.FIXED_PARAMETERS, 'training_formula_count': len(rows),
        'full_feature_count': full.shape[1], 'exact_v7_view_replays': list(matrices),
        'new_estimator_fits': 0, 'new_application_labels_read': False,
        'scope': 'Preparation only; separate frozen cohort/protocol and review required before two fits.',
    })
    print(json.dumps({'prepared': str(output), 'rows': len(rows), 'columns': full.shape[1], 'fits': 0}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--restored-v7', type=Path, required=True)
    args = parser.parse_args()
    run(args.output, args.restored_v7)
