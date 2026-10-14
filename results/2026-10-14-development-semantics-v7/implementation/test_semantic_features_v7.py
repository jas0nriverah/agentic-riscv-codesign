"""V7 rule boundaries, reconstruction interactions and bounded proof fallbacks."""
from dataclasses import replace
import itertools
import random
import subprocess

import pytest
from isaforge import semantic_features_v7 as v7
from isaforge.features import parse_formula
from isaforge.rtl import evaluate_formula

BOUNDARY = (0, 1, 2, 127, 128, 129, 255, 65535, 0x7fffffff, 0x80000000, 0xaaaaaaaa, 0x55555555, v7.MASK)


def same_values(formula, normalized):
    for x, y in itertools.product(BOUNDARY, repeat=2):
        assert evaluate_formula(formula, x, y) == evaluate_formula(normalized, x, y)


@pytest.mark.parametrize('mask', [0, 1, 128, 255, 65535, 0x55555555, 0xaaaaaaaa, -1, -2147483648])
@pytest.mark.parametrize('template', ['sub(ori(in0,{c}),in0)', 'sub(or({c},in0),in0)',
                                     'sub(in0,andi(in0,{c}))', 'sub(in0,and({c},in0))'])
def test_generic_mask_instances_boundary_oracle_and_idempotence(mask, template):
    formula = template.format(c=mask); result = v7.analyze_formula(formula, 'bit')
    same_values(formula, result['normalized_formula'])
    assert result['metadata']['steps'] and all(s['proof']['result'] == 'unsat' for s in result['metadata']['steps'])
    assert v7.normalize_formula(result['normalized_formula'], 'bit') == result['normalized_formula']


@pytest.mark.parametrize('shift', [0, 1, 16, 31, 32, 63, -1, -2147483648])
def test_left_shift_coefficients_use_rv32_mask(shift):
    formula = f'sub(slli(in0,{shift}),sll(in0,{shift}))'
    normalized = v7.normalize_formula(formula, 'affine')
    assert normalized == 'addi(0,0)'
    same_values(formula, normalized)


@pytest.mark.parametrize('formula', [
    'add(slli(in0,1),sub(in1,add(in0,in0)))',
    'slli(slli(in0,16),16)',
    'add(add(in0,in1),sub(in0,in1))',
    'sub(0,add(slli(in0,31),in1))',
    'add(addi(in0,-1),addi(sub(in1,in0),1))',
    'add(slli(in0,1),in0)',
    'sub(ori(sub(in0,in0),255),sub(in0,in0))',
    'mulhsu(sub(ori(in1,255),in1),slli(in0,16))',
    'mulh(sub(in0,andi(in0,255)),sub(ori(in1,-1),in1))',
])
def test_interactions_reconstruct_modularly_and_stabilize(formula):
    for mode in v7.MODES:
        normalized = v7.normalize_formula(formula, mode)
        same_values(formula, normalized)
        parse_formula(normalized)
        assert v7.normalize_formula(normalized, mode) == normalized


@pytest.mark.parametrize('formula', [
    'sub(ori(in0,255),in1)', 'sub(in1,ori(in0,255))',
    'sub(andi(in0,255),in0)', 'sub(in0,andi(in1,255))',
    'sub(ori(in0,in1),in0)',
])
def test_correlation_requires_exact_operand_and_constant(formula):
    # ori requires literal immediate; a symbolic OR is legal only with `or`.
    formula = formula.replace('ori(in0,in1)', 'or(in0,in1)')
    assert v7.normalize_formula(formula, 'bit') == formula


@pytest.mark.parametrize('formula', [
    'sub(srli(add(in0,in1),1),srli(in0,1))',
    'sub(sra(in0,in1),srl(in0,in1))',
    'sub(sll(in0,in1),slli(in0,1))',
    'sub(mulh(in0,in1),mulhsu(in0,in1))',
    'sub(mulhu(in0,in1),mulhsu(in0,in1))',
])
def test_opaque_nonaffine_operations_are_never_distributed(formula):
    normalized = v7.normalize_formula(formula, 'affine')
    same_values(formula, normalized)
    atoms = v7._collect(parse_formula(formula), v7.Budget())[1]
    assert len(atoms) == 2
    for atom in atoms.values(): assert atom.canonical() in normalized


def test_combined_block_is_exact_independent_concat_and_wire_keeps_grammar():
    formula = 'add(sub(ori(in0,255),in0),sub(slli(in1,1),add(in1,in1)))'
    combined = v7.feature_dict(formula)
    assert combined == {**v7.feature_dict(formula, 'bit'), **v7.feature_dict(formula, 'affine')}
    assert tuple(combined) == v7.FEATURE_NAMES
    assert len(v7.BIT_NAMES) == len(v7.AFFINE_NAMES) == 8
    assert v7.normalize_formula('sub(in0,in0)', 'affine') == 'addi(0,0)'
    assert v7.analyze_formula('sub(in0,in0)')['metadata']['original_zero_override'] is False


