"""Guard against schema/order and fitting-target drift in V8 preparation."""
import copy
import importlib.util
from pathlib import Path

import numpy as np
import pytest

SPEC = importlib.util.spec_from_file_location('prepare_v8_training', Path(__file__).resolve().parents[1] / 'scripts/prepare_v8_training.py')
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


@pytest.fixture
def inputs():
    # Distinct values make equal-width column swaps detectable.
    prefix = np.tile(np.arange(336, dtype=float), (1665, 1))
    rewritten = np.tile(np.arange(119, dtype=float) + 1000, (1665, 1))
    full = np.column_stack((prefix, rewritten))
    rows = [{'formula': 'add(in0,in1)'} for _ in range(1665)]
    fit = list(range(1665))
    targets = np.arange(1665, dtype=float)
    fitting = {'rows': [{'formula': row['formula'], 'development_index': i, 'lut4_count': float(i)}
                        for i, row in enumerate(rows)]}
    matrices = {}
    for name, view in [('base', 'mapping217'), ('legacy_original', 'legacy_original336'),
                       ('legacy_rewritten', 'legacy_rewritten336')]:
        names_view = 'legacy_original336' if name == 'legacy_rewritten' else view
        matrices[name] = {'columns': list(MODULE.v8.view_columns(names_view)),
                          'values': full[:, MODULE.v8.view_indices(view)].tolist()}
    return [rows, fit, prefix, targets, fitting, matrices]


def test_exact_reconstruction(inputs):
    result = MODULE.reconcile(*inputs)
    assert result.shape == (1665, 455)
    assert np.array_equal(result[:, :336], inputs[2])
    assert result[0, 336] == 1000


@pytest.mark.parametrize('field,value', [('formula', 'sub(in0,in1)'), ('development_index', 1), ('lut4_count', 1)])
def test_reject_row_lineage_change(inputs, field, value):
    inputs[4]['rows'][0][field] = value
    with pytest.raises(ValueError, match='formula/target/order'):
        MODULE.reconcile(*inputs)


def test_reject_equal_width_reordering(inputs):
    inputs[5]['legacy_original']['columns'][0:2] = reversed(inputs[5]['legacy_original']['columns'][0:2])
    with pytest.raises(ValueError, match='schema/values'):
        MODULE.reconcile(*inputs)


def test_reject_prefix_value_drift(inputs):
    inputs[5]['legacy_rewritten']['values'][0][0] += 1
    with pytest.raises(ValueError, match='exact V7 replay'):
        MODULE.reconcile(*inputs)


def test_reject_original_descriptor_drift(inputs):
    inputs[5]['legacy_original']['values'][0][-1] += 1
    with pytest.raises(ValueError, match='exact V7 replay'):
        MODULE.reconcile(*inputs)
