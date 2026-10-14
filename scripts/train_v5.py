#!/usr/bin/env python3
"""Select equally tuned V5 feature views without consulting test labels."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import joblib
import numpy as np
from sklearn.model_selection import GroupKFold, GroupShuffleSplit
from threadpoolctl import threadpool_limits
from isaforge.area_model import _validated_rows, _unique_formulas, _versions
from isaforge.area_model_v5 import (FeatureExtractor, V5Predictor, VIEWS, CONFIGS,
    columns, source_hashes, sha, view_indices, fit_estimator, predict_values, group_upper_margin)
from isaforge.v5_corpus import group_components, seal_inputs


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def record(path, base):
    return {'path': os.path.relpath(path, base), 'sha256': sha(path)}


def now():
    return datetime.now(timezone.utc).isoformat()


def stats(y, p, strata):
    positive = y > 0
    return {'mae_lut4': float(abs(y-p).mean()),
            'macro_stratum_mae_lut4': float(np.mean([abs(y[strata == s]-p[strata == s]).mean() for s in sorted(set(strata))])),
            'rmsle': float(np.sqrt(np.mean((np.log1p(y)-np.log1p(p))**2))),
            'positive_mape_percent': float((100*abs(y[positive]-p[positive])/y[positive]).mean()),
            'by_stratum_mae_lut4': {s: float(abs(y[strata == s]-p[strata == s]).mean()) for s in sorted(set(strata))}}


@threadpool_limits.wrap(limits=1, user_api='blas')
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT/'results/2026-10-14-v5')
    parser.add_argument('--features-only', action='store_true')
    args = parser.parse_args()
    out = args.root.resolve()
    if (out/'freeze.json').exists():
        raise ValueError('Frozen experiment; use a new lineage')
    if any((out/p).exists() for p in ('label-release.json', 'corpus/test/dataset.json', 'corpus/test/completion.json')):
        raise ValueError('Test labels have been released; use a new untouched lineage')
    inputs = [ROOT/'results/2026-10-13-v4/development-data.json',
              ROOT/'results/2026-10-13-v4/corpus/test/dataset.json',
              out/'corpus/development/dataset.json']
    rows = sorted(_unique_formulas(_validated_rows([r for p in inputs for r in read(p)])), key=lambda r: r['formula'])
    test = read(out/'corpus/test/candidates.json')
    if len(rows) != 2057 or len(test) != 256:
        raise ValueError('Expected 1545 previous plus 512 development, and 256 test inputs')
    sources = source_hashes()
    controls = [Path(__file__).resolve(), ROOT/'scripts/evaluate_v5.py', ROOT/'scripts/evaluate_v4.py',
                ROOT/'scripts/measure_v5.py', ROOT/'docs/v5-protocol.md']
    control_hashes = {str(p): sha(p) for p in controls}
    cache = ROOT/'generated/v5-features'
    extractor = FeatureExtractor(cache)
    started = time.perf_counter()
    x, features = extractor.matrix(rows, workers=2)
    xt, test_features = extractor.matrix(test, workers=2)
    write(out/'development-data.json', rows)
    write(out/'development-features.json', {'columns': columns(), 'records': features})
    write(out/'test-features.json', {'columns': columns(), 'records': test_features})
    write(out/'feature-extraction.json', {'seconds': time.perf_counter()-started,
          'scope': 'combined development/test extraction, cache may be partially warm',
          'source_sha256': sources, 'frozen_tool': extractor.graph.tool})
    seal = seal_inputs(rows, test, features, test_features)
    write(out/'input-seal.json', seal)
    test_clusters = group_components(test, test_features, include_skeletons=True)
    write(out/'test-clusters.json', {'definition': 'same skeleton-plus-equivalence component rule as calibration, restricted to test inputs',
                                   'component_by_formula': test_clusters})
    print('Complete features and input seal', len(rows), len(test), flush=True)
    if args.features_only:
        return
    mapping = group_components(rows, features, include_skeletons=True)
    groups = np.asarray([mapping[r['formula']] for r in rows])
    y = np.asarray([r['lut4_count'] for r in rows], dtype=float)
    strata = np.asarray([r.get('stratum', 'workload') for r in rows])
    fit, calibration = next(GroupShuffleSplit(n_splits=1, test_size=.2, random_state=2026101417).split(x, y, groups))
    if len(set(groups[fit])) < 5 or set(strata[fit]) != set(strata):
        raise ValueError('Predeclared split lacks fitting groups or a required stratum')
    folds = list(GroupKFold(5).split(x[fit], y[fit], groups[fit]))
    split = {'fit_indices': fit.tolist(), 'calibration_indices': calibration.tolist(),
             'component_by_formula': mapping,
             'fit_count': len(fit), 'calibration_count': len(calibration),
             'fit_group_count': len(set(groups[fit])), 'calibration_group_count': len(set(groups[calibration])),
             'fit_stratum_counts': {s: int(np.sum(strata[fit] == s)) for s in sorted(set(strata))},
             'calibration_stratum_counts': {s: int(np.sum(strata[calibration] == s)) for s in sorted(set(strata))},
             'fold_validation_indices': [fit[v].tolist() for _, v in folds],
             'seed': 2026101417, 'calibration_fraction_of_groups': .2}
    write(out/'split.json', split)
    write(out/'training-start.json', {'started_at_utc': now(), 'sources': sources,
          'control_sha256': control_hashes, 'views': VIEWS, 'configurations': CONFIGS,
          'fit_count': len(fit), 'calibration_count': len(calibration),
          'input_seal': record(out/'input-seal.json', out), 'dataset_sources': [record(p, out) for p in inputs]})
    print('Group split', len(fit), len(calibration), 'fit/calibration', flush=True)
    selections, models, predictions = {}, {}, {}
    for view in VIEWS:
        candidates = {}
        for config in CONFIGS:
            p = np.zeros(len(fit))
            for train, valid in folds:
                model = fit_estimator(x[fit[train]][:, view_indices(view)], y[fit[train]], config)
                p[valid] = predict_values(model, x[fit[valid]], view, config)
            candidates[config] = {**stats(y[fit], p, strata[fit]), 'oof_predictions': p.tolist()}
            print(view, config, candidates[config]['macro_stratum_mae_lut4'], flush=True)
        selected = min(candidates, key=lambda c: (candidates[c]['macro_stratum_mae_lut4'], c))
        fitted = fit_estimator(x[fit][:, view_indices(view)], y[fit], selected)
        cp = predict_values(fitted, x[calibration], view, selected)
        calibrated = group_upper_margin(y[calibration], cp, groups[calibration])
        predictor = V5Predictor(fitted, view, selected, columns(), len(fit), calibrated,
                                x[fit].min(axis=0).tolist(), x[fit].max(axis=0).tolist(), extractor.graph.tool, str(cache))
        path = out/'models'/f'{view}.joblib'
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(predictor, path, compress=3)
        write(path.with_suffix('.json'), {'artifact_sha256': sha(path), 'runtime_source_sha256': sources,
              'versions': _versions(), 'feature_columns': columns(), 'view': view, 'configuration': selected,
              'fitted_parameters': fitted.get_params(),
              'frozen_tool': extractor.graph.tool, 'calibration': calibrated,
              'training_formula_count': len(fit), 'training_dataset_sha256': sha(out/'development-data.json'),
              'split_sha256': sha(out/'split.json'), 'trained_at_utc': now()})
        models[view] = path
        predictions[view] = predictor.predict_features(test, xt)
        selections[view] = {'selected': selected, 'selection_metrics': candidates,
                            'calibration_metrics': stats(y[calibration], cp, strata[calibration]),
                            'calibration': calibrated}
    write(out/'development-evaluation.json', {'scope': 'selection OOF is development-only; calibration is not for selection',
          'views': selections, 'fit_count': len(fit), 'calibration_count': len(calibration)})
    from isaforge import masterrtl_baseline as master
    matched = master.train_model([rows[i] for i in fit], cache/'sog')
    paths = master.save_model(matched, out/'models/masterrtl-fixed', {'split_sha256': sha(out/'split.json')})
    models['masterrtl_fixed'] = Path(paths['model_path'])
    predictions['masterrtl_fixed'] = matched.predict(test)
    from isaforge.area_model_v4 import load_model as load_v4
    old = ROOT/'results/2026-10-13-v4/models/v4.joblib'
    models['v4_frozen'] = old
    predictions['v4_frozen'] = load_v4(old, ROOT/'generated/masterrtl-baseline/sog-cache').predict(test)
    # Commit every prediction before the collector is authorized to expose labels.
    entries = {}
    for name, values in predictions.items():
        path = out/'predictions'/f'{name}.json'
        write(path, values)
        entries[name] = {'frozen_at_utc': now(), 'predictions': record(path, out),
                         'artifact': record(models[name], out), 'schema': record(models[name].with_suffix('.json'), out)}
    if source_hashes() != sources or any(sha(p) != h for p, h in control_hashes.items()):
        raise ValueError('Sources changed during training; freeze rejected')
    frozen_files = [*controls, *(ROOT/'isaforge'/name for name in sources),
                    out/'development-data.json', out/'development-features.json', out/'test-features.json',
                    out/'input-seal.json', out/'test-clusters.json', out/'split.json', out/'training-start.json', out/'development-evaluation.json',
                    out/'corpus/test/candidates.json', out/'corpus/test/freeze.json',
                    out/'corpus/development/completion.json', out/'corpus/development/verification.json']
    write(out/'freeze.json', {'schema': 'isaforge-v5-freeze-v1', 'frozen_at_utc': now(),
          'models': entries, 'files': [record(p, out) for p in dict.fromkeys(frozen_files)],
          'test_candidate_sha256': sha(out/'corpus/test/candidates.json'),
          'test_labels_read': False, 'primary': 'unseen_compositions macro-stratum MAE',
          'primary_comparison': 'dual_semantics minus sog_tuned'})
    print('Frozen V5 model/prediction bundle; test labels not read', flush=True)


if __name__ == '__main__':
    main()
