"""Versioned dual-representation area prediction with explicit uncertainty.

Features describe original and normalized RTL. Targets always describe original
RTL. Prediction intervals assume exchangeable calibration/test groups; this is
not a coverage guarantee on a new device, application or arithmetic family.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

import numpy as np

from .area_model_v4 import CONFIGS, estimate, fit_estimator
from .graph_features_v5 import GraphExtractor, COLUMNS as GRAPH_COLUMNS
from .masterrtl_baseline import SOGExtractor, FEATURE_COLUMNS as SOG_COLUMNS
from .structural_features_v5 import FEATURE_NAMES, feature_dict

VIEWS = ('sog_tuned', 'original_graph', 'dual_graph', 'dual_semantics')


def columns():
    return tuple('sog_' + n for n in SOG_COLUMNS) + tuple(GRAPH_COLUMNS) + tuple(FEATURE_NAMES)


def view_indices(view):
    if view not in VIEWS:
        raise ValueError('Unknown feature view')
    if view == 'sog_tuned':
        return np.arange(len(SOG_COLUMNS))
    if view == 'original_graph':
        return np.asarray([i for i, n in enumerate(columns()) if n.startswith(('sog_', 'original_'))])
    if view == 'dual_graph':
        return np.arange(len(SOG_COLUMNS)+len(GRAPH_COLUMNS))
    return np.arange(len(columns()))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_hashes():
    from .graph_features_v5 import source_hashes as graph_sources
    result = graph_sources()
    for name in ('area_model_v5.py', 'v5_corpus.py', 'v4_corpus.py', 'v4_validation.py', 'probe_corpus.py'):
        result[name] = sha(Path(__file__).parent/name)
    return result


class FeatureExtractor:
    def __init__(self, cache_root, *, frozen_tool=None):
        self.cache_root = Path(cache_root).resolve()
        self.graph = GraphExtractor(self.cache_root/'generic', frozen_tool=frozen_tool)
        # The old SOG implementation expects an executable member, which is only
        # an invocation hint; actual binary identity is still checked on a miss.
        tool = {**self.graph.tool, 'executable': 'yosys'}
        self.sog = SOGExtractor(self.cache_root/'sog', frozen_tool=tool)

    def matrix(self, rows, workers=2):
        graph, records = self.graph.matrix(rows, workers=workers)
        sog = self.sog.matrix(rows, workers=workers)
        semantic_records = [feature_dict(r['formula']) for r in rows]
        semantic = np.asarray([[r[n] for n in FEATURE_NAMES] for r in semantic_records])
        x = np.column_stack((sog, graph, semantic))
        if x.shape != (len(rows), len(columns())) or not np.isfinite(x).all():
            raise ValueError('Invalid V5 feature matrix')
        # Keep large graph manifests once in the content-addressed cache instead
        # of repeating both contexts and every column name on every dataset row.
        full = []
        for r, v in zip(records, x):
            _, sog_key = self.sog.key(r['formula'])
            full.append({'formula': r['formula'], 'normalized_formula': r['normalized_formula'],
                         'values': v.tolist(), 'cache_hit': r['cache_hit'],
                         'original_cache_key': r['original']['cache_key'],
                         'normalized_cache_key': r['normalized']['cache_key'],
                         'sog_cache_key': sog_key,
                         'sog_manifest_sha256': sha(self.sog.cache_dir/sog_key/'features.json'),
                         'original_manifest_sha256': sha(self.graph.cache_dir/r['original']['cache_key']/'features.json'),
                         'normalized_manifest_sha256': sha(self.graph.cache_dir/r['normalized']['cache_key']/'features.json')})
        return x, full


def original_zero(x):
    """Only original implementation generic graph with no operators is zero."""
    return x[:, columns().index('original_gate_count')] == 0


def predict_values(estimator, x, view, configuration):
    p = estimate(estimator, x[:, view_indices(view)], configuration)
    p[original_zero(x)] = 0
    return p


def group_upper_margin(y, p, groups, alpha=.1):
    """Finite-sample group-max one-sided split-conformal quantile.

    None denotes an unbounded interval when too few calibration groups exist.
    Assumes exchangeability of complete groups, not just individual rows.
    """
    if (any(isinstance(v, (bool, np.bool_)) for v in list(y)+list(p))
            or any(not isinstance(g, str) or not g for g in groups)):
        raise ValueError('Calibration requires numeric observations and named groups')
    y, p, groups = np.asarray(y), np.asarray(p), np.asarray(groups)
    if (not 0 < alpha < 1 or y.ndim != 1 or p.ndim != 1 or groups.ndim != 1
            or len(y) != len(p) or len(y) != len(groups)):
        raise ValueError('Invalid calibration inputs')
    if (not np.isfinite(y).all() or not np.isfinite(p).all() or np.any(y < 0) or np.any(p < 0)
            or any(not isinstance(g, str) or not g for g in groups)):
        raise ValueError('Calibration requires finite nonnegative values and named groups')
    unique = sorted(set(groups))
    if not unique:
        raise ValueError('Calibration groups required')
    residual = np.asarray(y)-np.asarray(p)
    group_values = np.asarray([max(residual[np.asarray(groups) == g]) for g in unique])
    rank = int(np.ceil((len(unique)+1)*(1-alpha)))
    margin = None if rank > len(unique) else max(0., float(np.sort(group_values)[rank-1]))
    return {'alpha': alpha, 'group_count': len(unique), 'rank': rank, 'upper_margin_lut4': margin,
            'method': 'one-sided split-conformal maximum residual per complete group',
            'assumption': 'exchangeable complete calibration/test groups; not guaranteed under distribution shift'}


@dataclass
class V5Predictor:
    estimator: object
    view: str
    configuration: str
    feature_columns: tuple
    training_formula_count: int
    calibration: dict
    feature_minimum: list
    feature_maximum: list
    frozen_tool: dict
    cache_root: str = 'generated/v5-features'

    def predict_features(self, rows, x):
        x = np.asarray(x, dtype=float)
        if tuple(self.feature_columns) != columns() or x.shape != (len(rows), len(columns())):
            raise ValueError('V5 schema mismatch')
        if not np.isfinite(x).all() or np.any(x < 0):
            raise ValueError('V5 features must be finite and nonnegative')
        values = predict_values(self.estimator, x, self.view, self.configuration)
        if not np.isfinite(values).all() or np.any(values < 0):
            raise ValueError('V5 predictions must be finite and nonnegative')
        indices = view_indices(self.view)
        domain = ((x < np.asarray(self.feature_minimum)) | (x > np.asarray(self.feature_maximum)))[:, indices].sum(axis=1)
        spread = None
        if CONFIGS[self.configuration]['kind'] == 'extra':
            tree_values = np.asarray([tree.predict(x[:, indices]) for tree in self.estimator.estimators_])
            spread = tree_values.std(axis=0)
            spread[original_zero(x)] = 0
        margin = self.calibration['upper_margin_lut4']
        if margin is not None and (isinstance(margin, bool) or not np.isfinite(margin) or margin < 0):
            raise ValueError('Calibration margin must be finite nonnegative or unbounded')
        result = []
        for i, row in enumerate(rows):
            result.append({**{k: row[k] for k in ('benchmark', 'candidate_id', 'formula') if k in row},
                           'predicted_lut4': float(values[i]),
                           'upper_lut4': None if margin is None else float(values[i]+margin),
                           'tree_disagreement_lut4': None if spread is None else float(spread[i]),
                           'outside_training_feature_ranges': int(domain[i]),
                           'uncertainty_scope': self.calibration['assumption'],
                           'model': f'v5_{self.view}_{self.configuration}'})
        return result

    def predict(self, rows):
        if not rows:
            return []
        x, _ = FeatureExtractor(self.cache_root, frozen_tool=self.frozen_tool).matrix(rows, workers=1)
        return self.predict_features(rows, x)


def load_model(path, cache_root=None):
    import joblib
    from .area_model import _versions
    path = Path(path)
    schema = json.loads(path.with_suffix('.json').read_text())
    if schema['artifact_sha256'] != sha(path) or schema['runtime_source_sha256'] != source_hashes():
        raise ValueError('V5 source or artifact differs from recorded lineage')
    actual = _versions()
    if actual != schema['versions']:
        raise ValueError(f'V5 numerical environment mismatch: expected {schema["versions"]}, received {actual}')
    model = joblib.load(path)
    if not isinstance(model, V5Predictor) or tuple(model.feature_columns) != columns():
        raise ValueError('Invalid V5 artifact')
    if (model.frozen_tool != schema['frozen_tool'] or model.view != schema['view']
            or tuple(schema['feature_columns']) != columns()
            or model.configuration != schema['configuration']
            or model.calibration != schema['calibration']
            or model.training_formula_count != schema['training_formula_count']):
        raise ValueError('V5 artifact metadata mismatch')
    model.cache_root = str(Path(cache_root).resolve()) if cache_root is not None else str(path.parent/'cache')
    return model


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', type=Path, required=True)
    parser.add_argument('--candidates', type=Path, required=True)
    parser.add_argument('--cache-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    rows = json.loads(args.candidates.read_text())
    predictions = load_model(args.model, args.cache_root).predict(rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(predictions, indent=2, allow_nan=False)+'\n')
    print(json.dumps({'prediction_count': len(predictions), 'output': str(args.output)}))


if __name__ == '__main__':
    from .area_model_v5 import main as canonical_main
    canonical_main()
