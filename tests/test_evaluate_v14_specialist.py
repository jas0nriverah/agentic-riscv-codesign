import importlib.util
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location('v14_router', Path(__file__).parents[1] / 'scripts/evaluate_v14_specialist.py')
router = importlib.util.module_from_spec(spec); spec.loader.exec_module(router)


@pytest.mark.parametrize('op', ['mulh', 'mulhu', 'mulhsu'])
@pytest.mark.parametrize('mask', [1, 17, 12345, -1])
def test_general_masks_and_high_product_kinds(op, mask):
    assert router.route(f'{op}(sub(ori(in0,{mask}),in0),in1)')['use_augmented']


@pytest.mark.parametrize('formula', [
    'mul(in0,sub(ori(in1,17),in1))',
    'mulhu(in0,in1)',
    'mulhu(sub(ori(in0,17),in1),in0)',
    'mulhu(sub(ori(0,17),0),in1)',
    'sub(ori(in0,17),in0)',
])
def test_fallback_without_eligible_correlation(formula):
    assert not router.route(formula)['use_augmented']


def test_nested_correlation_and_both_operand_positions():
    result = router.route('add(in0,mulhsu(in1,slli(sub(in0,andi(in0,-18)),2)))')
    assert result == {'use_augmented': True, 'matches': [{'product': 'mulhsu', 'product_path': [1],
            'operand_index': 1, 'pattern_path': [0], 'pattern': 'sub_and'}]}


def test_gate_cannot_receive_target_or_dataset_fields():
    with pytest.raises(TypeError): router.route('mulhu(in0,in1)', target=0)
    with pytest.raises(ValueError): router.route({'formula': 'mulhu(in0,in1)', 'target': 0})
