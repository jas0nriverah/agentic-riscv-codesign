"""Pin completeness and honest interpretation of place-and-route timing."""
import pytest

from isaforge.core_routing import (package_pins, placement_pins, port_signature,
                                  timing_summary, validate_memory_boundary)


def test_chip_database_package_and_dedicated_clock_pins():
    text = '''
.pins other
1 4 5 0
.pins ct256
A1 0 16 1
B2 1 0 0
.gbufpin
0 16 1 0
4 5 0 1
.other
'''
    pins, globals_ = package_pins(text, 'ct256')
    assert pins == {(0, 16, 1): 'A1', (1, 0, 0): 'B2'}
    assert globals_ == {(0, 16, 1)}
    with pytest.raises(ValueError, match='missing'):
        package_pins(text, 'absent')


def placed():
    return {'modules': {'top': {
        'ports': {'clk': {'direction': 'input', 'bits': [1]},
                  'data': {'direction': 'output', 'bits': [2, 3]}},
        'cells': {
            name: {'type': 'SB_IO', 'connections': {'PACKAGE_PIN': [bit]},
                   'attributes': {'NEXTPNR_BEL': f'X{x}/Y0/io0'}}
            for name, bit, x in [('clk', 1, 0), ('data0', 2, 1), ('data1', 3, 2)]}}}}


def test_fixed_mapping_covers_every_port_bit_once():
    data = placed()
    signature = port_signature(data, 'top')
    locations = {(x, 0, 0): f'P{x}' for x in range(3)}
    assert placement_pins(data, locations, signature) == {'clk': 'P0', 'data[0]': 'P1', 'data[1]': 'P2'}
    del data['modules']['top']['cells']['data1']
    with pytest.raises(ValueError, match='cover'):
        placement_pins(data, locations, signature)


def test_duplicate_or_invalid_io_constraints_cannot_be_published():
    data = placed()
    signature = port_signature(data, 'top')
    data['modules']['top']['cells']['data1']['attributes']['NEXTPNR_BEL'] = 'X1/Y0/io0'
    with pytest.raises(ValueError, match='duplicate'):
        placement_pins(data, {(x, 0, 0): f'P{x}' for x in range(3)}, signature)
    data['modules']['top']['cells']['data1']['attributes']['NEXTPNR_BEL'] = 'unplaced'
    with pytest.raises(ValueError, match='placement'):
        placement_pins(data, {(x, 0, 0): f'P{x}' for x in range(3)}, signature)


def report():
    return {'fmax': {'clk': {'achieved': 60., 'constraint': 12.}},
            'utilization': {'ICESTORM_LC': {'used': 1600, 'available': 7680}},
            'critical_paths': [{'from': 'posedge clk', 'to': 'posedge clk',
                                'path': [{'delay': 6.}, {'delay': 10.}]}]}


def test_clock_and_fit_checks_are_distinct_from_external_system_timing():
    summary = timing_summary(report(), 12.)
    assert summary['internal_timing_pass'] and summary['device_fits']
    assert summary['limiting_internal_fmax_mhz'] == 60.
    assert summary['critical_path_summaries'][0]['delay_ns'] == 16.
    data = report()
    data['utilization']['ICESTORM_LC']['used'] = 9000
    assert not timing_summary(data, 12.)['device_fits']
    data = report()
    data['fmax']['clk']['achieved'] = 11.
    assert not timing_summary(data, 12.)['internal_timing_pass']


@pytest.mark.parametrize('bad', [{}, {'fmax': {}},
    {'fmax': {'clk': {'achieved': float('nan'), 'constraint': 12.}}},
    {'fmax': {'clk': {'achieved': 60., 'constraint': 20.}}}])
def test_missing_or_incompatible_timing_reports_fail(bad):
    with pytest.raises(ValueError):
        timing_summary(bad, 12.)


def test_closed_memory_claim_rejects_an_exposed_data_or_memory_input():
    valid = {'clk': 'input', 'resetn': 'input', 'done': 'output', 'passed': 'output'}
    validate_memory_boundary(valid, 'onchip_initialized_memory')
    for invalid in ({**valid, 'mem_rdata[0]': 'input'}, {**valid, 'mem_valid': 'output'},
                    {**valid, 'report_ready': 'input'}):
        with pytest.raises(ValueError, match='closed-memory'):
            validate_memory_boundary(invalid, 'onchip_initialized_memory')
