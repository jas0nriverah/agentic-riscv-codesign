"""Source-bound joint Gaussian adapter with fixed initial preprocessing.

This is a new update control, not the frozen live policy's dynamic refit. Inputs,
output centers/scales, kernel and scalar alpha stay fixed after the initial fit.
Each hardware output has an independent GP; alpha is explicitly *assumed* iid
Gaussian observation noise in normalized units, not calibrated measurement noise.
Latent covariances and alpha*scale**2 are reported separately in physical units
(LUT4 squared, MHz squared, and log(seconds) squared). No target labels are read.
The caller owns source/family holdouts and charged dispatch authorization; the
queried_id check is a cooperative boundary, not an access-control sandbox.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass
import math
from pathlib import Path

import numpy as np

from . import budgeted_selection as b, codesign as c
from . import semantic_selection as s

OUTPUTS = tuple(b.GP_SETTINGS['output_scale_floors'])
SCHEMA = 'isaforge-fixed-initial-joint-hardware-v1'
UPDATE_RULE = 'Gaussian conditioning; fixed initial input/output preprocessing and kernel'
NOISE_ASSUMPTION = 'independent Gaussian observation noise; alpha is assumed noise, not calibrated'
OUTPUT_UNITS = dict(area_delta_lut4='LUT4', routed_fmax_min_mhz='MHz',
                    log_measurement_seconds='log(seconds)')
SOURCES = ('isaforge/joint_hardware.py', *s.SOURCES)
ROOT = Path(__file__).resolve().parents[1]


def source_bindings():
    return {name: c.sha(ROOT/name) for name in SOURCES}


def _array(values):
    result = np.array(values, dtype=float, copy=True)
    c.require(np.isfinite(result).all(), 'Finite joint posterior required')
    result.setflags(write=False)
    return result


def _public(rows):
    rows = b.public_rows(copy.deepcopy(list(rows)))
    ids = [row['candidate_id'] for row in rows]
    c.require(all(isinstance(value, str) and value for value in ids), 'Nonempty string identities required')
    return rows


@dataclass(frozen=True)
class _Output:
    mean: np.ndarray
    covariance: np.ndarray
    noise: float


@dataclass(frozen=True)
class JointHardwarePosterior:
    """Finite public-pool posterior; all update/clone methods return new states.

    Construct with fit or from_fitted. joint returns copies, including separate
    latent and future-observation covariance. condition accepts only complete,
    verified successful outcomes matching the explicitly authorized query.
    Failures are charged/retained by the controller and never Gaussian labels.
    """
    _public: tuple
    _outputs: dict
    _initial_snapshot: dict
    _source_bindings: dict
    _paid: tuple = ()
    _fantasies: tuple = ()
    _device_successes: int = 0
    _device_total: int = 0

    @classmethod
    def fit(cls, training, public):
        """Fit exactly one unchanged semantic surrogate, then freeze its state."""
        training = copy.deepcopy(list(training))
        public = _public(public)
        cls._validate_history(training, public)
        return cls.from_fitted(s.SemanticHardwareSurrogate().fit(training), training, public)

    @staticmethod
    def _validate_history(training, public):
        c.require(training and all(b.validate_outcome(row) for row in training),
                  'Successful verified measured history required')
        projected = [{key: copy.deepcopy(row[key]) for key in b.PUBLIC_KEYS} for row in training]
        _public(projected)
        c.require(not {row['candidate_id'] for row in training} &
                  {row['candidate_id'] for row in public}, 'Target identity in initial history')

    @classmethod
    def from_fitted(cls, surrogate, training, public):
        """Read an already fitted semantic model without estimator fit/refit.

        The supplied historical rows must exactly authenticate the fitted snapshot.
        Targets must be public-only and disjoint in identity. Source/family holdout
        exclusions are deliberately the controller's responsibility.
        """
        c.require(type(surrogate) is s.SemanticHardwareSurrogate,
                  'Exact fitted SemanticHardwareSurrogate required')
        training = copy.deepcopy(list(training))
        public = _public(public)
        cls._validate_history(training, public)
        snapshot = surrogate.snapshot()
        c.require(snapshot['training_ids'] == [r['candidate_id'] for r in training] and
                  snapshot['training_rows_sha256'] == c.digest(training),
                  'Initial history differs from fitted model')
        c.require(snapshot['source_bindings'] == s.source_bindings(), 'Fitted sources differ')
        projected = [{key: copy.deepcopy(row[key]) for key in b.PUBLIC_KEYS} for row in training]
        matrix = s.semantic_matrix(projected)
        c.require(snapshot['feature_matrix_sha256'] == c.digest(matrix), 'Fitted feature matrix differs')
        # Authenticate current scaler/normalization against supplied initial history.
        raw = np.asarray(matrix, dtype=float)
        means = raw.mean(axis=0)
        scales = np.sqrt(raw.var(axis=0))
        scales[scales == 0] = 1.
        c.require(np.allclose(surrogate.scaler.mean_, means, rtol=0, atol=1e-12) and
                  np.allclose(surrogate.scaler.scale_, scales, rtol=1e-12, atol=1e-12),
                  'Fitted scaler differs from initial history')
        x = surrogate.scaler.transform(s.semantic_matrix(public))
        initial_x = surrogate.scaler.transform(matrix)
        outputs = {}
        for key in OUTPUTS:
            gp, center, scale = surrogate.models[key]
            y = np.asarray([math.log(r['measurement_seconds']) if key == 'log_measurement_seconds'
                            else r[key] for r in training], dtype=float)
            expected_center = float(y.mean())
            expected_scale = max(float(y.std()), b.GP_SETTINGS['output_scale_floors'][key])
            c.require(center == expected_center and scale == expected_scale,
                      'Fitted output preprocessing differs from initial history')
            c.require(np.array_equal(gp.X_train_, initial_x) and
                      np.array_equal(gp.y_train_, (y-center)/scale), 'Fitted GP history differs')
            c.require(np.ndim(gp.alpha) == 0 and float(gp.alpha) == b.GP_SETTINGS['alpha'] and
                      gp.optimizer is None and gp.normalize_y is False and
                      gp.kernel_.get_params() == gp.kernel.get_params(), 'Unsupported GP/noise settings')
            mean, covariance = gp.predict(x, return_cov=True)
            outputs[key] = _Output(_array(mean*scale+center),
                _array(covariance*scale**2), float(gp.alpha)*scale**2)
        return cls(tuple(public), outputs, copy.deepcopy(snapshot), source_bindings(),
                   _device_successes=sum(r['device_fits'] for r in training), _device_total=len(training))

    @property
    def candidate_ids(self):
        return tuple(row['candidate_id'] for row in self._public)

    @property
    def observed_ids(self):
        return tuple(row['candidate_id'] for row in self._paid)

    @property
    def conditioned_ids(self):
        return self.observed_ids + tuple(row['candidate_id'] for row in self._fantasies)

    @property
    def device_fit_alpha(self):
        return 1+self._device_successes

    @property
    def device_fit_beta(self):
        return 1+self._device_total-self._device_successes

    @property
    def device_fit_probability(self):
        return self.device_fit_alpha/(self.device_fit_alpha+self.device_fit_beta)

    def _indices(self, candidate_ids):
        ids = self.candidate_ids if candidate_ids is None else tuple(candidate_ids)
        c.require(len(set(ids)) == len(ids) and set(ids) <= set(self.candidate_ids),
                  'Unique declared target identities required')
        return ids, [self.candidate_ids.index(value) for value in ids]

    def joint(self, candidate_ids=None):
        ids, indices = self._indices(candidate_ids)
        outputs = {}
        for key, output in self._outputs.items():
            covariance = output.covariance[np.ix_(indices, indices)].copy()
            outputs[key] = dict(mean=output.mean[indices].copy(), covariance=covariance,
                observation_noise_variance=output.noise,
                observation_covariance=covariance+np.eye(len(indices))*output.noise)
        return dict(candidate_ids=list(ids), outputs=outputs,
                    device_fit_probability=self.device_fit_probability,
                    device_fit_alpha=self.device_fit_alpha, device_fit_beta=self.device_fit_beta)

    def predict(self, rows=None):
        if rows is None:
            ids = self.candidate_ids
        else:
            rows = list(rows)
            if not rows:
                return []
            public = _public(rows)
            by_id = {r['candidate_id']: r for r in self._public}
            c.require(all(r == by_id.get(r['candidate_id']) for r in public),
                      'Prediction rows differ from declared public pool')
            ids = [r['candidate_id'] for r in public]
        values = self.joint(ids)
        result = []
        for i, identity in enumerate(ids):
            row = dict(candidate_id=identity, device_fit_probability=self.device_fit_probability)
            for key, output in values['outputs'].items():
                row[key+'_mean'] = float(output['mean'][i])
                row[key+'_std'] = math.sqrt(max(0., float(output['covariance'][i, i])))
            result.append(row)
        return result

    def clone(self):
        """Independent immutable branch; no shared mutable arrays or row records."""
        return type(self)(copy.deepcopy(self._public),
            {key: _Output(_array(out.mean), _array(out.covariance), out.noise)
             for key, out in self._outputs.items()}, copy.deepcopy(self._initial_snapshot),
            copy.deepcopy(self._source_bindings), copy.deepcopy(self._paid),
            copy.deepcopy(self._fantasies), self._device_successes, self._device_total)

    def _updated(self, candidate_id, values, device_fits, record, *, fantasy):
        c.require(candidate_id in self.candidate_ids, 'Unqueried identity outside declared pool')
        c.require(candidate_id not in self.conditioned_ids, 'Duplicate paid/fantasy query')
        c.require(type(device_fits) is bool, 'Explicit boolean device-fit outcome required')
        c.require(values and set(values) <= set(OUTPUTS), 'Declared nonempty Gaussian hardware outputs required')
        values = {key: b._number(value, key) for key, value in values.items()}
        index = self.candidate_ids.index(candidate_id)
        outputs = {}
        for key, out in self._outputs.items():
            if key not in values:
                outputs[key] = _Output(_array(out.mean), _array(out.covariance), out.noise)
                continue
            cross = out.covariance[:, index]
            denominator = float(out.covariance[index, index])+out.noise
            c.require(denominator > 0, 'Positive observation variance required')
            mean = out.mean+cross*((values[key]-out.mean[index])/denominator)
            covariance = out.covariance-np.outer(cross, cross)/denominator
            covariance = (covariance+covariance.T)*.5
            c.require(float(np.diag(covariance).min()) >= -1e-10,
                      'Negative conditional latent variance')
            np.fill_diagonal(covariance, np.maximum(0., np.diag(covariance)))
            outputs[key] = _Output(_array(mean), _array(covariance), out.noise)
        return type(self)(copy.deepcopy(self._public), outputs, copy.deepcopy(self._initial_snapshot),
            copy.deepcopy(self._source_bindings),
            self._paid if fantasy else (*self._paid, copy.deepcopy(record)),
            (*self._fantasies, copy.deepcopy(record)) if fantasy else self._fantasies,
            self._device_successes+int(device_fits), self._device_total+1)

    def condition(self, outcome, *, queried_id):
        """Condition on one caller-authorized, verified successful paid result.

        Rejected or failed results do not mutate this state or manufacture labels.
        Actual authorization/ledger evidence must be enforced by the controller.
        """
        c.require(not self._fantasies, 'Hypothetical state cannot accept real paid outcomes')
        c.require(queried_id in self.candidate_ids, 'Unqueried identity outside declared pool')
        row = self._public[self.candidate_ids.index(queried_id)]
        outcome = copy.deepcopy(outcome)
        c.require(outcome.get('candidate_id') == queried_id, 'Outcome differs from authorized query')
        c.require(b.validate_outcome(outcome, row), 'Failed result is not a Gaussian observation')
        values = {key: math.log(outcome['measurement_seconds']) if key == 'log_measurement_seconds'
                  else outcome[key] for key in OUTPUTS}
        return self._updated(queried_id, values, outcome['device_fits'], outcome, fantasy=False)

    def fantasize(self, candidate_id, values, *, device_fits=True):
        """Condition a marked hypothetical branch; values are Gaussian outputs.

        Only supplied outputs are conditioned (area/timing suffice for count utility).
        Log-duration, when supplied, is already log(seconds). Finite Gaussian
        tails are allowed even for negative timing; no measurement record or
        verified label results.
        """
        record = dict(candidate_id=candidate_id, values=copy.deepcopy(values), device_fits=device_fits)
        return self._updated(candidate_id, values, device_fits, record, fantasy=True)

    def snapshot(self):
        outputs = {key: dict(mean=out.mean.tolist(), covariance=out.covariance.tolist(),
                            observation_noise_variance=out.noise) for key, out in self._outputs.items()}
        result = dict(schema=SCHEMA, update_rule=UPDATE_RULE, noise_interpretation=NOISE_ASSUMPTION,
            independent_outputs=True, covariance_kind='latent',
            output_units=copy.deepcopy(OUTPUT_UNITS), covariance_units='output units squared',
            fixed_initial_preprocessing=True, initial_snapshot=copy.deepcopy(self._initial_snapshot),
            initial_training_ids=list(self._initial_snapshot['training_ids']),
            public_pool_sha256=c.digest(list(self._public)), candidate_ids=list(self.candidate_ids),
            paid_ids=list(self.observed_ids), hypothetical=bool(self._fantasies),
            fantasy_ids=[r['candidate_id'] for r in self._fantasies],
            paid_outcomes_sha256=c.digest(list(self._paid)), fantasies_sha256=c.digest(list(self._fantasies)),
            device_fit_probability=self.device_fit_probability,
            device_fit_alpha=self.device_fit_alpha, device_fit_beta=self.device_fit_beta,
            device_fit_update='independent common Beta(1,1) rate; successful paid/fantasy booleans only',
            source_bindings=copy.deepcopy(self._source_bindings))
        result['posterior_state_sha256'] = c.digest(dict(provenance=result, outputs=outputs))
        return result
