"""Synthetic interface/representation checks, never scientific variant fits."""
import copy
import json
import math
from unittest.mock import patch

import numpy as np
import pytest
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import Matern
from sklearn.preprocessing import StandardScaler

from isaforge import budgeted_selection as b, codesign as c
from isaforge import semantic_selection as s
from isaforge.rtl import MASK, evaluate_formula
from test_budgeted_selection import history, measured, public


EXPECTED = (
    'v3_edge_adder_shift', 'v3_edge_shift_adder', 'v3_adder_sum_bits',
    'v3_adder_carry_bits', 'v3_live_demand_bits', 'v3_output_constant_bits',
)


def vector(formula):
    return s.semantic_matrix([public('candidate', formula)])[0][-6:]


def test_exact_fixed_block_breaks_order_alias_without_changing_original_columns():
    a = public('left', 'add(in0,slli(in1,2))')
    z = public('right', 'slli(add(in0,in1),2)')
    assert s.EXTRA_COLUMNS == EXPECTED
    assert s.COLUMNS == (*b.STRUCTURAL_COLUMNS, *EXPECTED)
    assert len(s.COLUMNS) == len(set(s.COLUMNS)) == 37
    assert b.structural_matrix([a]) == b.structural_matrix([z])
    values = s.semantic_matrix([a, z])
    assert [row[:31] for row in values] == b.structural_matrix([a, z])
    assert values[0][-6:] == [1., 0., 30., 29., 62., 0.]
    assert values[1][-6:] == [0., 1., 30., 29., 60., 2.]
    assert vector('add(in0,slli(in1,3))') == [1., 0., 29., 28., 61., 0.]


def test_retains_constant_dct_counterexample_instead_of_claiming_a_lut_predictor():
    a = public('a', 'addi(lui(-16384),315)')
    z = public('z', 'addi(lui(4096),-1650)')
    assert b.structural_matrix([a]) != b.structural_matrix([z])
    assert vector(a['formula']) == vector(z['formula']) == [0., 0., 0., 0., 0., 32.]
    # Full expression values differ even though these six descriptors do not.
    assert evaluate_formula(a['formula'], 0, 0) != evaluate_formula(z['formula'], 0, 0)


def test_expint_bit_counts_are_conservative_and_u32_semantics_are_preserved():
    cheap = 'addi(andi(sub(0,sltiu(in0,1)),998),2)'
    subtraction = 'sub(addi(0,4),in0)'
    assert vector(cheap) == [0., 0., 3., 11., 23., 24.]
    assert vector(subtraction) == [0., 0., 31., 31., 32., 0.]
    # Algebra: sltiu(x,1) is exactly [x=0], negated modulo u32, then masked.
    # These boundary evaluations guard the implementation, not an exhaustive proof.
    for x in (0, 1, 2, 31, 32, 998, 1000, 2**31-1, 2**31, MASK):
        assert evaluate_formula(cheap, x, 0) == (1000 if x == 0 else 2)
        assert evaluate_formula(subtraction, x, 0) == (4-x) & MASK


@pytest.mark.parametrize('formula', [
    "__import__('os')", 'add(in2,in0)', 'unknown(in0,in1)',
    'add(in0)', 'slli(in0,4294967296)',
])
def test_invalid_formulas_are_rejected_before_feature_use(formula):
    row = public('candidate')
    row['formula'] = formula
    with pytest.raises(ValueError):
        s.semantic_matrix([row])


def test_prediction_projection_has_no_labels_and_no_execution_exposure_features():
    a = public('one', runs=10)
    z = public('two', runs=20, benchmark='other:context')
    assert s.semantic_matrix([a]) == s.semantic_matrix([z])
    assert s.semantic_matrix([]) == []
    for name in ('area_delta_lut4', 'speedup', 'measurement_seconds', 'v3_adder_sum_bits'):
        row = copy.deepcopy(a)
        row[name] = 1
        with pytest.raises(ValueError):
            s.semantic_matrix([row])
        row = copy.deepcopy(a)
        row['latency_features'][name] = 1
        with pytest.raises(ValueError):
            s.semantic_matrix([row])
    row = copy.deepcopy(a)
    row['max_abs_constant'] = float('nan')
    with pytest.raises(ValueError):
        s.semantic_matrix([row])


