"""Generic graph provenance, arithmetic proxies and inference label isolation."""
import copy
import json
from pathlib import Path
import shutil
import subprocess

import numpy as np
import pytest

from isaforge import graph_features_v5 as v5


def graph(gates=(), output=2):
    cells = {}
    for i, (kind, inputs, out) in enumerate(gates):
        ports = v5.PRIMITIVES[kind]
        connections = {p: [b] for p, b in zip(ports, inputs)}
        connections['Y'] = [out]
        cells[str(i)] = {'type': kind, 'connections': connections,
                         'port_directions': {p: 'output' if p == 'Y' else 'input' for p in connections}}
    return {'modules': {'candidate': {'ports': {
        'in0': {'direction': 'input', 'bits': [2, 3]},
        'result': {'direction': 'output', 'bits': [output]}}, 'cells': cells}}}


def word(cells=()):
    return {'modules': {'candidate': {'cells': {str(i): c for i, c in enumerate(cells)}}}}


def arithmetic(kind, a=32, b=32, y=32, signed=0):
    return {'type': kind, 'parameters': {'A_WIDTH': format(a, '032b'),
                                       'B_WIDTH': format(b, '032b'),
                                       'Y_WIDTH': format(y, '032b'),
                                       'A_SIGNED': format(signed, '032b'),
                                       'B_SIGNED': '0'}}


def test_word_arithmetic_proxies_do_not_disappear_with_bit_blasting():
    result = dict(zip(v5.WORD_COLUMNS, v5.word_features(word([
        arithmetic('$add'), arithmetic('$sub', y=8), arithmetic('$mul', a=4, b=7, y=11, signed=1)]))))
    assert result['word_carry_span_proxy'] == 40
    assert result['word_carry_span_max_proxy'] == 32
    assert result['word_multiply_partial_terms_proxy'] == 28
    assert result['word_signed_arithmetic_count'] == 1
    assert result['word_arithmetic_output_bits'] == 51


@pytest.mark.parametrize('output', ['0', '1', 2])
def test_constants_and_wires_have_no_generic_gates(output):
    values = dict(zip(v5.CHANNEL_COLUMNS, v5.channel_features(graph(output=output), word())))
    assert values['gate_count'] == values['greedy_lut4_cover'] == 0
    assert values['word_carry_span_proxy'] == 0
    assert values['input_support_bits'] == (1 if output == 2 else 0)


def test_primitive_ports_and_support_are_validated():
    netlist = graph([('$_AND_', (2, 3), 10), ('$_NOT_', (10,), 11)], output=11)
    values = dict(zip(v5.CHANNEL_COLUMNS, v5.channel_features(netlist, word())))
    assert values['primitive_and'] == values['primitive_not'] == 1
    assert values['depth_max'] == 2
    assert values['input_support_bits'] == 2
    bad = copy.deepcopy(netlist)
    bad['modules']['candidate']['cells']['0']['connections']['A'] = [999]
    with pytest.raises(ValueError, match='Undriven'):
        v5.channel_features(bad, word())
    bad = copy.deepcopy(netlist)
    bad['modules']['candidate']['cells']['0']['connections']['B'] = [3, 3]
    with pytest.raises(ValueError, match='one-bit'):
        v5.channel_features(bad, word())


@pytest.mark.parametrize('kind', ['SB_LUT4', 'SB_CARRY', '$lut', '$_DFF_P_'])
def test_target_and_sequential_cells_are_rejected(kind):
    netlist = graph([('$_AND_', (2, 3), 10)], output=10)
    netlist['modules']['candidate']['cells']['0']['type'] = kind
    with pytest.raises(ValueError, match='Unsupported'):
        v5.channel_features(netlist, word())


def test_cycles_and_undefined_constants_are_rejected():
    cyclic = graph([('$_AND_', (11, 2), 10), ('$_XOR_', (10, 3), 11)], output=11)
    with pytest.raises(ValueError, match='Cyclic'):
        v5.channel_features(cyclic, word())
    with pytest.raises(ValueError, match='Undefined'):
        v5.channel_features(graph(output='x'), word())


def test_pipeline_explicitly_avoids_abc_and_target_mapping():
    assert 'synth -top candidate -noabc' in v5.PIPELINE
    assert 'synth_ice40' not in v5.PIPELINE
    assert not any(line.strip().startswith(('abc ', 'abc9 ', 'dfflibmap ')) for line in v5.PIPELINE.splitlines())


