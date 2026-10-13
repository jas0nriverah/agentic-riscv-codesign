"""RV32 edge cases and actual compiled RTL equivalence when tools are installed."""
import json
import shutil

import pytest

from isaforge.features import IMMEDIATE_OPERATIONS, OPERATIONS
from isaforge.rtl import evaluate_formula, generate_rtl, verify_rtl_batch


@pytest.mark.parametrize('formula,a,b,expected', [
    ('add(in0,in1)', 0xFFFFFFFF, 1, 0),
    ('sub(in0,in1)', 0, 1, 0xFFFFFFFF),
    ('sll(in0,in1)', 1, 32, 1),
    ('sll(in0,in1)', 1, 0xFFFFFFFF, 0x80000000),
    ('sra(in0,in1)', 0x80000000, 31, 0xFFFFFFFF),
    ('srl(in0,in1)', 0x80000000, 31, 1),
    ('slt(in0,in1)', 0xFFFFFFFF, 0, 1),
    ('sltu(in0,in1)', 0xFFFFFFFF, 0, 0),
    ('sltiu(in0,-1)', 0xFFFFFFFE, 0, 1),
    ('mul(in0,in1)', 0x80000000, 2, 0),
    ('mulh(in0,in1)', 0x80000000, 0x80000000, 0x40000000),
    ('mulh(in0,in1)', 0xFFFFFFFF, 0xFFFFFFFF, 0),
    ('mulhsu(in0,in1)', 0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF),
    ('mulhsu(in0,in1)', 0x80000000, 0xFFFFFFFF, 0x80000000),
    ('mulhu(in0,in1)', 0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFE),
    ('lui(-2147483648)', 0, 0, 0x80000000),
    ('srl(add(in0,in1),in1)', 0xFFFFFFFF, 1, 0),
    ('srli(slli(sll(in0,addi(in1,-11)),12),12)', 0x7FFFFFFF, 0, 0),
])
def test_rv32_architectural_edges(formula, a, b, expected):
    assert evaluate_formula(formula, a, b) == expected


def test_generator_rejects_injected_module_identifier():
    with pytest.raises(ValueError, match='module name'):
        generate_rtl('add(in0,in1)', 'foo; endmodule')


def test_rtl_wraps_each_node_and_shares_common_expressions():
    rtl = generate_rtl('add(mul(in0,in1),mul(in0,in1))')
    assert rtl.count('in0 * in1') == 1
    assert 'wire [31:0] n0' in rtl
    assert 'n0 + n0' in rtl


@pytest.mark.skipif(not shutil.which('verilator'), reason='requires actual Verilator installation')
def test_actual_verilator_all_operators_and_compositions(tmp_path):
    formulas = [f'{op}(4096)' if op == 'lui' else f'{op}(in0,-1)'
                if op in IMMEDIATE_OPERATIONS else f'{op}(in0,in1)' for op in OPERATIONS]
    formulas += ['sra(add(in0,in1),in1)', 'mulh(addi(in0,-1),xori(in1,-1))',
                 'mulhsu(mulh(in0,in1),mulhu(in1,in0))',
                 'slt(sub(in0,in1),addi(in1,-1))', 'add(mul(in0,in1),mul(in0,in1))',
                 'srli(slli(sll(in0,addi(in1,-11)),12),12)']
    report = verify_rtl_batch(formulas, tmp_path, random_vectors=256)
    assert report['verified']
    assert report['total_comparisons'] == len(formulas) * 356
    assert (tmp_path / 'verilator-build.log').is_file()
    (tmp_path / 'verification-report.json').write_text(json.dumps(report))
