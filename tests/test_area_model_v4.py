"""Topology feature and formula-only metadata checks, without synthesis labels."""
import json
from pathlib import Path

import numpy as np
import pytest

from isaforge import area_model_v4 as v4


def netlist(gates=(), outputs=(2,), inputs=(2, 3, 4, 5, 6)):
    cells = {}
    for i, (kind, ins, out) in enumerate(gates):
        connections = {f'I{j}': [b] for j, b in enumerate(ins)}
        connections['Y'] = [out]
        directions = {p: 'input' for p in connections}
        directions['Y'] = 'output'
        cells[f'gate{i}'] = {'type': f'$_{kind.upper()}_',
                            'connections': connections, 'port_directions': directions}
    return {'modules': {'candidate': {'ports': {
        'in': {'direction': 'input', 'bits': list(inputs)},
        'out': {'direction': 'output', 'bits': list(outputs)}}, 'cells': cells}}}


def named(graph):
    return dict(zip(v4.GRAPH_COLUMNS, v4.graph_features(graph)))


def test_wires_constants_and_nonconstant_support_remain_distinct():
    f = named(netlist(outputs=('0', '1', 2, 2)))
    assert f['gate_count'] == f['greedy_lut4_cover'] == 0
    assert f['output_constant_bits'] == 2
    assert f['output_wire_bits'] == 2
    assert f['input_support_bits'] == 1
    assert f['output_support_mean'] == .5
    assert f['depth_max'] == 0


def test_equal_operator_counts_different_topology_have_different_features():
    chain = netlist([('and', (2, 3), 10), ('and', (10, 4), 11),
                     ('xor', (11, 5), 12)], outputs=(12,))
    parallel = netlist([('and', (2, 3), 10), ('and', (4, 5), 11),
                        ('xor', (10, 11), 12)], outputs=(12,))
    a, b = named(chain), named(parallel)
    assert a['gate_count'] == b['gate_count'] == 3
    assert a['input_support_bits'] == b['input_support_bits'] == 4
    assert a['depth_max'] == 3 and b['depth_max'] == 2
    assert a['edge_and_and'] == 1 and b['edge_and_and'] == 0
    assert a['greedy_lut4_cover'] == b['greedy_lut4_cover'] == 1


def test_five_input_chain_requires_two_four_input_cuts():
    f = named(netlist([('and', (2, 3), 10), ('and', (10, 4), 11),
                       ('and', (11, 5), 12), ('and', (12, 6), 13)], outputs=(13,)))
    assert f['input_support_bits'] == 5
    assert f['greedy_lut4_cover'] == 2
    assert f['support_gt4_count'] == 1
    assert f['depth_max'] == 4


def test_shared_output_cover_is_counted_once_and_shared_cut_is_retained():
    graph = netlist([('and', (2, 3), 10), ('xor', (10, 4), 11)],
                    outputs=(10, 10, 11))
    f = named(graph)
    assert f['output_driven_bits'] == 3
    assert f['output_distinct_driven_bits'] == 2
    assert f['output_gate_reuse'] == 1
    assert f['greedy_lut4_cover'] == 2
    assert f['fanout_max'] == 3
    assert f['edge_and_xor'] == 1


def test_cell_iteration_order_does_not_change_features():
    graph = netlist([('and', (2, 3), 10), ('or', (4, 5), 11),
                     ('mux', (10, 11, 6), 12)], outputs=(12,))
    expected = v4.graph_features(graph)
    graph['modules']['candidate']['cells'] = dict(reversed(
        list(graph['modules']['candidate']['cells'].items())))
    assert np.array_equal(v4.graph_features(graph), expected)


@pytest.mark.parametrize('gates', [
    [('and', (2, 3), 10), ('xor', (4, 5), 10)],
    [('and', (11, 2), 10), ('xor', (10, 3), 11)],
    [('unsupported', (2, 3), 10)],
])
def test_invalid_primitive_graph_rejected(gates):
    with pytest.raises(ValueError):
        v4.graph_features(netlist(gates, outputs=(10,)))


def test_features_ignore_all_row_outcomes_and_trace_metadata(monkeypatch, tmp_path):
    """A fake extractor supplies a label-free graph; labels cannot reach it."""
    class FakeSOG:
        def __init__(self, cache_dir, **kwargs):
            self.cache_dir = Path(cache_dir)
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            self.tool = {'version': 'fake', 'executable_sha256': 'fake'}

        def extract(self, formula):
            directory = self.cache_dir / 'fake'
            directory.mkdir(exist_ok=True)
            (directory / 'sog.json').write_text(json.dumps(netlist(
                [('and', (2, 3), 10)], outputs=(10,))))
            (directory / 'features.json').write_text('{}')
            return {'cache_key': 'fake', 'feature_values': [0.] * len(v4.SOG_COLUMNS)}, True

    monkeypatch.setattr(v4, 'SOGExtractor', FakeSOG)
    clean = {'benchmark': 'one', 'candidate_id': 'x', 'formula': 'and(in0,in1)'}
    poisoned = {**clean, 'benchmark': 'different', 'candidate_id': 'different',
                'lut4_count': 999999, 'carry_count': float('nan'),
                'measurement_source': 'impossible', 'correctness_verified': False,
                'speedup': -100, 'generic_cell_count': 12345, 'runs': 999,
                'saved': 55555, 'stratum': 'invented', 'area': float('inf')}
    x, _ = v4.FeatureExtractor(tmp_path / 'cache1').matrix([clean], workers=1)
    z, _ = v4.FeatureExtractor(tmp_path / 'cache2').matrix([poisoned], workers=1)
    assert x.shape == (1, len(v4.columns()))
    assert np.array_equal(x, z)


def test_normalized_equal_formulas_stay_in_same_fold_group():
    assert v4.grouping('add(in0,0)') == v4.grouping('andi(in0,4294967295)')
    assert v4.grouping('add(in0,7)') == v4.grouping('add(in1,3)')


def test_inference_uses_frozen_tool_and_zero_graph_override(monkeypatch):
    seen = []
    frozen_tool = {'version': 'frozen', 'executable_sha256': 'abc'}

    class FakeExtractor:
        def __init__(self, cache, *, frozen_tool=None):
            seen.append(frozen_tool)

        def matrix(self, rows, workers):
            x = np.zeros((len(rows), len(v4.columns())))
            x[1, len(v4.SOG_COLUMNS) + v4.GRAPH_COLUMNS.index('gate_count')] = 1
            return x, []

    class Estimator:
        def predict(self, x):
            return np.full(len(x), 7.)

    monkeypatch.setattr(v4, 'FeatureExtractor', FakeExtractor)
    model = v4.V4Predictor(Estimator(), 'xgb_raw_d3', 1289, v4.columns(), 'unused', frozen_tool)
    predictions = model.predict([{'formula': 'ori(in0,0)'}, {'formula': 'and(in0,in1)'}])
    assert seen == [frozen_tool]
    assert [r['predicted_lut4'] for r in predictions] == [0., 7.]