def test_two_channels_and_delta_ignore_row_outcomes(monkeypatch, tmp_path):
    frozen = {'version': 'test', 'executable_sha256': 'test'}
    extractor = v5.GraphExtractor(tmp_path, frozen_tool=frozen)
    monkeypatch.setattr(v5, '_normalize_formula', lambda formula: 'in0')
    calls = []

    def fake(formula):
        calls.append(formula)
        values = [0.] * len(v5.CHANNEL_COLUMNS)
        values[0] = 1. if formula != 'ori(in0,0)' else 0.
        return {'feature_values': values, 'cache_hit': True}

    monkeypatch.setattr(extractor, '_channel', fake)
    clean = {'formula': 'xor(in0,in0)'}
    poisoned = {**clean, 'lut4_count': float('nan'), 'area': 999, 'carry_count': 777,
                'correctness_verified': False, 'stratum': 'other', 'speedup': float('inf')}
    x, records = extractor.matrix([clean, poisoned], workers=1)
    assert x.shape == (2, len(v5.COLUMNS))
    assert np.array_equal(x[0], x[1])
    n = len(v5.CHANNEL_COLUMNS)
    assert x[0, 0] == x[0, 2*n] == 1. and x[0, n] == 0.
    assert calls == ['xor(in0,in0)', 'ori(in0,0)'] * 2
    assert records[0]['feature_columns'] == list(v5.COLUMNS)
    assert extractor.matrix([], workers=1)[0].shape == (0, len(v5.COLUMNS))


@pytest.mark.parametrize('value, expected', [('in0', 'ori(in0,0)'), ('in1', 'ori(in1,0)'),
                                          ('0', 'lui(0)'), ('4294967295', 'lui(4294967295)')])
def test_normalized_leaf_roots_remain_legal_rtl_formulas(value, expected):
    assert v5._normalized_root(value) == expected


@pytest.mark.skipif(shutil.which('yosys') is None, reason='Yosys is not installed')
def test_real_graph_cache_is_portable_and_checked_without_yosys(monkeypatch, tmp_path):
    # Identity normalization exercises both channels without depending on another
    # agent's normalizer implementation; arithmetic is rendered by real Yosys.
    monkeypatch.setattr(v5, '_normalize_formula', lambda formula: formula)
    extractor = v5.GraphExtractor(tmp_path / 'first')
    first = extractor.extract('add(in0,in1)')
    named = dict(zip(v5.COLUMNS, first['values']))
    assert named['original_word_add_count'] == 1
    assert named['original_word_carry_span_proxy'] == 32
    assert named['original_gate_count'] > 0
    assert not first['cache_hit']
    assert all(not Path(p).is_absolute() for p in first['original']['paths'].values())
    moved = tmp_path / 'moved'
    shutil.copytree(extractor.cache_dir, moved)
    cold_key = first['original']['cache_key']
    monkeypatch.setattr(v5, 'tool_identity', lambda *a: (_ for _ in ()).throw(RuntimeError('no tool')))
    restored = v5.GraphExtractor(moved, frozen_tool=extractor.tool)
    replay = restored.extract('add(in0,in1)')
    assert replay['cache_hit'] and replay['values'] == first['values']
    (moved / cold_key / 'graph.json').write_text('{}')
    with pytest.raises(ValueError, match='hash mismatch'):
        restored.extract('add(in0,in1)')
    with pytest.raises(RuntimeError, match='no tool'):
        restored.extract('sub(in0,in1)')


@pytest.mark.skipif(shutil.which('yosys') is None, reason='Yosys is not installed')
def test_concurrent_duplicate_channels_share_complete_cache(monkeypatch, tmp_path):
    monkeypatch.setattr(v5, '_normalize_formula', lambda formula: formula)
    extractor = v5.GraphExtractor(tmp_path)
    x, records = extractor.matrix([{'formula': 'xor(in0,in1)'}] * 6, workers=2)
    assert np.all(x == x[0])
    assert len(list(tmp_path.glob('*/features.json'))) == 1
    assert all(r['original']['feature_values'] == r['normalized']['feature_values'] for r in records)


def test_source_changes_invalidate_live_extractor(monkeypatch, tmp_path):
    extractor = v5.GraphExtractor(tmp_path, frozen_tool={'version': 'test', 'executable_sha256': 'test'})
    monkeypatch.setattr(v5, 'source_hashes', lambda: {'changed': 'hash'})
    with pytest.raises(ValueError, match='sources changed'):
        extractor.extract('in0')


def test_timeouts_are_explicit_failures_without_complete_cache(monkeypatch, tmp_path):
    identity = {'version': 'test', 'executable_sha256': 'test', 'executable': 'yosys'}
    monkeypatch.setattr(v5, 'tool_identity', lambda *a: identity)
    monkeypatch.setattr(v5, '_normalize_formula', lambda formula: formula)
    monkeypatch.setattr(v5.subprocess, 'run', lambda *a, **k: (_ for _ in ()).throw(subprocess.TimeoutExpired('yosys', 1)))
    extractor = v5.GraphExtractor(tmp_path, timeout=1)
    with pytest.raises(RuntimeError, match='timed out'):
        extractor.extract('add(in0,in1)')
    assert not list(tmp_path.glob('*/features.json'))
    assert 'timeout' in next(tmp_path.glob('*/extract.log')).read_text()
