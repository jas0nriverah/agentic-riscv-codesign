"""Fixed syntax router and fitting-only provenance/metric contracts."""
import sys
from pathlib import Path
import numpy as np
import pytest

sys.path.insert(0,str(Path(__file__).parents[1]/'scripts'))
import develop_v6_targeted as study


@pytest.mark.parametrize('operation',['mul','mulh','mulhu','mulhsu'])
def test_gate_finds_nested_all_rv32_products(operation):
    assert study.has_multiply(f'addi({operation}(in0,in1),3)')


def test_gate_handles_dead_products_and_nonmultiply_arithmetic():
    assert study.has_multiply('andi(mul(in0,in1),0)')
    assert not study.has_multiply('slli(add(in0,in1),3)')
    assert not study.has_multiply('addi(in0,123)')


def test_router_preserves_exact_expert_values_and_not_strata_or_targets():
    formulas=['addi(in0,1)','mul(in0,in1)','srai(mulhsu(in1,in0),7)']
    assert study.route_predictions(formulas,[2,3,4],[5,6,7]).tolist()==[2,6,7]
    for base,semantic in [([1],[2,3]),([float('nan')]*3,[1]*3),([-1]*3,[1]*3)]:
        with pytest.raises(ValueError):study.route_predictions(formulas,base,semantic)


def test_oof_rejects_calibration_indices_label_or_identity_changes():
    rows=[{'formula':'addi(in0,1)','lut4_count':3}]
    record={'formula':rows[0]['formula'],'development_index':7,'stratum':'workload','lut4_count':3,'predicted_lut4':2}
    assert study.aligned_oof(rows,[7],[record]).tolist()==[2]
    for field,value in [('development_index',8),('lut4_count',4),('formula','addi(in0,2)'),('stratum','multiplication')]:
        with pytest.raises(ValueError,match='aligned'):study.aligned_oof(rows,[7],[{**record,field:value}])


def test_macro_is_family_balanced_not_row_weighted():
    score=study.metrics(np.zeros(4),np.array([1.,1.,1.,9.]),np.array(['a','a','a','b']))
    assert score['macro_stratum_mae_lut4']==5
    assert score['mae_lut4']==3


def test_output_cannot_modify_frozen_repo_or_overwrite(tmp_path):
    with pytest.raises(ValueError,match='outside repository'):study.run(study.ROOT,study.ROOT,study.ROOT/'generated/forbidden')
    (tmp_path/'evidence').write_text('retained')
    with pytest.raises(ValueError,match='immutable'):study.run(study.ROOT,study.ROOT,tmp_path)


def test_recorded_input_hash_survives_checkout_relocation():
    old='/original/repo/results/2026-10-14-v5/development-data.json'
    new=Path('/relocated/repo/results/2026-10-14-v5/development-data.json')
    assert study.recorded_input_digest({old:'expected'},new)=='expected'
    with pytest.raises(ValueError,match='ambiguous'):
        study.recorded_input_digest({old:'expected',str(new):'other'},new)
    with pytest.raises(ValueError,match='missing'):
        study.recorded_input_digest({'/wrong/development-data.json':'expected'},new)