def test_multiply_operand_support_width_and_signed_roles():
    result = v7.analyze_formula('mulhsu(sub(ori(in1,255),in1),andi(in0,-129))', 'bit')
    a, b = result['metadata']['normalized_multiply_operands']
    assert a['signed'] and a['sign'] == 'zero'
    assert (a['possible_one_bits'], a['unsigned_width'], a['interpreted_width']) == (8, 8, 9)
    assert not b['signed'] and b['unsigned_width'] == b['interpreted_width'] == 32
    assert b['unsigned_maximum'] == ((-129) & v7.MASK)


@pytest.mark.parametrize('budget', [v7.Budget(max_atoms=1), v7.Budget(max_island_ops=1),
    v7.Budget(max_output_ops=1), v7.Budget(max_passes=1)])
def test_tight_budgets_are_visible_and_do_not_leave_unstable_normal_form(budget):
    formula = 'add(sub(in0,in1),slli(in0,1))'
    result = v7.analyze_formula(formula, 'affine', budget)
    same_values(formula, result['normalized_formula'])
    assert result['metadata']['attempts'] or result['metadata']['proof_engine']['fallback_reason']
    assert v7.normalize_formula(result['normalized_formula'], 'affine', budget) == result['normalized_formula']
    assert not any('budget' in name or 'proof' in name for name in result['features'])


def test_reconstruction_budget_checked_before_building_large_atoms():
    atom = 'xor(in0,in1)'
    formula = f'add(slli({atom},1),{atom})'
    with pytest.raises(v7.BudgetExceeded):
        v7._rebuild(v7._collect(parse_formula(formula), v7.Budget()), limit=1)


def test_unknown_and_missing_proof_fall_back_but_sat_stops(monkeypatch):
    formula = 'sub(ori(in0,255),in0)'
    for status in ('unknown', 'unavailable'):
        monkeypatch.setattr(v7, '_prove', lambda *a, **k: {'result': status})
        result = v7.analyze_formula(formula, 'bit')
        assert result['normalized_formula'] == formula and not result['metadata']['steps']
        assert result['metadata']['attempts'][0]['proof']['result'] == status
    monkeypatch.setattr(v7, '_prove', lambda *a, **k: {'result': 'sat'})
    with pytest.raises(v7.ProofError, match='SAT'): v7.normalize_formula(formula, 'bit')


def test_known_masks_are_sound_on_arithmetic_shift_and_highproduct_boundaries():
    formulas = ['add(andi(in0,255),slli(in1,16))', 'sub(andi(in0,255),1)',
        'srai(ori(in0,-2147483648),31)', 'slli(andi(in0,255),63)',
        'mul(andi(in0,65520),slli(in1,4))', 'mulhsu(andi(in0,0),in1)',
        'xor(andi(in0,255),ori(in1,65535))', 'srl(in0,in1)']
    rng = random.Random(20261014)
    for formula in formulas:
        zero, one = v7._known(parse_formula(formula)); assert not zero & one
        for x, y in [*itertools.product(BOUNDARY, repeat=2), *((rng.getrandbits(32), rng.getrandbits(32)) for _ in range(100))]:
            value = evaluate_formula(formula, x, y)
            assert value & zero == 0 and value & one == one


def test_source_only_matrix_ignores_outcomes_and_has_no_native_processes(monkeypatch):
    monkeypatch.setattr(subprocess, 'Popen', lambda *a, **k: (_ for _ in ()).throw(AssertionError('No native tools')))
    rows = [{'formula': 'sub(ori(in0,255),in0)', 'lut4_count': float('nan'), 'predicted_lut4': -999}]
    matrix, records = v7.feature_matrix(rows)
    assert matrix == [v7.feature_vector(rows[0]['formula'])]
    assert records[0]['original_formula'] == rows[0]['formula']
    assert all(type(n) is int and n >= 0 for n in matrix[0])
    assert set(v7.source_hashes()) == {'features.py', 'semantic_features_v7.py'}


def test_one_shared_formula_proof_budget_rolls_back_all_modes(monkeypatch):
    timeouts = []
    def slow_proof(before, after, atoms, timeout_ms):
        timeouts.append(timeout_ms)
        return {'result': 'unsat', 'elapsed_ms': 300., 'cpu_ms': 250.}
    monkeypatch.setattr(v7, '_prove', slow_proof)
    formula = 'add(sub(ori(in0,255),in0),sub(in1,andi(in1,255)))'
    result = v7.analyze_modes(formula)
    assert timeouts == [500, 200]
    for record in result.values():
        assert record['normalized_formula'] == formula
        assert record['metadata']['status'] == 'fallback_original'
        assert not record['metadata']['steps']
        assert record['metadata']['proof_engine']['fallback_reason'] == 'proof_budget'
        assert record['metadata']['proof_engine']['solver_seconds'] == .5
    assert result['combined']['features'] == {**result['bit']['features'], **result['affine']['features']}


def test_repeated_local_proofs_reused_across_modes():
    record = v7.analyze_modes('sub(ori(in0,255),in0)')
    engine = record['combined']['metadata']['proof_engine']
    assert engine['local_cache_hits'] >= 1
    assert engine['unique_solver_calls'] >= 1
    assert record['bit']['metadata']['proof_engine'] == engine


def test_pattern_counts_deduplicate_original_shared_subexpressions():
    atom = 'sub(ori(in0,255),in0)'
    result = v7.feature_dict('xor('+atom+','+atom+')', 'bit')
    assert result['v7_bit_or_sub_count'] == 1