def test_same_standardization_targets_and_fixed_gp_as_explicit_reference():
    rows = history()
    rows[1]['measurement_seconds'] = 3.7
    before = copy.deepcopy(rows)
    model = s.SemanticHardwareSurrogate().fit(rows)
    projected = [{key: row[key] for key in b.PUBLIC_KEYS} for row in rows]
    matrix = s.semantic_matrix(projected)
    scaler = StandardScaler().fit(matrix)
    np.testing.assert_array_equal(model.scaler.mean_, scaler.mean_)
    np.testing.assert_array_equal(model.scaler.scale_, scaler.scale_)
    assert s.GP_SETTINGS == b.GP_SETTINGS
    assert rows == before
    targets = [public('new', 'sub(in0,slli(in1,3))')]
    prediction = model.predict(targets)[0]
    for key, floor in b.GP_SETTINGS['output_scale_floors'].items():
        y = np.asarray([math.log(row['measurement_seconds']) if key == 'log_measurement_seconds'
                        else row[key] for row in rows], dtype=float)
        center, scale = float(y.mean()), max(float(y.std()), floor)
        reference = GaussianProcessRegressor(kernel=Matern(length_scale=1.,
            length_scale_bounds='fixed', nu=1.5), alpha=1e-4, optimizer=None, normalize_y=False)
        reference.fit(scaler.transform(matrix), (y-center)/scale)
        means, stds = reference.predict(scaler.transform(s.semantic_matrix(targets)), return_std=True)
        fitted, fitted_center, fitted_scale = model.models[key]
        assert fitted_center == center and fitted_scale == scale
        assert fitted.get_params()['alpha'] == 1e-4
        assert fitted.optimizer is None and fitted.normalize_y is False
        np.testing.assert_array_equal(fitted.y_train_, reference.y_train_)
        assert prediction[key+'_mean'] == float(means[0]*scale+center)
        assert prediction[key+'_std'] == float(stds[0]*scale)
    assert prediction['device_fit_probability'] == 4/5


def test_compact_snapshot_binds_exact_input_cohort_sources_and_model_state():
    rows = history()
    model = s.SemanticHardwareSurrogate().fit(rows)
    snapshot = model.snapshot()
    assert snapshot['columns'] == list(s.COLUMNS)
    assert snapshot['extra_columns'] == list(EXPECTED)
    assert snapshot['training_ids'] == [row['candidate_id'] for row in rows]
    assert snapshot['training_rows_sha256'] == c.digest(rows)
    public_rows = [{key: row[key] for key in b.PUBLIC_KEYS} for row in rows]
    assert snapshot['public_training_rows_sha256'] == c.digest(public_rows)
    assert snapshot['feature_matrix_sha256'] == c.digest(s.semantic_matrix(public_rows))
    assert snapshot['source_bindings'] == s.source_bindings()
    assert all(len(value) == 64 for value in snapshot['source_bindings'].values())
    assert set(snapshot['packages']) == {'numpy', 'scipy', 'scikit-learn'}
    assert len(snapshot['scaler']['mean']) == len(snapshot['scaler']['scale']) == 37
    assert len(snapshot['model_state_sha256']) == 64
    assert len(json.dumps(snapshot, allow_nan=False)) < 15000
    assert 'cholesky' not in snapshot and 'training_matrix' not in snapshot
    assert snapshot == s.SemanticHardwareSurrogate().fit(rows).snapshot()
    rows[0]['area_delta_lut4'] += 1
    changed = s.SemanticHardwareSurrogate().fit(rows).snapshot()
    assert changed['feature_matrix_sha256'] == snapshot['feature_matrix_sha256']
    assert changed['training_rows_sha256'] != snapshot['training_rows_sha256']
    assert changed['model_state_sha256'] != snapshot['model_state_sha256']
    snapshot['columns'].clear()
    assert model.snapshot()['columns'] == list(s.COLUMNS)


def test_fit_rejects_duplicates_failures_and_unverified_rows():
    for rows in ([], history()+[history()[0]]):
        with pytest.raises(ValueError):
            s.SemanticHardwareSurrogate().fit(rows)
    rows = history()
    rows[0]['correctness_verified'] = False
    with pytest.raises(ValueError):
        s.SemanticHardwareSurrogate().fit(rows)
    failure = dict(**public('failed'), status='failed', measurement_seconds=3., error='unknown outcome')
    with pytest.raises(ValueError):
        s.SemanticHardwareSurrogate().fit(history()+[failure])
    rows = history()
    rows[0]['latency_features']['hidden_area_label'] = 41
    with pytest.raises(ValueError):
        s.SemanticHardwareSurrogate().fit(rows)


def test_snapshot_digest_reflects_current_scaler_and_model_state():
    model = s.SemanticHardwareSurrogate().fit(history())
    original = model.snapshot()
    model.scaler.scale_[0] += 1.
    changed = model.snapshot()
    assert changed['scaler']['scale'][0] == model.scaler.scale_[0]
    assert changed['model_state_sha256'] != original['model_state_sha256']
    key = next(iter(model.models))
    model.models[key][0].alpha_[0] += 1.
    assert model.snapshot()['model_state_sha256'] != changed['model_state_sha256']


