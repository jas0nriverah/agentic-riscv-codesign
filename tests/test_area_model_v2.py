"""Formula-only inference, resource abstractions, and frozen artifact contracts."""
import json
import os
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest

from isaforge.area_model_v2 import (EXTRA_COLUMNS, FEATURE_COLUMNS, MODEL_CONFIG,
                                   RESOURCE_COLUMNS, _symbols, feature_matrix,
                                   load_area_model_v2, resource_matrix, save_model,
                                   train_resource_model, train_v2_model)
from isaforge.features import IMMEDIATE_OPERATIONS, OPERATIONS, parse_formula
from isaforge.rtl import evaluate_formula


def rows():
    # Artificial labels exercise API contracts, never serve as accuracy evidence.
    return [{'benchmark': str(index % 3), 'formula': formula, 'lut4_count': value,
             'measurement_source': 'rtl_synthesis'}
            for index, (formula, value) in enumerate([
                ('add(in0,in1)', 61), ('addi(in0,1)', 31), ('xor(in0,in1)', 32),
                ('sll(in0,in1)', 155), ('sltu(in0,in1)', 32),
                ('mul(andi(in0,255),andi(in1,255))', 128),
                ('mul(andi(in0,65535),andi(in1,65535))', 512),
                ('mul(in0,3)', 45), ('xor(in0,in0)', 0)])]


def extra(formula):
    x = feature_matrix([{'formula': formula}])[0]
    return dict(zip(FEATURE_COLUMNS, x))


def test_no_measured_or_dynamic_fields_can_enter_features_or_inference():
    clean = {'formula': 'mul(srai(slli(in0,16),16),in1)'}
    poison = {**clean, 'benchmark': 'poison', 'candidate_id': 'other', 'runs': 10**12,
              'lut4_count': -200, 'generic_cell_count': 4000, 'generic_logic_depth': 999,
              'ice40_dsp_count': 888, 'saved': 10**10, 'merit': -1}
    np.testing.assert_array_equal(feature_matrix([clean]), feature_matrix([poison]))
    model = train_v2_model(rows())
    assert model.predict([clean])[0]['predicted_lut4'] == model.predict([poison])[0]['predicted_lut4']
    assert not any('lut' in name or 'generic' in name or 'runs' in name for name in FEATURE_COLUMNS)


def test_multiplier_resources_distinguish_sign_extension_and_retained_product():
    full = extra('mul(in0,in1)')
    narrow = extra('mul(srai(slli(in0,16),16),in1)')
    high_unsigned = extra('mulhu(srai(slli(in0,16),16),in1)')
    truncated = extra('andi(mul(in0,in1),255)')
    assert full['variable_mul_partial_products'] == 528
    assert narrow['variable_mul_partial_products'] == 392
    assert narrow['multiply_operand_width_product_sum'] == 512
    assert high_unsigned['variable_mul_partial_products'] == 1024
    assert truncated['variable_mul_partial_products'] == 36
    assert truncated['multiply_output_demand_bits_sum'] == 8


@pytest.mark.parametrize('formula', [
    'mul(in0,8)', 'mul(in0,0)', 'addi(in0,0)', 'add(in0,in0)',
    'add(andi(in0,65535),slli(in1,16))', 'xor(addi(in0,1),addi(in0,1))',
    'mulhu(andi(in0,65535),andi(in1,65535))',
    'andi(add(in0,in1),0)', 'slli(in0,4)',
])
def test_proved_wiring_or_constant_formulas_have_zero_resource_cost(formula):
    assert not resource_matrix([{'formula': formula}]).any()
    assert train_v2_model(rows()).predict([{'formula': formula}])[0]['predicted_lut4'] == 0


def test_shared_nodes_are_costed_once_with_union_of_bit_demands():
    base = extra('xor(in0,in1)')
    doubled = extra('add(xor(in0,in1),xor(in0,in1))')
    # The shared XOR's highest bit is discarded by x+x == x<<1.
    assert doubled['logic_bits'] == base['logic_bits'] - 1
    assert doubled['adder_active_bits'] == 0
    assert doubled['shared_live_node_count'] == 1


