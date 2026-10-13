"""Matched recipe, target isolation, pre-ABC extraction and artifact contracts."""
import json
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys

import numpy as np
import pytest

from isaforge.masterrtl_baseline import (FEATURE_COLUMNS, MODEL_CONFIG, PIPELINE,
    PRIMITIVE_TYPES, SOGExtractor, WEIGHTS, load_model, netlist_features, save_model,
    train_model)


def netlist(counts):
    cells = {}
    for typ, count in counts.items():
        for index in range(count):
            cells[f'{typ}{index}'] = {'type': typ, 'connections': {'A': [1], 'Y': [index+2]},
                                     'port_directions': {'A': 'input', 'Y': 'output'}}
    return {'modules': {'candidate': {'cells': cells, 'ports': {
        'in0': {'direction': 'input', 'bits': list(range(32))},
        'in1': {'direction': 'input', 'bits': list(range(32, 64))},
        'result': {'direction': 'output', 'bits': list(range(64, 96))}}}}}


def data():
    return [{'formula': formula, 'benchmark': str(index % 3), 'lut4_count': label,
             'measurement_source': 'rtl_synthesis'} for index, (formula, label) in enumerate([
                 ('xor(in0,in1)', 32), ('add(in0,in1)', 61), ('addi(in0,1)', 31),
                 ('sll(in0,in1)', 155), ('sltu(in0,in1)', 32), ('xor(in0,in0)', 0)])]


def test_fourteen_feature_order_and_exact_rounded_reference_weights():
    counts = {name: index+1 for index, name in enumerate(PRIMITIVE_TYPES)}
    vector, primitive = netlist_features(netlist(counts))
    assert len(vector) == len(FEATURE_COLUMNS) == 14
    assert vector[:8] == [0, 0, 96, 1, 2, 3, 4, 5]
    expected = {kind: round(sum(WEIGHTS[kind][op]*(index+1) for index, op in enumerate(PRIMITIVE_TYPES.values())), 0)
                for kind in WEIGHTS}
    assert vector[8:] == [0, expected['area_comb'], expected['area_comb'],
                          expected['stat_pwr'], expected['dyn_pwr'], expected['stat_pwr']+expected['dyn_pwr']]
    assert primitive == counts
    assert MODEL_CONFIG['n_estimators'] == 25 and MODEL_CONFIG['max_depth'] == 12
    assert MODEL_CONFIG['target_transform'] == 'none'
    assert 'abc' not in PIPELINE and 'ice40' not in PIPELINE


def test_unexpected_primitive_or_word_level_cell_rejected():
    with pytest.raises(ValueError, match='unsupported'):
        netlist_features(netlist({'$add': 1}))
    bad = netlist({'$_XOR_': 1})
    next(iter(bad['modules']['candidate']['cells'].values()))['connections']['Y'] = [1, 2]
    with pytest.raises(ValueError, match='single-bit'):
        netlist_features(bad)


@pytest.mark.skipif(shutil.which('yosys') is None, reason='requires Yosys')
def test_actual_preabc_extraction_preserves_graph_logs_and_verified_cache(tmp_path):
    extractor = SOGExtractor(tmp_path)
    record, cached = extractor.extract('xor(in0,in1)')
    assert not cached
    assert record['feature_values'][6] == 32
    assert record['primitive_cell_counts'] == {'$_XOR_': 32}
    folder = tmp_path/record['cache_key']
    assert all((folder/name).exists() for name in ('candidate.v', 'sog.ys', 'sog.v', 'sog.json', 'sog.log', 'features.json'))
    assert 'ABC RESULTS' not in (folder/'sog.log').read_text()
    second, cached = extractor.extract('xor(in0,in1)')
    assert cached and second == record
    second['feature_values'][6] = 999
    (folder/'features.json').write_text(json.dumps(second))
    with pytest.raises(ValueError, match='features hash'):
        extractor.extract('xor(in0,in1)')
    second['feature_values_sha256'] = hashlib.sha256(json.dumps(second['feature_values'], separators=(',', ':')).encode()).hexdigest()
    (folder/'features.json').write_text(json.dumps(second))
    with pytest.raises(ValueError, match='differ from retained'):
        extractor.extract('xor(in0,in1)')
    (folder/'features.json').write_text(json.dumps(record))
    (folder/'sog.json').write_text((folder/'sog.json').read_text()+' ')
    with pytest.raises(ValueError, match='source/netlist/log hash'):
        extractor.extract('xor(in0,in1)')