def test_rejected_refit_and_unfitted_models_cannot_predict_or_snapshot():
    model = s.SemanticHardwareSurrogate()
    for call in (lambda: model.predict([]), model.snapshot):
        with pytest.raises(ValueError):
            call()
    model.fit(history())
    assert model.predict([]) == []
    with pytest.raises(ValueError):
        model.predict([measured(public('labeled-target'))])
    with pytest.raises(ValueError):
        model.fit([])
    with pytest.raises(ValueError):
        model.predict([public('new')])


def test_synthetic_fit_does_not_read_or_fit_legacy_area_models():
    forbidden = AssertionError('Historical area data/weights/fits forbidden')
    with patch('isaforge.area_model._read_rows', side_effect=forbidden), \
         patch('isaforge.area_model_v2._read_rows', side_effect=forbidden), \
         patch('isaforge.area_model.train_area_model', side_effect=forbidden), \
         patch('isaforge.area_model_v2.train_area_model', side_effect=forbidden):
        assert s.SemanticHardwareSurrogate().fit(history()).predict([public('new')])


def test_semantic_factory_does_not_mutate_frozen_surrogate_or_predictions():
    rows = history()
    targets = [public('new', 'add(in0,slli(in1,3))')]
    source_hash = c.sha(s.ROOT/'isaforge/budgeted_selection.py')
    matrix_function = b.structural_matrix
    old = b.HardwareSurrogate().fit(rows)
    expected = old.predict(targets)
    s.SemanticHardwareSurrogate().fit(rows).predict(targets)
    assert old.predict(targets) == expected
    assert b.HardwareSurrogate().fit(rows).predict(targets) == expected
    assert b.structural_matrix is matrix_function
    assert old.scaler.n_features_in_ == 31
    assert c.sha(s.ROOT/'isaforge/budgeted_selection.py') == source_hash


def test_count_search_uses_same_semantics_for_each_successful_paid_prefix():
    from isaforge import count_selection

    training = history()
    targets = [public('target-a', 'add(in0,slli(in1,3))', saved_cycles=60),
               public('target-b', 'slli(add(in0,in1),2)', saved_cycles=30),
               public('target-c', 'sub(in0,in1)', saved_cycles=20)]
    initial = s.SemanticHardwareSurrogate().fit(training)
    snapshots = []

    class Observed(s.SemanticHardwareSurrogate):
        def fit(self, rows):
            result = super().fit(rows)
            snapshots.append(result.snapshot())
            return result

    result = count_selection.search(targets, training, lambda row: measured(row),
        area_cap=64, clock_mhz=12, seed=0, budget=3,
        predictions=dict(hardware=initial.predict(targets), inference_seconds={}),
        surrogate_factory=Observed)
    assert len(snapshots) == 2
    for i, snapshot in enumerate(snapshots, 1):
        prefix = [row['candidate_id'] for row in training] + result['curve'][i-1]['measured_ids']
        assert snapshot['training_ids'] == prefix
        assert snapshot['columns'] == list(s.COLUMNS)
        assert snapshot['gp_settings'] == b.GP_SETTINGS
    assert len(result['curve'][-1]['attempted_ids']) == 3
    assert training == history()


def test_failed_paid_attempt_is_charged_but_never_in_semantic_fit_cohort():
    from isaforge import count_selection

    training = history()
    targets = [public('target-a', 'add(in0,slli(in1,3))'),
               public('target-b', 'slli(add(in0,in1),2)'),
               public('target-c', 'sub(in0,in1)')]
    calls, fit_ids = [], []

    class Observed(s.SemanticHardwareSurrogate):
        def fit(self, rows):
            fit_ids.append([row['candidate_id'] for row in rows])
            return super().fit(rows)

    def provider(row):
        calls.append(row['candidate_id'])
        if len(calls) == 1:
            return dict(**row, status='failed', measurement_seconds=7., error='unknown infrastructure outcome')
        return measured(row)

    initial = s.SemanticHardwareSurrogate().fit(training).predict(targets)
    result = count_selection.search(targets, training, provider, area_cap=64,
        clock_mhz=12, seed=0, budget=3, predictions=dict(hardware=initial, inference_seconds={}),
        surrogate_factory=Observed)
    assert len(fit_ids) == 1
    assert fit_ids[0] == [row['candidate_id'] for row in training]+[calls[1]]
    assert calls[0] not in fit_ids[0]
    assert result['curve'][-1]['budget'] == 3
    assert result['curve'][-1]['failed_attempts'] == 1
    assert result['curve'][-1]['target_measurement_seconds'] == 11.