def test_bit_symbols_are_sound_for_constants_wires_and_correlations():
    formulas = [f'{op}(4096)' if op == 'lui' else f'{op}(in0,-1)'
                if op in IMMEDIATE_OPERATIONS else f'{op}(in0,in1)' for op in OPERATIONS]
    formulas += ['srai(slli(in0,16),16)', 'add(in0,in0)',
                 'add(andi(in0,65535),slli(in1,16))', 'xor(ori(in0,3),3)',
                 'mulhu(andi(in0,65535),andi(in1,65535))',
                 'mulh(andi(in0,255),andi(in1,255))',
                 'mulhsu(andi(in0,255),andi(in1,255))',
                 'mul(andi(in0,255),andi(in1,255))', 'mul(in0,8)',
                 'and(xori(in0,-1),in0)', 'or(xori(in0,-1),in0)']
    rng = np.random.default_rng(20261013)
    for formula in formulas:
        root = parse_formula(formula)
        symbols = _symbols(root)
        for a, b in rng.integers(0, 2**32, size=(100, 2), dtype=np.uint64):
            output = evaluate_formula(root, int(a), int(b))
            observed = {}
            for bit, token in enumerate(symbols):
                value = (output >> bit) & 1
                if isinstance(token, int): assert value == token
                elif token[0] == 'input':
                    operand = int(a) if token[1] == 'in0' else int(b)
                    assert value == (operand >> token[2]) & 1
                if token in observed: assert value == observed[token]
                observed[token] = value


def test_resource_model_is_transparent_nonnegative_and_can_extrapolate():
    model = train_resource_model(rows())
    assert len(model.coefficients) == len(RESOURCE_COLUMNS)
    assert np.all(model.coefficients >= 0)
    full = model.predict([{'formula': 'mul(in0,in1)'}])[0]['predicted_lut4']
    assert full > max(row['lut4_count'] for row in rows())
    assert model.predict([]) == []


def test_distinct_formulas_receive_one_training_weight():
    data = rows()
    duplicate = {**data[0], 'benchmark': 'other'}
    a, b = train_resource_model(data), train_resource_model(data+[duplicate])
    np.testing.assert_array_equal(a.coefficients, b.coefficients)
    assert b.training_formula_count == len(data)
    with pytest.raises(ValueError, match='inconsistent'):
        train_resource_model(data+[{**duplicate, 'lut4_count': 100}])
    with pytest.raises(ValueError, match='rtl_synthesis'):
        train_v2_model([{**data[0], 'measurement_source': 'synthetic'}])


def test_both_models_roundtrip_and_reject_config_or_artifact_tampering(tmp_path):
    for name, model in [('resource-ridge', train_resource_model(rows())),
                        ('area-model-v2', train_v2_model(rows()))]:
        paths = save_model(model, tmp_path, name)
        loaded = load_area_model_v2(paths['model_path'])
        assert loaded.predict(rows()) == model.predict(rows())
    schema_path = tmp_path / 'area-model-v2.json'
    schema = json.loads(schema_path.read_text())
    assert schema['model_configs'] == MODEL_CONFIG
    schema['model_configs']['resource_residual_xgb']['max_depth'] = 999
    schema_path.write_text(json.dumps(schema))
    with pytest.raises(ValueError, match='configuration'):
        load_area_model_v2(tmp_path / 'area-model-v2.joblib')
    artifact = tmp_path / 'resource-ridge.joblib'
    artifact.write_bytes(artifact.read_bytes()+b'tampered')
    with pytest.raises(ValueError, match='hash'):
        load_area_model_v2(artifact)


def test_cli_training_artifacts_load_in_a_fresh_library_process(tmp_path):
    dataset = tmp_path / 'rows.json'
    dataset.write_text(json.dumps(rows()))
    output = tmp_path / 'model'
    root = Path(__file__).resolve().parents[1]
    environment = {**os.environ, 'PYTHONPATH': str(root)}
    train = subprocess.run([sys.executable, '-m', 'isaforge.area_model_v2', 'train',
                            '--rows', str(dataset), '--output-dir', str(output)],
                           cwd=root, env=environment, capture_output=True, text=True)
    assert train.returncode == 0, train.stderr
    # A separate process has no ResourcePredictor or ResidualPredictor aliases
    # in __main__; both baseline and ML artifacts must still load normally.
    code = '''
import sys
from isaforge.area_model_v2 import load_area_model_v2
for name in ('resource-ridge', 'area-model-v2'):
    model = load_area_model_v2(sys.argv[1]+'/'+name+'.joblib')
    assert type(model).__module__ == 'isaforge.area_model_v2'
    assert len(model.predict([{'formula': 'add(in0,in1)'}])) == 1
'''
    inference = subprocess.run([sys.executable, '-c', code, str(output)], cwd=root,
                               env=environment, capture_output=True, text=True)
    assert inference.returncode == 0, inference.stderr