@pytest.mark.skipif(shutil.which('yosys') is None, reason='requires Yosys')
def test_labels_and_trace_fields_cannot_enter_inference_features_or_prediction(tmp_path):
    model = train_model(data(), tmp_path)
    clean = {'formula': 'xor(in0,in1)'}
    poisoned = {**clean, 'lut4_count': -999, 'ice40_lut4_count': 10**9, 'runs': 90000,
                'generic_cell_count': 300, 'benchmark': 'poison'}
    assert model.predict([clean])[0]['predicted_lut4'] == model.predict([poisoned])[0]['predicted_lut4']
    np.testing.assert_array_equal(SOGExtractor(tmp_path).matrix([clean]), SOGExtractor(tmp_path).matrix([poisoned]))
    assert model.predict([]) == []
    duplicate = {**data()[0], 'benchmark': 'other'}
    assert train_model(data()+[duplicate], tmp_path).training_formula_count == len(data())
    with pytest.raises(ValueError, match='rtl_synthesis'):
        train_model([{**data()[0], 'measurement_source': 'synthetic'}], tmp_path)


@pytest.mark.skipif(shutil.which('yosys') is None, reason='requires Yosys')
def test_canonical_artifact_roundtrip_cli_and_configuration_tamper(tmp_path, monkeypatch):
    model = train_model(data(), tmp_path/'cache')
    paths = save_model(model, tmp_path/'model')
    assert load_model(paths['model_path']).predict(data()) == model.predict(data())
    assert type(load_model(paths['model_path'])).__module__ == 'isaforge.masterrtl_baseline'
    candidates = tmp_path/'candidates.json'; candidates.write_text(json.dumps([{'formula': 'xor(in0,in1)'}]))
    output = tmp_path/'predictions.json'
    process = subprocess.run([sys.executable, '-m', 'isaforge.masterrtl_baseline', 'predict',
                              '--model', paths['model_path'], '--candidates', str(candidates), '--output', str(output)],
                             capture_output=True, text=True)
    assert process.returncode == 0, process.stderr
    assert len(json.loads(output.read_text())) == 1
    portable = tmp_path/'portable'; portable.mkdir()
    portable_model = portable/'masterrtl-sog.joblib'
    shutil.copyfile(paths['model_path'], portable_model)
    shutil.copyfile(paths['schema_path'], portable_model.with_suffix('.json'))
    shutil.copytree(tmp_path/'cache', portable/'sog-cache')
    restored = load_model(portable_model)
    assert Path(restored.cache_dir) == portable/'sog-cache'
    def unavailable(*args, **kwargs):
        raise RuntimeError('Yosys deliberately unavailable to test cached inference')
    monkeypatch.setattr('isaforge.masterrtl_baseline.tool_identity', unavailable)
    assert restored.predict([{'formula': 'xor(in0,in1)'}]) == model.predict([{'formula': 'xor(in0,in1)'}])
    copied_process = subprocess.run([sys.executable, '-m', 'isaforge.masterrtl_baseline', 'predict',
                                     '--model', str(portable_model), '--candidates', str(candidates), '--output', str(output)],
                                    capture_output=True, text=True, env={**os.environ, 'PATH': ''})
    assert copied_process.returncode == 0, copied_process.stderr
    schema = json.loads(Path(paths['schema_path']).read_text())
    schema['model_config']['max_depth'] = 3
    Path(paths['schema_path']).write_text(json.dumps(schema))
    with pytest.raises(ValueError, match='configuration'):
        load_model(paths['model_path'])
