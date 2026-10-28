"""One six-field formula-only representation hypothesis for the existing GP.

The frozen surrogate remains untouched. Only its input matrix is extended;
targets, standardization procedure, kernel, noise and output floors are copied
exactly. Source/family exclusions and paid-prefix authorization belong to the
experiment/controller, not to this predictor. Circuit counts are not LUT labels
or calibrated confidence. No historical area-model weights or data are loaded.
"""
from __future__ import annotations

import copy
import importlib.metadata
import math
from pathlib import Path

from . import budgeted_selection as b, codesign as c
from .structural_features_v3 import feature_dict

EXTRA_COLUMNS = (
    'v3_edge_adder_shift', 'v3_edge_shift_adder', 'v3_adder_sum_bits',
    'v3_adder_carry_bits', 'v3_live_demand_bits', 'v3_output_constant_bits',
)
COLUMNS = (*b.STRUCTURAL_COLUMNS, *EXTRA_COLUMNS)
GP_SETTINGS = copy.deepcopy(b.GP_SETTINGS)
SOURCES = tuple(dict.fromkeys((
    'isaforge/semantic_selection.py', 'isaforge/structural_features_v3.py',
    # v3 reuses formula-only symbolic helpers from these modules, never fits.
    'isaforge/area_model_v2.py', 'isaforge/area_model.py', 'isaforge/rtl.py',
    *b.SOURCES,
)))
ROOT = Path(__file__).resolve().parents[1]


def source_bindings():
    return {name: c.sha(ROOT/name) for name in SOURCES}


def semantic_matrix(rows):
    """Accept only the frozen public schema, then append the six fixed fields."""
    rows = list(rows)
    if not rows:
        return []
    public = b.public_rows(rows)
    result = []
    for row, original in zip(public, b.structural_matrix(public)):
        values = feature_dict(row['formula'])
        extra = [b._number(values[name], name) for name in EXTRA_COLUMNS]
        c.require(all(value >= 0 for value in extra), 'Nonnegative semantic fields required')
        result.append(original + extra)
    return result


class SemanticHardwareSurrogate:
    """fit/predict factory compatible with count_selection.search paid updates."""

    def __init__(self):
        self.models = None
        self._fit_record = None

    def fit(self, rows):
        import numpy as np
        from sklearn.gaussian_process import GaussianProcessRegressor
        from sklearn.gaussian_process.kernels import Matern
        from sklearn.preprocessing import StandardScaler

        # A rejected refit must not leave an apparently usable previous model.
        self.models = None
        self._fit_record = None
        rows = copy.deepcopy(list(rows))
        c.require(rows and all(b.validate_outcome(row) for row in rows),
                  'Successful verified measured history required')
        ids = [row['candidate_id'] for row in rows]
        c.require(all(isinstance(value, str) and value for value in ids)
                  and len(set(ids)) == len(ids), 'Unique nonempty training identities required')
        public = [{key: copy.deepcopy(row[key]) for key in b.PUBLIC_KEYS} for row in rows]
        matrix = semantic_matrix(public)
        self.scaler = StandardScaler().fit(matrix)
        x = self.scaler.transform(matrix)
        models = {}
        for key, floor in GP_SETTINGS['output_scale_floors'].items():
            y = np.asarray([math.log(row['measurement_seconds'])
                            if key == 'log_measurement_seconds' else row[key]
                            for row in rows], dtype=float)
            center, scale = float(y.mean()), max(float(y.std()), floor)
            model = GaussianProcessRegressor(kernel=Matern(
                length_scale=1.0, length_scale_bounds='fixed', nu=1.5),
                alpha=1e-4, optimizer=None, normalize_y=False)
            model.fit(x, (y-center)/scale)
            models[key] = model, center, scale
        self.device_fit_probability = (1+sum(row['device_fits'] for row in rows))/(len(rows)+2)
        self._fit_record = dict(
            schema='isaforge-six-semantic-hardware-gp-v1',
            columns=list(COLUMNS), extra_columns=list(EXTRA_COLUMNS),
            training_ids=ids, training_rows_sha256=c.digest(rows),
            public_training_rows_sha256=c.digest(public),
            feature_matrix_sha256=c.digest(matrix),
            gp_settings=copy.deepcopy(GP_SETTINGS), source_bindings=source_bindings(),
            packages={name: importlib.metadata.version(name) for name in ('numpy', 'scipy', 'scikit-learn')},
            scaler=dict(mean=self.scaler.mean_.tolist(), scale=self.scaler.scale_.tolist()),
            outputs={key: dict(mean=center, scale=scale)
                     for key, (_, center, scale) in models.items()},
            device_fit_probability=self.device_fit_probability,
        )
        self.models = models
        return self

    def predict(self, rows):
        c.require(self.models is not None and self._fit_record is not None, 'Fit semantic surrogate first')
        rows = list(rows)
        if not rows:
            return []
        matrix = semantic_matrix(rows)
        x = self.scaler.transform(matrix)
        values = {}
        for key, (model, center, scale) in self.models.items():
            means, stds = model.predict(x, return_std=True)
            values[key] = means*scale+center, stds*scale
        result = []
        for i, row in enumerate(rows):
            item = dict(candidate_id=row['candidate_id'], device_fit_probability=self.device_fit_probability)
            for key, (means, stds) in values.items():
                item[key+'_mean'], item[key+'_std'] = float(means[i]), float(stds[i])
            c.digest(item)  # Reject nonfinite output before acquisition.
            result.append(item)
        return result

    def snapshot(self):
        """Compact provenance plus a digest of the fitted numerical model state.

        Authenticated input rows and deterministic refitting reproduce the model;
        arrays/Cholesky factors are hashed rather than serialized into archives.
        """
        c.require(self.models is not None and self._fit_record is not None, 'Fit semantic surrogate first')
        record = copy.deepcopy(self._fit_record)
        record['scaler'] = dict(mean=self.scaler.mean_.tolist(), scale=self.scaler.scale_.tolist())
        record['outputs'] = {key: dict(mean=center, scale=scale)
                             for key, (_, center, scale) in self.models.items()}
        record['device_fit_probability'] = self.device_fit_probability
        numerical = {
            key: dict(kernel=model.kernel_.get_params(),
                      x_sha256=c.digest(model.X_train_.tolist()),
                      y_sha256=c.digest(model.y_train_.tolist()),
                      cholesky_sha256=c.digest(model.L_.tolist()),
                      alpha_sha256=c.digest(model.alpha_.tolist()))
            for key, (model, _, _) in self.models.items()
        }
        record['model_state_sha256'] = c.digest(dict(provenance=record, numerical=numerical))
        return record
