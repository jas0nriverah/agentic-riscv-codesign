"""Resource metric extraction and actual Yosys/iCE40 synthesis integration."""
import shutil

import pytest

from isaforge.synthesis import netlist_metrics, run_synthesis


def test_depth_counts_connected_cells_not_wire_names():
    netlist = {'modules': {'candidate': {'ports': {
        'in0': {'direction': 'input', 'bits': [1, 2]},
        'result': {'direction': 'output', 'bits': [5, '0']}},
        'cells': {
            'a': {'type': '$_AND_', 'port_directions': {'A': 'input', 'B': 'input', 'Y': 'output'},
                  'connections': {'A': [1], 'B': [2], 'Y': [4]}},
            'b': {'type': '$_NOT_', 'port_directions': {'A': 'input', 'Y': 'output'},
                  'connections': {'A': [4], 'Y': [5]}}}}}}
    assert netlist_metrics(netlist) == {'cell_count': 2, 'logic_depth': 2,
                                      'cell_types': {'$_AND_': 1, '$_NOT_': 1}}


@pytest.mark.skipif(not shutil.which('yosys'), reason='requires actual Yosys installation')
def test_actual_yosys_constant_elimination_and_fpga_mapping(tmp_path):
    constant = run_synthesis('xor(in0,in0)', tmp_path / 'constant')
    assert constant['generic_cell_count'] == constant['generic_logic_depth'] == 0
    assert constant['ice40_lut4_count'] == 0
    add = run_synthesis('add(in0,in1)', tmp_path / 'add')
    assert add['generic_cell_count'] > 0
    assert add['generic_logic_depth'] > 0
    assert add['ice40_lut4_count'] > 0
    assert add['ice40_carry_count'] > 0
    assert add['measurement_source'] == 'rtl_synthesis'
    assert 'candidate_period_ns' not in add
