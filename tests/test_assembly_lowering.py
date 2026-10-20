from collections import Counter
import copy

import pytest

from isaforge import assembly_lowering as a
from isaforge.workload_experiment import validate_execution


SOURCE = '''\t.text
\t.type kernel, @function
kernel:
\tsrli a0,a0,31
.Lnext:
\tslli a1,a1,1
\tadd a0,a0,a1
\tli a1,0
\tret
\t.size kernel, .-kernel
'''


def fixture():
    marked, sites = a.mark_assembly(SOURCE)
    symbols = '\n'.join(f'{pc:08x} t __isaforge_{kind}_{i}'
                        for i in range(5) for kind, pc in [('begin', i*4), ('end', i*4+4)])
    mapping = a.map_sites(sites, symbols)
    assembly = '\n'.join(f'{pc:x}: {word:08x} instruction' for pc, word in
                         [(0, 0x01f55513), (4, 0x00159593), (8, 0x00b50533),
                          (12, 0x00000593), (16, 0x00008067)])
    program = a.read_program(assembly)
    profile = {'region_counts': {str(i*4): 10 for i in range(5)},
               'total_counts': {str(i*4): 11 for i in range(5)}, 'block_starts': [0],
               'words': [0x49534146, 0, 100, 51, 1]}
    result = a.extract(program, profile, mapping, 6)
    return marked, program, result


def test_markers_preserve_original_statements_and_labels():
    marked, sites = a.mark_assembly(SOURCE)
    assert len(sites) == 5
    assert '\n'.join(line for line in marked.splitlines() if not line.startswith('__isaforge_'))+'\n' == SOURCE
    assert all(site['function'] == 'kernel' for site in sites)


def test_reject_partial_pseudo_instruction_mapping():
    _, sites = a.mark_assembly(SOURCE)
    mapping = a.map_sites(sites, '00000000 t __isaforge_begin_0\n00000008 t __isaforge_end_0')
    assert mapping == {}


def test_discovery_and_lowering_use_actual_register_bindings():
    marked, program, result = fixture()
    row = next(row for row in result['pool'] if row['formula'] == 'add(srli(in0,31),slli(in1,1))')
    assert row['region_custom_instructions'] == 10
    assert row['total_custom_instructions'] == 11
    assert row['expected_instruction_reduction'] == 20
    assert row['occurrences'][0]['inputs'] == [10, 11]
    lowered = a.lower(marked, row)
    assert '.insn r 0x0b, 0, 1, x10, x10, x11' in lowered
    assert 'srli' not in lowered and 'slli' not in lowered
    assert '.Lnext:' in lowered and '\tli a1,0' in lowered
    assert a.verify_lowering(row, program, result['block_starts'])['comparisons'] == 64


def test_overlapping_rewrites_rejected():
    marked, _, result = fixture()
    row = copy.deepcopy(result['pool'][0])
    row['occurrences'] *= 2
    with pytest.raises(ValueError, match='Overlapping'):
        a.lower(marked, row)


@pytest.mark.parametrize('field,value', [('inputs', [11,10]), ('output', 12)])
def test_tampered_register_bindings_rejected(field, value):
    _, program, result = fixture()
    row = copy.deepcopy(result['pool'][0])
    row['occurrences'][0][field] = value
    with pytest.raises(ValueError, match='binding changed'):
        a.verify_lowering(row, program, result['block_starts'])


def test_formula_tampering_rejected():
    _, program, result = fixture()
    row = copy.deepcopy(result['pool'][0]); row['formula'] = 'sub(in0,in1)'
    with pytest.raises(ValueError, match='Formula differs'):
        a.verify_lowering(row, program, result['block_starts'])


def test_missing_statement_rejected():
    marked, _, result = fixture()
    with pytest.raises(ValueError, match='Malformed|Missing'):
        a.lower(marked.replace('__isaforge_begin_0:', 'lost:'), result['pool'][0])


def test_trace_counter_mismatch_rejected():
    with pytest.raises(ValueError, match='Profile/counter'):
        a.extract({}, {'region_counts': {'0': 1}, 'block_starts': [0], 'words': [0,0,0,99]}, {}, 6)


def test_multi_statement_source_rejected():
    with pytest.raises(ValueError, match='Multiple assembly'):
        a.mark_assembly(SOURCE.replace('\tsrli a0,a0,31', '\tadd a0,a0,a1; add a1,a1,a0'))


def test_dynamic_custom_count_and_latency_required():
    raw = {'status': 0x600d600d, 'words': [0x49534146, 0, 100, 50, 1], 'fault': 0,
           'partial_report_bits': 0, 'pcpi_handshakes': 11, 'pcpi_valid_cycles': 22, 'pcpi_wait_cycles': 11}
    candidate = {'total_custom_instructions': 11, 'region_custom_instructions': 10}
    assert validate_execution(raw, candidate)['region_custom_instructions'] == 10
    with pytest.raises(ValueError, match='execution count'):
        validate_execution(raw)
    with pytest.raises(ValueError, match='latency'):
        validate_execution({**raw, 'pcpi_wait_cycles': 0}, candidate)
    with pytest.raises(ValueError, match='self-check'):
        validate_execution({**raw, 'words': [0x49534146,0,100,50,0]}, candidate)
